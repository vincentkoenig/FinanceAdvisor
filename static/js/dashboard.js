// Globale Variablen für den aktuellen Portfolio Wert
let currentTotalValue = 0
let currentTotalPL = 0
let currentTotalPLProzent = 0
let currentPlColor = '#2ea043'
// Aktueller Zeitraum
let currentPeriod = '1J'
let chartInstance = null

// Globale Variable für Asset Daten - wird für Sortierung benötigt
let portfolioData = []
let sortDirection = 1  // 1 = aufsteigend, -1 = absteigend

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
    // Spinner anzeigen während Daten geladen werden
    document.getElementById('portfolio-body').innerHTML = `
        <tr><td colspan="4" style="text-align:center; padding: 30px;"><span class="spinner"></span></td></tr>
    `

    // GET Request an /users/<user_id>/assets schicken
    const response = await fetch(`/users/${userId}/assets`, {
        method: 'GET',
    })

    // Daten holen
    const data = await response.json()

    // Daten global speichern für Sortierung
    portfolioData = data

    // Tabelle rendern
    renderTable(portfolioData)

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


function renderTable(assets) {
    const tableBody = document.getElementById('portfolio-body')
    tableBody.innerHTML = ''

    let totalKaufpreisGesamt = 0
    let totalPositionGesamt = 0
    let totalPLGesamt = 0

    assets.forEach(asset => {
        const kaufpreisGesamt = asset.avg_buy_price * asset.quantity
        const positionGesamt = asset.current_price * asset.quantity
        const plEur = positionGesamt - kaufpreisGesamt
        const plProzent = (plEur / kaufpreisGesamt * 100).toFixed(2)
        const rowPlColor = plEur >= 0 ? '#2ea043' : '#f85149'

        totalKaufpreisGesamt += kaufpreisGesamt
        totalPositionGesamt += positionGesamt
        totalPLGesamt += plEur

        tableBody.innerHTML += `
            <tr onclick="showAssetDetail(${asset.asset_id}, '${asset.name}')" style="cursor: pointer;">
                <td><strong>${asset.name}</strong><br><small>${asset.quantity}x</small></td>
                <td>${formatCurrency(kaufpreisGesamt)} €<br><small>${formatCurrency(asset.avg_buy_price)} €</small></td>
                <td>${formatCurrency(positionGesamt)} €<br><small>${formatCurrency(asset.current_price)} €</small></td>
                <td style="color: ${rowPlColor}">${formatCurrency(plEur)} €<br><small>${plProzent}%</small></td>
            </tr>
        `
    })

    // Gesamtsummen anzeigen
    const totalPLColor = totalPLGesamt >= 0 ? '#2ea043' : '#f85149'
    document.getElementById('total-kaufpreis').innerHTML = `<strong>${formatCurrency(totalKaufpreisGesamt)} €</strong>`
    document.getElementById('total-position').innerHTML = `<strong>${formatCurrency(totalPositionGesamt)} €</strong>`
    document.getElementById('total-pl-table').innerHTML = `<strong style="color: ${totalPLColor}">${formatCurrency(totalPLGesamt)} €</strong>`
}


function sortTable(column) {
    portfolioData.sort((a, b) => {
        let valueA, valueB

        if (column === 'name') {
            valueA = a.name
            valueB = b.name
            return sortDirection * valueA.localeCompare(valueB)
        } else if (column === 'kaufpreis') {
            valueA = a.avg_buy_price * a.quantity
            valueB = b.avg_buy_price * b.quantity
        } else if (column === 'position') {
            valueA = a.current_price * a.quantity
            valueB = b.current_price * b.quantity
        } else if (column === 'pl') {
            valueA = (a.current_price - a.avg_buy_price) * a.quantity
            valueB = (b.current_price - b.avg_buy_price) * b.quantity
        }

        return sortDirection * (valueA - valueB)
    })

    // Richtung umkehren für nächsten Klick
    sortDirection *= -1
    renderTable(portfolioData)
}


