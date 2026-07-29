async function analysePortfolio() {
    // Werte aus den Input Feldern holen
    const userId = localStorage.getItem('user_id')

    // Spinner anzeigen während die Analyse läuft
    const result = document.getElementById('analyse-result')
    result.innerHTML = `
        <div class="analyse-card" style="align-items: center; flex-direction: row; justify-content: center; gap: 15px;">
            <span class="spinner"></span>
            <p style="margin: 0;">Analyse wird erstellt...</p>
        </div>
    `

    // Button deaktivieren damit nicht mehrfach geklickt werden kann
    const button = document.querySelector('.analyse-button')
    button.disabled = true

    // POST Request an /chat schicken - wie Postman aber in JavaScript
    const response = await fetch('/portfolio/analyze', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({user_id: userId,})
    });

    // Auf die JSON Antwort warten und in data speichern
    const data = await response.json();

    // Button wieder aktivieren
    button.disabled = false

    // Ergebnis anzeigen
    result.innerHTML = `
        <div class="analyse-card">
            <h3>Gesamtwert: ${data.total_value} ${data.currency}</h3>
            <p>${data.summary}</p>
            <h4>Risikobewertung:</h4>
            <p>${data.risk_assessment}</p>
            <h4>Empfehlungen:</h4>
            <ul>
                ${data.recommendations.map(r => `<li>${r}</li>`).join('')}
            </ul>
            <p><small>${data.disclaimer}</small></p>
        </div>
    `
}


const userId = localStorage.getItem('user_id')

// Vorherige Analysen laden
async function loadPreviousAnalyses() {
    const response = await fetch(`/users/${userId}/portfolio/analyses`)
    const data = await response.json()

    const analysesList = document.getElementById('analyses-list')
    analysesList.innerHTML = ''

    data.forEach(analysis => {
        analysesList.innerHTML += `
            <div class="analysis-item" onclick="showAnalysis(${analysis.id})">
                <div class="analysis-item-header">
                    <span>${analysis.created_at}</span>
                    <span>${analysis.total_value.toLocaleString('de-DE', {minimumFractionDigits: 2})} €</span>
                </div>
                <p>${analysis.summary.substring(0, 100)}...</p>
            </div>
        `
    })
}

// Analyse anzeigen wenn angeklickt
async function showAnalysis(analysisId) {
    const response = await fetch(`/users/${userId}/portfolio/analyses`)
    const data = await response.json()
    const analysis = data.find(a => a.id === analysisId)

    const result = document.getElementById('analyse-result')
    result.innerHTML = `
        <div class="analyse-card">
            <h3>Gesamtwert: ${analysis.total_value.toLocaleString('de-DE', {minimumFractionDigits: 2})} €</h3>
            <p>${analysis.summary}</p>
            <h4>Risikobewertung:</h4>
            <p>${analysis.risk_assessment}</p>
            <h4>Empfehlungen:</h4>
            <ul>${JSON.parse(analysis.recommendations.replace(/'/g, '"')).map(r => `<li>${r}</li>`).join('')}</ul>
            <p><small>${analysis.created_at}</small></p>
        </div>
    `

    // Nach oben scrollen
    window.scrollTo(0, 0)
}

// Beim Laden aufrufen
loadPreviousAnalyses()