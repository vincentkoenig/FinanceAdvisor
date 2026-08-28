// User ID aus localStorage holen
const userId = localStorage.getItem('user_id')

// Aktuell angezeigter Monat - startet mit dem heutigen Monat
let currentMonthDate = new Date()

// Globale Variable für alle Kategorien - einmal geladen, wird für die
// verschachtelte Dropdown-Auswahl (Typ -> Hauptkategorie -> Unterkategorie) genutzt
let allCategories = []

// Donut Chart Instanz - global damit sie beim Monatswechsel zerstört
// und neu erstellt werden kann, statt sich zu überlagern
let expenseDonutChart = null

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

async function loadCategories() {
    const response = await fetch(`/users/${userId}/categories`)
    allCategories = await response.json()
}

async function loadBudget() {
    // Aktuellen Monat anzeigen
    document.getElementById('current-month-label').innerHTML = getMonthLabel(currentMonthDate)

    // Sicherstellen dass Kategorien bereits geladen sind, bevor wir sie nachschlagen
    if (allCategories.length === 0) {
        await loadCategories()
    }

    // Transaktionen für den gewählten Monat holen
    const month = getMonthString(currentMonthDate)
    const response = await fetch(`/users/${userId}/transactions?month=${month}`)
    const transactions = await response.json()

    // Nach Kategorie-Typ aufsummieren (Gesamtzahlen für die Kennzahlen oben)
    let totalIncome = 0
    let totalFixed = 0
    let totalVariable = 0

    // Zusätzlich pro Hauptkategorie aufsummieren (für die Aufschlüsselung)
    const mainCategoryTotals = {}  // z.B. { 6: 850 } - Hauptkategorie-ID -> Summe

    transactions.forEach(transaction => {
        if (transaction.category_type === 'income') {
            totalIncome += transaction.amount
        } else if (transaction.category_type === 'fixed_expense') {
            totalFixed += transaction.amount
        } else if (transaction.category_type === 'variable_expense') {
            totalVariable += transaction.amount
        }

        // Zur Hauptkategorie hochrechnen: Unterkategorie -> parent_id finden
        const subCategory = allCategories.find(c => c.id === transaction.category_id)
        if (subCategory) {
            const mainCategoryId = subCategory.parent_id || subCategory.id
            mainCategoryTotals[mainCategoryId] = (mainCategoryTotals[mainCategoryId] || 0) + transaction.amount
        }
    })

    const balance = totalIncome - totalFixed - totalVariable
    const balanceColor = balance >= 0 ? '#2ea043' : '#f85149'

    // Kennzahlen anzeigen
    document.getElementById('summary-income').innerHTML = `${formatCurrency(totalIncome)} €`
    document.getElementById('summary-fixed').innerHTML = `${formatCurrency(totalFixed)} €`
    document.getElementById('summary-variable').innerHTML = `${formatCurrency(totalVariable)} €`
    document.getElementById('summary-balance').innerHTML = `<span style="color: ${balanceColor}">${formatCurrency(balance)} €</span>`

    // Aufschlüsselung nach Hauptkategorie für alle drei Blöcke rendern
    renderBreakdown('breakdown-income', 'income', mainCategoryTotals, totalIncome)
    renderBreakdown('breakdown-fixed', 'fixed_expense', mainCategoryTotals, totalFixed)
    renderBreakdown('breakdown-variable', 'variable_expense', mainCategoryTotals, totalVariable)

    // Donut Chart über alle Ausgaben aktualisieren
    renderExpenseDonut(mainCategoryTotals)
    renderTransactionsList(transactions)
}

