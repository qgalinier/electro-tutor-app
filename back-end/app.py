#Importamos todo lo que vamos a necesitar.
#Flask para el servidor, openai para el modelo, gspread para Google Sheets,
#y otras librerías de soporte como os, json, etc.
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
#La API key se lee de las variables de entorno.
openai.api_key = os.getenv('OPENAI_API_KEY')
if not openai.api_key:
    logger.error("No se encontró la OPENAI_API_KEY.")
    logger.info("Si estás en local, asegúrate de tener tu archivo .env")

#Configuramos la API de Google Sheets.
#Estos son los permisos que pedimos a la API de Google.
SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file"
]

#Para manejar las credenciales de forma segura.
google_creds_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
CREDS = None 

if google_creds_json:
    #Si la variable de entorno existe (en Vercel), la usamos.
    creds_dict = json.loads(google_creds_json)
    CREDS = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
else:
    #Si no, buscamos el archivo local (para desarrollo).
    logger.info("Variable GOOGLE_CREDENTIALS_JSON no encontrada. Buscando client_secret.json localmente...")
    try:
        CREDS = ServiceAccountCredentials.from_json_keyfile_name('back-end/client_secret.json', SCOPE)
    except FileNotFoundError:
        logger.error("client_secret.json no encontrado. El feedback a Google Sheets no funcionará.")

#Nos conectamos a la hoja de cálculo.
sheet = None
if CREDS:
    try:
        CLIENT = gspread.authorize(CREDS)
        SPREADSHEET_NAME = "ElectroTutor_Feedback"
        
        #Intentamos abrir el spreadsheet por su nombre.
        spreadsheet = CLIENT.open(SPREADSHEET_NAME)
        sheet = spreadsheet.worksheet("Respuestas")
        logger.info(f"Conectado a la hoja de cálculo: '{SPREADSHEET_NAME}'.")
        
    except gspread.exceptions.SpreadsheetNotFound:
        #Si no existe, la creamos desde cero.
        logger.warning(f"Spreadsheet '{SPREADSHEET_NAME}' no encontrado. Creando uno nuevo...")
        spreadsheet = CLIENT.create(SPREADSHEET_NAME)
        #Le damos permisos a nuestra cuenta de servicio para que pueda escribir.
        spreadsheet.share(CREDS.service_account_email, perm_type='user', role='writer')
        #Opcional: compártela contigo para ver los resultados en tu Drive.
        #spreadsheet.share('tu_correo@gmail.com', perm_type='user', role='writer')
        
        #Preparamos la hoja con sus cabeceras.
        sheet = spreadsheet.worksheet("Sheet1")
        sheet.rename("Respuestas")
        headers = ['timestamp', 'rating', 'comment', 'topic', 'question', 'response']
        sheet.append_row(headers)
        logger.info(f"Spreadsheet '{SPREADSHEET_NAME}' creado y listo.")
        
    except Exception as e:
        #Si algo falla, lo registramos y desactivamos la conexión.
        logger.error(f"Error al conectar con Google Sheets: {e}")
        sheet = None

