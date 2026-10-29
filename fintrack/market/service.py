"""
market/service.py - Kurse und Wechselkurse speichern, aktualisieren und in
Euro umrechnen.

Grundregel: Gespeichert wird immer in der Handelswährung des Assets
(PriceHistory.currency). In Euro umgerechnet wird erst beim Anzeigen, mit
dem Wechselkurs des jeweiligen Tages (FxRate). So bleiben historische
Werte korrekt, auch wenn sich der Wechselkurs später ändert.

Aktualisierung: Bei jedem Lauf werden die letzten ROLLING_DAYS Tage neu
geladen und überschrieben. Ein Zwischenstand während der Handelszeit wird
dadurch beim nächsten Lauf automatisch durch den Schlusskurs ersetzt, und
ausgefallene Läufe werden nachgeholt.
"""

import logging
from bisect import bisect_right
from datetime import date, datetime, timedelta

from fintrack.extensions import db
from fintrack.market import yahoo
from fintrack.models import Asset, FxRate, PriceHistory

logger = logging.getLogger(__name__)

# So viele Tage werden bei jedem Lauf neu geladen und überschrieben
ROLLING_DAYS = 7
# So weit zurück wird die Historie für neue Assets geladen
INITIAL_HISTORY_DAYS = 365
# Nach dieser Zeit werden Währung, Typ und Börse erneut abgefragt
METADATA_MAX_AGE = timedelta(days=30)


def _midnight(day):
    return datetime.combine(day, datetime.min.time())


# ─── METADATEN ────────────────────────────────────────────────────────────────

def refresh_asset_metadata(asset, force=False):
    """
    Holt Handelswährung, Typ und Börse bei yfinance, falls noch nie oder vor
    längerer Zeit geschehen. Gibt False zurück, wenn yfinance das Symbol
    nicht kennt.
    """
    fresh = asset.metadata_updated_at and datetime.now() - asset.metadata_updated_at < METADATA_MAX_AGE
    if fresh and not force:
        return True

    metadata = yahoo.fetch_metadata(asset.symbol)
    if not metadata:
        return False

    asset.currency = metadata['currency']
    asset.asset_type = metadata['asset_type']
    asset.exchange = metadata['exchange']
    asset.metadata_updated_at = datetime.now()
    return True


# ─── KURSE SPEICHERN ──────────────────────────────────────────────────────────

def _upsert_prices(asset, closes):
    """Speichert Schlusskurse, ein vorhandener Tag wird überschrieben."""
    if not closes:
        return 0
    existing = {row.date.date(): row for row in PriceHistory.query.filter(
        PriceHistory.asset_id == asset.id,
        PriceHistory.date >= _midnight(closes[0][0])).all()}

    for day, close, currency in closes:
        row = existing.get(day)
        if row:
            row.price = close
            row.currency = currency
        else:
            db.session.add(PriceHistory(asset_id=asset.id, date=_midnight(day), price=close, currency=currency))
    return len(closes)


def update_asset_prices(asset, today=None):
    """
    Lädt die Schlusskurse eines Assets nach: ohne Historie ein ganzes Jahr,
    sonst ab dem letzten gespeicherten Tag, mindestens aber die letzten
    ROLLING_DAYS Tage. Gibt die Anzahl gespeicherter Tage zurück.
    """
    today = today or date.today()
    last = PriceHistory.query.filter_by(asset_id=asset.id).order_by(PriceHistory.date.desc()).first()

    if last is None:
        start = today - timedelta(days=INITIAL_HISTORY_DAYS)
    else:
        start = min(last.date.date() + timedelta(days=1), today - timedelta(days=ROLLING_DAYS))

    return _upsert_prices(asset, yahoo.fetch_daily_closes(asset.symbol, start, today))


def update_fx_rates(currency, today=None):
    """Wie update_asset_prices, nur für den Wechselkurs einer Währung nach Euro."""
    if currency == 'EUR':
        return 0
    today = today or date.today()
    last = FxRate.query.filter_by(currency=currency).order_by(FxRate.date.desc()).first()
    if last is None:
        start = today - timedelta(days=INITIAL_HISTORY_DAYS)
    else:
        start = min(last.date + timedelta(days=1), today - timedelta(days=ROLLING_DAYS))

    closes = yahoo.fetch_fx_closes(currency, start, today)
    existing = {row.date: row for row in FxRate.query.filter(
        FxRate.currency == currency, FxRate.date >= start).all()}
    for day, rate in closes:
        if day in existing:
            existing[day].rate_to_eur = rate
        else:
            db.session.add(FxRate(currency=currency, date=day, rate_to_eur=rate))
    return len(closes)


