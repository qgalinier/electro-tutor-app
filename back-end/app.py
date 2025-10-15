#Importamos todo lo que vamos a necesitar.
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from flask_cors import CORS
import openai
import os
import json
import logging
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

#Cargamos las variables de entorno del archivo .env (para desarrollo local).
load_dotenv()

#Inicializamos la app de Flask.
app = Flask(__name__)

#Configuramos CORS para que el frontend pueda hablar con este backend sin problemas.
CORS(app, origins='*')

#Configuramos el logging para ver qué está pasando en la consola.
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

#Configuración de las APIs externas

#Configuramos la API de OpenAI.
openai.api_key = os.getenv('OPENAI_API_KEY')
if not openai.api_key:
    logger.error("No se encontró la OPENAI_API_KEY.")
    logger.info("Si estás en local, asegúrate de tener tu archivo .env")

#Configuramos la API de Google Sheets.
SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file"
]

google_creds_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
CREDS = None 

if google_creds_json:
    creds_dict = json.loads(google_creds_json)
    CREDS = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
else:
    logger.info("Variable GOOGLE_CREDENTIALS_JSON no encontrada. Buscando client_secret.json localmente...")
    try:
        CREDS = ServiceAccountCredentials.from_json_keyfile_name('back-end/client_secret.json', SCOPE)
    except FileNotFoundError:
        logger.error("client_secret.json no encontrado. El feedback a Google Sheets no funcionará.")

sheet = None
if CREDS:
    try:
        CLIENT = gspread.authorize(CREDS)
        SPREADSHEET_NAME = "ElectroTutor_Feedback"
        
        # Intentamos abrir el spreadsheet por su nombre. No lo creamos nunca.
        try:
            spreadsheet = CLIENT.open(SPREADSHEET_NAME)
            sheet = spreadsheet.worksheet("Respuestas")
            logger.info(f"Conectado a la hoja de cálculo: '{SPREADSHEET_NAME}'.")
        except gspread.exceptions.SpreadsheetNotFound:
            logger.error(
                f"Spreadsheet '{SPREADSHEET_NAME}' no encontrado. "
                "Debes crearlo manualmente en tu Google Drive y compartirlo como editor con la cuenta de servicio."
            )
            sheet = None
        except gspread.exceptions.WorksheetNotFound:
            logger.error(
                "La pestaña 'Respuestas' no existe en el Spreadsheet. Debes crearla manualmente en Google Sheets."
            )
            sheet = None

    except Exception as e:
        logger.error(f"Error al conectar con Google Sheets: {e}")
        sheet = None

SYSTEM_PROMPT = """Eres un tutor experto en Electromagnetismo, basado en el libro "Physics for Scientists and Engineers" de Knight. Tu única misión es guiar a los estudiantes usando el método socrático.

**Tu Regla de Oro Absoluta: NUNCA des la respuesta directa a una pregunta conceptual o de resolución de problemas. Tu respuesta SIEMPRE debe ser otra pregunta que guíe al estudiante a pensar.**

**Directrices de Comportamiento:**
1.  **Pregunta, no respondas:** Ante una pregunta del estudiante, formula una contra-pregunta que lo ayude a conectar con conocimientos previos, a descomponer el problema, o a reflexionar sobre algún aspecto clave.
2.  **Mantén un tono de apoyo:** Sé paciente, amable y alentador. Usa frases como "¡Excelente pregunta!", "Vamos a pensarlo juntos...", "Estás muy cerca de la idea...".
3.  **Dominio Estricto:** Rechaza de forma breve y amable cualquier pregunta que no sea de electromagnetismo. Tu conocimiento se limita a este campo.
4.  **Uso de LaTeX:** Incorpora notación matemática en formato LaTeX cuando sea necesario para formular tus preguntas guía.

**Ejemplo de tu comportamiento:**
- **NO DEBES HACER ESTO:**
  - *Usuario:* "¿Qué es la Ley de Gauss?"
  - *Tú:* "La Ley de Gauss dice que el flujo eléctrico a través de una superficie cerrada es proporcional a la carga encerrada."

- **SÍ DEBES HACER ESTO:**
  - *Usuario:* "¿Qué es la Ley de Gauss?"
  - *Tú:* "¡Una ley fundamental! Antes de escribir la ecuación, ¿podrías explicar con tus propias palabras qué es lo que relaciona la Ley de Gauss? ¿Qué dos cantidades físicas conecta?"
"""

