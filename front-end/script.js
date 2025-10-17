const CONFIG = {
    API_ENDPOINT: '/api/chat',
    HEALTH_ENDPOINT: '/api/health',
    FEEDBACK_ENDPOINT: '/api/feedback',
    VALIDATE_KEY_ENDPOINT: '/api/validate_key'
};

function generateUUID() {
    return ([1e7]+-1e3+-4e3+-8e3+-1e11).replace(/[018]/g, c =>
        (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16)
    );
}

class TutorChat {
    constructor() {
        this.elements = {
            mainContainer: document.getElementById('mainContainer'),
            chatContainer: document.getElementById('chatContainer'),
            questionInput: document.getElementById('questionInput'),
            sendButton: document.getElementById('sendButton'),
            buttonText: document.getElementById('buttonText'),
            buttonLoader: document.getElementById('buttonLoader'),
            suggestions: document.getElementById('suggestions'),
            status: document.getElementById('status'),
            statusText: document.querySelector('.status-text'),
            
            errorModal: document.getElementById('errorModal'),
            errorMessage: document.getElementById('errorMessage'),
            closeModalBtn: document.getElementById('closeModalBtn'),
            
            accessModal: document.getElementById('accessModal'),
            accessKeyInput: document.getElementById('accessKeyInput'),
            submitAccessKey: document.getElementById('submitAccessKey'),
            accessError: document.getElementById('accessError')
        };
        
        this.isLoading = false;
        this.sessionId = null;
        this.accessKey = null;
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.setupAutoResize();
        this.handleAccess();
    }
    
    handleAccess() {
        const savedKey = localStorage.getItem('electroTutorAccessKey');
        if (savedKey) {
            this.validateKey(savedKey);
        } else {
            this.showAccessModal();
        }
    }

    showAccessModal() {
        document.body.classList.add('modal-open');
        this.elements.accessModal.classList.add('visible');
        this.elements.accessKeyInput.focus();
    }

    hideAccessModal() {
        document.body.classList.remove('modal-open');
        this.elements.accessModal.classList.remove('visible');
    }

