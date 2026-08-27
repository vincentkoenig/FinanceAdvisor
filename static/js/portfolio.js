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

// Globale Variablen für die Watchlist (Tab-Umschalter auf Portfolio-Seite)
let watchlistData = []
let watchlistSortDirection = 1
let selectedWatchlistAssetId = null
let assetTransactionsData = []
let assetIdsWithSavingsPlan = []

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

    // Aktive Sparpläne abrufen, um in der Tabelle ein Badge bei
    // betroffenen Assets anzuzeigen
    const savingsPlansResponse = await fetch(`/users/${userId}/savings-plans`)
    const savingsPlans = await savingsPlansResponse.json()
    assetIdsWithSavingsPlan = savingsPlans.map(plan => plan.asset_id)

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

    currentTotalValue = totalValue
    currentTotalPL = totalPL
    currentTotalPLProzent = totalPLProzent
    currentPlColor = plColor

    document.getElementById('total-value').innerHTML = `${formatCurrency(totalValue)} €`
    document.getElementById('total-pl').innerHTML = `<span style="color: ${plColor}">${formatCurrency(totalPL)} € (${totalPLProzent}%)</span>`
    document.getElementById('donut-value').innerHTML = `${formatCurrency(totalValue)} €`

    const labels = data.map(asset => asset.name)
    const values = data.map(asset => asset.current_price * asset.quantity)

    new Chart(document.getElementById('donutChart'), {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: generateColors(values.length)
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

        // Sparplan-Badge anzeigen, falls für dieses Asset ein aktiver Sparplan existiert
        const savingsPlanBadge = assetIdsWithSavingsPlan.includes(asset.asset_id)
            ? '<i class="fa-solid fa-rotate" title="Sparplan aktiv" style="margin-left: 6px; color: var(--text-secondary); font-size: 12px;"></i>'
            : ''

        tableBody.innerHTML += `
            <tr onclick="showAssetDetail(${asset.asset_id}, '${asset.name}')" style="cursor: pointer;">
                <td data-label="Titel"><strong>${asset.name}</strong>${savingsPlanBadge}<br><small>${asset.quantity}x</small></td>
                <td data-label="Kaufpreis">${formatCurrency(kaufpreisGesamt)} €<br><small>${formatCurrency(asset.avg_buy_price)} €</small></td>
                <td data-label="Position">${formatCurrency(positionGesamt)} €<br><small>${formatCurrency(asset.current_price)} €</small></td>
                <td data-label="P/L" style="color: ${rowPlColor}">${formatCurrency(plEur)} €<br><small>${plProzent}%</small></td>
            </tr>
        `
    })

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

    // Gesamtwert pro Tag berechnen - pro Asset wird der letzte bekannte
    // Preis bis zu diesem Datum verwendet (Forward-Fill), damit
    // Wochenenden/Feiertage bei Aktien nicht zu Sprüngen führen und
    // neu hinzugefügte Assets erst ab ihrem ersten Datenpunkt mitzählen
    const chartData = []
    filteredByPeriod.forEach(date => {
        let total = 0
        let hasAnyPrice = false

        Object.values(data).forEach(prices => {
            // Letzten Preis suchen, dessen Datum <= aktuelles Datum ist
            let lastKnown = null
            for (const p of prices) {
                if (p.date <= date) {
                    lastKnown = p
                } else {
                    break
                }
            }

            if (lastKnown) {
                total += lastKnown.price
                hasAnyPrice = true
            }
        })

        if (hasAnyPrice) {
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

    // Kaufdatum darf nicht in der Zukunft liegen
    if (boughtAt > today) {
        showToast('Das Kaufdatum darf nicht in der Zukunft liegen!', 'error')
        return
    }

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

    // Menge und Preis müssen gültige, positive Zahlen sein
    if (quantity === '' || isNaN(quantity) || parseFloat(quantity) <= 0) {
        showToast('Bitte eine gültige Menge größer 0 angeben!', 'error')
        return
    }
    if (price === '' || isNaN(price) || parseFloat(price) <= 0) {
        showToast('Bitte einen gültigen Preis größer 0 angeben!', 'error')
        return
    }

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
    const price = document.getElementById('sell-price').value

    // Menge muss eine gültige, positive Zahl sein
    if (quantity === '' || isNaN(quantity) || parseFloat(quantity) <= 0) {
        showToast('Bitte eine gültige Menge größer 0 angeben!', 'error')
        return
    }

    // Verkaufspreis muss eine gültige, positive Zahl sein
    if (price === '' || isNaN(price) || parseFloat(price) <= 0) {
        showToast('Bitte einen gültigen Verkaufspreis größer 0 angeben!', 'error')
        return
    }

    // Prüfen ob nicht mehr verkauft wird als aktuell gehalten wird
    const asset = portfolioData.find(a => a.asset_id === selectedAssetId)
    if (asset && parseFloat(quantity) > asset.quantity) {
        showToast(`Du besitzt nur ${asset.quantity} Stück!`, 'error')
        return
    }

    const response = await fetch(`/users/${userId}/assets/${selectedAssetId}/sell`, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({quantity: quantity, price: price})
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


// Wechselt zwischen Positionen-, Watchlist-, Transaktionen- und Sparplan-Tab
function switchTab(tab) {
    const tabs = {
        positions: { button: 'tab-positions', panel: 'positions-panel' },
        watchlist: { button: 'tab-watchlist', panel: 'watchlist-panel' },
        transactions: { button: 'tab-transactions', panel: 'transactions-panel' },
        'savings-plans': { button: 'tab-savings-plans', panel: 'savings-plans-panel' }
    }

    for (const key in tabs) {
        document.getElementById(tabs[key].button).classList.remove('active')
        document.getElementById(tabs[key].panel).style.display = 'none'
    }

    document.getElementById(tabs[tab].button).classList.add('active')
    document.getElementById(tabs[tab].panel).style.display = 'block'

    if (tab === 'watchlist' && watchlistData.length === 0) {
        loadWatchlist()
    }
    if (tab === 'transactions' && assetTransactionsData.length === 0) {
        loadAssetTransactions()
    }
    if (tab === 'savings-plans') {
        loadSavingsPlans()
    }
}


async function addToWatchlist() {
    const query = document.getElementById('asset-search').value

    const searchResponse = await fetch(`/assets/search?query=${query}`)
    const asset = await searchResponse.json()

    if (!searchResponse.ok) {
        showToast('Asset nicht gefunden!')
        return
    }

    const response = await fetch(`/users/${userId}/watchlist`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({asset_id: asset.id})
    })

    const data = await response.json()

    if (response.ok) {
        showToast('Asset hinzugefügt!')
        document.getElementById('asset-search').value = ''
        loadWatchlist()
    } else {
        showToast(data.error, 'error')
    }
}


function renderWatchlist(data) {
    const tableBody = document.getElementById('watchlist-body')
    tableBody.innerHTML = ''

    for (const item of data) {
        const change = item.current_price - item.price_added
        const changePercent = ((change / item.price_added) * 100).toFixed(2)
        const changeColor = change >= 0 ? '#2ea043' : '#f85149'
        const changeSign = change >= 0 ? '+' : ''

        tableBody.innerHTML += `
            <tr onclick="showWatchlistDetail(${item.asset_id}, '${item.name}')" style="cursor: pointer;">
                <td data-label="Titel"><strong>${item.name}</strong></td>
                <td data-label="Symbol">${item.symbol}</td>
                <td data-label="Aktueller Preis">${item.current_price} €</td>
                <td data-label="Preis beim Hinzufügen">${item.price_added ? item.price_added + ' €' : '-'}</td>
                <td data-label="Veränderung" style="color: ${changeColor}">
                    ${changeSign}${change.toFixed(2)} €<br>
                    <small>${changeSign}${changePercent}%</small>
                </td>
                <td data-label="Hinzugefügt am">${item.added_at}</td>
            </tr>
        `
    }
}


async function loadWatchlist() {
    const response = await fetch(`/users/${userId}/watchlist`)
    const data = await response.json()

    watchlistData = []

    for (const item of data) {
        const assetResponse = await fetch(`/assets/${item.asset_id}`)
        const asset = await assetResponse.json()

        watchlistData.push({
            asset_id: item.asset_id,
            name: asset.name,
            symbol: asset.symbol,
            current_price: asset.current_price,
            price_added: item.price_added,
            added_at: item.added_at
        })
    }

    renderWatchlist(watchlistData)
}


function sortWatchlist(column) {
    watchlistData.sort((a, b) => {
        let valueA, valueB

        if (column === 'name') {
            valueA = a.name
            valueB = b.name
            return watchlistSortDirection * valueA.localeCompare(valueB)
        } else if (column === 'symbol') {
            valueA = a.symbol
            valueB = b.symbol
            return watchlistSortDirection * valueA.localeCompare(valueB)
        }
    })

    watchlistSortDirection *= -1
    renderWatchlist(watchlistData)
}


function showWatchlistDetail(assetId, assetName) {
    selectedWatchlistAssetId = assetId
    document.getElementById('watchlist-modal-asset-name').innerHTML = assetName
    document.getElementById('watchlist-detail-modal').style.display = 'block'
}

function hideWatchlistDetail() {
    document.getElementById('watchlist-detail-modal').style.display = 'none'
}

async function removeFromWatchlistModal() {
    await removeFromWatchlist(selectedWatchlistAssetId)
    hideWatchlistDetail()
}

function showWatchlistBuy() {
    document.getElementById('watchlist-buy-fields').style.display = 'block'
}

async function buyFromWatchlist() {
    const quantity = document.getElementById('watchlist-buy-quantity').value
    const price = document.getElementById('watchlist-buy-price').value
    const today = new Date().toISOString().split('T')[0]

    if (quantity === '' || isNaN(quantity) || parseFloat(quantity) <= 0) {
        showToast('Bitte eine gültige Menge größer 0 angeben!', 'error')
        return
    }
    if (price === '' || isNaN(price) || parseFloat(price) <= 0) {
        showToast('Bitte einen gültigen Preis größer 0 angeben!', 'error')
        return
    }

    const response = await fetch(`/users/${userId}/assets`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            asset_id: selectedWatchlistAssetId,
            quantity: quantity,
            avg_buy_price: price,
            bought_at: today,
            status: 'owned'
        })
    })

    if (response.ok) {
        await removeFromWatchlist(selectedWatchlistAssetId)
        hideWatchlistDetail()
        showToast('Asset gekauft und zur Watchlist entfernt!')
        // Portfolio-Tab aktualisieren, da eine neue Position hinzugekommen ist
        loadPortfolio()
    } else {
        showToast('Fehler beim Kaufen!', 'error')
    }
}


