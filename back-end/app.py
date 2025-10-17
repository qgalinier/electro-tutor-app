
#imports
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from flask_cors import CORS
import openai
import os
import logging
from datetime import datetime
from supabase import create_client, Client

#carga variables del entorno
load_dotenv()

#flask
app = Flask(__name__)
CORS(app, origins='*')
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

#openai
openai_api_key = os.getenv('OPENAI_API_KEY')
if not openai_api_key:
    logger.error('no se encontró la OPENAI_API_KEY')

#supabase
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')
supabase: Client = None
if supabase_url and supabase_key:
    try:
        supabase = create_client(supabase_url, supabase_key)
        logger.info("Cliente de Supabase inicializado correctamente.")
    except Exception as e:
        logger.error(f'Error al inicializar Supabase: {e}')
else:
    logger.error('Faltan las variables SUPABASE_URL o SUPABASE_KEY.')

#definimos las claves de acceso válidas y a qué grupo pertenecen
VALID_ACCESS_KEYS = {
    "localjuarez": "uacj",
    "utepusers": "utep",
    "general": "public"
}

#diccionario para manejar las conversaciones de cada sesión en memoria
sessions = {}

#prompt del sistema
SYSTEM_PROMPT = """Eres un tutor experto en Electromagnetismo, basado en el libro "Physics for Scientists and Engineers" de Knight. Tu única misión es guiar a los estudiantes usando el método socrático. Tu Regla de Oro Absoluta: NUNCA des la respuesta directa. Tu respuesta SIEMPRE debe ser otra pregunta que guíe al estudiante a pensar."""

#clase del tutor
class ElectromagnetismTutor:
    def __init__(self):
        self.conversation_history = []
        self.openai_client = openai.OpenAI(api_key=openai_api_key) if openai_api_key else None

    def get_response(self, user_question):
        if not self.openai_client:
            return "El servicio de IA no está configurado en el servidor."
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

#endpoints
@app.route('/api/validate_key', methods=['POST'])
def validate_key():
    #este nuevo endpoint solo verifica si la clave enviada es válida
    data = request.get_json()
    key = data.get('access_key')
    if key and key in VALID_ACCESS_KEYS:
        logger.info(f"Clave '{key}' validada exitosamente.")
        return jsonify({'status': 'valid'}), 200
    else:
        logger.warning(f"Intento de acceso con clave inválida: '{key}'")
        return jsonify({'error': 'Clave inválida'}), 401

@app.route('/api/chat', methods=['POST', 'OPTIONS'])
def chat():
    if request.method == 'OPTIONS':
        return '', 204
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        access_key = data.get('access_key')
        user_question = data.get('question', '').strip()

        #validamos que la petición contenga una clave y sesión válidas
        if not session_id or not access_key or access_key not in VALID_ACCESS_KEYS:
            return jsonify({'error': 'Acceso no autorizado o sesión inválida'}), 401
        
        #si es la primera vez que vemos esta sesión, creamos un nuevo tutor para ella
        if session_id not in sessions:
            sessions[session_id] = ElectromagnetismTutor()
            #también registramos esta nueva sesión en nuestra base de datos
            if supabase:
                try:
                    # Usamos el session_id generado por el cliente como 'id'
                    supabase.table('sessions').insert({
                        'id': session_id,
                        'access_key': VALID_ACCESS_KEYS[access_key]
                    }).execute()
                    logger.info(f"Nueva sesión {session_id} (grupo: {VALID_ACCESS_KEYS[access_key]}) registrada en DB.")
                except Exception as e:
                    logger.error(f"No se pudo registrar la nueva sesión en Supabase: {e}")
            logger.info(f"Nueva conversación iniciada para sesión: {session_id}")
        
        #usamos el tutor que corresponde a esta sesión
        current_tutor = sessions[session_id]
        response = current_tutor.get_response(user_question)
        
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
        return jsonify({'error': 'La conexión con la base de datos no está configurada.'}), 503
    try:
        data = request.get_json()
        
        #aquí podrías añadir la lógica para clasificar el tópico con el LLM
        topic = 'desconocido' 

        feedback_data = {
            'rating': int(data['rating']),
            'comment': data.get('comment', ''),
            'topic': topic,
            'question': data['question'],
            'response': data['response'],
            'session_id': data.get('session_id'), #guardamos el id de sesión
            'access_key': VALID_ACCESS_KEYS.get(data.get('access_key')) #guardamos el grupo (uacj, utep, etc)
        }
        
        response_obj, count = supabase.table('feedback').insert(feedback_data).execute()
        
        #manejamos la respuesta de la librería para v2
        if count is None and isinstance(response_obj, list) and len(response_obj) > 0:
             pass # Inserción exitosa en v2
        elif isinstance(count, dict) and 'error' in count:
             raise Exception(f"Supabase error: {count['error']}")


        logger.info(f'Feedback guardado en Supabase para sesión {data.get("session_id")}')
        return jsonify({'status': 'success', 'message': 'Feedback recibido'}), 201
    except Exception as e:
        logger.error(f'Error en el endpoint /api/feedback: {str(e)}')
        return jsonify({'error': 'Error interno al guardar el feedback'}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'openai_configured': bool(openai_api_key),
        'supabase_configured': bool(supabase)
    })

@app.route('/api/reset', methods=['POST'])
def reset_conversation():
    data = request.get_json()
    session_id = data.get('session_id')
    if session_id and session_id in sessions:
        del sessions[session_id]
        logger.info(f'Sesión {session_id} ha sido reiniciada.')
        return jsonify({'message': f'Sesión {session_id} reiniciada.'})
    return jsonify({'error': 'Sesión no encontrada o no proporcionada.'}), 404


@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint no encontrado'}), 404

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({'error': 'Método no permitido para este endpoint'}), 405

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Error interno del servidor'}), 500

if __name__ == '__main__':
    print('*' * 50)
    print('Iniciando servidor del Tutor de Electromagnetismo')
    print(f'   Estado de OpenAI: {"CONFIGURADO" if openai_api_key else "NO CONFIGURADO"}')
    print(f'   Estado de Supabase: {"CONFIGURADO" if supabase else "NO CONFIGURADO"}')
    print('   Servidor escuchando en: http://127.0.0.1:5000')
    print('*' * 50)
    app.run(debug=True, host='127.0.0.1', port=5000)

