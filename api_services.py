import requests
import os
from dotenv import load_dotenv
import time


load_dotenv()

def get_crypto_price(coin_id):
    # CoinGecko API aufrufen
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": coin_id,
        "vs_currencies": "eur",
        "x_cg_demo_api_key": os.getenv("COINGECKO_API_KEY")
    }

    try:
        # GET-Anfrage an die API senden
        response = requests.get(url, params=params)

        # HTTP-Objekt entpacken und Daten als Dictionary speichern
        data = response.json()

        return data[coin_id]['eur']
    except Exception as e:
        print(f"Error fetching crypto price: {e}")
        return None


def get_stock_price(symbol):
    # Basis-URL der Alpha Vantage API
    url = "https://www.alphavantage.co/query"
    params = {
        "function": "GLOBAL_QUOTE",
        "symbol": symbol,
        "apikey": os.getenv("ALPHAVANTAGE_API_KEY")
    }

    try:
        # GET-Anfrage an die API senden
        response = requests.get(url, params=params)
        # 1 Sekunde warten um Rate Limit zu vermeiden
        time.sleep(1)
        # HTTP-Objekt entpacken und Daten als Dictionary speichern
        data = response.json()
        # Preis aus dem Dictionary herausziehen
        price = data['Global Quote']['05. price']

        return float(price)
    except Exception as e:
        print(f"Error fetching stock price: {e}")
        return None


def get_metal_price(symbol):
    url = "https://www.alphavantage.co/query"
    params = {
        "function": "GOLD_SILVER_SPOT",
        "symbol": symbol,
        "apikey": os.getenv("ALPHAVANTAGE_API_KEY")
    }

    try:
        # GET-Anfrage an die API senden
        response = requests.get(url, params=params)
        # 1 Sekunde warten um Rate Limit zu vermeiden
        time.sleep(1)
        # HTTP-Objekt entpacken und Daten als Dictionary speichern
        data = response.json()
        # Preis aus dem Dictionary herausziehen
        price = data['price']

        return float(price)
    except Exception as e:
        print(f"Error fetching metal price: {e}")
        return None


if __name__ == "__main__":
    print(get_crypto_price("bitcoin"))
    print(get_stock_price("AAPL"))
    print(get_metal_price("GOLD"))