function logout() {
    // localStorage leeren
    localStorage.removeItem('user_id')
    // Zur Login Seite weiterleiten
    window.location.href = '/'
}