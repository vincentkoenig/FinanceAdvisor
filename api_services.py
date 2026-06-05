import requests
import os
from dotenv import load_dotenv
import time
import yfinance as yf

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
    Benutzt yfinance - kostenlos und kein Rate Limit!
    Parameter: symbol → z.B. "AAPL", "MSFT", "NVDA"
    Gibt den Preis in EUR zurück oder None bei Fehler.
    """
    try:
        ticker = yf.Ticker(symbol)
        price_usd = ticker.fast_info['lastPrice']

        # USD zu EUR umrechnen
        rate = get_exchange_rate("USD", "EUR")
        return round(float(price_usd) * rate, 2)
    except Exception as e:
        print(f"Error fetching stock price: {e}")
        return None


def get_metal_price(symbol):
    """
    Ruft den aktuellen Preis eines Edelmetalls ab.
    Benutzt yfinance - kostenlos und kein Rate Limit!
    Parameter: symbol → "GOLD" oder "SILVER"
    Gibt den Preis in USD als Float zurück oder None bei Fehler.
    """
    symbols = {
        "GOLD": "GC=F",
        "SILVER": "SI=F"
    }

    try:
        ticker = yf.Ticker(symbols[symbol])
        price_usd = ticker.fast_info['lastPrice']
        rate = get_exchange_rate("USD", "EUR")
        return round(float(price_usd) * rate, 2)
    except Exception as e:
        print(f"Error fetching metal price: {e}")
        return None


def get_exchange_rate(from_currency, to_currency):
    """
    Ruft den aktuellen Wechselkurs ab.
    Benutzt yfinance - kostenlos und kein Rate Limit!
    """
    try:
        ticker = yf.Ticker(f"{from_currency}{to_currency}=X")
        rate = ticker.fast_info['lastPrice']
        return float(rate)
    except Exception as e:
        print(f"Error fetching exchange rate: {e}")
        return 0.89  # Fallback Wechselkurs EUR/USD


# Testaufruf - wird nur ausgeführt wenn diese Datei direkt gestartet wird
if __name__ == "__main__":
    print(get_stock_price("AAPL"))
    print(get_stock_price("NVDA"))
    print(get_metal_price("GOLD"))
    print(get_exchange_rate("USD", "EUR"))