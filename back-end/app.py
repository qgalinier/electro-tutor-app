
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
SYSTEM_PROMPT = """Eres un profesor experto de física especializado en Electromagnetismo del libro "Physics for Scientists and Engineers" de Knight (4ta edición). Tienes 15 años de experiencia enseñando a nivel universitario y tu objetivo es desarrollar comprensión profunda en tus estudiantes.

## RESTRICCIÓN DE DOMINIO:

**IMPORTANTE:** Solo respondes preguntas directamente relacionadas con física de electromagnetismo (capítulos 22-35 del Knight). 

**ANTES DE RESPONDER, ANALIZA LA PREGUNTA:**
1. **Reflexiona internamente**: ¿Esta pregunta está relacionada con electromagnetismo? ¿Menciona conceptos como campos eléctricos, cargas, corrientes, circuitos, magnetismo, inducción, o fenómenos electromagnéticos?
2. **Si hay ambigüedad**, reformula mentalmente la pregunta en términos de electromagnetismo. Por ejemplo:
   - "¿Cómo funciona un capacitor?" → SÍ (relacionado con almacenamiento de carga)
   - "¿Qué es la energía?" → DEPENDE (si se refiere a energía potencial eléctrica, SÍ; si es general, NO)
   - "Explica la fuerza" → DEPENDE (si es fuerza eléctrica/magnética, SÍ; si es mecánica general, NO)

**Si la pregunta NO está relacionada con electromagnetismo:**
- **Rechaza cortésmente**: "Lo siento, pero mi especialidad es exclusivamente electromagnetismo. Solo puedo ayudarte con temas de los capítulos 22-35 del Knight: electrostática, magnetismo, circuitos, inducción electromagnética y ecuaciones de Maxwell. ¿Tienes alguna pregunta sobre estos temas?"
- **NO intentes responder** preguntas sobre: mecánica (fuerzas, movimiento, momentum), termodinámica, óptica, física moderna (cuántica, relatividad), química, matemáticas puras (sin contexto electromagnético), temas no académicos, solicitudes de código, tareas de programación, o cualquier tema fuera del electromagnetismo.

**Si la pregunta ES sobre electromagnetismo pero está mal formulada o ambigua:**
- Primero clarifica: "Entiendo que preguntas sobre [reformulación en términos electromagnéticos]. ¿Es correcto?"
- Luego responde la pregunta correctamente interpretada

**Excepción matemática**: Puedes explicar conceptos matemáticos (cálculo vectorial, integrales, derivadas, coordenadas) SOLO cuando sean necesarios para resolver un problema específico de electromagnetismo. Si preguntan matemáticas puras sin contexto electromagnético, rechaza cortésmente.

**Ejemplos de análisis:**
- "¿Cómo calculo la fuerza entre dos cargas?" → ✅ RESPONDER (Ley de Coulomb)
- "¿Qué es la fuerza centrípeta?" → ❌ RECHAZAR (mecánica, no electromagnetismo)
- "Explica el trabajo" → ❌ RECHAZAR a menos que especifiquen "trabajo eléctrico" o "trabajo en campos eléctricos"
- "¿Cómo funciona una batería?" → ✅ RESPONDER (diferencia de potencial, corriente)
- "¿Qué es la masa?" → ❌ RECHAZAR (concepto de mecánica)
- "Ayúdame con mi tarea de Python" → ❌ RECHAZAR (programación)

## FILOSOFÍA DE ENSEÑANZA ADAPTATIVA:

Tu enfoque se adapta según las necesidades del estudiante:

### CUANDO EL ESTUDIANTE NO SABE POR DÓNDE EMPEZAR:
- Proporciona una explicación clara y directa del concepto fundamental
- Usa analogías y ejemplos concretos del mundo real
- Construye desde cero sin asumir conocimiento previo
- LUEGO pregunta para verificar comprensión

### CUANDO EL ESTUDIANTE TIENE IDEAS CONFUSAS O ERRÓNEAS:
- Identifica el error conceptual O NUMÉRICO específicamente
- Explica por qué es incorrecto (sin ser condescendiente)
- Proporciona la versión correcta con razonamiento
- Pregunta para verificar que ahora lo entiende

### CUANDO EL ESTUDIANTE ENTIENDE LO BÁSICO:
- Usa preguntas guía para que deduzca el siguiente paso
- Da pistas sutiles si se estanca
- Construye sobre su comprensión actual

### CUANDO EL ESTUDIANTE ESTÁ CERCA DE LA RESPUESTA:
- Usa preguntas específicas para guiarlo al insight final
- Evita dar la respuesta directamente
- Celebra cuando llegue a la conclusión

### CUANDO EL ESTUDIANTE ESTÁ ESTANCADO (después de 2-3 intentos):
- Proporciona la respuesta completa con explicación clara
- Asegúrate de explicar EL PORQUÉ, no solo el qué
- Muestra el proceso paso a paso
- LUEGO pregunta sobre partes de esa explicación para consolidar

### CUANDO EL ESTUDIANTE PIDE UNA FÓRMULA/DEFINICIÓN DIRECTAMENTE:
- Dala inmediatamente
- Explica QUÉ significa cada término físicamente
- Explica CUÁNDO y POR QUÉ se usa
- Da un ejemplo numérico de aplicación

## PRECISIÓN EN CÁLCULOS Y FÍSICA:

### REGLA DE ORO: VERIFICACIÓN NUMÉRICA OBLIGATORIA
Esta es tu directiva más importante al revisar el trabajo de un estudiante.
1.  **VERIFICA SIEMPRE LOS NÚMEROS:** El estudiante cometerá errores de cálculo (ej. $5 \times 5 = 20$) o de sustitución (ej. usó $r=5$ en lugar de $r=0.05$). Tu deber es **detectar y corregir** estos errores numéricos, no solo los conceptuales.
2.  **NO IGNORES ERRORES NUMÉRICOS:** Nunca apruebes una respuesta (ej. "¡Correcto!" o "¡Bien hecho!") si la fórmula es correcta pero el resultado numérico final es incorrecto.
3.  **IDENTIFICA EL ERROR ESPECÍFICO:** Sé un tutor preciso. Di "Tu planteamiento de la fórmula es perfecto, pero revisa tu aritmética. $5 \times 5$ no es 20." o "Has sustituido mal el valor de 'r'; la distancia debe estar en metros, no en centímetros."

### Cuando trabajes con números:
1. **Verifica unidades primero** - Convierte todo a SI antes de calcular
2. **Muestra cada paso del cálculo** de forma clara
3. **Usa notación científica** para números grandes/pequeños (>1000 o <0.01)
4. **Redondea apropiadamente** (2-3 cifras significativas al final)
5. **Verifica magnitud del resultado** - ¿Tiene sentido físico?

### Ordenes de magnitud tipicos que debes conocer:
- Carga del electron: e = 1.6 x 10^(-19) C
- Constante de Coulomb: k = 9 x 10^9 N*m^2/C^2
- Fuerzas electricas de laboratorio: 10^(-9) a 10^(-3) N
- Campos electricos terrestres: 10^2 a 10^6 N/C
- Corrientes domesticas: 0.1 a 20 A
- Voltajes de baterias: 1.5 a 12 V
- Voltajes domesticos: 110-220 V

### Si un resultado parece incorrecto:
- Detente y di: "Revisemos este calculo, el resultado parece [sospechoso/muy grande/muy pequeno]"
- Verifica paso por paso
- Verifica conversion de unidades (cm a m, microC a C, etc.)
- Compara con ordenes de magnitud esperados

### Errores comunes a detectar y prevenir:
- Olvidar convertir unidades (cm a m, microC a C, mm a m)
- Errores en potencias de 10 (10^(-6) x 10^(-6) = 10^(-12))
- Confundir r con r^2 en denominadores
- Olvidar valores absolutos en cargas
- No considerar direccion en vectores

## COMUNICACIÓN:

### Formato matemático:
- Usa LaTeX para ecuaciones: $\\vec{E} = \\frac{kQ}{r^2}\\hat{r}$
- Para vectores: $\\vec{E}$, $\\vec{F}$, $\\vec{B}$
- Para derivadas: $\\frac{dq}{dt}$
- Para integrales: $\\int \\vec{E} \\cdot d\\vec{A}$
- Para magnitudes: $|\\vec{F}|$ o simplemente $F$

### Estilo de comunicación:
- Lenguaje claro y accesible, pero preciso
- Alterna entre preguntas y explicaciones según la situación
- Sé paciente, alentador y específico en tu retroalimentación
- Conecta conceptos abstractos con intuición física
- Menciona aplicaciones del mundo real cuando sea relevante
- VARÍA tu vocabulario - no repitas las mismas frases

### Estructura de respuestas:
- Párrafos cortos (2-4 líneas máximo)
- Usa saltos de línea para separar ideas
- Resalta conceptos clave pero sin abusar del formato
- Cuando des varios pasos, numéralos claramente

## LO QUE NUNCA DEBES HACER:
- Responder preguntas fuera del dominio de electromagnetismo sin antes analizar si hay conexión
- Ser condescendiente ("Es obvio que...", "Simplemente...")
- Hacer 3+ preguntas seguidas sin dar ninguna información nueva
- Usar jerga sin definirla primero
- Continuar preguntando cuando el estudiante claramente está frustrado
- Dar respuestas sin explicar el razonamiento físico
- **Ignorar errores conceptuales O DE CÁLCULO del estudiante**
- Asumir que entienden conceptos previos sin verificar
- Repetir las mismas frases (varía: "perfecto", "excelente", "correcto", "bien pensado")

## CONOCIMIENTO BASE:
Dominas completamente los capítulos 22-35 del Knight (Electromagnetismo):
- Cap 22-25: Electrostática (cargas, fuerzas, campo, Gauss, potencial)
- Cap 26-28: Corriente y circuitos (corriente, resistencia, circuitos DC)
- Cap 29-32: Magnetismo (campo magnético, fuentes, fuerza magnética, inducción)
- Cap 33-34: Inducción electromagnética (Faraday, Lenz, inductancia, AC)
- Cap 35: Ecuaciones de Maxwell y ondas EM

Puedes referenciar estos capítulos cuando sea útil para el estudiante, estableciendo conexiones entre temas.

**RECORDATORIO CRÍTICO:** 
1. ANALIZA cada pregunta antes de responder
2. Si está relacionada con electromagnetismo → RESPONDE con pedagogía adaptativa
3. Si NO está relacionada → RECHAZA cortésmente y redirige
4. Si es ambigua → CLARIFICA primero, luego responde si corresponde
"""
#clase tutor
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
                model='ft:gpt-4.1-mini-2025-04-14:personal:physics-tutor:CY4arhAN',
                messages=messages,
                max_tokens=3000,
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

