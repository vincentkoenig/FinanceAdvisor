// User ID aus localStorage holen
const userId = localStorage.getItem('user_id')

// Zahl im deutschen Format formatieren z.B. 1.234,50
function formatCurrency(value) {
    return value.toLocaleString('de-DE', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    })
}

async function loadHomeOverview() {
    // Portfolio-Wert holen - Summe aus current_price * quantity aller Assets,
    // gleiche Berechnung wie im Portfolio-Dashboard
    const assetsResponse = await fetch(`/users/${userId}/assets`)
    const assets = await assetsResponse.json()

    let portfolioValue = 0
    assets.forEach(asset => {
        portfolioValue += asset.current_price * asset.quantity
    })

    // Cash-Bestand aus dem Haushaltsbuch holen
    const budgetResponse = await fetch(`/users/${userId}/budget/summary`)
    const budget = await budgetResponse.json()

    const cashBalance = budget.cumulative_balance
    const currentMonthBalance = budget.current_month_balance
    const totalNetWorth = portfolioValue + cashBalance

    // Werte anzeigen
    document.getElementById('home-portfolio-value').innerHTML = `${formatCurrency(portfolioValue)} €`
    document.getElementById('home-cash-balance').innerHTML = `${formatCurrency(cashBalance)} €`

    const monthColor = currentMonthBalance >= 0 ? '#2ea043' : '#f85149'
    const monthPrefix = currentMonthBalance >= 0 ? '+' : ''
    document.getElementById('home-current-month-balance').innerHTML =
        `<span style="color: ${monthColor}">${monthPrefix}${formatCurrency(currentMonthBalance)} € diesen Monat</span>`

    document.getElementById('home-total-net-worth').innerHTML = `${formatCurrency(totalNetWorth)} €`
}

// Beim Laden der Seite aufrufen
loadHomeOverview()