async function loadChart(period = '1J') {
    // Portfolio Historie holen
    const response = await fetch(`/users/${userId}/portfolio/history`)
    const data = await response.json()

    // Alle Daten zusammenführen
    const allDates = new Set()
    Object.values(data).forEach(prices => {
        prices.forEach(p => allDates.add(p.date))
    })
    const sortedDates = [...allDates].sort()

    // Datum filtern je nach Zeitraum
    const today = new Date()
    const filteredByPeriod = sortedDates.filter(date => {
        const d = new Date(date)
        if (period === '1T') {
            const yesterday = new Date(today)
            yesterday.setDate(today.getDate() - 1)
            return d >= yesterday
        } else if (period === '1W') {
            const oneWeekAgo = new Date(today)
            oneWeekAgo.setDate(today.getDate() - 7)
            return d >= oneWeekAgo
        } else if (period === '1M') {
            const oneMonthAgo = new Date(today)
            oneMonthAgo.setMonth(today.getMonth() - 1)
            return d >= oneMonthAgo
        } else if (period === 'YTD') {
            const startOfYear = new Date(today.getFullYear(), 0, 1)
            return d >= startOfYear
        } else if (period === '1J') {
            const oneYearAgo = new Date(today)
            oneYearAgo.setFullYear(today.getFullYear() - 1)
            return d >= oneYearAgo
        } else if (period === 'Max') {
            return true  // alle Daten anzeigen
        }
        return true
    })

    // Gesamtwert pro Tag berechnen
    const chartData = []
    filteredByPeriod.forEach(date => {
        let total = 0
        let allAssetsHavePrice = true

        Object.values(data).forEach(prices => {
            const price = prices.find(p => p.date === date)
            if (!price) allAssetsHavePrice = false
            else total += price.price
        })

        if (allAssetsHavePrice) {
            chartData.push({ date: date, value: total })
        }
    })

    const filteredDates = chartData.map(d => d.date)
    const totalValues = chartData.map(d => d.value)

    // Farbe basierend auf Performance
    const firstValue = totalValues[0]
    const lastValue = totalValues[totalValues.length - 1]
    const chartColor = lastValue >= firstValue ? '#2ea043' : '#f85149'

    // Alten Chart zerstören falls vorhanden
    if (chartInstance) {
        chartInstance.destroy()
    }

    // Liniendiagramm erstellen
    chartInstance = new Chart(document.getElementById('lineChart'), {
        type: 'line',
        data: {
            labels: filteredDates,
            datasets: [{
                data: totalValues,
                borderColor: chartColor,
                backgroundColor: 'transparent',
                fill: false,
                tension: 0.1,
                pointRadius: 0,
                pointHoverRadius: 5,
                pointHoverBackgroundColor: chartColor
            }]
        },
        options: {
            plugins: {
                legend: { display: false },
                tooltip: { enabled: false }
            },
            hover: {
                mode: 'index',
                intersect: false
            },
            onHover: (event, elements) => {
                if (elements.length > 0 && valuesVisible) {
                    const index = elements[0].index
                    const date = filteredDates[index]
                    const value = totalValues[index]

                    document.getElementById('total-value').innerHTML = `${formatCurrency(value)} €`
                    document.getElementById('total-pl').innerHTML = `<span style="color: #8b949e">${formatDate(date)}</span>`
                }
            },
            scales: {
                x: { display: false },
                y: { display: false }
            }
        }
    })

    // Wenn Maus den Chart verlässt
    document.getElementById('lineChart').addEventListener('mouseleave', () => {
        if (valuesVisible) {
            document.getElementById('total-value').innerHTML = `${formatCurrency(currentTotalValue)} €`
            document.getElementById('total-pl').innerHTML = `<span style="color: ${currentPlColor}">${formatCurrency(currentTotalPL)} € (${currentTotalPLProzent}%)</span>`
        }
    })
}

// Beim Laden aufrufen
loadChart('1J')


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

    // Menge und Kaufpreis müssen gültige, positive Zahlen sein
    if (quantity === '' || isNaN(quantity) || parseFloat(quantity) <= 0) {
        showToast('Bitte eine gültige Menge größer 0 angeben!', 'error')
        return
    }
    if (avgBuyPrice === '' || isNaN(avgBuyPrice) || parseFloat(avgBuyPrice) <= 0) {
        showToast('Bitte einen gültigen Kaufpreis größer 0 angeben!', 'error')
        return
    }

    // Datum holen - wenn leer heutiges Datum nehmen
    const today = new Date().toISOString().split('T')[0]
    const boughtAt = document.getElementById('position-date').value || today

    // Schritt 1: Asset suchen oder automatisch erstellen
    const searchResponse = await fetch(`/assets/search?query=${symbol}`)
    const asset = await searchResponse.json()

    if (!searchResponse.ok) {
        showToast('Asset nicht gefunden!', 'error')
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
        showToast('Position hinzugefügt!')
        // Modal schließen
        hideAddPosition()
        // Dashboard neu laden
        loadPortfolio()
    } else {
        showToast(data.error)
    }
}


