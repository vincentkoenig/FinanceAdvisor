// Gespeicherte Einstellungen beim Öffnen der Seite in die Felder laden
async function loadSettings() {
    const response = await fetch('/api/v1/me')
    if (!response.ok) return
    const me = await response.json()

    for (const field of ['risk_profile', 'investment_experience', 'investment_horizon']) {
        if (me[field]) document.getElementById(field).value = me[field]
    }
    if (me.monthly_budget) document.getElementById('monthly_budget').value = me.monthly_budget
}

loadSettings()

async function saveSettings() {
    // Werte aus den Input Feldern holen
    const risk_profile = document.getElementById('risk_profile').value
    const investment_experience = document.getElementById('investment_experience').value
    const monthly_budget = document.getElementById('monthly_budget').value
    const investment_horizon = document.getElementById('investment_horizon').value

    // Budget ist optional, aber falls ausgefüllt muss es eine gültige,
    // positive Zahl sein
    if (monthly_budget !== '' && (isNaN(monthly_budget) || parseFloat(monthly_budget) <= 0)) {
        showToast('Bitte ein gültiges Budget größer 0 angeben!', 'error')
        return
    }

    // POST Request an /chat schicken - wie Postman aber in JavaScript
    const response = await fetch('/api/v1/me/settings', {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'}, // sagt Flask: ich schicke JSON
        body: JSON.stringify({risk_profile: risk_profile, investment_experience: investment_experience, monthly_budget: monthly_budget, investment_horizon: investment_horizon})      // message als JSON
    });

    // Auf die JSON Antwort warten und in data speichern
    const data = await response.json();

    if (response.ok) {
        showToast('Einstellungen gespeichert!')
    } else {
        showToast(data.error)
    }

}