import requests
import os
from dotenv import load_dotenv
import time

# .env Datei laden - API Keys sicher aus .env holen
load_dotenv()

def get_crypto_price(coin_id):
    """
    Ruft den aktuellen Preis einer Kryptowährung ab.
    Benutzt die CoinGecko API.
    Parameter: coin_id → z.B. "bitcoin", "ethereum", "solana"
    Gibt den Preis in EUR zurück oder None bei Fehler.
    """
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

        # Preis aus dem Dictionary herausziehen und zurückgeben
        return data[coin_id]['eur']

    except Exception as e:
        print(f"Error fetching crypto price: {e}")

        # None zurückgeben wenn API nicht erreichbar
        return None


def get_stock_price(symbol):
    """
    Ruft den aktuellen Preis einer Aktie oder eines ETFs ab.
    Benutzt die Alpha Vantage API.
    Parameter: symbol → z.B. "AAPL", "MSFT", "NVDA"
    Gibt den Preis in USD als Float zurück oder None bei Fehler.
    """
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

        # 1 Sekunde warten um Rate Limit zu vermeiden (max. 25 Requests/Tag)
        time.sleep(1)

        # HTTP-Objekt entpacken und Daten als Dictionary speichern
        data = response.json()

        # Preis aus dem Dictionary herausziehen
        price = data['Global Quote']['05. price']

        # USD zu EUR umrechnen
        rate = get_exchange_rate("USD", "EUR")

        # Als Float zurückgeben damit man damit rechnen kann
        return round(float(price) * rate, 2)

    except Exception as e:
        print(f"Error fetching stock price: {e}")

        # None zurückgeben wenn API nicht erreichbar
        return None


def get_metal_price(symbol):
    """
    Ruft den aktuellen Preis eines Edelmetalls ab.
    Benutzt die Alpha Vantage Commodities API.
    Parameter: symbol → "GOLD" oder "SILVER"
    Gibt den Preis in USD als Float zurück oder None bei Fehler.
    """
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

        # Preis direkt aus dem Dictionary holen
        price = data['price']

        # USD zu EUR umrechnen
        rate = get_exchange_rate("USD", "EUR")

        # Als Float zurückgeben damit man damit rechnen kann
        return round(float(price) * rate, 2)

    except Exception as e:
        print(f"Error fetching metal price: {e}")

        # None zurückgeben wenn API nicht erreichbar
        return None


def get_exchange_rate(from_currency, to_currency):
    """
    Ruft den aktuellen Wechselkurs ab.
    z.B. get_exchange_rate("USD", "EUR")
    """
    url = "https://www.alphavantage.co/query"
    params = {
        "function": "CURRENCY_EXCHANGE_RATE",
        "from_currency": from_currency,
        "to_currency": to_currency,
        "apikey": os.getenv("ALPHAVANTAGE_API_KEY")
    }

    try:
        response = requests.get(url, params=params)
        data = response.json()
        rate = data['Realtime Currency Exchange Rate']['5. Exchange Rate']
        return float(rate)
    except Exception as e:
        print(f"Error fetching exchange rate: {e}")
        return None


# Testaufruf - wird nur ausgeführt wenn diese Datei direkt gestartet wird
if __name__ == "__main__":
    print(get_crypto_price("bitcoin"))
    print(get_stock_price("AAPL"))
    print(get_metal_price("GOLD"))
    print(get_exchange_rate("USD", "EUR"))