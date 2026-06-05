// User ID aus localStorage holen
const userId = localStorage.getItem('user_id')

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
                <td><strong>${asset.name}</strong><br><small>${asset.symbol} x${asset.quantity}</small></td>
                <td>${kaufpreisGesamt.toFixed(2)} €<br><small>${asset.avg_buy_price.toFixed(2)} €</small></td>
                <td>${positionGesamt.toFixed(2)} €<br><small>${asset.current_price.toFixed(2)} €</small></td>
                <td style="color: ${rowPlColor}">${plEur.toFixed(2)} €<br><small>${plProzent}%</small></td>
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
    document.getElementById('total-value').innerHTML = `${totalValue.toFixed(2)} €`
    document.getElementById('total-pl').innerHTML = `<span style="color: ${plColor}">${totalPL.toFixed(2)} € (${totalPLProzent}%)</span>`

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
                        color: '#e6edf3'  // Weiße Schrift für Dark Mode
                    }
                }
            }
        }
    })
}

// Funktion aufrufen wenn Seite geladen wird
loadPortfolio()


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