async function removeFromWatchlist(assetId) {
    const response = await fetch(`/users/${userId}/watchlist/${assetId}`, {
        method: 'DELETE',
        headers: {'Content-Type': 'application/json'}
    })

    const data = await response.json()

    if (response.ok) {
        showToast('Asset entfernt!')
        loadWatchlist()
    } else {
        showToast(data.error)
    }
}


async function loadAssetTransactions() {
    const response = await fetch(`/users/${userId}/assets/transactions`)
    const data = await response.json()

    assetTransactionsData = data
    renderAssetTransactions(data)
}


function renderAssetTransactions(transactions) {
    const tableBody = document.getElementById('transactions-body')

    if (transactions.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="6" style="text-align:center; color: var(--text-secondary);">Keine Transaktionen vorhanden</td></tr>'
        return
    }

    tableBody.innerHTML = transactions.map(t => {
        const isBuy = t.type === 'buy'
        const typeLabel = isBuy ? 'Kauf' : 'Verkauf'
        const typeColor = isBuy ? '#2ea043' : '#f85149'

        return `
            <tr>
                <td data-label="Datum">${formatDate(t.date)}</td>
                <td data-label="Titel"><strong>${t.asset_name}</strong></td>
                <td data-label="Typ" style="color: ${typeColor}">${typeLabel}</td>
                <td data-label="Menge">${t.quantity}</td>
                <td data-label="Preis">${formatCurrency(t.price)} €</td>
                <td data-label="Gesamt">${formatCurrency(t.total)} €</td>
            </tr>
        `
    }).join('')
}


