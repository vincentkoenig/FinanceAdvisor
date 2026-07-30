// User ID aus localStorage holen
const userId = localStorage.getItem('user_id')

// Aktuell angezeigter Monat - startet mit dem heutigen Monat
let currentMonthDate = new Date()

// Globale Variable für alle Kategorien - einmal geladen, wird für die
// verschachtelte Dropdown-Auswahl (Typ -> Hauptkategorie -> Unterkategorie) genutzt
let allCategories = []

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

// Beim Laden der Seite aufrufen
loadBudget()


async function loadCategories() {
    const response = await fetch(`/users/${userId}/categories`)
    allCategories = await response.json()
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


// Kategorien beim Laden der Seite direkt mit abrufen
loadCategories()