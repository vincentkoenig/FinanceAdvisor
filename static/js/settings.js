async function saveSettings() {
    // Werte aus den Input Feldern holen
    const userId = localStorage.getItem('user_id')
    const risk_profile = document.getElementById('risk_profile').value
    const investment_experience = document.getElementById('investment_experience').value
    const monthly_budget = document.getElementById('monthly_budget').value
    const investment_horizon = document.getElementById('investment_horizon').value

    // POST Request an /chat schicken - wie Postman aber in JavaScript
    const response = await fetch(`/users/${userId}/settings`, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'}, // sagt Flask: ich schicke JSON
        body: JSON.stringify({user_id: userId, risk_profile: risk_profile, investment_experience: investment_experience, monthly_budget: monthly_budget, investment_horizon: investment_horizon})      // message als JSON
    });

    // Auf die JSON Antwort warten und in data speichern
    const data = await response.json();

    if (response.ok) {
        alert('Einstellungen gespeichert!')
    } else {
        alert(data.error)
    }

}