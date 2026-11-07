"""
imports/depot_service.py - Aus Abrechnungen gelesene Käufe und Verkäufe prüfen und ins Depot übernehmen.

Vorschau je Ausführung:
- Wertpapier über die ISIN suchen (Euro-Börsen zuerst, wie die normale Suche);
  Kryptowährungen aus einem CSV-Export kommen mit Kürzel ("BTC") und werden als Euro-Paar
  ("BTC-EUR") gesucht, wie überall in FinTrack
- 'duplicate':    gleicher Kauf/Verkauf (Asset, Tag, Stück) ist schon gebucht
- 'unknown':      zur ISIN wurde nichts gefunden - lässt sich so nicht übernehmen
- 'insufficient': Verkauf von mehr Stück, als nach den Käufen davor im Depot wären
- 'invalid':      Stück oder Kurs fehlen, oder das Datum liegt in der Zukunft
Fressen beim Verkauf die Gebühren den Erlös auf (z.B. Wirecard nach der Insolvenz), wird er zu 0 €
gebucht: Die Stücke sind weg, sonst bliebe die Position für immer im Depot.
- 'new':          kann übernommen werden
Aktiensplits nach dem Handelstag werden eingerechnet (1 Tesla von 2020 sind nach 5:1 und 3:1 heute 15),
weil auch die Kurshistorie um Splits bereinigt ist. Findet die Suche die ISIN nicht, wird über den
Namen gesucht; solche Treffer sind markiert (found_by = 'name'), damit man sie prüft.
Als Preis zählt der Kurs inklusive Gebühren je Stück (beim Verkauf abzüglich) -
so stimmt der Einstand mit dem überein, was tatsächlich bezahlt wurde.
"""

import hashlib
import logging
import re
from collections import defaultdict
from datetime import date, datetime

from fintrack.api import ApiError
from fintrack.extensions import db
from fintrack.imports.crypto_csv import TICKER
from fintrack.imports.depot_pdf import ISIN
from fintrack.market import yahoo
from fintrack.market.search import create_asset, search_assets
from fintrack.models import Asset, AssetTransaction, UserAsset
from fintrack.portfolio.service import QUANTITY_EPSILON, record_buy, record_sell


def effective_price(trade_type, price, fees, quantity):
    """Kurs inklusive Gebühren je Stück (Kauf teurer, Verkauf weniger Erlös)."""
    per_share = fees / quantity if quantity else 0
    # 8 Stellen: Kryptowährungen kosten teils Bruchteile eines Cents und dürfen nicht auf 0 fallen
    return round(price + per_share if trade_type == 'buy' else price - per_share, 8)


def _midnight(day):
    return datetime.combine(day, datetime.min.time())


def _already_booked(user_id, asset_id, trade_type, day, quantity):
    if asset_id is None:
        return False
    start = _midnight(day)
    end = datetime(day.year, day.month, day.day, 23, 59, 59)
    for existing in AssetTransaction.query.filter(
            AssetTransaction.user_id == user_id, AssetTransaction.asset_id == asset_id,
            AssetTransaction.type == trade_type, AssetTransaction.date >= start, AssetTransaction.date <= end).all():
        if abs(existing.quantity - quantity) < QUANTITY_EPSILON:
            return True
    return False


logger = logging.getLogger(__name__)

# Rechtsformen und Kürzel, die eine Suche über den Namen nur stören
_NAME_NOISE = {'AG', 'SE', 'INC', 'NV', 'N', 'V', 'CO', 'CORP', 'PLC', 'SA', 'HOLDING', 'GMBH', 'LTD', 'KGAA', 'ADR', 'REG', 'SHS'}


def _name_query(name):
    """'TAIWAN SEMICONDUCT.MANUFACT.CO' -> 'TAIWAN SEMICONDUCT' (die ersten zwei aussagekräftigen Wörter)"""
    words = [word for word in re.split(r'[\s.,/()-]+', name or '') if word and word.upper() not in _NAME_NOISE]
    return ' '.join(words[:2])


def _find_asset(isin, cache, name=None):
    """Bestes Suchergebnis zur ISIN (Euro-Börse zuerst), sonst über den Namen, oder None."""
    if isin not in cache:
        results = search_assets(isin)
        found_by = 'isin'
        query = _name_query(name)
        if not results and query:
            results = search_assets(query)
            found_by = 'name'
        match = dict(results[0], found_by=found_by) if results else None
        # Die Suche kennt Assets nur über Name/Symbol, nicht über die ISIN: schon angelegte nachschlagen
        if match and match['asset_id'] is None:
            known = Asset.query.filter_by(symbol=match['symbol']).first()
            match['asset_id'] = known.id if known else None
        cache[isin] = match
    return cache[isin]


def _find_crypto(ticker, cache):
    """Kryptowährung als Euro-Paar (BTC -> BTC-EUR), wenn FinTrack sie kennt oder Yahoo sie liefert."""
    symbol = f'{ticker}-EUR'
    if symbol not in cache:
        known = Asset.query.filter_by(symbol=symbol).first()
        if known:
            cache[symbol] = {'symbol': symbol, 'name': known.name, 'asset_id': known.id}
        else:
            cache[symbol] = {'symbol': symbol, 'name': f'{ticker} EUR', 'asset_id': None}                 if yahoo.fetch_metadata(symbol) else None
    return cache[symbol]


