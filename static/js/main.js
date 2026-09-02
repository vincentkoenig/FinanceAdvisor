let pendingUserId = null

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
        // Nutzer ist angelegt, aber noch nicht verifiziert -
        // Verifizierungs-Modal statt direkter Weiterleitung anzeigen
        pendingUserId = data.user_id
        document.getElementById('verification-modal').style.display = 'block'

        if (!data.email_sent) {
            showToast('Registrierung erfolgreich, aber die Email konnte nicht verschickt werden. Bitte "Code erneut senden" versuchen.', 'error')
        } else {
            showToast('Wir haben dir einen Bestätigungscode geschickt!')
        }
    } else {
        showToast(data.error);
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
        body: JSON.stringify({user_id: pendingUserId, code: code})
    })

    const data = await response.json()

    if (response.ok) {
        showToast('Email erfolgreich bestätigt!')
        localStorage.setItem('user_id', pendingUserId)
        window.location.href = '/home-page'
    } else {
        showToast(data.error, 'error')
    }
}


async function resendVerificationCode() {
    const response = await fetch('/resend-verification', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({user_id: pendingUserId})
    })

    const data = await response.json()

    if (response.ok) {
        showToast('Neuer Code wurde verschickt!')
    } else {
        showToast(data.error, 'error')
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
        localStorage.setItem('user_id', data.user_id)
        window.location.href = '/home-page'
    } else if (response.status === 404) {
        showToast('Diese E-Mail-Adresse ist noch nicht registriert. Bitte registriere dich zuerst.', 'error')
    } else if (response.status === 401) {
        showToast('Falsches Passwort. Bitte versuche es erneut.', 'error')
    } else if (response.status === 403 && data.needs_verification) {
        // Account existiert, aber Email noch nicht bestätigt -
        // Verifizierungs-Modal öffnen statt nur eine Fehlermeldung zu zeigen
        pendingUserId = data.user_id
        document.getElementById('verification-modal').style.display = 'block'
        showToast('Bitte bestätige zuerst deine Email-Adresse.', 'error')
    } else {
        showToast(data.error || 'Login fehlgeschlagen', 'error')
    }
}
