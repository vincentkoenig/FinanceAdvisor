async function addToWatchlist() {
    // Werte aus den Input Feldern holen
    const userId = localStorage.getItem('user_id')
    // Symbol aus dem Input Feld holen
    const query = document.getElementById('asset-search').value

    // Schritt 1: Asset suchen
    const searchResponse = await fetch(`/assets/search?query=${query}`)
    const asset = await searchResponse.json()

    if (!searchResponse.ok) {
        showToast('Asset nicht gefunden!')
        return
    }

    // Schritt 2: Asset dem Nutzer zur Watchlist hinzufügen
    const response = await fetch(`/users/${userId}/watchlist`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({asset_id: asset.id})  // user_id nicht mehr nötig!
    })

    // Auf die JSON Antwort warten und in data speichern
    const data = await response.json();

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
        // Veränderung berechnen
        const change = item.current_price - item.price_added
        const changePercent = ((change / item.price_added) * 100).toFixed(2)
        const changeColor = change >= 0 ? '#2ea043' : '#f85149'
        const changeSign = change >= 0 ? '+' : ''

        tableBody.innerHTML += `
            <tr onclick="showWatchlistDetail(${item.asset_id}, '${item.name}')" style="cursor: pointer;">
                <td><strong>${item.name}</strong></td>
                <td>${item.symbol}</td>
                <td>${item.current_price} €</td>
                <td>${item.price_added ? item.price_added + ' €' : '-'}</td>
                <td style="color: ${changeColor}">
                    ${changeSign}${change.toFixed(2)} €<br>
                    <small>${changeSign}${changePercent}%</small>
                </td>
                <td>${item.added_at}</td>
            </tr>
        `
    }
}


async function loadWatchlist() {
    const userId = localStorage.getItem('user_id')
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

// Beim Laden der Seite aufrufen
loadWatchlist()

let selectedWatchlistAssetId = null

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
    const userId = localStorage.getItem('user_id')
    const quantity = document.getElementById('watchlist-buy-quantity').value
    const price = document.getElementById('watchlist-buy-price').value
    const today = new Date().toISOString().split('T')[0]

    // Menge und Preis müssen gültige, positive Zahlen sein
    if (quantity === '' || isNaN(quantity) || parseFloat(quantity) <= 0) {
        showToast('Bitte eine gültige Menge größer 0 angeben!', 'error')
        return
    }
    if (price === '' || isNaN(price) || parseFloat(price) <= 0) {
        showToast('Bitte einen gültigen Preis größer 0 angeben!', 'error')
        return
    }

    // Schritt 1: Asset dem Portfolio hinzufügen
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
        // Schritt 2: Asset von der Watchlist entfernen
        await removeFromWatchlist(selectedWatchlistAssetId)
        hideWatchlistDetail()
        showToast('Asset gekauft und zur Watchlist entfernt!')
    } else {
        showToast('Fehler beim Kaufen!', 'error')
    }
}


async function removeFromWatchlist(assetId) {
    const userId = localStorage.getItem('user_id')

    const response = await fetch(`/users/${userId}/watchlist/${assetId}`, {
        method: 'DELETE',
        headers: {'Content-Type': 'application/json'}
    })

    const data = await response.json()

    if (response.ok) {
        showToast('Asset entfernt!')
        loadWatchlist()  // Watchlist neu laden
    } else {
        showToast(data.error)
    }
}




// Globale Variable für Watchlist Daten
let watchlistData = []
let watchlistSortDirection = 1

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