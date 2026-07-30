// User ID aus localStorage holen
const userId = localStorage.getItem('user_id')

// Aktuell angezeigter Monat - startet mit dem heutigen Monat
let currentMonthDate = new Date()

// Zahl im deutschen Format formatieren z.B. 1.234,50
function formatCurrency(value) {
    return value.toLocaleString('de-DE', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    })
}

// Monat als YYYY-MM String z.B. "2026-07" - Format das das Backend erwartet
function getMonthString(date) {
    const year = date.getFullYear()
    const month = String(date.getMonth() + 1).padStart(2, '0')
    return `${year}-${month}`
}

// Monat als lesbarer Text z.B. "Juli 2026"
function getMonthLabel(date) {
    return date.toLocaleDateString('de-DE', { month: 'long', year: 'numeric' })
}

// Monat wechseln - direction ist -1 (zurück) oder 1 (vor)
function changeMonth(direction) {
    currentMonthDate.setMonth(currentMonthDate.getMonth() + direction)
    loadBudget()
}

async function loadBudget() {
    // Aktuellen Monat anzeigen
    document.getElementById('current-month-label').innerHTML = getMonthLabel(currentMonthDate)

    // Transaktionen für den gewählten Monat holen
    const month = getMonthString(currentMonthDate)
    const response = await fetch(`/users/${userId}/transactions?month=${month}`)
    const transactions = await response.json()

    // Nach Kategorie-Typ aufsummieren
    let totalIncome = 0
    let totalFixed = 0
    let totalVariable = 0

    transactions.forEach(transaction => {
        if (transaction.category_type === 'income') {
            totalIncome += transaction.amount
        } else if (transaction.category_type === 'fixed_expense') {
            totalFixed += transaction.amount
        } else if (transaction.category_type === 'variable_expense') {
            totalVariable += transaction.amount
        }
    })

    const balance = totalIncome - totalFixed - totalVariable
    const balanceColor = balance >= 0 ? '#2ea043' : '#f85149'

    // Kennzahlen anzeigen
    document.getElementById('summary-income').innerHTML = `${formatCurrency(totalIncome)} €`
    document.getElementById('summary-fixed').innerHTML = `${formatCurrency(totalFixed)} €`
    document.getElementById('summary-variable').innerHTML = `${formatCurrency(totalVariable)} €`
    document.getElementById('summary-balance').innerHTML = `<span style="color: ${balanceColor}">${formatCurrency(balance)} €</span>`
}

// Beim Laden der Seite aufrufen
loadBudget()