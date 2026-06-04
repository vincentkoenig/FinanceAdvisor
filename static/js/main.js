// Aktuelle User ID nach dem Login speichern - null = kein Nutzer eingeloggt
let currentUserId = null;

async function login() {
    // Werte aus den Input Feldern holen
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;

    // POST Request an /login schicken - wie Postman aber in JavaScript
    const response = await fetch('/login', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'}, // sagt Flask: ich schicke JSON
        body: JSON.stringify({username, password})      // username und password als JSON
    });

    // Auf die JSON Antwort warten und in data speichern
    const data = await response.json();

    // Wenn Login erfolgreich (200 OK)
    if (response.ok) {
        currentUserId = data.user_id  // User ID speichern!
        alert('Login erfolgreich!');
        // Dashboard einblenden
        document.getElementById('dashboard-section').style.display = 'block';
    } else {
        // Fehlermeldung anzeigen z.B. "User not found"
        alert(data.error);
    }
}