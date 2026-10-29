"""
prices.py - Zentraler Zugriff auf den aktuellen Preis eines Assets in Euro.
Der Kurs kommt in der Handelswährung von yfinance und wird mit dem
aktuellen Wechselkurs umgerechnet - Euro-Titel wie SAP.DE oder BTC-EUR
werden also nicht mehr fälschlich von Dollar in Euro "umgerechnet".
"""

import logging
from time import time

from fintrack.market import yahoo
from fintrack.market.service import latest_fx_rate

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
    Aktueller Preis eines Assets in Euro. Liefert yfinance keinen Kurs,
    kommt unknown_type_default zurück (manche Aufrufer setzen dort den
    Kaufpreis als Ersatzwert ein), sonst None.
    """
    cached = _cache.get(asset.symbol)
    if cached and time() - cached[1] < CACHE_SECONDS:
        return cached[0]

    try:
        quote = yahoo.fetch_last_price(asset.symbol)
        rate = latest_fx_rate(quote[1]) if quote else None
    except Exception:
        logger.exception('Live-Preis für %s nicht verfügbar', asset.symbol)
        quote, rate = None, None

    if not quote or rate is None:
        return unknown_type_default

    price = round(quote[0] * rate, 2)
    _cache[asset.symbol] = (price, time())
    return price