// Rendert die Liste der Hauptkategorien mit Betrag und Prozentanteil
// für einen der drei Blöcke (Einkommen/Fixkosten/Variable Ausgaben)
function renderBreakdown(containerId, type, mainCategoryTotals, blockTotal) {
    const container = document.getElementById(containerId)

    // Alle Hauptkategorien dieses Typs, die tatsächlich Buchungen haben
    const mainCategories = allCategories.filter(c => c.type === type && c.parent_id === null)

    let html = ''
    mainCategories.forEach(category => {
        const amount = mainCategoryTotals[category.id]
        if (!amount) return  // Kategorien ohne Buchungen in diesem Monat überspringen

        const percent = blockTotal > 0 ? ((amount / blockTotal) * 100).toFixed(1) : 0

        html += `
            <div class="breakdown-row">
                <span class="breakdown-row-name">${category.name}</span>
                <div class="breakdown-row-values">
                    <div class="breakdown-row-amount">${formatCurrency(amount)} €</div>
                    <div class="breakdown-row-percent">${percent}%</div>
                </div>
            </div>
        `
    })

    container.innerHTML = html || '<div class="breakdown-empty">Keine Buchungen</div>'
}

// Erstellt den Donut Chart über alle Ausgaben (Fixkosten + Variable)
// nach Hauptkategorie, unabhängig vom Typ
function renderExpenseDonut(mainCategoryTotals) {
    // Nur Hauptkategorien vom Typ fixed_expense oder variable_expense berücksichtigen
    const expenseCategories = allCategories.filter(
        c => c.parent_id === null && (c.type === 'fixed_expense' || c.type === 'variable_expense')
    )

    const labels = []
    const values = []

    expenseCategories.forEach(category => {
        const amount = mainCategoryTotals[category.id]
        if (amount) {
            labels.push(category.name)
            values.push(amount)
        }
    })

    const totalExpenses = values.reduce((sum, v) => sum + v, 0)
    document.getElementById('donut-expense-value').innerHTML = `${formatCurrency(totalExpenses)} €`

    // Alten Chart zerstören falls vorhanden, bevor ein neuer erstellt wird
    if (expenseDonutChart) {
        expenseDonutChart.destroy()
    }

    expenseDonutChart = new Chart(document.getElementById('expenseDonutChart'), {
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


// Rendert die Liste aller Buchungen des aktuellen Monats als Tabelle
function renderTransactionsList(transactions) {
    const tableBody = document.getElementById('transactions-body')

    if (transactions.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="5" style="text-align:center; color: var(--text-secondary);">Keine Buchungen in diesem Monat</td></tr>'
        return
    }

    const sorted = [...transactions].sort((a, b) => b.date.localeCompare(a.date))

    tableBody.innerHTML = sorted.map(transaction => {
        const isIncome = transaction.category_type === 'income'
        const amountColor = isIncome ? '#2ea043' : '#f85149'
        const amountPrefix = isIncome ? '+' : '-'
        const recurringIcon = transaction.is_recurring
            ? '<i class="fa-solid fa-rotate" title="Wiederkehrend" style="margin-left: 6px; color: var(--text-secondary); font-size: 12px;"></i>'
            : ''

        // Pausieren/Fortsetzen-Button nur bei wiederkehrenden Buchungen anzeigen
        const pauseButton = transaction.is_recurring
            ? `<button class="btn-secondary" style="width: auto; padding: 6px 12px; font-size: 13px;" onclick="toggleTransactionPause(${transaction.id})" title="${transaction.is_paused ? 'Fortsetzen' : 'Pausieren'}">
                   <i class="fa-solid ${transaction.is_paused ? 'fa-play' : 'fa-pause'}"></i>
               </button>`
            : ''

        // Optische Kennzeichnung pausierter Buchungen
        const pausedStyle = transaction.is_paused ? 'opacity: 0.5;' : ''

        return `
            <tr style="${pausedStyle}">
                <td data-label="Datum">${formatDate(transaction.date)}</td>
                <td data-label="Kategorie">${transaction.category_name}${recurringIcon}</td>
                <td data-label="Beschreibung">${transaction.description || '-'}${transaction.is_paused ? ' <small style="color: var(--text-secondary);">(pausiert)</small>' : ''}</td>
                <td data-label="Betrag" style="color: ${amountColor}">${amountPrefix}${formatCurrency(transaction.amount)} €</td>
                <td data-label="">
                    ${pauseButton}
                    <button class="btn-secondary" style="width: auto; padding: 6px 12px; font-size: 13px; margin-left: 6px;" onclick="deleteTransaction(${transaction.id})">
                        <i class="fa-solid fa-trash"></i>
                    </button>
                </td>
            </tr>
        `
    }).join('')
}


async function toggleTransactionPause(transactionId) {
    const response = await fetch(`/transactions/${transactionId}/toggle-pause`, {
        method: 'PUT'
    })

    const data = await response.json()

    if (response.ok) {
        showToast(data.message)
        loadBudget()
    } else {
        showToast(data.error || 'Fehler beim Pausieren!', 'error')
    }
}

// Datum im deutschen Format formatieren z.B. 05.07.2026
function formatDate(dateString) {
    const [year, month, day] = dateString.split('-')
    return `${day}.${month}.${year}`
}

async function deleteTransaction(transactionId) {
    const response = await fetch(`/transactions/${transactionId}`, {
        method: 'DELETE'
    })

    if (response.ok) {
        showToast('Buchung gelöscht!')
        loadBudget()
    } else {
        showToast('Fehler beim Löschen!', 'error')
    }
}


// Modal anzeigen
function showAddTransaction() {
    document.getElementById('add-transaction-modal').style.display = 'block'
    loadMainCategoryOptions()
}

// Modal verstecken
function hideAddTransaction() {
    document.getElementById('add-transaction-modal').style.display = 'none'
}

// Hauptkategorien passend zum gewählten Typ ins Dropdown laden
function loadMainCategoryOptions() {
    const type = document.getElementById('transaction-type').value
    const mainCategorySelect = document.getElementById('transaction-main-category')

    // Nur Hauptkategorien (parent_id ist null) mit passendem Typ
    const mainCategories = allCategories.filter(c => c.type === type && c.parent_id === null)

    mainCategorySelect.innerHTML = mainCategories
        .map(c => `<option value="${c.id}">${c.name}</option>`)
        .join('')

    // Direkt im Anschluss die passenden Unterkategorien laden
    loadSubCategoryOptions()
}

// Unterkategorien passend zur gewählten Hauptkategorie ins Dropdown laden
function loadSubCategoryOptions() {
    const mainCategoryId = parseInt(document.getElementById('transaction-main-category').value)
    const subCategorySelect = document.getElementById('transaction-sub-category')

    const subCategories = allCategories.filter(c => c.parent_id === mainCategoryId)

    subCategorySelect.innerHTML = subCategories
        .map(c => `<option value="${c.id}">${c.name}</option>`)
        .join('')
}

async function addTransaction() {
    const categoryId = document.getElementById('transaction-sub-category').value
    const amount = document.getElementById('transaction-amount').value
    const date = document.getElementById('transaction-date').value
    const description = document.getElementById('transaction-description').value
    const isRecurring = document.getElementById('transaction-recurring').checked
    const endDate = document.getElementById('transaction-end-date').value

    // Betrag muss eine gültige, positive Zahl sein
    if (amount === '' || isNaN(amount) || parseFloat(amount) <= 0) {
        showToast('Bitte einen gültigen Betrag größer 0 angeben!', 'error')
        return
    }
    if (!date) {
        showToast('Bitte ein Datum angeben!', 'error')
        return
    }

    const response = await fetch(`/users/${userId}/transactions`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            category_id: categoryId,
            amount: amount,
            date: date,
            description: description,
            is_recurring: isRecurring,
            end_date: endDate || null
        })
    })

    if (response.ok) {
        showToast('Buchung hinzugefügt!')
        hideAddTransaction()
        loadBudget()
    } else {
        showToast('Fehler beim Hinzufügen der Buchung!', 'error')
    }
}

// Enddatum-Feld ein-/ausblenden je nachdem ob "Wiederkehrend" angehakt ist,
// und das Datum-Label entsprechend anpassen
function toggleEndDateField() {
    const isRecurring = document.getElementById('transaction-recurring').checked
    const endDateField = document.getElementById('end-date-field')
    const dateLabel = document.getElementById('transaction-date-label')

    endDateField.style.display = isRecurring ? 'block' : 'none'
    dateLabel.innerHTML = isRecurring ? 'Startdatum' : 'Datum'
}

// Kategorien und Budget beim Laden der Seite abrufen - Kategorien zuerst,
// damit loadBudget() beim ersten Aufruf sofort darauf zugreifen kann
loadCategories().then(() => loadBudget())