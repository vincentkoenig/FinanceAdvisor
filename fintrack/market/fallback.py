"""
fallback.py - Ersatzquellen für Kurse, wenn yfinance ausfällt oder nichts liefert.
Welche Quelle zuerst gefragt wird, entscheidet market/quotes.py; hier steht nur,
wie jede Ersatzquelle abgefragt wird. Alle Funktionen geben dieselben Formen
zurück wie market/yahoo.py und werfen keine Fehler: Klappt etwas nicht, kommt
eine leere Liste oder None zurück.

- Wechselkurse: Referenzkurse der Europäischen Zentralbank (kostenlos, ohne Schlüssel)
- Kryptowährungen: CoinGecko (optional mit COINGECKO_API_KEY)
- Aktien und ETFs: Alpha Vantage (ALPHAVANTAGE_API_KEY). Der kostenlose Schlüssel
  erlaubt nur 25 Abfragen am Tag und eine pro Sekunde, deshalb nur für Tageskurse
  im täglichen Lauf, nie für Live-Kurse beim Laden einer Seite.
"""

import csv
import io
import logging
import os
import re
import threading
from datetime import date, datetime, timedelta, timezone
from time import monotonic, sleep

import requests

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 15

# ─── WECHSELKURSE: EZB ────────────────────────────────────────────────────────

ECB_URL = 'https://data-api.ecb.europa.eu/service/data/EXR/D.{currency}.EUR.SP00.A'
FX_SYMBOL = re.compile(r'^([A-Z]{3})EUR=X$')


def _ecb_rates(currency, params):
    """
    Referenzkurse als Liste von (Datum, Wert von 1 Einheit in Euro). Die EZB
    nennt, wie viel der Währung ein Euro kostet (1 EUR = 1,12 USD), umgerechnet
    wird in die Richtung der App (1 USD = 0,89 EUR).
    """
    try:
        response = requests.get(ECB_URL.format(currency=currency), timeout=TIMEOUT_SECONDS,
                                params={**params, 'format': 'csvdata'})
        if response.status_code == 404:  # Währung ohne EZB-Referenzkurs
            return []
        response.raise_for_status()
        rates = []
        for row in csv.DictReader(io.StringIO(response.text)):
            value = float(row['OBS_VALUE']) if row.get('OBS_VALUE') else 0
            if value > 0:
                rates.append((date.fromisoformat(row['TIME_PERIOD']), round(1 / value, 6)))
        return sorted(rates)
    except Exception as error:
        logger.warning('EZB-Kurs %s nicht verfügbar: %s', currency, error)
        return []


def fetch_fx_closes(currency, start, end=None):
    """Wie yahoo.fetch_fx_closes: Liste von (Datum, Wert von 1 Einheit in Euro)."""
    params = {'startPeriod': start.isoformat()}
    if end:
        params['endPeriod'] = end.isoformat()
    return _ecb_rates(currency, params)


def fetch_latest_fx(currency):
    """Neuester EZB-Referenzkurs als Wert von 1 Einheit in Euro, oder None."""
    rates = _ecb_rates(currency, {'lastNObservations': 1})
    return rates[-1][1] if rates else None


# ─── KRYPTO: COINGECKO ────────────────────────────────────────────────────────

COINGECKO_URL = 'https://api.coingecko.com/api/v3'
CRYPTO_SYMBOL = re.compile(r'^([A-Z0-9]+)-(EUR|USD)$')
# Mit dem kostenlosen Schlüssel reicht die Historie höchstens ein Jahr zurück
COINGECKO_MAX_DAYS = 365

# Ticker -> CoinGecko-ID für die gängigen Coins; andere werden über die Suche gefunden
COINGECKO_IDS = {
    'BTC': 'bitcoin', 'ETH': 'ethereum', 'SOL': 'solana', 'XRP': 'ripple', 'ADA': 'cardano',
    'DOGE': 'dogecoin', 'DOT': 'polkadot', 'LTC': 'litecoin', 'LINK': 'chainlink',
    'AVAX': 'avalanche-2', 'POL': 'polygon-ecosystem-token', 'MATIC': 'matic-network',
    'BNB': 'binancecoin', 'TRX': 'tron', 'XLM': 'stellar', 'ATOM': 'cosmos', 'USDT': 'tether',
    'USDC': 'usd-coin', 'SHIB': 'shiba-inu', 'UNI': 'uniswap', 'BCH': 'bitcoin-cash',
    'ETC': 'ethereum-classic',
}
_found_ids = {}


