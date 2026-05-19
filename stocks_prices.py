# Libraries importieren
import requests
from dotenv import load_dotenv
import os
import time

# API Key sicher aus .env Datei laden
load_dotenv()

# Basis-URL der Alpha Vantage API
url = "https://www.alphavantage.co/query"

# Liste der abzufragenden Aktien
symbols = ["AAPL", "MSFT", "NVDA"]

# Schleife über alle Aktien
for stock in symbols:
    # Anfrage-Details für jede Aktie
    params = {
        "function": "GLOBAL_QUOTE",
        "symbol": stock,
        "apikey": os.getenv("ALPHAVANTAGE_API_KEY")
    }
    # GET-Anfrage an die API senden
    response = requests.get(url, params=params)
    # 1 Sekunde warten um Rate Limit zu vermeiden
    time.sleep(1)
    # HTTP-Objekt entpacken und Daten als Dictionary speichern
    data = response.json()
    # Preis und Symbol aus dem Dictionary herausziehen
    price = data['Global Quote']['05. price']
    symbol = data['Global Quote']['01. symbol']

    print(f"{symbol}: {price} USD")