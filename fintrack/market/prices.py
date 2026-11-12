"""
prices.py - Zentraler Zugriff auf den aktuellen Preis eines Assets in Euro.
Der Kurs kommt in der Handelswährung von yfinance und wird mit dem
aktuellen Wechselkurs umgerechnet - Euro-Titel wie SAP.DE oder BTC-EUR
werden also nicht mehr fälschlich von Dollar in Euro "umgerechnet".

Liefert keine Quelle einen Live-Kurs (market/quotes.py), gilt der letzte
gespeicherte Schlusskurs, damit ein Ausfall nicht den Depotwert verfälscht.
"""

import logging
from datetime import date
from time import time

from fintrack.market import quotes
from fintrack.market.service import latest_fx_rate, price_in_eur_on

logger = logging.getLogger(__name__)

# Live-Preise kurz zwischenspeichern, damit z.B. das mehrfache Laden der
# Portfolio-Seite nicht jedes Mal yfinance abfragt. Läuft im Prozess,
# passend zu einem einzelnen Gunicorn-Worker.
CACHE_SECONDS = 120
_cache = {}


def clear_cache():
    _cache.clear()


def get_current_price(asset, unknown_type_default=None):
    """
    Aktueller Preis eines Assets in Euro. Gibt es keinen Live-Kurs, gilt der
    letzte gespeicherte Schlusskurs. Fehlt auch der, kommt unknown_type_default
    zurück (manche Aufrufer setzen dort den Kaufpreis als Ersatzwert ein), sonst None.
    """
    cached = _cache.get(asset.symbol)
    if cached and time() - cached[1] < CACHE_SECONDS:
        return cached[0]

    try:
        quote = quotes.fetch_last_price(asset.symbol)
        rate = latest_fx_rate(quote[1]) if quote else None
    except Exception:
        logger.exception('Live-Preis für %s nicht verfügbar', asset.symbol)
        quote, rate = None, None

    if quote and rate is not None:
        price = round(quote[0] * rate, 2)
    else:
        stored = price_in_eur_on(asset, date.today())
        if stored is None:
            return unknown_type_default
        price = round(stored, 2)
    _cache[asset.symbol] = (price, time())
    return price