class ElectromagnetismTutor:
    def __init__(self):
        self.conversation_history = []
        self.openai_client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    def get_response(self, user_question):
        try:
            self.conversation_history.append({"role": "user", "content": user_question})
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            messages.extend(self.conversation_history[-20:])

            response = self.openai_client.chat.completions.create(
                model="ft:gpt-4o-2024-08-06:personal:tutor-electro-v1:COp6sgDQ",
                messages=messages,
                max_tokens=1500,
                temperature=0.9
            )

            assistant_response = response.choices[0].message.content
            self.conversation_history.append({"role": "assistant", "content": assistant_response})
            return assistant_response

        except openai.APIError as e:
            logger.error(f"Error de la API de OpenAI: {e}")
            return "Lo siento, hubo un problema con el servicio de IA. Intenta de nuevo más tarde."
        except Exception as e:
            logger.error(f"Error inesperado al llamar a OpenAI: {str(e)}")
            return "Lo siento, mi cerebro de IA está un poco cansado. ¿Podrías intentar de nuevo?"

tutor = ElectromagnetismTutor()

@app.route('/', methods=['GET'])
@app.route('/api/health', methods=['GET'])
def health_check():
    try:
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "service": "electromagnetism-tutor",
            "openai_configured": bool(openai.api_key),
            "google_sheets_configured": bool(sheet)
        })
    except Exception as e:
        logger.error(f"Error en health_check: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/chat', methods=['POST', 'OPTIONS'])
def chat():
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        data = request.get_json()
        user_question = data.get('question', '').strip()
        if not user_question:
            return jsonify({"error": "La pregunta no puede estar vacía"}), 400
        if len(user_question) > 1000:
            return jsonify({"error": "La pregunta es demasiado larga"}), 400
        
        logger.info(f"Pregunta recibida: '{user_question[:100]}...'")
        response = tutor.get_response(user_question)
        return jsonify({
            "response": response,
            "timestamp": datetime.now().isoformat()
        })
    
    except Exception as e:
        logger.error(f"Error en endpoint /api/chat: {str(e)}")
        return jsonify({"error": "Error interno del servidor"}), 500
    
@app.route('/api/feedback', methods=['POST'])
def handle_feedback():
    if not sheet:
        logger.error("Se intentó guardar feedback, pero la conexión con Google Sheets no está activa.")
        return jsonify({"error": "La conexión con Google Sheets no está configurada en el servidor."}), 503

    try:
        data = request.get_json()
        if not all(k in data for k in ['question', 'response', 'rating']):
            return jsonify({"error": "Faltan datos en la solicitud"}), 400

        row_data = [
            datetime.now().isoformat(),
            int(data['rating']),
            data.get('comment', '').strip(),
            data.get('topic', 'desconocido').strip(),
            data['question'].strip(),
            data['response'].strip()
        ]

        sheet.append_row(row_data)

        logger.info(f"Feedback (rating: {data['rating']}) guardado en Google Sheets.")
        return jsonify({"status": "success", "message": "Feedback recibido"}), 200

    except ValueError:
        return jsonify({"error": "El rating debe ser un número entero"}), 400
    except Exception as e:
        logger.error(f"Error en el endpoint /api/feedback: {str(e)}")
        return jsonify({"error": "Error interno al guardar el feedback"}), 500

@app.route('/api/reset', methods=['POST'])
def reset_conversation():
    global tutor
    tutor.conversation_history = []
    logger.info("La conversación ha sido reiniciada.")
    return jsonify({"message": "Conversación reiniciada"})

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint no encontrado"}), 404

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({"error": "Método no permitido para este endpoint"}), 405

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Error interno del servidor"}), 500

if __name__ == '__main__':
    print("*" * 50)
    print("🚀 Iniciando servidor del Tutor de Electromagnetismo 🚀")
    print(f"   - Estado de OpenAI: {'CONFIGURADO' if openai.api_key else 'NO CONFIGURADO'}")
    print(f"   - Estado de Google Sheets: {'CONFIGURADO' if sheet else 'NO CONFIGURADO'}")
    print("   - Servidor escuchando en: http://127.0.0.1:5000")
    print("*" * 50)
    app.run(debug=True, host='127.0.0.1', port=5000)