async function loadSavingsPlans() {
    const response = await fetch(`/users/${userId}/savings-plans`)
    const data = await response.json()
    renderSavingsPlans(data)
}


function renderSavingsPlans(plans) {
    const tableBody = document.getElementById('savings-plans-body')

    if (plans.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="5" style="text-align:center; color: var(--text-secondary);">Keine Sparpläne vorhanden</td></tr>'
        return
    }

    tableBody.innerHTML = plans.map(plan => {
        const dueLabel = plan.is_due
            ? `<span style="color: #2ea043;">Fällig!</span>`
            : `Am ${plan.day_of_month}.`

        const executeButton = plan.is_due
            ? `<button class="btn-primary" style="width: auto; padding: 6px 14px; font-size: 13px;" onclick="executeSavingsPlan(${plan.id})">Jetzt ausführen</button>`
            : ''

        return `
            <tr>
                <td data-label="Titel"><strong>${plan.asset_name}</strong></td>
                <td data-label="Betrag">${formatCurrency(plan.amount)} €</td>
                <td data-label="Fällig am">${dueLabel}</td>
                <td data-label="Zuletzt ausgeführt">${plan.last_executed ? formatDate(plan.last_executed) : '-'}</td>
                <td data-label="">
                    ${executeButton}
                    <button class="btn-secondary" style="width: auto; padding: 6px 12px; font-size: 13px; margin-left: 6px;" onclick="deleteSavingsPlan(${plan.id})">
                        <i class="fa-solid fa-trash"></i>
                    </button>
                </td>
            </tr>
        `
    }).join('')
}


