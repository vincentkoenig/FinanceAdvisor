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
    // Werte aus den Input Feldern holen
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;

    // POST Request an /login schicken - wie Postman aber in JavaScript
    const response = await fetch('/login', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'}, // sagt Flask: ich schicke JSON
        body: JSON.stringify({email, password})      // username und password als JSON
    });

    // Auf die JSON Antwort warten und in data speichern
    const data = await response.json();

    // Wenn Login erfolgreich (200 OK)
    if (response.ok) {
        // user_id im Browser speichern und weiterleiten
        localStorage.setItem('user_id', data.user_id)  // user_id speichern
        window.location.href = '/home-page'
    } else {
        // Fehlermeldung anzeigen z.B. "User not found"
        showToast(data.error);
    }
}