def _coingecko(path, params):
    key = os.getenv('COINGECKO_API_KEY')
    if key:
        params = {**params, 'x_cg_demo_api_key': key}
    response = requests.get(f'{COINGECKO_URL}{path}', params=params, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def _coin_id(ticker):
    """CoinGecko-ID eines Tickers, oder None. Bei mehreren Treffern der größte Coin."""
    if ticker in COINGECKO_IDS:
        return COINGECKO_IDS[ticker]
    if ticker not in _found_ids:
        coins = _coingecko('/search', {'query': ticker}).get('coins', [])
        matches = [coin for coin in coins if (coin.get('symbol') or '').upper() == ticker]
        matches.sort(key=lambda coin: coin.get('market_cap_rank') or 10 ** 9)
        _found_ids[ticker] = matches[0]['id'] if matches else None
    return _found_ids[ticker]


def _crypto(symbol):
    """(CoinGecko-ID, Währung) für Symbole wie BTC-EUR, sonst None."""
    match = CRYPTO_SYMBOL.match(symbol)
    if not match:
        return None
    coin = _coin_id(match.group(1))
    return (coin, match.group(2)) if coin else None


def _crypto_closes(symbol, start, end):
    """
    Tagesschlusskurse von CoinGecko. Die Tageswerte stehen dort auf 0 Uhr UTC; der Wert
    um 0 Uhr ist der Schlusskurs des Vortags, so wie yfinance Krypto-Tage abschließt.
    Der letzte Wert ist der aktuelle Kurs und gilt für heute.
    """
    crypto = _crypto(symbol)
    if not crypto:
        return []
    coin, currency = crypto
    today = datetime.now(timezone.utc).date()
    days = min((today - start).days + 1, COINGECKO_MAX_DAYS)
    data = _coingecko(f'/coins/{coin}/market_chart',
                      {'vs_currency': currency.lower(), 'days': max(days, 1), 'interval': 'daily'})
    closes = {}
    for millis, price in data.get('prices', []):
        moment = datetime.fromtimestamp(millis / 1000, timezone.utc)
        midnight = moment.hour == 0 and moment.minute == 0
        day = moment.date() - timedelta(days=1) if midnight else moment.date()
        closes[day] = round(float(price), 6)
    last_day = end or today
    return [(day, price, currency) for day, price in sorted(closes.items()) if start <= day <= last_day]


def _crypto_last_price(symbol):
    crypto = _crypto(symbol)
    if not crypto:
        return None
    coin, currency = crypto
    price = _coingecko('/simple/price', {'ids': coin, 'vs_currencies': currency.lower()}) \
        .get(coin, {}).get(currency.lower())
    return (float(price), currency) if price else None


# ─── AKTIEN UND ETFS: ALPHA VANTAGE ───────────────────────────────────────────

ALPHAVANTAGE_URL = 'https://www.alphavantage.co/query'
# Yahoo-Börsenkürzel -> (Alpha-Vantage-Kürzel, Währung). Nur Börsen, die getestet sind
# und in einer festen Währung notieren; London (teils Pence, teils Pfund) bewusst nicht.
ALPHAVANTAGE_EXCHANGES = {'DE': ('DEX', 'EUR'), 'PA': ('PAR', 'EUR'), 'AS': ('AMS', 'EUR')}
US_SYMBOL = re.compile(r'^[A-Z]{1,5}$')
ALPHAVANTAGE_DAILY_LIMIT = 25
ALPHAVANTAGE_PAUSE_SECONDS = 1.2

_alphavantage_lock = threading.Lock()
_alphavantage_state = {'day': None, 'calls': 0, 'last': 0.0}


def alphavantage_symbol(symbol):
    """(Alpha-Vantage-Symbol, Währung) zu einem Yahoo-Symbol, oder None, wenn nicht abgedeckt."""
    if US_SYMBOL.match(symbol):
        return symbol, 'USD'
    base, _, suffix = symbol.rpartition('.')
    if base and suffix in ALPHAVANTAGE_EXCHANGES:
        exchange, currency = ALPHAVANTAGE_EXCHANGES[suffix]
        return f'{base}.{exchange}', currency
    return None


def _alphavantage_slot():
    """
    Wartet bis zur nächsten erlaubten Abfrage. Gibt False zurück, wenn das
    Tageskontingent aufgebraucht ist.
    """
    with _alphavantage_lock:
        state = _alphavantage_state
        today = date.today()
        if state['day'] != today:
            state.update(day=today, calls=0)
        if state['calls'] >= ALPHAVANTAGE_DAILY_LIMIT:
            return False
        wait = state['last'] + ALPHAVANTAGE_PAUSE_SECONDS - monotonic()
        if wait > 0:
            sleep(wait)
        state['calls'] += 1
        state['last'] = monotonic()
        return True


def _stock_closes(symbol, start, end):
    """
    Tagesschlusskurse von Alpha Vantage. Der kostenlose Schlüssel liefert nur die
    letzten 100 Handelstage; für den täglichen Lauf mit 7 Tagen reicht das.
    """
    mapped = alphavantage_symbol(symbol)
    key = os.getenv('ALPHAVANTAGE_API_KEY')
    if not mapped or not key or not _alphavantage_slot():
        return []
    av_symbol, currency = mapped
    response = requests.get(ALPHAVANTAGE_URL, timeout=TIMEOUT_SECONDS, params={
        'function': 'TIME_SERIES_DAILY', 'symbol': av_symbol, 'outputsize': 'compact', 'apikey': key})
    response.raise_for_status()
    series = response.json().get('Time Series (Daily)')
    if not series:
        # Kontingent erschöpft oder Symbol unbekannt: Alpha Vantage antwortet dann mit einem Hinweistext
        logger.warning('Alpha Vantage ohne Kurse für %s', av_symbol)
        return []
    last_day = end or date.today()
    closes = []
    for day_text, values in series.items():
        day = date.fromisoformat(day_text)
        if start <= day <= last_day:
            closes.append((day, round(float(values['4. close']), 6), currency))
    return sorted(closes)


# ─── ÖFFENTLICHE FUNKTIONEN ───────────────────────────────────────────────────

def fetch_daily_closes(symbol, start, end=None):
    """
    Wie yahoo.fetch_daily_closes, aus der passenden Ersatzquelle:
    Liste von (Datum, Kurs, Währung), leer wenn keine Quelle das Symbol kennt.
    Gibt außerdem den Namen der Quelle zurück, für die Zusammenfassung des Laufs.
    """
    fx = FX_SYMBOL.match(symbol)
    try:
        if fx:
            return [(day, rate, 'EUR') for day, rate in fetch_fx_closes(fx.group(1), start, end)], 'ezb'
        if CRYPTO_SYMBOL.match(symbol):
            return _crypto_closes(symbol, start, end), 'coingecko'
        return _stock_closes(symbol, start, end), 'alphavantage'
    except Exception as error:
        logger.warning('Ersatzquelle für %s nicht verfügbar: %s', symbol, error)
        return [], None


def fetch_last_price(symbol):
    """
    Wie yahoo.fetch_last_price: (Kurs, Währung) oder None. Nur Wechselkurse und
    Krypto; Aktien bekommen hier nichts, damit Seitenaufrufe nicht das kleine
    Tageskontingent von Alpha Vantage verbrauchen.
    """
    fx = FX_SYMBOL.match(symbol)
    try:
        if fx:
            rate = fetch_latest_fx(fx.group(1))
            return (rate, 'EUR') if rate else None
        if CRYPTO_SYMBOL.match(symbol):
            return _crypto_last_price(symbol)
    except Exception as error:
        logger.warning('Ersatzquelle für %s nicht verfügbar: %s', symbol, error)
    return None
