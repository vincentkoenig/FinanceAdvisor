# Libraries importieren
import requests
from dotenv import load_dotenv
import os

# API Key sicher aus .env Datei laden
load_dotenv()

# URL der CoinGecko API
url = "https://api.coingecko.com/api/v3/simple/price"

# Anfrage-Details: welche Coins und in welcher Währung
params = {
    "ids": "bitcoin,ethereum,solana",
    "vs_currencies": "eur",
    "x_cg_demo_api_key": os.getenv("COINGECKO_API_KEY")
}

# GET-Anfrage an die API senden
response = requests.get(url, params=params)

# HTTP-Objekt entpacken und Daten als Dictionary speichern
data = response.json()

# Schleife um jeden einzelnen Coin auszugeben
for coin in data:
    print(f"{coin}: {data[coin]['eur']} EUR")

