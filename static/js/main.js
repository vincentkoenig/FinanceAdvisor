async function register() {
    // Werte aus den Input Feldern holen
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;

    // POST Request an /register schicken - wie Postman aber in JavaScript
    const response = await fetch('/register', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'}, // sagt Flask: ich schicke JSON
        body: JSON.stringify({email, password})      // email, username und password als JSON
    });

    // Auf die JSON Antwort warten und in data speichern
    const data = await response.json();

    // Wenn Login erfolgreich (200 OK)
    if (response.ok) {
        // user_id im Browser speichern und weiterleiten
        localStorage.setItem('user_id', data.user_id)
        window.location.href = '/home-page';
    } else {
        // Fehlermeldung anzeigen z.B. "User not found"
        showToast(data.error);
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
        // E-Mail nicht registriert - klare Handlungsaufforderung statt
        // generischer Fehlermeldung
        showToast('Diese E-Mail-Adresse ist noch nicht registriert. Bitte registriere dich zuerst.', 'error')
    } else if (response.status === 401) {
        showToast('Falsches Passwort. Bitte versuche es erneut.', 'error')
    } else {
        showToast(data.error || 'Login fehlgeschlagen', 'error')
    }
}
