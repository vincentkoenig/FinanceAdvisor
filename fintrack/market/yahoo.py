"""
yahoo.py - Einziger Zugriff auf yfinance für Kurse, Metadaten und
Wechselkurse. Alle Werte kommen in der Handelswährung des Symbols zurück -
umgerechnet wird erst in market/service.py.

Bewusst schmal gehalten, damit Tests diese Funktionen durch aufgezeichnete
Daten ersetzen können, ohne echte Netzabfragen.
"""

from datetime import date, timedelta

import yfinance as yf

# Manche Börsen notieren in der Untereinheit der Währung:
# London in Pence (GBp), Johannesburg in Cent (ZAc), Tel Aviv in Agorot (ILA).
# Kurse werden dann durch 100 geteilt und in der Hauptwährung gespeichert.
MINOR_UNITS = {'GBp': 'GBP', 'GBX': 'GBP', 'ZAc': 'ZAR', 'ILA': 'ILS'}

# yfinance-Typ -> Asset-Typ der App
ASSET_TYPES = {
    'EQUITY': 'stock',
    'ETF': 'etf',
    'MUTUALFUND': 'etf',
    'CRYPTOCURRENCY': 'crypto',
    'FUTURE': 'metal',      # z.B. Gold (GC=F) und Silber (SI=F)
}

# Ältere Assets wurden mit Kurzbezeichnungen statt yfinance-Symbolen angelegt
SYMBOL_ALIASES = {'GOLD': 'GC=F', 'SILVER': 'SI=F'}


def yahoo_symbol(symbol):
    """Das Symbol, unter dem yfinance ein Asset kennt."""
    return SYMBOL_ALIASES.get(symbol, symbol)


def normalize_currency(currency):
    """
    Gibt (Hauptwährung, Faktor) zurück, z.B. ('GBP', 0.01) für Pence.
    Kurse werden mit dem Faktor multipliziert.
    """
    if currency in MINOR_UNITS:
        return MINOR_UNITS[currency], 0.01
    return (currency or 'EUR').upper(), 1.0


def fetch_metadata(symbol):
    """
    Währung, Typ und Börse eines Symbols. Gibt None zurück, wenn yfinance
    das Symbol nicht kennt.
    """
    info = yf.Ticker(yahoo_symbol(symbol)).fast_info
    raw_currency = info.get('currency')
    if not raw_currency:
        return None
    currency, _ = normalize_currency(raw_currency)
    return {
        'currency': currency,
        'raw_currency': raw_currency,
        'asset_type': ASSET_TYPES.get(info.get('quoteType'), 'other'),
        'exchange': info.get('exchange'),
    }


def fetch_last_price(symbol):
    """
    Aktueller Kurs in der Hauptwährung des Symbols als (Kurs, Währung),
    oder None, wenn kein Kurs verfügbar ist.
    """
    info = yf.Ticker(yahoo_symbol(symbol)).fast_info
    price = info.get('lastPrice')
    if price is None:
        return None
    currency, factor = normalize_currency(info.get('currency'))
    return float(price) * factor, currency


def fetch_daily_closes(symbol, start, end=None):
    """
    Tages-Schlusskurse von start bis einschließlich end (Standard: heute)
    als Liste von (Datum, Kurs, Währung) in der Hauptwährung des Symbols.
    Bewusst unbereinigte Schlusskurse (auto_adjust=False): Gezeigt werden
    sollen die Kurse, zu denen tatsächlich gehandelt wurde.
    """
    end = end or date.today()
    ticker = yf.Ticker(yahoo_symbol(symbol))
    history = ticker.history(start=start.isoformat(), end=(end + timedelta(days=1)).isoformat(),
                             auto_adjust=False)
    if history is None or history.empty:
        return []

    currency, factor = normalize_currency(ticker.fast_info.get('currency'))
    closes = []
    for timestamp, close in zip(history.index, history['Close']):
        if close != close:  # NaN - kein Handel an diesem Tag
            continue
        closes.append((timestamp.date(), round(float(close) * factor, 6), currency))
    return closes


def fetch_fx_closes(currency, start, end=None):
    """
    Tageskurse "1 Einheit currency in Euro" (z.B. USD -> 0.897) von start
    bis end als Liste von (Datum, Kurs).
    """
    return [(day, rate) for day, rate, _ in fetch_daily_closes(f'{currency}EUR=X', start, end)]


def fetch_dividends(symbol, since):
    """
    Dividenden pro Aktie nach dem Datum since als Liste von (Ex-Tag, Betrag)
    in der Hauptwährung des Symbols.
    """
    ticker = yf.Ticker(yahoo_symbol(symbol))
    dividends = ticker.dividends
    if dividends is None or dividends.empty:
        return []
    _, factor = normalize_currency(ticker.fast_info.get('currency'))
    return [(timestamp.date(), round(float(amount) * factor, 6))
            for timestamp, amount in dividends.items() if timestamp.date() > since]
