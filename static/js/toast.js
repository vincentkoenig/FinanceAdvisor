/**
 * toast.js - Kleine Benachrichtigungen statt alert()
 * Zeigt eine Toast-Nachricht unten rechts an, die nach ein paar
 * Sekunden automatisch wieder verschwindet.
 */

function showToast(message, type = 'success') {
    // Container erstellen, falls er noch nicht existiert
    let container = document.getElementById('toast-container')
    if (!container) {
        container = document.createElement('div')
        container.id = 'toast-container'
        document.body.appendChild(container)
    }

    // Toast Element erstellen
    const toast = document.createElement('div')
    toast.className = `toast toast-${type}`
    toast.textContent = message

    container.appendChild(toast)

    // Nach 3 Sekunden wieder entfernen
    setTimeout(() => {
        toast.classList.add('toast-fade-out')
        setTimeout(() => toast.remove(), 300)
    }, 3000)
}