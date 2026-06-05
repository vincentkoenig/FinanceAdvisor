// Globale Variablen für den aktuellen Portfolio Wert
let currentTotalValue = 0
let currentTotalPL = 0
let currentTotalPLProzent = 0
let currentPlColor = '#2ea043'

// User ID aus localStorage holen
const userId = localStorage.getItem('user_id')

// Zahl im deutschen Format formatieren z.B. 30.502,50
function formatCurrency(value) {
    return value.toLocaleString('de-DE', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    })
}

// Datum im deutschen Format formatieren z.B. 05.06.2026
function formatDate(dateString) {
    const [year, month, day] = dateString.split('-')
    return `${day}.${month}.${year}`
}

async function loadPortfolio() {
    // Tabelle leeren bevor neu geladen wird
    document.getElementById('portfolio-body').innerHTML = ''

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
        const kaufpreisGesamt = asset.avg_buy_price * asset.quantity      // Gesamtkaufpreis
        const positionGesamt = asset.current_price * asset.quantity        // Aktueller Gesamtwert
        const plEur = positionGesamt - kaufpreisGesamt                     // Gewinn/Verlust in EUR
        const plProzent = (plEur / kaufpreisGesamt * 100).toFixed(2)      // Gewinn/Verlust in %
        const rowPlColor = plEur >= 0 ? '#2ea043' : '#f85149'             // Grün wenn positiv, rot wenn negativ

        tableBody.innerHTML += `
            <tr>
                <td><strong>${asset.name}</strong><br><small>${asset.quantity}x</small></td>
                <td>${formatCurrency(kaufpreisGesamt)} €<br><small>${formatCurrency(asset.avg_buy_price)} €</small></td>
                <td>${formatCurrency(positionGesamt)} €<br><small>${formatCurrency(asset.current_price)} €</small></td>
                <td style="color: ${rowPlColor}">${formatCurrency(plEur)} €<br><small>${plProzent}%</small></td>
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

    // Globale Variablen setzen damit mouseleave sie benutzen kann
    currentTotalValue = totalValue
    currentTotalPL = totalPL
    currentTotalPLProzent = totalPLProzent
    currentPlColor = plColor

    // Gesamtwert anzeigen
    document.getElementById('total-value').innerHTML = `${formatCurrency(totalValue)} €`
    document.getElementById('total-pl').innerHTML = `<span style="color: ${plColor}">${formatCurrency(totalPL)} € (${totalPLProzent}%)</span>`

    // Donut Mitte aktualisieren
    document.getElementById('donut-value').innerHTML = `${formatCurrency(totalValue)} €`

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
            cutout: '75%',
            plugins: {
                legend: { display: false }
            }
        }
    })
}

// Funktion aufrufen wenn Seite geladen wird
loadPortfolio()


async function loadChart() {
    // Portfolio Historie holen
    const response = await fetch(`/users/${userId}/portfolio/history`)
    const data = await response.json()

    // Alle Daten zusammenführen für den Gesamtwert
    const allDates = new Set()
    Object.values(data).forEach(prices => {
        prices.forEach(p => allDates.add(p.date))
    })
    const sortedDates = [...allDates].sort()

    // Gesamtwert pro Tag berechnen
    const totalValues = sortedDates.map(date => {
        let total = 0
        Object.values(data).forEach(prices => {
            const price = prices.find(p => p.date === date)
            if (price) total += price.price
        })
        return total
    })

    // Farbe basierend auf Performance - grün wenn gestiegen, rot wenn gefallen
    const firstValue = totalValues[0]
    const lastValue = totalValues[totalValues.length - 1]
    const chartColor = lastValue >= firstValue ? '#2ea043' : '#f85149'

    // Liniendiagramm erstellen
    new Chart(document.getElementById('lineChart'), {
        type: 'line',
        data: {
            labels: sortedDates,
            datasets: [{
                data: totalValues,
                borderColor: chartColor,
                backgroundColor: 'transparent',
                fill: false,
                tension: 0.1,
                pointRadius: 0,                          // kein Punkt standardmäßig
                pointHoverRadius: 5,                     // Punkt beim Hover
                pointHoverBackgroundColor: chartColor    // Punkt in Chart Farbe
            }]
        },
        options: {
            plugins: {
                legend: { display: false },
                tooltip: { enabled: false }              // kein Tooltip
            },
            hover: {
                mode: 'index',
                intersect: false
            },
            onHover: (event, elements) => {
                if (elements.length > 0) {
                    const index = elements[0].index
                    const date = sortedDates[index]
                    const value = totalValues[index]

                    // Gesamtwert und Datum links oben aktualisieren
                    document.getElementById('total-value').innerHTML = `${formatCurrency(value)} €`
                    document.getElementById('total-pl').innerHTML = `<span style="color: #8b949e">${formatDate(date)}</span>`
                }
            },
            scales: {
                x: { display: false },  // keine X Achse
                y: { display: false }   // keine Y Achse
            }
        }
    })

    // Wenn Maus den Chart verlässt - zurück zum aktuellen Wert
    document.getElementById('lineChart').addEventListener('mouseleave', () => {
        document.getElementById('total-value').innerHTML = `${formatCurrency(currentTotalValue)} €`
        document.getElementById('total-pl').innerHTML = `<span style="color: ${currentPlColor}">${formatCurrency(currentTotalPL)} € (${currentTotalPLProzent}%)</span>`
    })
}

// Beim Laden aufrufen
loadChart()


// Modal anzeigen
function showAddPosition() {
    document.getElementById('add-position-modal').style.display = 'block'
}

// Modal verstecken
function hideAddPosition() {
    document.getElementById('add-position-modal').style.display = 'none'
}


async function addPosition() {
    const userId = localStorage.getItem('user_id')

    // Werte aus dem Modal holen
    const symbol = document.getElementById('position-symbol').value
    const quantity = document.getElementById('position-quantity').value
    const avgBuyPrice = document.getElementById('position-price').value

    // Datum holen - wenn leer heutiges Datum nehmen
    const today = new Date().toISOString().split('T')[0]
    const boughtAt = document.getElementById('position-date').value || today

    // Schritt 1: Asset suchen oder automatisch erstellen
    const searchResponse = await fetch(`/assets/search?query=${symbol}`)
    const asset = await searchResponse.json()

    if (!searchResponse.ok) {
        alert('Asset nicht gefunden!')
        return
    }

    // Schritt 2: Asset dem Nutzer hinzufügen
    const response = await fetch(`/users/${userId}/assets`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            asset_id: asset.id,
            quantity: quantity,
            avg_buy_price: avgBuyPrice,
            bought_at: boughtAt,
            status: 'owned'
        })
    })

    const data = await response.json()

    if (response.ok) {
        alert('Position hinzugefügt!')
        // Modal schließen
        hideAddPosition()
        // Dashboard neu laden
        loadPortfolio()
    } else {
        alert(data.error)
    }
}