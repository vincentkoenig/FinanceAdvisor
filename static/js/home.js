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

        // Fällige Sparpläne prüfen und als Hinweis anzeigen
        const savingsPlansResponse = await fetch(`/users/${userId}/savings-plans`)
        const savingsPlans = await savingsPlansResponse.json()
        const duePlans = savingsPlans.filter(plan => plan.is_due)

        const dueContainer = document.getElementById('due-savings-plans')

        if (duePlans.length > 0) {
            const planRows = duePlans.map(plan => `
                <div class="due-plan-row">
                    <span>${plan.asset_name} <small style="color: var(--text-secondary);">(${formatCurrency(plan.amount)} €)</small></span>
                    <button class="btn-primary" style="width: auto; padding: 8px 16px; font-size: 13px;" onclick="executeSavingsPlanFromHome(${plan.id})">Sparplan ausführen</button>
                </div>
            `).join('')

            dueContainer.innerHTML = `
                <div class="glass-card" style="border-radius: 10px; padding: 20px;">
                    <p style="margin-bottom: 12px; font-weight: bold;">${duePlans.length} Sparplan${duePlans.length > 1 ? '\u00e4ne' : ''} fällig</p>
                    ${planRows}
                </div>
            `
            dueContainer.style.display = 'block'
        } else {
            dueContainer.style.display = 'none'
        }
    }


async function executeSavingsPlanFromHome(planId) {
    const response = await fetch(`/savings-plans/${planId}/execute`, {
        method: 'POST'
    })

    const data = await response.json()

    if (response.ok) {
        showToast(`Sparplan ausgeführt: ${data.quantity} Stück zu ${data.price} €`)
        loadHomeOverview()
    } else {
        showToast(data.error || 'Fehler beim Ausführen!', 'error')
    }
}

// Beim Laden der Seite aufrufen
loadHomeOverview()