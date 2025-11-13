(function() {
    // Создание контейнера чат-бота
    const chatbotContainer = document.createElement('div');
    chatbotContainer.id = 'consultant-it-chatbot';
    chatbotContainer.innerHTML = `
        <style>
            #consultant-it-chatbot {
                position: fixed;
                bottom: 20px;
                right: 20px;
                width: 350px;
                height: 500px;
                border: 1px solid #ccc;
                border-radius: 12px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                background: white;
                display: none;
                flex-direction: column;
                z-index: 9999;
            }
            #consultant-it-chatbot.open {
                display: flex;
            }
            #chatbot-header {
                background: #0284c7;
                color: white;
                padding: 15px;
                border-radius: 12px 12px 0 0;
                font-weight: bold;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            #chatbot-close {
                cursor: pointer;
                font-size: 20px;
            }
            #chatbot-messages {
                flex: 1;
                overflow-y: auto;
                padding: 15px;
                background: #f9f9f9;
            }
            .message {
                margin-bottom: 10px;
                padding: 10px;
                border-radius: 8px;
                max-width: 80%;
            }
            .message.user {
                background: #0284c7;
                color: white;
                margin-left: auto;
            }
            .message.bot {
                background: #e5e7eb;
                color: #1f2937;
            }
            #chatbot-input-container {
                display: flex;
                padding: 10px;
                border-top: 1px solid #ddd;
            }
            #chatbot-input {
                flex: 1;
                padding: 10px;
                border: 1px solid #ccc;
                border-radius: 6px;
                margin-right: 10px;
            }
            #chatbot-send {
                padding: 10px 20px;
                background: #0284c7;
                color: white;
                border: none;
                border-radius: 6px;
                cursor: pointer;
            }
            #chatbot-button {
                position: fixed;
                bottom: 20px;
                right: 20px;
                width: 60px;
                height: 60px;
                background: #0284c7;
                color: white;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 24px;
                cursor: pointer;
                box-shadow: 0 4px 12px rgba(0,0,0,0.2);
                z-index: 9998;
            }
        </style>
        <div id="chatbot-button">💬</div>
        <div id="consultant-it-chatbot">
            <div id="chatbot-header">
                <span>Consultant-IT</span>
                <span id="chatbot-close">×</span>
            </div>
            <div id="chatbot-messages"></div>
            <div id="chatbot-input-container">
                <input type="text" id="chatbot-input" placeholder="Напишите сообщение..." />
                <button id="chatbot-send">Отправить</button>
            </div>
        </div>
    `;
    document.body.appendChild(chatbotContainer);

    const chatbot = document.getElementById('consultant-it-chatbot');
    const button = document.getElementById('chatbot-button');
    const closeBtn = document.getElementById('chatbot-close');
    const messagesDiv = document.getElementById('chatbot-messages');
    const input = document.getElementById('chatbot-input');
    const sendBtn = document.getElementById('chatbot-send');

    let sessionId = 'session-' + Math.random().toString(36).substr(2, 9);

    button.addEventListener('click', () => {
        chatbot.classList.add('open');
        button.style.display = 'none';
    });

    closeBtn.addEventListener('click', () => {
        chatbot.classList.remove('open');
        button.style.display = 'flex';
    });

    function addMessage(text, sender) {
        const msg = document.createElement('div');
        msg.className = 'message ' + sender;
        msg.textContent = text;
        messagesDiv.appendChild(msg);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
    }

    async function sendMessage() {
        const message = input.value.trim();
        if (!message) return;

        addMessage(message, 'user');
        input.value = '';

        try {
            const response = await fetch('http://213.226.127.186/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message, sessionId })
            });
            const data = await response.json();
            addMessage(data.message || 'Ошибка ответа', 'bot');
        } catch (error) {
            addMessage('Ошибка соединения', 'bot');
        }
    }

    sendBtn.addEventListener('click', sendMessage);
    input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage();
    });
})();
