# -*- coding: utf-8 -*-

# Importamos todo lo que vamos a necesitar.
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from flask_cors import CORS
import openai
import os
import logging
from datetime import datetime
from supabase import create_client, Client

# Cargamos las variables de entorno del archivo .env (para desarrollo local).
load_dotenv()

# Inicializamos la app de Flask.
app = Flask(__name__)

# Configuramos CORS para que el frontend pueda hablar con este backend.
CORS(app, origins='*')

# Configuramos el logging para ver qué está pasando en la consola.
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Configuración de APIs Externas ---

# 1. OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')
if not openai.api_key:
    logger.error('No se encontró la OPENAI_API_KEY.')

# 2. Supabase
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')
supabase: Client = None

if supabase_url and supabase_key:
    supabase = create_client(supabase_url, supabase_key)
    logger.info("Cliente de Supabase inicializado correctamente.")
else:
    logger.error('Faltan las variables SUPABASE_URL o SUPABASE_KEY. La conexión con la base de datos no funcionará.')

# --- Lógica del Tutor ---

SYSTEM_PROMPT = """Eres un tutor experto en Electromagnetismo, basado en el libro "Physics for Scientists and Engineers" de Knight. Tu única misión es guiar a los estudiantes usando el método socrático.

**Tu Regla de Oro Absoluta: NUNCA des la respuesta directa a una pregunta conceptual o de resolución de problemas. Tu respuesta SIEMPRE debe ser otra pregunta que guíe al estudiante a pensar.**

**Directrices de Comportamiento:**
1.  **Pregunta, no respondas:** Ante una pregunta del estudiante, formula una contra-pregunta que lo ayude a conectar con conocimientos previos, a descomponer el problema, o a reflexionar sobre algún aspecto clave.
2.  **Mantén un tono de apoyo:** Sé paciente, amable y alentador. Usa frases como "¡Excelente pregunta!", "Vamos a pensarlo juntos...", "Estás muy cerca de la idea...".
3.  **Dominio Estricto:** Rechaza de forma breve y amable cualquier pregunta que no sea de electromagnetismo. Tu conocimiento se limita a este campo.
4.  **Uso de LaTeX:** Incorpora notación matemática en formato LaTeX cuando sea necesario para formular tus preguntas guía.
"""

class ElectromagnetismTutor:
    def __init__(self):
        self.conversation_history = []
        self.openai_client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    def get_response(self, user_question):
        try:
            self.conversation_history.append({'role': 'user', 'content': user_question})
            messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]
            messages.extend(self.conversation_history[-20:])
            
            response = self.openai_client.chat.completions.create(
                model='ft:gpt-4o-2024-08-06:personal:tutor-electro-v1:COp6sgDQ',
                messages=messages,
                max_tokens=1500,
                temperature=0.9
            )
            
            assistant_response = response.choices[0].message.content
            self.conversation_history.append({'role': 'assistant', 'content': assistant_response})
            return assistant_response
        except Exception as e:
            logger.error(f'Error llamando a OpenAI: {str(e)}')
            return 'Hubo un problema con el servicio de IA, intenta de nuevo más tarde.'

tutor = ElectromagnetismTutor()

# --- Rutas de la API (Endpoints) ---

@app.route('/', methods=['GET'])
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'electromagnetism-tutor',
        'openai_configured': bool(openai.api_key),
        'supabase_configured': bool(supabase)
    })

@app.route('/api/chat', methods=['POST', 'OPTIONS'])
def chat():
    if request.method == 'OPTIONS':
        return '', 204
    try:
        data = request.get_json()
        user_question = data.get('question', '').strip()
        if not user_question:
            return jsonify({'error': 'La pregunta no puede estar vacía'}), 400
        if len(user_question) > 1000:
            return jsonify({'error': 'La pregunta es demasiado larga'}), 400
        
        logger.info(f'Pregunta recibida: {user_question[:100]}...')
        response = tutor.get_response(user_question)
        return jsonify({
            'response': response,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f'Error en endpoint /api/chat: {str(e)}')
        return jsonify({'error': 'Error interno del servidor'}), 500

@app.route('/api/feedback', methods=['POST'])
def handle_feedback():
    if not supabase:
        logger.error('Se intentó guardar feedback pero la conexión con Supabase no está activa.')
        return jsonify({'error': 'La conexión con Supabase no está configurada en el servidor.'}), 503
    try:
        data = request.get_json()
        if not all(k in data for k in ['question', 'response', 'rating']):
            return jsonify({'error': 'Faltan datos en la solicitud'}), 400
        
        feedback_data = {
            'rating': int(data['rating']),
            'comment': data.get('comment', '').strip(),
            'topic': data.get('topic', 'desconocido').strip(),
            'question': data['question'].strip(),
            'response': data['response'].strip()
        }
        
        # El campo 'timestamp' se puede generar automáticamente en Supabase
        # si configuras un valor por defecto como now() en la tabla.
        # Si no, puedes añadirlo aquí:
        # feedback_data['timestamp'] = datetime.now().isoformat()

        data, error = supabase.table('feedback').insert(feedback_data).execute()
        
        # La API de Supabase v2 devuelve una tupla (datos, error)
        if error:
            raise Exception(f"Supabase error: {error}")

        logger.info(f'Feedback guardado en Supabase (rating: {feedback_data["rating"]})')
        return jsonify({'status': 'success', 'message': 'Feedback recibido'}), 201
        
    except ValueError:
        return jsonify({'error': 'El rating debe ser un número entero'}), 400
    except Exception as e:
        logger.error(f'Error en el endpoint /api/feedback: {str(e)}')
        return jsonify({'error': 'Error interno al guardar el feedback'}), 500

@app.route('/api/reset', methods=['POST'])
def reset_conversation():
    global tutor
    tutor.conversation_history = []
    logger.info('La conversación ha sido reiniciada.')
    return jsonify({'message': 'Conversación reiniciada'})

# --- Manejadores de Errores ---

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint no encontrado'}), 404

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({'error': 'Método no permitido para este endpoint'}), 405

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Error interno del servidor'}), 500

# --- Ejecución Local ---
if __name__ == '__main__':
    print('*' * 50)
    print('🚀 Iniciando servidor del Tutor de Electromagnetismo 🚀')
    print(f'   - Estado de OpenAI: {"CONFIGURADO" if openai.api_key else "NO CONFIGURADO"}')
    print(f'   - Estado de Supabase: {"CONFIGURADO" if supabase else "NO CONFIGURADO"}')
    print('   - Servidor escuchando en: http://127.0.0.1:5000')
    print('*' * 50)
    app.run(debug=True, host='127.0.0.1', port=5000)

