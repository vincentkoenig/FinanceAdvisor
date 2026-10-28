// E-Mail des Kontos, das gerade bestätigt werden muss (nach Registrierung
// oder bei einem Login mit noch unbestätigter Adresse)
let pendingEmail = null

function showVerificationModal(email) {
    pendingEmail = email
    document.getElementById('verification-modal').style.display = 'block'
}

async function register() {
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;

    const response = await fetch('/register', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({email, password})
    });

    const data = await response.json();

    if (response.ok) {
        // Konto ist angelegt, aber noch nicht bestätigt -
        // Verifizierungs-Modal statt direkter Weiterleitung anzeigen
        showVerificationModal(data.email)

        if (!data.email_sent) {
            showToast('Registrierung erfolgreich, aber die Email konnte nicht verschickt werden. Bitte "Code erneut senden" versuchen.', 'error')
        } else {
            showToast('Wir haben dir einen Bestätigungscode geschickt!')
        }
    } else if (response.status === 429) {
        showToast('Zu viele Versuche. Bitte warte etwas und versuche es dann erneut.', 'error')
    } else {
        showToast(data.error, 'error');
    }
}


async function verifyEmail() {
    const code = document.getElementById('verification-code').value

    if (code.length !== 6) {
        showToast('Bitte einen 6-stelligen Code eingeben!', 'error')
        return
    }

    const response = await fetch('/verify-email', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({email: pendingEmail, code: code})
    })

    const data = await response.json()

    if (response.ok) {
        // Der Server meldet nach erfolgreicher Bestätigung direkt an
        showToast('Email erfolgreich bestätigt!')
        window.location.href = '/home-page'
    } else {
        showToast(data.error || 'Zu viele Versuche. Bitte warte etwas.', 'error')
    }
}


async function resendVerificationCode() {
    const response = await fetch('/resend-verification', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({email: pendingEmail})
    })

    const data = await response.json()

    if (response.ok) {
        showToast('Neuer Code wurde verschickt!')
    } else {
        showToast(data.error || 'Zu viele Versuche. Bitte warte etwas.', 'error')
    }
}


async function login() {
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;

    const response = await fetch('/login', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({email, password})
    });

    const data = await response.json();

    if (response.ok) {
        // Der Server hat das Session-Cookie gesetzt - nichts weiter zu speichern
        window.location.href = '/home-page'
    } else if (response.status === 401) {
        showToast('E-Mail oder Passwort ist falsch.', 'error')
    } else if (response.status === 403 && data.needs_verification) {
        // Konto existiert, aber Email noch nicht bestätigt -
        // Verifizierungs-Modal öffnen statt nur eine Fehlermeldung zu zeigen
        showVerificationModal(data.email)
        showToast('Bitte bestätige zuerst deine Email-Adresse.', 'error')
    } else if (response.status === 429) {
        showToast('Zu viele Anmeldeversuche. Bitte warte etwas und versuche es dann erneut.', 'error')
    } else {
        showToast(data.error || 'Login fehlgeschlagen', 'error')
    }
}
