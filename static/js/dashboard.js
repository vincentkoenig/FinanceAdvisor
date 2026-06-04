// User ID aus localStorage holen
const userId = localStorage.getItem('user_id')

async function loadPortfolio() {
    // GET Request an /users/<user_id>/assets schicken
    const response = await fetch(`/users/${userId}/assets`, {
        method: 'GET',
    })

    // Daten holen
    const data = await response.json()

    // Tabellen Body holen
    const tableBody = document.getElementById('portfolio-body')

    // Für jeden Asset eine Zeile erstellen
    data.forEach(asset => {
        const kaufpreisGesamt = asset.avg_buy_price * asset.quantity
        const positionGesamt = asset.current_price * asset.quantity
        const plEur = positionGesamt - kaufpreisGesamt
        const plProzent = (plEur / kaufpreisGesamt * 100).toFixed(2)
        const rowPlColor = plEur >= 0 ? '#2ea043' : '#f85149'

        tableBody.innerHTML += `
            <tr>
                <td><strong>${asset.name}</strong><br><small>${asset.symbol} x${asset.quantity}</small></td>
                <td>${kaufpreisGesamt.toFixed(2)} $<br><small>${asset.avg_buy_price.toFixed(2)} $</small></td>
                <td>${positionGesamt.toFixed(2)} $<br><small>${asset.current_price.toFixed(2)} $</small></td>
                <td style="color: ${rowPlColor}">${plEur.toFixed(2)} $<br><small>${plProzent}%</small></td>
            </tr>
        `
    })

    // Gesamtwert berechnen
    let totalValue = 0
    let totalKaufpreis = 0

    data.forEach(asset => {
        totalValue += asset.current_price * asset.quantity
        totalKaufpreis += asset.avg_buy_price * asset.quantity
    })

    const totalPL = totalValue - totalKaufpreis
    const totalPLProzent = (totalPL / totalKaufpreis * 100).toFixed(2)
    const plColor = totalPL >= 0 ? '#2ea043' : '#f85149'

    // Gesamtwert anzeigen
    document.getElementById('total-value').innerHTML = `${totalValue.toFixed(2)} $`
    document.getElementById('total-pl').innerHTML = `<span style="color: ${plColor}">${totalPL.toFixed(2)} $ (${totalPLProzent}%)</span>`

    // Donut Diagramm erstellen
    const labels = data.map(asset => asset.name)
    const values = data.map(asset => asset.current_price * asset.quantity)

    new Chart(document.getElementById('donutChart'), {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: ['#58a6ff', '#2ea043', '#f85149', '#d29922', '#8b949e']
            }]
        },
        options: {
            plugins: {
                legend: {
                    labels: {
                        color: '#e6edf3'
                    }
                }
            }
        }
    })
}

// Funktion aufrufen wenn Seite geladen wird
loadPortfolio()