def update_all_prices(today=None):
    """
    Täglicher Lauf: Metadaten, Kurse und Wechselkurse aller Assets
    aktualisieren. Ein Fehler bei einem Asset bricht den Lauf nicht ab.
    Gibt eine Zusammenfassung zurück.
    """
    summary = {'assets': 0, 'prices': 0, 'fx_rates': 0, 'errors': []}
    currencies = set()

    for asset in Asset.query.order_by(Asset.id).all():
        try:
            if not refresh_asset_metadata(asset):
                summary['errors'].append(f'{asset.symbol}: bei yfinance unbekannt')
                db.session.commit()
                continue
            summary['prices'] += update_asset_prices(asset, today)
            currencies.add(asset.currency)
            summary['assets'] += 1
            db.session.commit()
        except Exception as error:
            db.session.rollback()
            logger.exception('Kurse für %s konnten nicht aktualisiert werden', asset.symbol)
            summary['errors'].append(f'{asset.symbol}: {error}')

    for currency in sorted(c for c in currencies if c):
        try:
            summary['fx_rates'] += update_fx_rates(currency, today)
            db.session.commit()
        except Exception as error:
            db.session.rollback()
            logger.exception('Wechselkurs %s konnte nicht aktualisiert werden', currency)
            summary['errors'].append(f'Wechselkurs {currency}: {error}')

    return summary


def prepare_new_asset(asset):
    """
    Für ein gerade angelegtes Asset: Metadaten holen, ein Jahr Kurse und die
    passenden Wechselkurse laden. Committet selbst.
    """
    refresh_asset_metadata(asset, force=True)
    stored = update_asset_prices(asset)
    if asset.currency:
        update_fx_rates(asset.currency)
    db.session.commit()
    return stored


# ─── UMRECHNUNG IN EURO ───────────────────────────────────────────────────────

class FxTable:
    """
    Alle gespeicherten Wechselkurse einer Währung, für schnelle Abfragen
    "Kurs am Tag X". An Tagen ohne Kurs (Wochenende, Feiertag) gilt der
    letzte bekannte Kurs davor.
    """

    def __init__(self, currency):
        self.currency = currency
        rows = [] if currency in (None, 'EUR') else \
            FxRate.query.filter_by(currency=currency).order_by(FxRate.date).all()
        self.days = [row.date for row in rows]
        self.rates = [row.rate_to_eur for row in rows]

    def rate_on(self, day):
        """Wert von 1 Einheit der Währung in Euro an diesem Tag, oder None."""
        if self.currency in (None, 'EUR'):
            return 1.0
        index = bisect_right(self.days, day) - 1
        if index < 0:
            # Vor dem ersten bekannten Kurs: den ersten verwenden
            return self.rates[0] if self.rates else None
        return self.rates[index]


def fx_rate_on(currency, day):
    """Bequemer Einzelaufruf von FxTable.rate_on."""
    return FxTable(currency).rate_on(day)


def latest_fx_rate(currency):
    """
    Aktuellster Wechselkurs: aus der Datenbank, sonst live bei yfinance.
    Gibt None zurück, wenn keiner zu bekommen ist.
    """
    if currency in (None, 'EUR'):
        return 1.0
    row = FxRate.query.filter_by(currency=currency).order_by(FxRate.date.desc()).first()
    if row and (date.today() - row.date).days <= ROLLING_DAYS:
        return row.rate_to_eur
    live = yahoo.fetch_last_price(f'{currency}EUR=X')
    if live:
        return live[0]
    return row.rate_to_eur if row else None


def price_history_in_eur(asset):
    """
    Gespeicherte Tagesschlusskurse eines Assets in Euro, älteste zuerst,
    als Liste von (Datum, Kurs in Euro). Jeder Tag mit seinem eigenen
    Wechselkurs.
    """
    rows = PriceHistory.query.filter_by(asset_id=asset.id).filter(PriceHistory.price.isnot(None)) \
        .order_by(PriceHistory.date).all()
    tables = {}
    result = []
    for row in rows:
        currency = row.currency or asset.currency or 'EUR'
        table = tables.setdefault(currency, FxTable(currency))
        rate = table.rate_on(row.date.date())
        if rate is not None:
            result.append((row.date.date(), round(row.price * rate, 4)))
    return result


def price_in_eur_on(asset, day):
    """Letzter bekannter Schlusskurs eines Assets bis einschließlich day, in Euro."""
    row = PriceHistory.query.filter(PriceHistory.asset_id == asset.id,
                                    PriceHistory.date <= _midnight(day),
                                    PriceHistory.price.isnot(None)) \
        .order_by(PriceHistory.date.desc()).first()
    if not row:
        return None
    rate = fx_rate_on(row.currency or asset.currency or 'EUR', row.date.date())
    return row.price * rate if rate is not None else None


def quote_in_eur(symbol):
    """
    Aktueller Kurs eines beliebigen Symbols in Euro (z.B. für den Chat),
    unabhängig davon, ob es als Asset gespeichert ist.
    """
    quote = yahoo.fetch_last_price(symbol)
    if not quote:
        return None
    price, currency = quote
    rate = latest_fx_rate(currency)
    return round(price * rate, 2) if rate is not None else None
