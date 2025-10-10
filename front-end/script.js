// declaramos variables para el desarrollo local, en este caso 2 endpoints, api y health 
const CONFIG = {
    API_ENDPOINT: 'http://127.0.0.1:5000/api/chat',
    HEALTH_ENDPOINT: 'http://127.0.0.1:5000/api/health',
    // nuevo endpoint para checar si funciona el metodo de evaluacion de respuesta
    FEEDBACK_ENDPOINT: 'http://127.0.0.1:5000/api/feedback', 
    // definimos un maximo de reintentos y un delay entre cada uno
    MAX_RETRIES: 3,
    RETRY_DELAY: 1000
};

//esta es la clase principal que maneja la logica del chat, definimos el metodo constructor y los elementos del DOM
// cada uno de los elementos del DOM son referenciados por su ID
// tambien definimos variables de estado como isLoading y retryCount
// finalmente llamamos al metodo init para inicializar la aplicacion
class TutorChat {
    constructor() {
        this.elements = {
            chatContainer: document.getElementById('chatContainer'),
            questionInput: document.getElementById('questionInput'),
            sendButton: document.getElementById('sendButton'),
            buttonText: document.getElementById('buttonText'),
            buttonLoader: document.getElementById('buttonLoader'),
            suggestions: document.getElementById('suggestions'),
            status: document.getElementById('status'),
            statusText: document.querySelector('.status-text'),
            statusIndicator: document.querySelector('.status-indicator'),
            errorModal: document.getElementById('errorModal'),
            errorMessage: document.getElementById('errorMessage'),
            closeModal: document.getElementById('closeModal')
        };
        
        this.isLoading = false;
        this.retryCount = 0;
        
        this.init();
    }
    // aqui se inicializan los eventos y se configura el auto resize del input ademas de checar la conexion con el backend
    init() {
        this.setupEventListeners();
        this.setupAutoResize();
        this.checkBackendConnection();
    }
    
