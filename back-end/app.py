from flask import Flask, request, jsonify
from dotenv import load_dotenv
from flask_cors import CORS
import openai
import os
from datetime import datetime
import json
import logging
import csv
from datetime import datetime



app = Flask(__name__)

# CORS corregido para desarrollo local
CORS(app, 
     origins='*',  # Permite cualquier origen para desarrollo
     methods=['GET', 'POST', 'OPTIONS'],
     allow_headers=['Content-Type', 'Authorization'],
     supports_credentials=False)


# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuración de OpenAI - CORREGIDO
load_dotenv()
openai.api_key = os.getenv('OPENAI_API_KEY')  # Variable de entorno correcta

# Verificar que la API key esté configurada
if not openai.api_key:
    logger.error("OPENAI_API_KEY no está configurada en las variables de entorno")
    logger.info("Crea un archivo .env con: OPENAI_API_KEY=sk-tu-api-key-aqui")

# Prompt del sistema para el tutor de electromagnetismo
SYSTEM_PROMPT = """Eres un profesor de física especializado en Electromagnetismo. Por defecto, proporciona respuestas claras y concisas. Si el usuario solicita una explicación detallada, muestra confusión (por ejemplo, preguntas básicas o errores conceptuales), o pide un desglose paso a paso, adopta un enfoque paciente y pedagógico. Rechaza amablemente los temas que no estén relacionados con Electromagnetismo.

Características de tus respuestas:
- Usa LaTeX para fórmulas matemáticas cuando sea necesario
- Proporciona explicaciones paso a paso para problemas complejos
- Incluye ejemplos prácticos cuando sea útil
- Mantén un tono pedagógico y amigable
- Si la pregunta no es sobre electromagnetismo, redirige amablemente al tema

Temas que puedes cubrir:
- Ley de Coulomb y fuerzas eléctricas
- Campos eléctricos y potencial eléctrico
- Ley de Gauss
- Capacitores y dieléctricos
- Corriente y resistencia
- Campos magnéticos
- Ley de Faraday e inducción electromagnética
- Ley de Ampère
- Ecuaciones de Maxwell
- Ondas electromagnéticas"""

class ElectromagnetismTutor:
    def __init__(self):
        self.conversation_history = []
    
    def get_response(self, user_question):
        """
        Obtiene respuesta del modelo de OpenAI para la pregunta del usuario
        """
        try:
            # Verificar API key
            if not openai.api_key:
                return "Error: API key de OpenAI no configurada. Verifica el archivo .env"
            
            # Agregar el mensaje del usuario al historial
            self.conversation_history.append({
                "role": "user", 
                "content": user_question
            })
            
            # Preparar los mensajes para la API
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            
            # Mantener solo los últimos 10 intercambios para no exceder límites
            recent_history = self.conversation_history[-20:]  # 20 mensajes = ~10 intercambios
            messages.extend(recent_history)
            
            # Llamada a la API de OpenAI usando la nueva sintaxis
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",  # o "gpt-4" si tienes acceso
                messages=messages,
                max_tokens=1500,
                temperature=0.7,
                top_p=0.9,
                frequency_penalty=0.1,
                presence_penalty=0.1
            )
            
            # Extraer la respuesta del asistente
            assistant_response = response.choices[0].message.content
            
            # Agregar la respuesta al historial
            self.conversation_history.append({
                "role": "assistant",
                "content": assistant_response
            })
            
            return assistant_response
            
        except openai.error.AuthenticationError as e:
            logger.error(f"Error de autenticación OpenAI: {str(e)}")
            return "Error de configuración: API key de OpenAI inválida. Verifica tu configuración."
        except openai.error.RateLimitError as e:
            logger.error(f"Rate limit excedido: {str(e)}")
            return "Lo siento, se ha excedido el límite de consultas. Intenta de nuevo en unos minutos."
        except openai.error.APIError as e:
            logger.error(f"Error de API OpenAI: {str(e)}")
            return "Lo siento, hubo un problema con el servicio de IA. Intenta de nuevo."
        except Exception as e:
            logger.error(f"Error inesperado: {str(e)}")
            return "Lo siento, hubo un error procesando tu pregunta. Por favor, intenta de nuevo."

# Instancia global del tutor
tutor = ElectromagnetismTutor()

@app.route('/', methods=['GET'])
def home():
    """Endpoint de salud para verificar que la API está funcionando"""
    return jsonify({
        "message": "Tutor de Electromagnetismo API",
        "status": "active",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "openai_configured": bool(openai.api_key)
    })

