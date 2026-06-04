async function sendMessage() {
    // Werte aus den Input Feldern holen
    const userId = localStorage.getItem('user_id')
    const message = document.getElementById('chat-input').value;

    // POST Request an /chat schicken - wie Postman aber in JavaScript
    const response = await fetch('/chat', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'}, // sagt Flask: ich schicke JSON
        body: JSON.stringify({user_id: userId, message: message})      // message als JSON
    });

    // Auf die JSON Antwort warten und in data speichern
    const data = await response.json();

    // Chat Bereich holen
    const chatMessages = document.getElementById('chat-messages')

    // Nutzer Nachricht anzeigen
    chatMessages.innerHTML += `
        <div class="message user-message">
            ${message}
        </div>
    `

    // LLM Antwort anzeigen
    chatMessages.innerHTML += `
        <div class="message assistant-message">
            ${marked.parse(data.reply)}
        </div>
    `

    // Eingabefeld leeren
    document.getElementById('chat-input').value = ''

    // Nach unten scrollen
    chatMessages.scrollTop = chatMessages.scrollHeight
}

// Chatverlauf beim Laden der Seite holen
async function loadChatHistory() {
    const userId = localStorage.getItem('user_id')

    const response = await fetch(`/chat/history/${userId}`, {
        method: 'GET'
    })

    const data = await response.json()
    const chatMessages = document.getElementById('chat-messages')

    data.forEach(entry => {
        if (entry.role === 'user') {
            chatMessages.innerHTML += `
                <div class="message user-message">${entry.message}</div>
            `
        } else {
            chatMessages.innerHTML += `
                <div class="message assistant-message">${marked.parse(entry.message)}</div>
            `
        }
    })
}

// Beim Laden der Seite aufrufen
loadChatHistory()