#Aquí definimos el "cerebro" del tutor.
#Este es el prompt que le dice a la IA cómo debe comportarse.
SYSTEM_PROMPT = """Eres un tutor experto en Electromagnetismo, basado en el libro "Physics for Scientists and Engineers" de Knight. Tu única misión es guiar a los estudiantes usando el método socrático.

**Tu Regla de Oro Absoluta: NUNCA des la respuesta directa a una pregunta conceptual o de resolución de problemas. Tu respuesta SIEMPRE debe ser otra pregunta que guíe al estudiante a pensar.**

**Directrices de Comportamiento:**
1.  **Pregunta, no respondas:** Ante una pregunta del estudiante, formula una contra-pregunta que lo ayude a conectar con conocimientos previos, a descomponer el problema, o a reflexionar sobre un concepto clave.
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
    #Esta clase se encarga de toda la lógica de la conversación.
    def __init__(self):
        #El historial de la conversación para que la IA tenga contexto.
        self.conversation_history = []
        #El cliente para hablar con la API de OpenAI.
        self.openai_client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    def get_response(self, user_question):
        #Recibe la pregunta del usuario y devuelve la respuesta del modelo.
        try:
            #Añadimos la pregunta al historial.
            self.conversation_history.append({"role": "user", "content": user_question})
            
            #Preparamos el paquete de mensajes para la API.
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            #Solo los últimos 20 para no exceder límites de tokens.
            messages.extend(self.conversation_history[-20:])

            #Llamamos a nuestro modelo fine-tuned.
            response = self.openai_client.chat.completions.create(
                model="ft:gpt-4o-2024-08-06:personal:tutor-electro-v1:COp6sgDQ",
                messages=messages,
                max_tokens=1500,
                temperature=0.9
            )

            #Sacamos la respuesta del objeto que nos devuelve la API.
            assistant_response = response.choices[0].message.content
            #La guardamos en el historial para la siguiente pregunta.
            self.conversation_history.append({"role": "assistant", "content": assistant_response})
            
            return assistant_response

        except openai.APIError as e:
            logger.error(f"Error de la API de OpenAI: {e}")
            return "Lo siento, hubo un problema con el servicio de IA. Intenta de nuevo más tarde."
        except Exception as e:
            logger.error(f"Error inesperado al llamar a OpenAI: {str(e)}")
            return "Lo siento, mi cerebro de IA está un poco cansado. ¿Podrías intentar de nuevo?"

#Creamos una sola instancia del tutor que usará toda la aplicación.
tutor = ElectromagnetismTutor()

#Rutas de la API (Endpoints)

@app.route('/', methods=['GET'])
@app.route('/api/health', methods=['GET'])
def health_check():
    #Endpoint de "health check" para saber si el servidor está funcionando.
    #Útil para Vercel y para nosotros al depurar.
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "electromagnetism-tutor",
        "openai_configured": bool(openai.api_key),
        "google_sheets_configured": bool(sheet)
    })

@app.route('/api/chat', methods=['POST', 'OPTIONS'])
def chat():
    #Endpoint principal del chat. Aquí llegan las preguntas del usuario.
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        data = request.get_json()
        user_question = data.get('question', '').strip()

        #Validamos que la pregunta no esté vacía o sea demasiado larga.
        if not user_question:
            return jsonify({"error": "La pregunta no puede estar vacía"}), 400
        if len(user_question) > 1000:
            return jsonify({"error": "La pregunta es demasiado larga"}), 400
        
        logger.info(f"Pregunta recibida: '{user_question[:100]}...'")
        
        #Le pasamos la pregunta al tutor.
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
    #Endpoint para recibir el feedback del usuario y guardarlo en Google Sheets.
    
    #Primero, checamos si la conexión a Sheets está activa. Si no, no hacemos nada.
    if not sheet:
        logger.error("Se intentó guardar feedback, pero la conexión con Google Sheets no está activa.")
        return jsonify({"error": "La conexión con Google Sheets no está configurada en el servidor."}), 503

    try:
        data = request.get_json()

        #Nos aseguramos de que el JSON que llega tiene los campos que esperamos.
        if not all(k in data for k in ['question', 'response', 'rating']):
            return jsonify({"error": "Faltan datos en la solicitud"}), 400

        #Preparamos la fila que vamos a insertar en la hoja.
        row_data = [
            datetime.now().isoformat(),
            int(data['rating']),
            data.get('comment', '').strip(),
            data.get('topic', 'desconocido').strip(),
            data['question'].strip(),
            data['response'].strip()
        ]

        #Añadimos la nueva fila al spreadsheet.
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
    #Endpoint para borrar el historial de la conversación y empezar de cero.
    global tutor
    tutor.conversation_history = []
    logger.info("La conversación ha sido reiniciada.")
    return jsonify({"message": "Conversación reiniciada"})

#Manejadores de errores para que la API devuelva JSON en lugar del HTML feo por defecto.

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint no encontrado"}), 404

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({"error": "Método no permitido para este endpoint"}), 405

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Error interno del servidor"}), 500

#Este bloque solo se ejecuta cuando corremos el script directamente (`python app.py`).
#No se usa en Vercel, pero es indispensable para probar en local.
if __name__ == '__main__':
    print("*" * 50)
    print("🚀 Iniciando servidor del Tutor de Electromagnetismo 🚀")
    print(f"   - Estado de OpenAI: {'CONFIGURADO' if openai.api_key else 'NO CONFIGURADO'}")
    print(f"   - Estado de Google Sheets: {'CONFIGURADO' if sheet else 'NO CONFIGURADO'}")
    print("   - Servidor escuchando en: http://127.0.0.1:5000")
    print("*" * 50)
    
    app.run(debug=True, host='127.0.0.1', port=5000)
