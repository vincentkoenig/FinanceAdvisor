// User ID aus localStorage holen
const userId = localStorage.getItem('user_id')
console.log('User ID:', userId)  // Was steht dort?

async function loadPortfolio() {
    // GET Request an /users/<user_id>/assets schicken
    const response = await fetch(`/users/${userId}/assets`,{
        method: 'GET',
    })

    // Daten holen
    const data = await response.json()
    console.log(data)

    // Tabellen Body holen
    const tableBody = document.getElementById('portfolio-body')

    // Für jeden Asset eine Zeile erstellen
    data.forEach(asset => {
        const kaufpreisGesamt = asset.avg_buy_price * asset.quantity
        const positionGesamt = asset.current_price * asset.quantity
        const plEur = positionGesamt - kaufpreisGesamt
        const plProzent = (plEur / kaufpreisGesamt * 100).toFixed(2)
        const plColor = plEur >= 0 ? '#2ea043' : '#f85149'
        tableBody.innerHTML += `
            <tr>
                <td><strong>${asset.name}</strong><br><small>${asset.symbol} x${asset.quantity}</small></td>
                <td>${kaufpreisGesamt.toFixed(2)} $<br><small>${asset.avg_buy_price.toFixed(2)} $</small></td>
                <td>${positionGesamt.toFixed(2)} $<br><small>${asset.current_price.toFixed(2)} $</small></td>
                <td style="color: ${plColor}">${plEur.toFixed(2)} $<br><small>${plProzent}%</small></td>
            </tr>
        `
    })
}

// Funktion aufrufen wenn Seite geladen wird
loadPortfolio()