    setupEventListeners() {
        // los event listeners manejan los eventos de la interfaz de usuario
        this.elements.sendButton.addEventListener('click', () => this.sendMessage());
        
        // podemos tambien configurar un event listener para saber si se presiona enter para enviar el mensaje
        this.elements.questionInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        
        // aqui configuramos los eventos para ver si el usuario da clic en alguna sugerencia predefinida por nosotros
        // estas sugerencias estan definidas en el HTML y se mantienen por lo general estaticas
        this.elements.suggestions.addEventListener('click', (e) => {
            if (e.target.classList.contains('suggestion-chip')) {
                const question = e.target.getAttribute('data-question');
                this.elements.questionInput.value = question;
                this.sendMessage();
            }
        });
        
        // aqui manejamos los eventos del modal de error que es
        // una ventana emergente que muestra mensajes de error en caso de que algo salga mal
        // el modal se puede cerrar dando clic en la "X" o presionando la tecla Escape
        this.elements.closeModal.addEventListener('click', () => this.hideErrorModal());
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') this.hideErrorModal();
        });

        // ==========================================================
        //         MANEJO DE EVENTOS DEL SISTEMA DE FEEDBACK (ESTRELLAS Y COMENTARIOS)
        // ==========================================================
        
        // Evento para HOVER (pasar el ratón por encima de las estrellas)
        this.elements.chatContainer.addEventListener('mouseover', (e) => {
            if (e.target.classList.contains('star')) {
                const ratingContainer = e.target.closest('.star-rating');
                if (!ratingContainer) return;

                const hoverRating = parseInt(e.target.dataset.rating);
                
                ratingContainer.querySelectorAll('.star').forEach(s => {
                    // Pinta de amarillo si su rating es <= al rating sobre el que se hace hover
                    if (parseInt(s.dataset.rating) <= hoverRating) {
                        s.style.color = '#f7d10c'; // Color de hover
                    } else {
                        s.style.color = '#ccc'; // Color de vacío
                    }
                });
            }
        });

        // Evento para MOUSEOUT (cuando el ratón sale de las estrellas)
        this.elements.chatContainer.addEventListener('mouseout', (e) => {
            // Solo reaccionar si el mouse sale de una estrella o del contenedor de estrellas
            // Evitar que se active si el mouse sale del contenedor de chat a un área que no es estrella
            if (e.target.classList.contains('star') || e.target.classList.contains('star-rating')) {
                const ratingContainer = e.target.closest('.star-rating');
                if (!ratingContainer) return; // Salir si no encontramos el contenedor

                // Obtener el rating ya clickeado, si existe. Si no, es 0 (ninguna seleccionada)
                const selectedRating = parseInt(ratingContainer.dataset.selectedRating || '0'); 

                ratingContainer.querySelectorAll('.star').forEach(s => {
                    // Restaurar al estado seleccionado o al estado vacío
                    if (parseInt(s.dataset.rating) <= selectedRating) {
                        s.style.color = '#f7d10c'; // Color seleccionado
                    } else {
                        s.style.color = '#ccc'; // Color vacío
                    }
                });
            }
        });

        // Evento para CLICK en las estrellas
        this.elements.chatContainer.addEventListener('click', async (e) => {
            const target = e.target;

            if (target.classList.contains('star')) {
                const ratingContainer = target.closest('.star-rating');
                if (!ratingContainer) return;

                const clickedRating = parseInt(target.dataset.rating); // El rating clickeado (ej. 3)
                
                // Actualizar el dataset para que mouseout sepa qué estrellas deben quedarse amarillas
                ratingContainer.dataset.selectedRating = clickedRating;

                ratingContainer.querySelectorAll('.star').forEach(s => {
                    s.classList.remove('selected'); // Primero limpiar la clase 'selected' de todas
                    // Luego añadir la clase 'selected' a las correctas y asegurar el color
                    if (parseInt(s.dataset.rating) <= clickedRating) { 
                        s.classList.add('selected');
                        s.style.color = '#f7d10c'; // Asegurar el color inmediatamente
                    } else {
                        s.style.color = '#ccc'; // Asegurar que las no seleccionadas se vean vacías
                    }
                });

                const controls = target.closest('.feedback-controls');
                const commentSection = controls.querySelector('.comment-section');
                const feedbackPrompt = controls.querySelector('.feedback-prompt');

                if (feedbackPrompt) feedbackPrompt.style.display = 'none';
                
                if (clickedRating < 4) { // si el rating es menor a 4 mostramos el textarea para comentarios
                    commentSection.classList.remove('hidden');
                    commentSection.querySelector('.feedback-comment-textarea').focus();
                } else { //sino el feedback es positivo y enviamos directamente el feedback
                    commentSection.classList.add('hidden');
                    await this.sendFeedback(ratingContainer);
                }
            }

            // Manejar el evento de enviar el comentario adicional
            if (target.classList.contains('send-comment-btn')) {
                const ratingContainer = target.closest('.feedback-controls').querySelector('.star-rating');
                await this.sendFeedback(ratingContainer);
            }
        });

        // ==========================================================
        //         FIN MANEJO DE EVENTOS DEL SISTEMA DE FEEDBACK
        // ==========================================================

        //el focus en el input de pregunta al iniciar la aplicacion significa que el cursor estara listo para escribir
        // esto mejora la experiencia del usuario al no tener que dar clic manualmente en el input
        this.elements.questionInput.focus();
    }
    
    // el autoresize ajusta automaticamente la altura del textarea segun el contenido
    //de esta manera el usuario puede ver todo lo que escribe sin necesidad de barras de desplazamiento
    setupAutoResize() {
        this.elements.questionInput.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 120) + 'px';
        });
    }
    
    async checkBackendConnection() {
        // aqui verificamos la conexion con el backend, en caso de que falle
        // intentamos reconectar un numero definido de veces con un delay entre cada intento
        // si no se logra conectar mostramos un mensaje de error en la interfaz
        try {
            const response = await fetch(CONFIG.HEALTH_ENDPOINT);
            if (response.ok) this.updateStatus('success', 'Listo para ayudarte');
            else throw new Error(`HTTP ${response.status}`);
        } catch (error) {
            this.updateStatus('error', 'Error de conexión');
            console.error('Error al conectar con backend:', error);
        }
    }
    
    updateStatus(type, message) {
        //  aqui actualizamos el estado de la conexion en la interfaz
        // el estado puede ser 'success' o 'error' y se refleja en el color y texto del indicador
        this.elements.status.className = `status ${type}`;
        this.elements.statusText.textContent = message;
    }
    
    async sendMessage() {
        // aqui manejamos el envio del mensaje del usuario al backend
        // primero validamos que el input no este vacio y que no haya una solicitud en curso
        // luego agregamos el mensaje del usuario al chat y limpiamos el input
        // despues llamamos al backend y esperamos la respuesta
        // finalmente agregamos la respuesta del bot al chat y manejamos cualquier error que ocurra
        // tambien nos aseguramos de que el input este enfocado al final del proceso para mejorar la experiencia del usuario
        // y deshabilitamos el boton de enviar mientras esperamos la respuesta para evitar multiples solicitudes
        const question = this.elements.questionInput.value.trim();
        if (!question || this.isLoading) return;
        if (this.elements.suggestions.style.display !== 'none') {
            this.elements.suggestions.style.display = 'none';
        }
        this.addMessage(question, 'user');
        this.elements.questionInput.value = '';
        this.elements.questionInput.style.height = 'auto';
        this.setLoading(true);
        try {
            const response = await this.callBackend(question);
            this.addMessage(response, 'bot');
        } catch (error) {
            console.error('Error al enviar mensaje:', error);
            this.handleError(error, question);
        } finally {
            this.setLoading(false);
            this.elements.questionInput.focus();
        }
    }
    
    async callBackend(question) {
        // aqui hacemos la llamada al backend usando fetch
        // enviamos la pregunta en el cuerpo de la solicitud como JSON
        // si la respuesta no es exitosa lanzamos un error
        // si todo va bien regresamos la respuesta del bot
        //
        const response = await fetch(CONFIG.API_ENDPOINT, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question })
        });
        if (!response.ok) throw new Error('API Error');
        const data = await response.json();
        return data.response;
    }
    
    handleError(error, originalQuestion) {
        // en esta funcion manejamos los errores que ocurren al enviar el mensaje
        // si el error es de tipo 'API Error' intentamos reconectar un numero definido de veces
        // con un delay entre cada intento
        this.updateStatus('error', 'Error de conexión');
        this.showErrorModal('No se pudo conectar con el tutor. Verifica tu conexión y que el backend esté ejecutándose.');
        this.addMessage('Lo siento, no pude procesar tu pregunta en este momento. Intenta de nuevo.', 'bot', true);
    }
    // aqui agregamos un mensaje al chat, ya sea del usuario o del bot
    // si el mensaje es del bot, tambien agregamos los controles de feedback
    // usamos escapeHtml para evitar inyecciones de codigo y formatBotMessage para dar formato al texto
    // finalmente desplazamos el chat hacia abajo para mostrar el nuevo mensaje

    addMessage(text, sender, isError = false) {
        const messageId = `msg-${Date.now()}`;
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}-message`;
        messageDiv.id = messageId;

        if (sender === 'user') {
            messageDiv.innerHTML = `
                <div class="user-avatar">Tú</div>
                <div class="message-bubble">${this.escapeHtml(text)}</div>
            `;
        } else {
            const avatar = isError ? '⚠️' : '🤖';
            messageDiv.innerHTML = `
                <div class="bot-avatar">${avatar}</div>
                <div class="message-content-wrapper">
                    <div class="message-bubble">${this.formatBotMessage(text)}</div>
                    <div class="feedback-controls">
                        <span class="feedback-prompt">¿Qué te pareció la respuesta?</span>
                        <div class="star-rating">
                            <span class="star" data-rating="1">★</span>
                            <span class="star" data-rating="2">★</span>
                            <span class="star" data-rating="3">★</span>
                            <span class="star" data-rating="4">★</span>
                            <span class="star" data-rating="5">★</span>
                        </div>
                        <div class="comment-section hidden">
                            <textarea class="feedback-comment-textarea" placeholder="¿Hay algo que podamos mejorar? (Opcional)"></textarea>
                            <button class="send-comment-btn">Enviar Feedback</button>
                        </div>
                    </div>
                </div>
            `;
        }
        //aqui agregamos el mensaje al contenedor del chat
        // y si es del bot, inicializamos MathJax para renderizar cualquier formula matematica

        this.elements.chatContainer.appendChild(messageDiv);
        if (sender === 'bot' && typeof MathJax !== "undefined") {
            MathJax.typesetPromise([`#${messageId}`]).catch((err) => console.log(err.message));
        }
        this.scrollToBottom();
    }
    
    formatBotMessage(text) {
        // aqui
        // damos formato al mensaje del bot para soportar negritas, italicas, codigo y saltos de linea
        // usamos expresiones regulares para buscar patrones en el texto y reemplazarlos con etiquetas HTML
        // tambien usamos escapeHtml para evitar inyecciones de codigo
        // finalmente regresamos el texto formateado    
        let formattedText = this.escapeHtml(text)
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code>$1</code>')
            .replace(/\n/g, '<br>');
        return formattedText;
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    //metodo para enviar el feedback al backend 
    // este metodo obtiene la calificacion seleccionada y el comentario adicional
    // deshabilita la UI y muestra un mensaje de carga
    // luego busca el mensaje del bot y la pregunta del usuario relacionada
    // finalmente envia toda la informacion al backend y maneja la respuesta o cualquier error
    // tambien actualiza la UI para mostrar mensajes de exito o error
    // ademas, si la calificacion es menor a 4, muestra un textarea para comentarios adicionales
    // si la calificacion es 4 o 5, envia el feedback directamente sin pedir comentarios adicionales

async sendFeedback(ratingContainer) {
    const selectedRating = parseInt(ratingContainer.dataset.selectedRating);
    const controls = ratingContainer.closest('.feedback-controls');
    const commentSection = controls.querySelector('.comment-section');
    const comment = commentSection.querySelector('.feedback-comment-textarea').value.trim();

    controls.innerHTML = '<span style="color: #10b981;">¡Enviando feedback...!</span>'; // mensaje temporal

    try {
        // busca el mensaje del bot a partir de 'controls' (que es el contenedor del feedback)
        // y luego subir al ancestro .bot-message
        // esto asegura que obtenemos el mensaje correcto incluso si hay múltiples mensajes en el chat
        //
        const botMessageDiv = controls.closest('.message.bot-message');
        if (!botMessageDiv) {
            throw new Error("No se encontró el contenedor del mensaje del bot para el feedback.");
        }

        const botResponseElement = botMessageDiv.querySelector('.message-bubble');
        
        // encontrar la pregunta del usuario correspondiente buscando hacia arriba en el DOM
        // desde el mensaje del bot hasta encontrar un elemento con la clase .user-message
        // esto asegura que obtenemos la pregunta correcta relacionada con la respuesta del bot
        let userQuestionElement = botMessageDiv.previousElementSibling;
        while(userQuestionElement && !userQuestionElement.classList.contains('user-message')) {
            userQuestionElement = userQuestionElement.previousElementSibling;
        }

        // para enviar al feedback necesitamos tanto la respuesta del bot como la pregunta del usuario
        // entonces si no encontramos alguno de los dos, lanzamos un error
        // esto ayuda a evitar enviar feedback incompleto al backend
        const botResponse = botResponseElement ? botResponseElement.innerText : 'N/A';
        const userQuestion = userQuestionElement ? userQuestionElement.querySelector('.message-bubble').innerText : 'N/A';
        
        const topic = 'desconocido'; // esto es un placeholder, en una version futura podemos analizar el tema de la conversacion
        const response = await fetch(CONFIG.FEEDBACK_ENDPOINT, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                question: userQuestion,
                response: botResponse,
                rating: selectedRating,
                comment: comment,
                topic: topic
            })
        });
        // en caso de que la respuesta del servidor no sea exitosa, lanzamos un error
        if (!response.ok) {
            throw new Error('El servidor no pudo guardar el feedback.');
        }
        // si todo va bien, mostramos un mensaje de exito en la UI
        // y registramos el feedback en la consola para fines de desarrollo
        // en una version futura podemos eliminar este console.log
        console.log(`Feedback (rating: ${selectedRating}) enviado.`);
        // mostramos un mensaje de agradecimiento
        controls.innerHTML = '<span style="color: #10b981;">¡Gracias por tu feedback!</span>'; 
    } catch (error) {
        // en caso de cualquier error, mostramos un mensaje de error en la UI
        console.error('Error al enviar el feedback:', error);
        controls.innerHTML = '<span style="color: #ef4444;">Error al enviar. Intenta de nuevo.</span>'; // Mensaje de error final
    }
}

    // Funciones auxiliares que ahora tienen una implementación funcional
    scrollToBottom() {
        // Usamos un pequeño timeout para darle tiempo al navegador de renderizar el nuevo mensaje
        // y calcular la altura correcta.
        setTimeout(() => {
            this.elements.chatContainer.scrollTop = this.elements.chatContainer.scrollHeight;
        }, 100);
    }
    setLoading(loading) {
        this.isLoading = loading;
        if (loading) {
            this.elements.sendButton.disabled = true;
            this.elements.buttonText.classList.add('hidden');
            this.elements.buttonLoader.classList.remove('hidden');
        } else {
            this.elements.sendButton.disabled = false;
            this.elements.buttonText.classList.remove('hidden');
            this.elements.buttonLoader.classList.add('hidden');
        }
    }
    showErrorModal(message) {
        this.elements.errorMessage.textContent = message;
        this.elements.errorModal.classList.remove('hidden');
    }
    hideErrorModal() {
        this.elements.errorModal.classList.add('hidden');
    }
    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

//aqui inicializamos la aplicacion cuando el DOM este completamente cargado
// esto asegura que todos los elementos del DOM esten disponibles antes de que intentemos acceder a ellos
// y evitamos errores de referencia nula
document.addEventListener('DOMContentLoaded', () => {
    new TutorChat();
});

// aqui registramos el service worker para habilitar funcionalidades offline y mejorar el rendimiento
// el service worker es un script que el navegador ejecuta en segundo plano
// separado de la pagina web, permitiendo funcionalidades que no necesitan una pagina web o interaccion del usuario
// como el cacheo de recursos y manejo de notificaciones push
// verificamos que el navegador soporte service workers antes de intentar registrarlo
// y manejamos cualquier error que ocurra durante el registro
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js').catch(err => console.log('SW reg failed: ', err));
    });
}