// Aktuell ausgewähltes Asset
let selectedAssetId = null

// Asset Detail Modal anzeigen
function showAssetDetail(assetId, assetName) {
    selectedAssetId = assetId
    document.getElementById('modal-asset-name').innerHTML = assetName
    document.getElementById('buy-fields').style.display = 'none'
    document.getElementById('sell-fields').style.display = 'none'
    document.getElementById('asset-detail-modal').style.display = 'block'
}

// Asset Detail Modal verstecken
function hideAssetDetail() {
    document.getElementById('asset-detail-modal').style.display = 'none'
}

// Kauf Felder anzeigen
function showBuy() {
    document.getElementById('buy-fields').style.display = 'block'
    document.getElementById('sell-fields').style.display = 'none'
}

// Verkauf Felder anzeigen
function showSell() {
    document.getElementById('sell-fields').style.display = 'block'
    document.getElementById('buy-fields').style.display = 'none'
}


async function addBuy() {
    const userId = localStorage.getItem('user_id')
    const quantity = document.getElementById('buy-quantity').value
    const price = document.getElementById('buy-price').value

    const response = await fetch(`/users/${userId}/assets/${selectedAssetId}/buy`, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({quantity: quantity, price: price})
    })

    const data = await response.json()

    if (response.ok) {
        showToast('Kauf hinzugefügt!')
        hideAssetDetail()
        loadPortfolio()
    } else {
        showToast(data.error)
    }
}


async function addSell() {
    const userId = localStorage.getItem('user_id')
    const quantity = document.getElementById('sell-quantity').value

    const response = await fetch(`/users/${userId}/assets/${selectedAssetId}/sell`, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({quantity: quantity})
    })

    const data = await response.json()

    if (response.ok) {
        showToast('Verkauf hinzugefügt!')
        hideAssetDetail()
        loadPortfolio()
    } else {
        showToast(data.error)
    }
}


// Sichtbarkeit der Zahlen umschalten
let valuesVisible = true

function toggleVisibility() {
    valuesVisible = !valuesVisible

    if (valuesVisible) {
        // Zahlen anzeigen
        document.getElementById('total-value').innerHTML = `${formatCurrency(currentTotalValue)} €`
        document.getElementById('total-pl').innerHTML = `<span style="color: ${currentPlColor}">${formatCurrency(currentTotalPL)} € (${currentTotalPLProzent}%)</span>`
        document.getElementById('donut-value').innerHTML = `${formatCurrency(currentTotalValue)} €`
        document.getElementById('eye-icon').className = 'fa-solid fa-eye'
        renderTable(portfolioData)
    } else {
        // Zahlen verstecken
        document.getElementById('total-value').innerHTML = '****** €'
        document.getElementById('total-pl').innerHTML = '<span>****** €</span>'
        document.getElementById('donut-value').innerHTML = '****** €'
        document.getElementById('eye-icon').className = 'fa-solid fa-eye-slash'
        const rows = document.querySelectorAll('#portfolio-body tr')
        rows.forEach(row => {
            const cells = row.querySelectorAll('td')
            cells[1].innerHTML = '****** €'
            cells[2].innerHTML = '****** €'
            cells[3].innerHTML = '****** €'
        })

        // Gesamtwerte verstecken
        document.getElementById('total-kaufpreis').innerHTML = '****** €'
        document.getElementById('total-position').innerHTML = '****** €'
        document.getElementById('total-pl-table').innerHTML = '****** €'
    }
}


function changeChartPeriod(period) {
    currentPeriod = period

    // Aktiven Button aktualisieren
    document.querySelectorAll('.period-btn').forEach(btn => {
        btn.classList.remove('active')
    })
    document.getElementById(`btn-${period}`).classList.add('active')

    // Chart neu laden
    loadChart(period)
}
