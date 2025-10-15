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
openai.api_key = os.getenv('OPENAI_API_KEY')
if not openai.api_key:
    logger.error('no se encontró la OPENAI_API_KEY')

#supabase
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
else:
    logger.error('faltan las variables SUPABASE_URL o SUPABASE_KEY')

#prompt del sistema
SYSTEM_PROMPT = """Eres un tutor experto en Electromagnetismo, basado en el libro "Physics for Scientists and Engineers" de Knight. Tu única misión es guiar a los estudiantes usando el método socrático.

Tu Regla de Oro Absoluta: NUNCA des la respuesta directa a una pregunta conceptual o de resolución de problemas. Tu respuesta SIEMPRE debe ser otra pregunta que guíe al estudiante a pensar.

Directrices de Comportamiento:
1.  Pregunta, no respondas: Ante una pregunta del estudiante, formula una contra-pregunta que lo ayude a conectar con conocimientos previos, a descomponer el problema, o a reflexionar sobre algún aspecto clave.
2.  Mantén un tono de apoyo: Sé paciente, amable y alentador. Usa frases como "¡Excelente pregunta!", "Vamos a pensarlo juntos...", "Estás muy cerca de la idea...".
3.  Dominio Estricto: Rechaza de forma breve y amable cualquier pregunta que no sea de electromagnetismo. Tu conocimiento se limita a este campo.
4.  Uso de LaTeX: Incorpora notación matemática en formato LaTeX cuando sea necesario para formular tus preguntas guía.

Ejemplo de tu comportamiento:
- NO DEBES HACER ESTO:
  - Usuario: "¿Qué es la Ley de Gauss?"
  - Tú: "La Ley de Gauss dice que el flujo eléctrico a través de una superficie cerrada es proporcional a la carga encerrada."

- SÍ DEBES HACER ESTO:
  - Usuario: "¿Qué es la Ley de Gauss?"
  - Tú: "¡Una ley fundamental! Antes de escribir la ecuación, ¿podrías explicar con tus propias palabras qué es lo que relaciona la Ley de Gauss? ¿Qué dos cantidades físicas conecta?"
"""

#clase del tutor
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
            logger.error(f'error llamando a openai: {str(e)}')
            return 'hubo un problema con el servicio de IA, intenta de nuevo más tarde'

tutor = ElectromagnetismTutor()

#endpoints
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
            return jsonify({'error': 'la pregunta no puede estar vacía'}), 400
        if len(user_question) > 1000:
            return jsonify({'error': 'la pregunta es demasiado larga'}), 400
        logger.info(f'pregunta recibida: {user_question[:100]}...')
        response = tutor.get_response(user_question)
        return jsonify({
            'response': response,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f'error en endpoint /api/chat: {str(e)}')
        return jsonify({'error': 'error interno del servidor'}), 500

@app.route('/api/feedback', methods=['POST'])
def handle_feedback():
    if not supabase:
        logger.error('se intentó guardar feedback pero la conexión con supabase no está activa')
        return jsonify({'error': 'la conexión con supabase no está configurada en el servidor'}), 503
    try:
        data = request.get_json()
        if not all(k in data for k in ['question', 'response', 'rating']):
            return jsonify({'error': 'faltan datos en la solicitud'}), 400
        feedback_data = {
            'timestamp': datetime.now().isoformat(),
            'rating': int(data['rating']),
            'comment': data.get('comment', '').strip(),
            'topic': data.get('topic', 'desconocido').strip(),
            'question': data['question'].strip(),
            'response': data['response'].strip()
        }
        res = supabase.table('feedback').insert(feedback_data).execute()
        if res.status_code == 201:
            logger.info(f'feedback guardado en supabase (rating: {data["rating"]})')
            return jsonify({'status': 'success', 'message': 'feedback recibido'}), 200
        else:
            logger.error(f'error al guardar feedback en supabase: {res}')
            return jsonify({'error': 'error al guardar el feedback'}), 500
    except ValueError:
        return jsonify({'error': 'el rating debe ser un número entero'}), 400
    except Exception as e:
        logger.error(f'error en el endpoint /api/feedback: {str(e)}')
        return jsonify({'error': 'error interno al guardar el feedback'}), 500

@app.route('/api/reset', methods=['POST'])
def reset_conversation():
    global tutor
    tutor.conversation_history = []
    logger.info('la conversación ha sido reiniciada')
    return jsonify({'message': 'conversación reiniciada'})

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'endpoint no encontrado'}), 404

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({'error': 'método no permitido para este endpoint'}), 405

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'error interno del servidor'}), 500

if __name__ == '__main__':
    print('*' * 50)
    print('iniciando servidor del tutor de electromagnetismo')
    print(f'   estado de openai: {"configurado" if openai.api_key else "no configurado"}')
    print(f'   estado de supabase: {"configurado" if supabase else "no configurado"}')
    print('   servidor escuchando en: http://127.0.0.1:5000')
    print('*' * 50)
    app.run(debug=True, host='127.0.0.1', port=5000)
