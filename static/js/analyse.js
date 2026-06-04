async function analysePortfolio() {
    // Werte aus den Input Feldern holen
    const userId = localStorage.getItem('user_id')

    // POST Request an /chat schicken - wie Postman aber in JavaScript
    const response = await fetch('/portfolio/analyze', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'}, // sagt Flask: ich schicke JSON
        body: JSON.stringify({user_id: userId,})      // message als JSON
    });

    // Auf die JSON Antwort warten und in data speichern
    const data = await response.json();

    // Ergebnis anzeigen
    const result = document.getElementById('analyse-result')
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