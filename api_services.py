"""
api_services.py - Externe API Funktionen für den FinanceAdvisor
Stellt Funktionen bereit um aktuelle Marktpreise abzurufen:
- get_crypto_price() → CoinGecko API für Kryptowährungen
- get_stock_price()  → yfinance für Aktien & ETFs
- get_metal_price()  → yfinance für Edelmetalle
- get_exchange_rate() → yfinance für Wechselkurse
Diese Funktionen werden im Chat (Function Calling) und
im Dashboard (Live Preise) verwendet.
"""

# Standard Library
import os
from datetime import datetime

# Third Party
import requests
import yfinance as yf
from dotenv import load_dotenv
from langchain_tavily import TavilySearch

# .env Datei laden - API Keys sicher aus .env holen
load_dotenv()


def get_crypto_price(coin_id):
    """
    Ruft den aktuellen Preis einer Kryptowährung ab.
    Benutzt die CoinGecko API.
    Parameter: coin_id → z.B. "bitcoin", "ethereum", "solana"
    Gibt den Preis in EUR zurück oder None bei Fehler.
    """
    import requests

    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": coin_id,
        "vs_currencies": "eur",
        "x_cg_demo_api_key": os.getenv("COINGECKO_API_KEY")
    }

    try:
        response = requests.get(url, params=params)
        data = response.json()
        return data[coin_id]['eur']

    except Exception as e:
        print(f"Error fetching crypto price: {e}")
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
    Gibt den Preis in EUR zurück oder None bei Fehler.
    """
    # yfinance Symbole für Edelmetalle
    symbols = {
        "GOLD": "GC=F",
        "SILVER": "SI=F"
    }

    try:
        ticker = yf.Ticker(symbols[symbol])
        price_usd = ticker.fast_info['lastPrice']

        # USD zu EUR umrechnen
        rate = get_exchange_rate("USD", "EUR")
        return round(float(price_usd) * rate, 2)

    except Exception as e:
        print(f"Error fetching metal price: {e}")
        return None


def get_exchange_rate(from_currency, to_currency):
    """
    Ruft den aktuellen Wechselkurs ab.
    Benutzt yfinance - kostenlos und kein Rate Limit!
    Parameter: from_currency → z.B. "USD"
               to_currency   → z.B. "EUR"
    Gibt den Wechselkurs als Float zurück oder 0.89 als Fallback.
    """
    try:
        ticker = yf.Ticker(f"{from_currency}{to_currency}=X")
        rate = ticker.fast_info['lastPrice']
        return float(rate)

    except Exception as e:
        print(f"Error fetching exchange rate: {e}")
        return 0.89  # Fallback Wechselkurs wenn API nicht erreichbar


def get_historical_prices(symbol, period="1y"):
    """
    Ruft historische Preise für ein Asset ab.
    Benutzt yfinance - kostenlos und kein Rate Limit!
    Parameter: symbol → z.B. "AAPL"
               period → z.B. "1y", "6mo", "3mo", "1mo"
    Gibt eine Liste von Dictionaries mit date und price zurück.
    """
    try:
        ticker = yf.Ticker(symbol)
        history = ticker.history(period=period)

        # Wechselkurs für USD zu EUR
        rate = get_exchange_rate("USD", "EUR")

        # Schlusskurs und Datum zurückgeben
        return [
            {
                "date": date.strftime('%Y-%m-%d'),
                "price": round(float(close), 2)
            }
            for date, close in zip(history.index, history['Close'])
        ]

    except Exception as e:
        print(f"Error fetching historical prices: {e}")
        return None


def get_stock_historical_range(symbol, start_date, end_date):
    """
    Ruft historische Preise für ein Asset in einem bestimmten Zeitraum ab.
    Benutzt yfinance - für Aktien, ETFs und Edelmetalle (mit Futures-Symbol).
    Parameter: symbol → yfinance Ticker Symbol
               start_date/end_date → date Objekte
    Gibt eine Liste von Dictionaries mit date und price zurück.
    """
    try:
        ticker = yf.Ticker(symbol)
        history = ticker.history(
            start=start_date.strftime('%Y-%m-%d'),
            end=end_date.strftime('%Y-%m-%d')
        )
        return [
            {
                "date": date.strftime('%Y-%m-%d'),
                "price": round(float(close), 2)
            }
            for date, close in zip(history.index, history['Close'])
        ]
    except Exception as e:
        print(f"Error fetching stock historical range: {e}")
        return []


def get_crypto_historical_range(coin_id, from_timestamp, to_timestamp):
    """
    Ruft historische Preise für eine Kryptowährung in einem Zeitraum ab.
    Benutzt CoinGecko's market_chart/range Endpoint.
    Parameter: coin_id → z.B. "bitcoin"
               from_timestamp/to_timestamp → Unix Timestamps (int)
    Gibt eine Liste von Dictionaries mit date und price (EUR) zurück.
    """
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart/range"
    params = {
        "vs_currency": "eur",
        "from": from_timestamp,
        "to": to_timestamp,
        "x_cg_demo_api_key": os.getenv("COINGECKO_API_KEY")
    }

    try:
        response = requests.get(url, params=params)
        data = response.json()

        # CoinGecko liefert mehrere Preise pro Tag - nur einen pro Tag behalten
        result = []
        seen_dates = set()
        for timestamp_ms, price in data['prices']:
            date_str = datetime.fromtimestamp(timestamp_ms / 1000).strftime('%Y-%m-%d')
            if date_str not in seen_dates:
                seen_dates.add(date_str)
                result.append({"date": date_str, "price": round(price, 2)})

        return result
    except Exception as e:
        print(f"Error fetching crypto historical range: {e}")
        return []


def search_web(query):
    """
    Sucht aktuelle Informationen im Web.
    Benutzt Tavily - speziell für LLMs optimiert.
    Parameter: query → Suchanfrage z.B. "Bitcoin Kurs aktuell"
    Gibt Suchergebnisse als Text zurück oder None bei Fehler.
    """
    try:
        tavily = TavilySearch(
            max_results=3,
            api_key=os.getenv("TAVILY_API_KEY")
        )
        results = tavily.invoke(query)
        return results
    except Exception as e:
        print(f"Error searching web: {e}")
        return None


def get_dividends_since(symbol, since_date):
    """
    Ruft alle Dividendenausschüttungen eines Assets seit einem
    bestimmten Datum ab. Gibt eine Liste von Dictionaries mit
    date und amount_per_share zurück (in der Originalwährung von
    Yahoo Finance, meist USD für US-Aktien).
    """
    try:
        ticker = yf.Ticker(symbol)
        dividends = ticker.dividends

        if dividends.empty:
            return []

        result = []
        for date, amount in dividends.items():
            # Zeitzone entfernen, damit der Vergleich mit unseren
            # eigenen, naiven datetime-Objekten funktioniert
            dividend_date = date.tz_localize(None) if date.tzinfo else date

            if dividend_date > since_date:
                result.append({
                    "date": dividend_date.strftime('%Y-%m-%d'),
                    "amount_per_share": round(float(amount), 4)
                })

        return result
    except Exception as e:
        print(f"Error fetching dividends: {e}")
        return []
    

# Testaufruf - wird nur ausgeführt wenn diese Datei direkt gestartet wird
if __name__ == "__main__":
    print(get_stock_price("AAPL"))
    print(get_stock_price("NVDA"))
    print(get_metal_price("GOLD"))
    print(get_exchange_rate("USD", "EUR"))