    async validateKey(key) {
        this.elements.accessError.textContent = '';
        try {
            const response = await fetch(CONFIG.VALIDATE_KEY_ENDPOINT, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ access_key: key })
            });

            if (response.ok) {
                this.accessKey = key;
                this.sessionId = generateUUID();
                localStorage.setItem('electroTutorAccessKey', key);
                
                this.hideAccessModal();
                this.elements.questionInput.focus();
                this.updateStatus('success', 'Conectado');
                console.log(`Acceso concedido. Sesión: ${this.sessionId}`);
                this.addMessage('¡Hola! Soy tu tutor de electromagnetismo. ¿En qué puedo ayudarte hoy?', 'bot');
            } else {
                localStorage.removeItem('electroTutorAccessKey');
                this.elements.accessError.textContent = 'Clave inválida. Intenta de nuevo.';
                this.elements.accessKeyInput.value = '';
                this.elements.accessKeyInput.focus();
                if (!this.elements.accessModal.classList.contains('visible')) {
                    this.showAccessModal();
                }
            }
        } catch (error) {
            this.elements.accessError.textContent = 'Error de conexión al validar la clave.';
        }
    }
    
    setupEventListeners() {
        this.elements.submitAccessKey.addEventListener('click', () => {
            const key = this.elements.accessKeyInput.value.trim();
            if (key) this.validateKey(key);
        });

        this.elements.accessKeyInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.elements.submitAccessKey.click();
        });
        
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

        this.elements.closeModalBtn.addEventListener('click', () => this.hideErrorModal());

        this.elements.chatContainer.addEventListener('click', async (e) => {
            const target = e.target;
            if (target.classList.contains('star')) {
                 const ratingContainer = target.closest('.star-rating');
                if (!ratingContainer) return;

                const clickedRating = parseInt(target.dataset.rating);
                ratingContainer.dataset.selectedRating = clickedRating;

                ratingContainer.querySelectorAll('.star').forEach(s => {
                    s.classList.toggle('selected', parseInt(s.dataset.rating) <= clickedRating);
                });

                const controls = target.closest('.feedback-controls');
                const commentSection = controls.querySelector('.comment-section');
                controls.querySelector('.feedback-prompt').style.display = 'none';
                
                if (clickedRating < 4) {
                    commentSection.classList.remove('hidden');
                    commentSection.querySelector('.feedback-comment-textarea').focus();
                } else {
                    commentSection.classList.add('hidden');
                    await this.sendFeedback(ratingContainer);
                }
            }

            if (target.classList.contains('send-comment-btn')) {
                const ratingContainer = target.closest('.feedback-controls').querySelector('.star-rating');
                await this.sendFeedback(ratingContainer);
            }
        });
    }
    
    setupAutoResize() {
        this.elements.questionInput.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = `${Math.min(this.scrollHeight, 120)}px`;
        });
    }

    updateStatus(type, message) {
        this.elements.status.className = `status ${type}`;
        this.elements.statusText.textContent = message;
    }

    async sendMessage() {
        if (!this.sessionId || !this.accessKey) {
            this.showErrorModal('Sesión no válida. Por favor, recarga la página e introduce una clave válida.');
            return;
        }
        
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
                session_id: this.sessionId,
                access_key: this.accessKey
            })
        });
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ error: 'Error desconocido en la API' }));
            throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
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
                    ${!isError ? `
                    <div class="feedback-controls">
                        <span class="feedback-prompt">¿Qué te pareció la respuesta?</span>
                        <div class="star-rating" data-message-id="${messageId}">
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
                    </div>` : ''}
                </div>
            `;
        }
        
        this.elements.chatContainer.appendChild(messageDiv);
        if (sender === 'bot' && typeof MathJax !== "undefined") {
            MathJax.typesetPromise([`#${messageId}`]).catch((err) => console.log(err.message));
        }
        this.scrollToBottom();
    }
    
    async sendFeedback(ratingContainer) {
        const selectedRating = parseInt(ratingContainer.dataset.selectedRating);
        const controls = ratingContainer.closest('.feedback-controls');
        const comment = controls.querySelector('.feedback-comment-textarea').value.trim();

        controls.innerHTML = '<span style="color: var(--success-color);">¡Enviando feedback...!</span>';

        try {
            const botMessageDiv = controls.closest('.message.bot-message');
            const botResponseElement = botMessageDiv.querySelector('.message-bubble');
            
            let userQuestionElement = botMessageDiv.previousElementSibling;
            while(userQuestionElement && !userQuestionElement.classList.contains('user-message')) {
                userQuestionElement = userQuestionElement.previousElementSibling;
            }

            const botResponse = botResponseElement ? botResponseElement.innerText : 'N/A';
            const userQuestion = userQuestionElement ? userQuestionElement.querySelector('.message-bubble').innerText : 'N/A';
            
            const response = await fetch(CONFIG.FEEDBACK_ENDPOINT, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    question: userQuestion,
                    response: botResponse,
                    rating: selectedRating,
                    comment: comment,
                    session_id: this.sessionId,
                    access_key: this.accessKey
                })
            });
            if (!response.ok) {
                throw new Error('El servidor no pudo guardar el feedback.');
            }
            controls.innerHTML = '<span style="color: var(--success-color);">¡Gracias por tu feedback!</span>';
        } catch (error) {
            console.error('Error al enviar el feedback:', error);
            controls.innerHTML = '<span style="color: var(--error-color);">Error al enviar. Intenta de nuevo.</span>';
        }
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
    
    setLoading(loading) {
        this.isLoading = loading;
        this.elements.sendButton.disabled = loading;
        this.elements.buttonText.classList.toggle('hidden', loading);
        this.elements.buttonLoader.classList.toggle('hidden', !loading);
    }

    showErrorModal(message) {
        this.elements.errorMessage.textContent = message;
        this.elements.errorModal.classList.add('visible');
        document.body.classList.add('modal-open');
    }

    hideErrorModal() {
        this.elements.errorModal.classList.remove('visible');
        if (!this.elements.accessModal.classList.contains('visible')) {
            document.body.classList.remove('modal-open');
        }
    }
    
    scrollToBottom() {
        setTimeout(() => {
            this.elements.chatContainer.scrollTop = this.elements.chatContainer.scrollHeight;
        }, 100);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new TutorChat();
});