def _split_factor(symbol, day, cache):
    """Wie viele Stück heute aus einem Stück am Tag day geworden sind (Splits danach multipliziert)."""
    key = f'splits:{symbol}'
    if key not in cache:
        try:
            cache[key] = yahoo.fetch_splits(symbol)
        except Exception:
            logger.warning('Splits für %s nicht abrufbar', symbol, exc_info=True)
            cache[key] = []
    factor = 1.0
    for split_day, ratio in cache[key]:
        # Nur echte Splits (2:1, 3:2, 1:10 ...). Yahoo führt auch Abspaltungen als "Split" mit krummem
        # Faktor nahe 1 (Merck/Organon 1,048): Die Stückzahl im Depot ändert sich dabei nicht
        if split_day > day and (ratio >= 1.5 or ratio <= 2 / 3):
            factor *= ratio
    return factor


def _identify(identifier, cache, name=None):
    """ISIN (Wertpapier) oder Kürzel (Kryptowährung) -> Suchtreffer oder None."""
    if ISIN.fullmatch(identifier):
        return _find_asset(identifier, cache, name)
    if TICKER.fullmatch(identifier):
        return _find_crypto(identifier, cache)
    return None


def build_depot_preview(user_id, trades, apply_splits=True):
    """
    trades: Liste von ExtractedTrade. Gibt die Vorschau-Einträge zurück, nach Datum sortiert.
    apply_splits=False für Quellen, die Splits schon selbst eingerechnet haben (Trade-Republic-Export).
    """
    cache = {}
    holdings = defaultdict(float)
    for position in UserAsset.query.filter_by(user_id=user_id).all():
        holdings[position.asset_id] += position.quantity or 0

    entries = []
    # Käufe vor Verkäufen am selben Tag, damit ein Verkauf die Stücke aus dem Kauf sieht
    for trade in sorted(trades, key=lambda t: (t.trade_date, t.type != 'buy')):
        isin = trade.isin.strip().upper()
        valid = trade.quantity > 0 and trade.price > 0 and trade.fees >= 0 and trade.trade_date <= date.today()
        price = effective_price(trade.type, trade.price, trade.fees, trade.quantity) if valid else None
        if valid and trade.type == 'sell':
            price = max(price, 0.0)
        valid = valid and (price > 0 or trade.type == 'sell')
        price = price if valid else None
        match = _identify(isin, cache, trade.name) if valid else None
        split = _split_factor(match['symbol'], trade.trade_date, cache) if match and apply_splits else 1.0
        quantity = round(trade.quantity * split, 8)
        entry = {
            "key": hashlib.sha256(f'{isin}|{trade.type}|{trade.trade_date}|{trade.quantity}|{trade.price}'
                                  .encode()).hexdigest()[:24],
            "type": trade.type, "isin": isin, "name": trade.name, "date": trade.trade_date.isoformat(),
            "quantity": quantity, "price": round(price / split, 8) if price else price,
            "quote": round(trade.price / split, 8), "fees": trade.fees,
            "split_factor": split, "found_by": match.get('found_by') if match else None,
            "symbol": match['symbol'] if match else None,
            "asset_name": match['name'] if match else None,
            "asset_id": match['asset_id'] if match else None,
            "status": 'new',
        }
        if not valid:
            entry["status"] = 'invalid'
        elif match is None:
            entry["status"] = 'unknown'
        elif _already_booked(user_id, match['asset_id'], trade.type, trade.trade_date, quantity):
            entry["status"] = 'duplicate'
        else:
            holding_key = match['asset_id'] or match['symbol']
            if trade.type == 'buy':
                holdings[holding_key] += quantity
            elif holdings[holding_key] + QUANTITY_EPSILON < quantity:
                entry["status"] = 'insufficient'
            else:
                holdings[holding_key] -= quantity
        entries.append(entry)
    return entries


def commit_trades(user_id, trades):
    """
    Bucht die bestätigten Ausführungen in zeitlicher Reihenfolge über dieselbe Logik wie
    Kauf/Verkauf von Hand. Fehlende Assets werden angelegt (mit Kurshistorie).
    Schon gebuchte werden übersprungen. Gibt (gebucht, übersprungen) zurück.
    """
    assets = {}
    for trade in trades:
        if trade.symbol not in assets:
            asset = Asset.query.filter_by(symbol=trade.symbol.upper()).first()
            assets[trade.symbol] = asset or create_asset(trade.symbol, trade.name)[0]

    booked, skipped = 0, 0
    for trade in sorted(trades, key=lambda t: (t.date, t.type != 'buy')):
        asset = assets[trade.symbol]
        if _already_booked(user_id, asset.id, trade.type, trade.date, trade.quantity):
            skipped += 1
            continue
        when = _midnight(trade.date)
        if trade.type == 'buy':
            record_buy(user_id, asset.id, trade.quantity, trade.price, when)
        else:
            try:
                record_sell(user_id, asset.id, trade.quantity, trade.price, when)
            except ApiError as error:
                db.session.rollback()
                raise ApiError(error.status, f'{trade.name} am {trade.date:%d.%m.%Y}: {error.message}')
        booked += 1
    db.session.commit()
    return booked, skipped
