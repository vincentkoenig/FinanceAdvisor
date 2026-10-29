async function logout() {
    // Session-Cookie auf dem Server löschen
    await fetch('/api/v1/auth/logout', {method: 'POST'})
    // Überbleibsel aus der Zeit vor der echten Anmeldung entfernen
    localStorage.removeItem('user_id')
    // Zur Login Seite weiterleiten
    window.location.href = '/'
}
