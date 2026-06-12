async function addToWatchlist() {
    // Werte aus den Input Feldern holen
    const userId = localStorage.getItem('user_id')
    // Symbol aus dem Input Feld holen
    const query = document.getElementById('asset-search').value

    // Schritt 1: Asset suchen
    const searchResponse = await fetch(`/assets/search?query=${query}`)
    const asset = await searchResponse.json()

    if (!searchResponse.ok) {
        alert('Asset nicht gefunden!')
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
        alert('Asset hinzugefügt!')
    } else {
        alert(data.error)
    }

}


function renderWatchlist(data) {
    const tableBody = document.getElementById('watchlist-body')
    tableBody.innerHTML = ''

    for (const item of data) {
        tableBody.innerHTML += `
            <tr>
                <td><strong>${item.name}</strong></td>
                <td>${item.symbol}</td>
                <td>${item.current_price} €</td>
                <td><button onclick="removeFromWatchlist(${item.asset_id})">Entfernen</button></td>
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
            current_price: asset.current_price
        })
    }

    renderWatchlist(watchlistData)
}


async function removeFromWatchlist(assetId) {
    const userId = localStorage.getItem('user_id')

    const response = await fetch(`/users/${userId}/watchlist/${assetId}`, {
        method: 'DELETE',
        headers: {'Content-Type': 'application/json'}
    })

    const data = await response.json()

    if (response.ok) {
        alert('Asset entfernt!')
        loadWatchlist()  // Watchlist neu laden
    } else {
        alert(data.error)
    }
}

// Beim Laden der Seite aufrufen
loadWatchlist()


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