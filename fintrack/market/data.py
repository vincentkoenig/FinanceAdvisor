"""
data.py - Externe Abfragen für den KI-Chat:
- get_crypto_price() → CoinGecko für Kryptowährungen (Function Calling)
- search_web()       → Tavily-Websuche
Kurse, Wechselkurse und Historien für Portfolio und Chart kommen
ausschließlich aus market/yahoo.py und market/service.py.
"""

# Standard Library
import os

# Third Party
import requests
from dotenv import load_dotenv
from langchain_tavily import TavilySearch
from functools import wraps
from time import time

# .env Datei laden - API Keys sicher aus .env holen
load_dotenv()

# Einfacher In-Memory-Cache für Live-Preise, um wiederholte API-Calls
# innerhalb kurzer Zeit zu vermeiden (z.B. beim mehrfachen Laden der
# Portfolio-Seite). Läuft im laufenden Server-Prozess, kein externer
# Dienst nötig - passend zu einem einzelnen Gunicorn-Worker.
_price_cache = {}
CACHE_DURATION_SECONDS = 120  # 2 Minuten


def cached_price(func):
    """
    Decorator, der das Ergebnis einer Preis-Funktion für
    CACHE_DURATION_SECONDS zwischenspeichert, getrennt pro
    Funktionsname und übergebenem Symbol/Coin-ID.
    """
    @wraps(func)
    def wrapper(identifier):
        cache_key = (func.__name__, identifier)
        now = time()

        if cache_key in _price_cache:
            cached_value, cached_at = _price_cache[cache_key]
            if now - cached_at < CACHE_DURATION_SECONDS:
                return cached_value

        result = func(identifier)

        # Nur erfolgreiche Ergebnisse cachen - ein None (Fehler)
        # soll beim nächsten Aufruf sofort erneut versucht werden,
        # statt 2 Minuten lang "None" zurückzugeben
        if result is not None:
            _price_cache[cache_key] = (result, now)

        return result

    return wrapper


@cached_price
def get_crypto_price(coin_id):
    """
    Ruft den aktuellen Preis einer Kryptowährung ab.
    Benutzt die CoinGecko API.
    Parameter: coin_id → z.B. "bitcoin", "ethereum", "solana"
    Gibt den Preis in EUR zurück oder None bei Fehler.
    """

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
