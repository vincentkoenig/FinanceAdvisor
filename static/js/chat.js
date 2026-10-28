async function sendMessage() {
    const userId = currentUserId()
    const input = document.getElementById('chat-input')
    const message = input.value
    if (!message) return

    const messages = document.getElementById('chat-messages')

    // Nutzer Nachricht sofort anzeigen
    messages.innerHTML += `
        <div class="message user-message">${escapeHtml(message)}</div>
    `

    // Eingabefeld leeren
    input.value = ''

    // "Antwort wird erstellt..." anzeigen
    const loadingId = 'loading-' + Date.now()
    messages.innerHTML += `
        <div class="message assistant-message" id="${loadingId}">
            <em>Antwort wird erstellt...</em>
        </div>
    `

    // Nach unten scrollen
    messages.scrollTop = messages.scrollHeight

    // Ans Backend schicken
    const response = await fetch('/chat', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({message: message})
    })

    const data = await response.json()

    // Loading ersetzen mit echter Antwort
    document.getElementById(loadingId).innerHTML = renderMarkdown(data.reply)

    // Nach unten scrollen
    messages.scrollTop = messages.scrollHeight
}

// Chatverlauf beim Laden der Seite holen
async function loadChatHistory() {
    const userId = currentUserId()

    const response = await fetch(`/chat/history/${userId}`, {
        method: 'GET'
    })

    const data = await response.json()
    const chatMessages = document.getElementById('chat-messages')

    data.forEach(entry => {
        if (entry.role === 'user') {
            chatMessages.innerHTML += `
                <div class="message user-message">${escapeHtml(entry.message)}</div>
            `
        } else {
            chatMessages.innerHTML += `
                <div class="message assistant-message">${renderMarkdown(entry.message)}</div>
            `
        }
    })
    // Nach dem Laden ganz nach unten scrollen
    chatMessages.scrollTop = chatMessages.scrollHeight
}

// Beim Laden der Seite aufrufen
loadChatHistory()

// Enter Taste zum Senden
document.getElementById('chat-input').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        sendMessage()
    }
})