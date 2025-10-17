//configuración de endpoints
const CONFIG = {
    API_ENDPOINT: '/api/chat',
    HEALTH_ENDPOINT: '/api/health',
    FEEDBACK_ENDPOINT: '/api/feedback',
    VALIDATE_KEY_ENDPOINT: '/api/validate_key' //nuevo endpoint para validar la clave
};

//función para generar un id único para la sesión
function generateUUID() {
    return ([1e7]+-1e3+-4e3+-8e3+-1e11).replace(/[018]/g, c =>
        (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16)
    );
}

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
            closeModal: document.getElementById('closeModal'),
            //elementos del nuevo modal de acceso
            accessModal: document.getElementById('accessModal'),
            accessKeyInput: document.getElementById('accessKeyInput'),
            submitAccessKey: document.getElementById('submitAccessKey'),
            accessError: document.getElementById('accessError')
        };
        
        this.isLoading = false;
        //inicializamos sessionId y accessKey como nulos hasta que se validen
        this.sessionId = null;
        this.accessKey = null;
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.setupAutoResize();
        this.handleAccess(); //inicia el flujo de validación
    }
    
    handleAccess() {
        //revisa si ya hay una clave guardada en el almacenamiento local del navegador
        const savedKey = localStorage.getItem('electroTutorAccessKey');
        if (savedKey) {
            this.validateKey(savedKey);
        } else {
            //si no, muestra el modal para que el usuario la ingrese
            this.elements.accessModal.style.display = 'flex';
            this.elements.accessKeyInput.focus();
        }
    }

    async validateKey(key) {
        this.elements.accessError.style.display = 'none';
        try {
            //hace una petición al nuevo endpoint del backend para ver si la clave es válida
            const response = await fetch(CONFIG.VALIDATE_KEY_ENDPOINT, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ access_key: key })
            });

            if (response.ok) {
                //si la clave es válida, guardamos los datos de la sesión
                this.accessKey = key;
                this.sessionId = generateUUID(); //generamos el id de sesión
                localStorage.setItem('electroTutorAccessKey', key); //guardamos la clave para futuras visitas
                
                this.elements.accessModal.style.display = 'none'; //ocultamos el modal
                this.elements.questionInput.focus();
                this.updateStatus('success', 'Conectado');
                console.log(`Acceso concedido. Sesión iniciada: ${this.sessionId}`);
            } else {
                //si la clave es inválida, borramos cualquier clave guardada y mostramos error
                localStorage.removeItem('electroTutorAccessKey');
                this.elements.accessError.textContent = 'Clave inválida. Intenta de nuevo.';
                this.elements.accessError.style.display = 'block';
                this.elements.accessModal.style.display = 'flex';
            }
        } catch (error) {
            this.elements.accessError.textContent = 'Error de conexión al validar la clave.';
            this.elements.accessError.style.display = 'block';
        }
    }
    
    setupEventListeners() {
        //evento para el botón "Entrar" del modal de acceso
        this.elements.submitAccessKey.addEventListener('click', () => {
            const key = this.elements.accessKeyInput.value.trim();
            if (key) {
                this.validateKey(key);
            }
        });
        //permite enviar la clave con la tecla Enter
        this.elements.accessKeyInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.elements.submitAccessKey.click();
            }
        });
        
        //eventos originales del chat
        this.elements.sendButton.addEventListener('click', () => this.sendMessage());
        this.elements.questionInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        this.elements.suggestions.addEventListener('click', (e) => {
            if (e.target.classList.contains('suggestion-chip')) {
                const question = e.target.getAttribute('data-question');
                this.elements.questionInput.value = question;
                this.sendMessage();
            }
        });
        this.elements.closeModal.addEventListener('click', () => this.hideErrorModal());
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') this.hideErrorModal();
        });
        //eventos de feedback no cambian
        //...
    }
    
    setupAutoResize() {
        this.elements.questionInput.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 120) + 'px';
        });
    }
    
    updateStatus(type, message) {
        this.elements.status.className = `status ${type}`;
        this.elements.statusText.textContent = message;
    }
    
    async sendMessage() {
        //nos aseguramos de que tengamos una sesión activa antes de enviar un mensaje
        if (!this.sessionId || !this.accessKey) {
            this.showErrorModal('Sesión no válida. Por favor, recarga la página.');
            return;
        }
        
        const question = this.elements.questionInput.value.trim();
        if (!question || this.isLoading) return;
        
        this.addMessage(question, 'user');
        this.elements.questionInput.value = '';
        this.elements.questionInput.style.height = 'auto';
        this.setLoading(true);

        try {
            const response = await this.callBackend(question);
            this.addMessage(response, 'bot');
        } catch (error) {
            console.error('Error al enviar mensaje:', error);
            this.handleError(error);
        } finally {
            this.setLoading(false);
            this.elements.questionInput.focus();
        }
    }
    
    async callBackend(question) {
        const response = await fetch(CONFIG.API_ENDPOINT, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                question: question, 
                session_id: this.sessionId, //enviamos el id de sesión
                access_key: this.accessKey   //enviamos la clave de acceso
            })
        });
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'API Error');
        }
        const data = await response.json();
        return data.response;
    }
    
    handleError(error) {
        this.updateStatus('error', 'Error de conexión');
        this.showErrorModal(`No se pudo conectar con el tutor. Error: ${error.message}`);
        this.addMessage('Lo siento, no pude procesar tu pregunta en este momento. Intenta de nuevo.', 'bot', true);
    }

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
        
        this.elements.chatContainer.appendChild(messageDiv);
        if (sender === 'bot' && typeof MathJax !== "undefined") {
            MathJax.typesetPromise([`#${messageId}`]).catch((err) => console.log(err.message));
        }
        this.scrollToBottom();
    }
    
    formatBotMessage(text) {
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

    async sendFeedback(ratingContainer) {
        const selectedRating = parseInt(ratingContainer.dataset.selectedRating);
        const controls = ratingContainer.closest('.feedback-controls');
        const commentSection = controls.querySelector('.comment-section');
        const comment = commentSection.querySelector('.feedback-comment-textarea').value.trim();

        controls.innerHTML = '<span style="color: #10b981;">Enviando feedback...</span>';

        try {
            const botMessageDiv = controls.closest('.message.bot-message');
            if (!botMessageDiv) throw new Error("No se encontró el mensaje del bot.");
            
            let userQuestionElement = botMessageDiv.previousElementSibling;
            while(userQuestionElement && !userQuestionElement.classList.contains('user-message')) {
                userQuestionElement = userQuestionElement.previousElementSibling;
            }

            const botResponse = botMessageDiv.querySelector('.message-bubble').innerText;
            const userQuestion = userQuestionElement ? userQuestionElement.querySelector('.message-bubble').innerText : 'N/A';
            
            const response = await fetch(CONFIG.FEEDBACK_ENDPOINT, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    question: userQuestion,
                    response: botResponse,
                    rating: selectedRating,
                    comment: comment,
                    session_id: this.sessionId, //enviamos el id de sesión
                    access_key: this.accessKey   //enviamos la clave de acceso
                })
            });
            
            if (!response.ok) {
                throw new Error('El servidor no pudo guardar el feedback.');
            }

            controls.innerHTML = '<span style="color: #10b981;">¡Gracias por tu feedback!</span>'; 
        } catch (error) {
            console.error('Error al enviar el feedback:', error);
            controls.innerHTML = '<span style="color: #ef4444;">Error al enviar. Intenta de nuevo.</span>';
        }
    }

    scrollToBottom() {
        setTimeout(() => {
            this.elements.chatContainer.scrollTop = this.elements.chatContainer.scrollHeight;
        }, 100);
    }
    setLoading(loading) {
        this.isLoading = loading;
        this.elements.sendButton.disabled = loading;
        this.elements.buttonText.classList.toggle('hidden', loading);
        this.elements.buttonLoader.classList.toggle('hidden', !loading);
    }
    showErrorModal(message) {
        this.elements.errorMessage.textContent = message;
        this.elements.errorModal.classList.remove('hidden');
    }
    hideErrorModal() {
        this.elements.errorModal.classList.add('hidden');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new TutorChat();
});
