const widgetUserId = localStorage.getItem('user_id')

// Chat Widget öffnen/schließen
function toggleChat() {
    const widget = document.getElementById('chat-widget')
    if (widget.style.display === 'none') {
        widget.style.display = 'flex'
        loadWidgetHistory()
    } else {
        widget.style.display = 'none'
    }
}

// Chatverlauf laden
async function loadWidgetHistory() {
    const response = await fetch(`/chat/history/${widgetUserId}`)
    const data = await response.json()

    const messages = document.getElementById('widget-messages')
    messages.innerHTML = ''

    data.forEach(entry => {
        messages.innerHTML += `
            <div class="message ${entry.role === 'user' ? 'user-message' : 'assistant-message'}">
                ${entry.message}
            </div>
        `
    })

    // Nach unten scrollen
    messages.scrollTop = messages.scrollHeight
}

// Nachricht senden
async function sendWidgetMessage() {
    const input = document.getElementById('widget-input')
    const message = input.value
    if (!message) return

    const messages = document.getElementById('widget-messages')

    // Nutzer Nachricht anzeigen
    messages.innerHTML += `
        <div class="message user-message">${message}</div>
    `
    input.value = ''

    // Ans Backend schicken
    const response = await fetch('/chat', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({user_id: widgetUserId, message: message})
    })

    const data = await response.json()

    // Antwort anzeigen
    messages.innerHTML += `
        <div class="message assistant-message">${data.reply}</div>
    `

    // Nach unten scrollen
    messages.scrollTop = messages.scrollHeight
}