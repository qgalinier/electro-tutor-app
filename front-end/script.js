// Configuración corregida para desarrollo local
const CONFIG = {
    API_ENDPOINT: 'http://127.0.0.1:5000/api/chat',
    HEALTH_ENDPOINT: 'http://127.0.0.1:5000/api/health',
    // Nuevo endpoint para el feedback
    FEEDBACK_ENDPOINT: 'http://127.0.0.1:5000/api/feedback', 
    MAX_RETRIES: 3,
    RETRY_DELAY: 1000
};

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
    
    init() {
        this.setupEventListeners();
        this.setupAutoResize();
        this.checkBackendConnection();
    }
    
    setupEventListeners() {
        // Enviar mensaje con clic
        this.elements.sendButton.addEventListener('click', () => this.sendMessage());
        
        // Enviar mensaje con Enter
        this.elements.questionInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        
        // Clic en sugerencias
        this.elements.suggestions.addEventListener('click', (e) => {
            if (e.target.classList.contains('suggestion-chip')) {
                const question = e.target.getAttribute('data-question');
                this.elements.questionInput.value = question;
                this.sendMessage();
            }
        });
        
        // Cerrar modal de error
        this.elements.closeModal.addEventListener('click', () => this.hideErrorModal());
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') this.hideErrorModal();
        });

        // --- LISTENER CORREGIDO PARA ESTRELLAS Y COMENTARIOS ---
        this.elements.chatContainer.addEventListener('click', async (e) => {
            const target = e.target;

            // Lógica para seleccionar estrellas
            if (target.classList.contains('star')) {
                const ratingContainer = target.closest('.star-rating');
                const rating = parseInt(target.dataset.rating);

                ratingContainer.querySelectorAll('.star').forEach(s => {
                    s.classList.remove('selected');
                    if (parseInt(s.dataset.rating) <= rating) {
                        s.classList.add('selected');
                    }
                });

                const controls = target.closest('.feedback-controls');
                const commentSection = controls.querySelector('.comment-section');
                const feedbackPrompt = controls.querySelector('.feedback-prompt');

                if (feedbackPrompt) feedbackPrompt.style.display = 'none';
                ratingContainer.dataset.selectedRating = rating;

                if (rating < 4) { // Pedir comentario para ratings bajos
                    commentSection.classList.remove('hidden');
                    commentSection.querySelector('.feedback-comment-textarea').focus();
                } else { // Enviar directamente para ratings altos
                    commentSection.classList.add('hidden');
                    await this.sendFeedback(ratingContainer);
                }
            }

            // Lógica para enviar comentario
            if (target.classList.contains('send-comment-btn')) {
                const ratingContainer = target.closest('.feedback-controls').querySelector('.star-rating');
                await this.sendFeedback(ratingContainer);
            }
        });

        // Focus automático en el input
        this.elements.questionInput.focus();
    }
    
    setupAutoResize() {
        this.elements.questionInput.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 120) + 'px';
        });
    }
    
    async checkBackendConnection() {
        // ... (esta función no necesita cambios)
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
        // ... (esta función no necesita cambios)
        this.elements.status.className = `status ${type}`;
        this.elements.statusText.textContent = message;
    }
    
    async sendMessage() {
        // ... (esta función no necesita cambios)
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
        // ... (esta función no necesita cambios)
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
        // ... (esta función no necesita cambios)
        this.updateStatus('error', 'Error de conexión');
        this.showErrorModal('No se pudo conectar con el tutor. Verifica tu conexión y que el backend esté ejecutándose.');
        this.addMessage('⚠️ Lo siento, no pude procesar tu pregunta en este momento. Intenta de nuevo.', 'bot', true);
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
        // ... (esta función no necesita cambios)
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

    // --- NUEVO MÉTODO PARA ENVIAR FEEDBACK ---
    // --- NUEVO MÉTODO PARA ENVIAR FEEDBACK ---
async sendFeedback(ratingContainer) {
    const selectedRating = parseInt(ratingContainer.dataset.selectedRating);
    const controls = ratingContainer.closest('.feedback-controls');
    const commentSection = controls.querySelector('.comment-section');
    const comment = commentSection.querySelector('.feedback-comment-textarea').value.trim();

    // Deshabilitar UI inmediatamente y mostrar mensaje de agradecimiento/carga
    controls.innerHTML = '<span style="color: #10b981;">¡Enviando feedback...!</span>'; // Mensaje temporal

    try {
        // --- MODIFICACIÓN CLAVE AQUÍ ---
        // Buscar el mensaje del bot a partir de 'controls' (que es el contenedor del feedback)
        // y luego subir al ancestro .bot-message
        const botMessageDiv = controls.closest('.message.bot-message');
        if (!botMessageDiv) {
            throw new Error("No se encontró el contenedor del mensaje del bot para el feedback.");
        }

        const botResponseElement = botMessageDiv.querySelector('.message-bubble');
        
        // Buscar el mensaje del usuario inmediatamente anterior
        let userQuestionElement = botMessageDiv.previousElementSibling;
        while(userQuestionElement && !userQuestionElement.classList.contains('user-message')) {
            userQuestionElement = userQuestionElement.previousElementSibling;
        }

        // Obtener el texto de la pregunta y la respuesta
        const botResponse = botResponseElement ? botResponseElement.innerText : 'N/A';
        const userQuestion = userQuestionElement ? userQuestionElement.querySelector('.message-bubble').innerText : 'N/A';
        
        const topic = 'desconocido'; // Lógica de clasificación a futuro

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

        if (!response.ok) {
            throw new Error('El servidor no pudo guardar el feedback.');
        }

        console.log(`Feedback (rating: ${selectedRating}) enviado.`);
        controls.innerHTML = '<span style="color: #10b981;">¡Gracias por tu feedback!</span>'; // Mensaje final de éxito
    } catch (error) {
        console.error('Error al enviar el feedback:', error);
        controls.innerHTML = '<span style="color: #ef4444;">Error al enviar. Intenta de nuevo.</span>'; // Mensaje de error final
    }
}

    scrollToBottom() { /* ... sin cambios ... */ }
    setLoading(loading) { /* ... sin cambios ... */ }
    showErrorModal(message) { /* ... sin cambios ... */ }
    hideErrorModal() { /* ... sin cambios ... */ }
    delay(ms) { /* ... sin cambios ... */ }
}

// --- INICIALIZACIÓN DE LA APLICACIÓN ---
document.addEventListener('DOMContentLoaded', () => {
    new TutorChat();
});

// Service Worker (opcional)
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js').catch(err => console.log('SW reg failed: ', err));
    });
}