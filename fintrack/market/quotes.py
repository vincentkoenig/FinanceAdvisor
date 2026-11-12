"""
quotes.py - Die Kette der Kursquellen: zuerst yfinance, und wenn das einen Fehler
wirft oder nichts liefert, die passende Ersatzquelle aus market/fallback.py.
Alle Stellen, die Kurse oder Wechselkurse laden, fragen hier statt direkt bei yahoo.py.

Metadaten, Suche, Dividenden und Splits gibt es nur bei yfinance und laufen weiter
direkt über yahoo.py.
"""

import logging

from fintrack.market import fallback, yahoo

logger = logging.getLogger(__name__)


def _from_yahoo(name, *args):
    """
    Ruft eine yahoo.py-Funktion auf und gibt (Ergebnis, Fehler) zurück. Ein Fehler
    zählt erst einmal wie ein leeres Ergebnis; liefert auch die Ersatzquelle nichts,
    wird er weitergegeben, damit er in der Zusammenfassung des Laufs steht.
    """
    try:
        return getattr(yahoo, name)(*args), None
    except Exception as error:
        logger.warning('yfinance %s(%s) fehlgeschlagen: %s', name, args[0], error)
        return None, error


def fetch_daily_closes_with_source(symbol, start, end=None):
    """
    Tagesschlusskurse wie yahoo.fetch_daily_closes, dazu der Name der Quelle,
    die sie geliefert hat ('yfinance', 'alphavantage', 'coingecko', 'ezb' oder None).
    """
    closes, error = _from_yahoo('fetch_daily_closes', symbol, start, end)
    if closes:
        return closes, 'yfinance'
    closes, source = fallback.fetch_daily_closes(yahoo.yahoo_symbol(symbol), start, end)
    if closes:
        logger.info('Kurse für %s aus Ersatzquelle %s', symbol, source)
        return closes, source
    if error:
        raise error
    return [], None


def fetch_daily_closes(symbol, start, end=None):
    return fetch_daily_closes_with_source(symbol, start, end)[0]


def fetch_fx_closes_with_source(currency, start, end=None):
    """Wechselkurse wie yahoo.fetch_fx_closes, dazu der Name der Quelle."""
    rates, error = _from_yahoo('fetch_fx_closes', currency, start, end)
    if rates:
        return rates, 'yfinance'
    rates = fallback.fetch_fx_closes(currency, start, end)
    if rates:
        logger.info('Wechselkurs %s aus Ersatzquelle ezb', currency)
        return rates, 'ezb'
    if error:
        raise error
    return [], None


def fetch_fx_closes(currency, start, end=None):
    return fetch_fx_closes_with_source(currency, start, end)[0]


def fetch_last_price(symbol):
    """Aktueller Kurs wie yahoo.fetch_last_price: (Kurs, Währung) oder None."""
    quote, _ = _from_yahoo('fetch_last_price', symbol)
    if quote:
        return quote
    return fallback.fetch_last_price(yahoo.yahoo_symbol(symbol))