@app.route('/api/health', methods=['GET'])
def health_check():
    """Endpoint de verificación de salud"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "electromagnetism-tutor",
        "openai_configured": bool(openai.api_key)
    })

@app.route('/api/chat', methods=['POST', 'OPTIONS'])
def chat():
    """Endpoint principal para el chat con el tutor"""
    # Manejar preflight CORS
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        # Verificar que el contenido sea JSON
        if not request.is_json:
            return jsonify({
                "error": "Content-Type debe ser application/json"
            }), 400
        
        data = request.get_json()
        
        # Validar que la pregunta existe
        if not data or 'question' not in data:
            return jsonify({
                "error": "Se requiere el campo 'question'"
            }), 400
        
        user_question = data['question'].strip()
        
        # Validar que la pregunta no esté vacía
        if not user_question:
            return jsonify({
                "error": "La pregunta no puede estar vacía"
            }), 400
        
        # Validar longitud de la pregunta
        if len(user_question) > 1000:
            return jsonify({
                "error": "La pregunta es demasiado larga (máximo 1000 caracteres)"
            }), 400
        
        logger.info(f"Pregunta recibida: {user_question[:100]}...")
        
        # Obtener respuesta del tutor
        response = tutor.get_response(user_question)
        
        # Respuesta exitosa
        return jsonify({
            "response": response,
            "timestamp": datetime.now().isoformat(),
            "status": "success"
        })
    
    except Exception as e:
        logger.error(f"Error en endpoint /api/chat: {str(e)}")
        return jsonify({
            "error": "Error interno del servidor",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500
    
@app.route('/api/feedback', methods=['POST'])
def handle_feedback():
    """Endpoint para recibir y guardar el feedback del usuario con rating y comentarios."""
    try:
        data = request.get_json()

        # 1. Validar que tenemos los datos necesarios
        # Ahora esperamos 'rating' en lugar de 'feedback'
        if not data or 'question' not in data or 'response' not in data or 'rating' not in data:
            return jsonify({"error": "Faltan datos en la solicitud"}), 400

        question = data.get('question', '').strip()
        response = data.get('response', '').strip()
        rating = int(data.get('rating')) # Convertimos a entero
        comment = data.get('comment', '').strip() # Campo opcional
        topic = data.get('topic', 'desconocido').strip() # Nuevo campo para el tópico
        timestamp = datetime.now().isoformat()

        # 2. Definir el archivo y las cabeceras del CSV
        feedback_file = 'feedback.csv'
        # Añade 'rating', 'comment' y 'topic' a las cabeceras
        headers = ['timestamp', 'rating', 'comment', 'topic', 'question', 'response']

        # 3. Escribir en el archivo CSV
        file_exists = os.path.exists(feedback_file)

        with open(feedback_file, 'a', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)

            if not file_exists:
                writer.writeheader()  # Escribir cabeceras si el archivo es nuevo

            writer.writerow({
                'timestamp': timestamp,
                'rating': rating,
                'comment': comment,
                'topic': topic,
                'question': question,
                'response': response
            })

        logger.info(f"Feedback (rating: {rating}, topic: {topic}) guardado exitosamente.")
        return jsonify({"status": "success", "message": "Feedback recibido"}), 200

    except ValueError:
        return jsonify({"error": "El rating debe ser un número entero"}), 400
    except Exception as e:
        logger.error(f"Error en el endpoint /api/feedback: {str(e)}")
        return jsonify({"error": "Error interno del servidor al guardar el feedback"}), 500
    

@app.route('/api/reset', methods=['POST'])
def reset_conversation():
    """Endpoint para reiniciar la conversación"""
    try:
        global tutor
        tutor.conversation_history = []
        
        return jsonify({
            "message": "Conversación reiniciada exitosamente",
            "timestamp": datetime.now().isoformat()
        })
    
    except Exception as e:
        logger.error(f"Error en reset_conversation: {str(e)}")
        return jsonify({
            "error": "Error al reiniciar la conversación"
        }), 500

@app.errorhandler(404)
def not_found(error):
    """Manejador de errores 404"""
    return jsonify({
        "error": "Endpoint no encontrado",
        "message": "Verifica la URL y el método HTTP"
    }), 404

@app.errorhandler(405)
def method_not_allowed(error):
    """Manejador de errores 405"""
    return jsonify({
        "error": "Método no permitido",
        "message": "Verifica el método HTTP utilizado"
    }), 405

@app.errorhandler(500)
def internal_error(error):
    """Manejador de errores 500"""
    return jsonify({
        "error": "Error interno del servidor",
        "message": "Algo salió mal en el servidor"
    }), 500

if __name__ == '__main__':
    # Verificar configuración antes de iniciar
    print(f"🔧 OpenAI API Key configurada: {'Sí' if openai.api_key else 'NO'}")
    if not openai.api_key:
        print("⚠️  ADVERTENCIA: Crea un archivo .env con tu OPENAI_API_KEY")
    
    print("🚀 Iniciando servidor en http://127.0.0.1:5000")
    print("📖 Endpoints disponibles:")
    print("   GET  / -> Información del servidor")
    print("   GET  /api/health -> Estado del servidor") 
    print("   POST /api/chat -> Chat con el tutor")
    
    # Configuración para desarrollo local
    app.run(debug=True, host='127.0.0.1', port=5000)