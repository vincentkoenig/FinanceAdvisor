// asset-picker.js - Suchfeld mit Ergebnisliste für Assets (Positionen,
// Watchlist, Sparpläne). Beim Tippen fragt es /api/v1/assets/search ab und
// zeigt die Treffer, Euro-Börsen zuerst. Erst der ausgewählte Treffer wird
// beim Speichern über POST /api/v1/assets angelegt - so landet niemand
// versehentlich bei der US-Variante von SAP oder bei Bitcoin in Dollar.

const assetPickers = {}

function attachAssetPicker(inputId) {
    const input = document.getElementById(inputId)
    const wrapper = document.createElement('div')
    wrapper.className = 'asset-picker'
    input.parentNode.insertBefore(wrapper, input)
    wrapper.appendChild(input)

    const list = document.createElement('ul')
    list.className = 'asset-picker-list'
    list.setAttribute('role', 'listbox')
    wrapper.appendChild(list)

    input.setAttribute('autocomplete', 'off')
    input.setAttribute('role', 'combobox')
    input.setAttribute('aria-expanded', 'false')

    const picker = {input, list, results: [], selected: null, active: -1, timer: null, requestId: 0}
    assetPickers[inputId] = picker

    input.addEventListener('input', () => {
        picker.selected = null
        clearTimeout(picker.timer)
        const query = input.value.trim()
        if (query.length < 2) {
            closeAssetPicker(picker)
            return
        }
        picker.timer = setTimeout(() => searchAssetPicker(picker, query), 300)
    })

    input.addEventListener('keydown', (event) => {
        if (!picker.results.length || picker.list.style.display !== 'block') return
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
            event.preventDefault()
            const step = event.key === 'ArrowDown' ? 1 : -1
            picker.active = (picker.active + step + picker.results.length) % picker.results.length
            renderAssetPicker(picker)
        } else if (event.key === 'Enter' && picker.active >= 0) {
            event.preventDefault()
            selectAssetPickerResult(picker, picker.active)
        } else if (event.key === 'Escape') {
            closeAssetPicker(picker)
        }
    })

    // Klick außerhalb schließt die Liste
    document.addEventListener('click', (event) => {
        if (!wrapper.contains(event.target)) closeAssetPicker(picker)
    })
}

async function searchAssetPicker(picker, query) {
    const requestId = ++picker.requestId
    picker.list.innerHTML = '<li class="asset-picker-hint">Suche…</li>'
    openAssetPicker(picker)

    const response = await fetch(`/api/v1/assets/search?query=${encodeURIComponent(query)}`)
    // Nur die Antwort auf die letzte Eingabe zählt
    if (requestId !== picker.requestId) return
    const data = await response.json().catch(() => ({}))

    picker.results = response.ok ? data.results : []
    picker.active = picker.results.length ? 0 : -1
    renderAssetPicker(picker)
}

const ASSET_TYPE_LABELS = {stock: 'Aktie', etf: 'ETF', crypto: 'Krypto', metal: 'Edelmetall'}

function renderAssetPicker(picker) {
    if (!picker.results.length) {
        picker.list.innerHTML = '<li class="asset-picker-hint">Nichts gefunden - Name, Symbol (z.B. TL0.DE) oder ISIN probieren</li>'
        return
    }
    picker.list.innerHTML = picker.results.map((result, index) => `
        <li role="option" class="asset-picker-item${index === picker.active ? ' active' : ''}"
            aria-selected="${index === picker.active}" data-index="${index}">
            <span class="asset-picker-name">${escapeHtml(result.name)}</span>
            <span class="asset-picker-meta">
                ${[result.symbol, result.exchange, ASSET_TYPE_LABELS[result.asset_type] || result.asset_type]
                    .filter(Boolean).map(escapeHtml).join(' · ')}
                ${result.eur ? '<span class="asset-picker-badge">€</span>' : ''}
                ${result.asset_id ? '<span class="asset-picker-badge">bekannt</span>' : ''}
            </span>
        </li>
    `).join('')

    picker.list.querySelectorAll('.asset-picker-item').forEach((item) => {
        // mousedown statt click, damit das Eingabefeld den Fokus nicht vorher verliert
        item.addEventListener('mousedown', (event) => {
            event.preventDefault()
            selectAssetPickerResult(picker, Number(item.dataset.index))
        })
    })
}

function selectAssetPickerResult(picker, index) {
    const result = picker.results[index]
    picker.selected = result
    picker.input.value = `${result.name} (${result.symbol})`
    closeAssetPicker(picker)
}

function openAssetPicker(picker) {
    picker.list.style.display = 'block'
    picker.input.setAttribute('aria-expanded', 'true')
}

function closeAssetPicker(picker) {
    picker.list.style.display = 'none'
    picker.input.setAttribute('aria-expanded', 'false')
}

function clearAssetPicker(inputId) {
    const picker = assetPickers[inputId]
    picker.input.value = ''
    picker.selected = null
    picker.results = []
    closeAssetPicker(picker)
}

// Liefert das ausgewählte Asset mit id - legt es bei Bedarf an.
// Ohne Auswahl gibt es einen Hinweis und null.
async function resolveAssetPicker(inputId) {
    const picker = assetPickers[inputId]
    const selected = picker.selected
    if (!selected) {
        showToast('Bitte einen Treffer aus der Liste auswählen!', 'error')
        picker.input.focus()
        return null
    }
    if (selected.asset_id) {
        return {id: selected.asset_id, name: selected.name, symbol: selected.symbol}
    }

    const response = await fetch('/api/v1/assets', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({symbol: selected.symbol, name: selected.name})
    })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) {
        showToast(data.error || 'Asset konnte nicht angelegt werden!', 'error')
        return null
    }
    // Beim nächsten Mal nicht erneut anlegen
    selected.asset_id = data.id
    return data
}
