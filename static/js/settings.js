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

// Exportdatei einlesen und in das (leere) Konto einspielen
async function importData() {
    const fileInput = document.getElementById('import-file')
    const file = fileInput.files[0]

    if (!file) {
        showToast('Bitte zuerst eine Exportdatei auswählen!', 'error')
        return
    }

    let payload
    try {
        payload = JSON.parse(await file.text())
    } catch {
        showToast('Die Datei ist keine gültige Exportdatei.', 'error')
        return
    }

    if (!confirm('Daten aus dieser Datei in dein Konto importieren? Das geht nur, solange dein Konto noch keine eigenen Daten enthält.')) {
        return
    }

    const response = await fetch('/api/v1/me/import', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    })
    const data = await response.json().catch(() => ({}))

    if (response.ok) {
        const counts = data.imported
        showToast(`Importiert: ${counts.transactions} Buchungen, ${counts.positions} Positionen, ${counts.categories} Kategorien`)
        fileInput.value = ''
        loadSettings()
    } else {
        showToast(data.error || 'Import fehlgeschlagen', 'error')
    }
}