function showAddSavingsPlan() {
    document.getElementById('add-savings-plan-modal').style.display = 'block'
}

function hideAddSavingsPlan() {
    document.getElementById('add-savings-plan-modal').style.display = 'none'
}


async function addSavingsPlan() {
    const symbol = document.getElementById('savings-plan-symbol').value
    const amount = document.getElementById('savings-plan-amount').value
    const day = document.getElementById('savings-plan-day').value

    if (amount === '' || isNaN(amount) || parseFloat(amount) <= 0) {
        showToast('Bitte einen gültigen Betrag größer 0 angeben!', 'error')
        return
    }
    if (day === '' || isNaN(day) || parseInt(day) < 1 || parseInt(day) > 28) {
        showToast('Bitte einen Tag zwischen 1 und 28 angeben!', 'error')
        return
    }

    // Asset suchen oder automatisch erstellen, gleiche Logik wie bei addPosition
    const searchResponse = await fetch(`/assets/search?query=${symbol}`)
    const asset = await searchResponse.json()

    if (!searchResponse.ok) {
        showToast('Asset nicht gefunden!', 'error')
        return
    }

    const response = await fetch(`/users/${userId}/savings-plans`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            asset_id: asset.id,
            amount: amount,
            day_of_month: parseInt(day)
        })
    })

    if (response.ok) {
        showToast('Sparplan angelegt!')
        hideAddSavingsPlan()
        loadSavingsPlans()
    } else {
        showToast('Fehler beim Anlegen des Sparplans!', 'error')
    }
}


async function executeSavingsPlan(planId) {
    const response = await fetch(`/savings-plans/${planId}/execute`, {
        method: 'POST'
    })

    const data = await response.json()

    if (response.ok) {
        showToast(`Sparplan ausgeführt: ${data.quantity} Stück zu ${data.price} €`)
        loadSavingsPlans()
        loadPortfolio()  // Positionstabelle aktualisieren, da sich die Menge geändert hat
    } else {
        showToast(data.error || 'Fehler beim Ausführen!', 'error')
    }
}


async function deleteSavingsPlan(planId) {
    const response = await fetch(`/savings-plans/${planId}`, {
        method: 'DELETE'
    })

    if (response.ok) {
        showToast('Sparplan gelöscht!')
        loadSavingsPlans()
    } else {
        showToast('Fehler beim Löschen!', 'error')
    }
}