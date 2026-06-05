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

    // Schritt 2: asset_id aus der Antwort holen und zur Watchlist hinzufügen
    const response = await fetch('/watchlist', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({user_id: userId, asset_id: asset.id})
    })

    // Auf die JSON Antwort warten und in data speichern
    const data = await response.json();

    if (response.ok) {
        alert('Asset hinzugefügt!')
    } else {
        alert(data.error)
    }

}


async function loadWatchlist() {
    const userId = localStorage.getItem('user_id')

    // Watchlist aus DB holen
    const response = await fetch(`/users/${userId}/watchlist`)
    const data = await response.json()

    const tableBody = document.getElementById('watchlist-body')

    // Für jeden Eintrag eine Zeile erstellen
    for (const item of data) {
        // Asset Details holen
        const assetResponse = await fetch(`/assets/${item.asset_id}`)
        const asset = await assetResponse.json()

        tableBody.innerHTML += `
            <tr>
                <td><strong>${asset.name}</strong></td>
                <td>${asset.symbol}</td>
                <td>${asset.current_price} $</td>
                <td><button onclick="removeFromWatchlist(${item.asset_id})">Entfernen</button></td>
            </tr>
        `
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
        alert('Asset entfernt!')
        loadWatchlist()  // Watchlist neu laden
    } else {
        alert(data.error)
    }
}

// Beim Laden der Seite aufrufen
loadWatchlist()