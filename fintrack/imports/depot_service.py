"""
imports/depot_service.py - Aus Abrechnungen gelesene Käufe und Verkäufe prüfen und ins Depot übernehmen.

Vorschau je Ausführung:
- Wertpapier über die ISIN suchen (Euro-Börsen zuerst, wie die normale Suche)
- 'duplicate':    gleicher Kauf/Verkauf (Asset, Tag, Stück) ist schon gebucht
- 'unknown':      zur ISIN wurde nichts gefunden - lässt sich so nicht übernehmen
- 'insufficient': Verkauf von mehr Stück, als nach den Käufen davor im Depot wären
- 'new':          kann übernommen werden
Als Preis zählt der Kurs inklusive Gebühren je Stück (beim Verkauf abzüglich) -
so stimmt der Einstand mit dem überein, was tatsächlich bezahlt wurde.
"""

import hashlib
from collections import defaultdict
from datetime import datetime

from fintrack.api import ApiError
from fintrack.extensions import db
from fintrack.imports.depot_pdf import ISIN
from fintrack.market.search import create_asset, search_assets
from fintrack.models import Asset, AssetTransaction, UserAsset
from fintrack.portfolio.service import record_buy, record_sell

QUANTITY_EPSILON = 1e-6


def effective_price(trade_type, price, fees, quantity):
    """Kurs inklusive Gebühren je Stück (Kauf teurer, Verkauf weniger Erlös)."""
    per_share = fees / quantity if quantity else 0
    return round(price + per_share if trade_type == 'buy' else price - per_share, 4)


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


def _find_asset(isin, cache):
    """Bestes Suchergebnis zur ISIN (Euro-Börse zuerst) oder None."""
    if isin not in cache:
        results = search_assets(isin)
        match = dict(results[0]) if results else None
        # Die Suche kennt Assets nur über Name/Symbol, nicht über die ISIN: schon angelegte nachschlagen
        if match and match['asset_id'] is None:
            known = Asset.query.filter_by(symbol=match['symbol']).first()
            match['asset_id'] = known.id if known else None
        cache[isin] = match
    return cache[isin]


def build_depot_preview(user_id, trades):
    """trades: Liste von ExtractedTrade. Gibt die Vorschau-Einträge zurück, nach Datum sortiert."""
    cache = {}
    holdings = defaultdict(float)
    for position in UserAsset.query.filter_by(user_id=user_id).all():
        holdings[position.asset_id] += position.quantity or 0

    entries = []
    # Käufe vor Verkäufen am selben Tag, damit ein Verkauf die Stücke aus dem Kauf sieht
    for trade in sorted(trades, key=lambda t: (t.trade_date, t.type != 'buy')):
        isin = trade.isin.strip().upper()
        valid = bool(ISIN.fullmatch(isin)) and trade.quantity > 0 and trade.price > 0 and trade.fees >= 0
        match = _find_asset(isin, cache) if valid else None
        price = effective_price(trade.type, trade.price, trade.fees, trade.quantity) if valid else None
        entry = {
            "key": hashlib.sha256(f'{isin}|{trade.type}|{trade.trade_date}|{trade.quantity}|{trade.price}'
                                  .encode()).hexdigest()[:24],
            "type": trade.type, "isin": isin, "name": trade.name, "date": trade.trade_date.isoformat(),
            "quantity": trade.quantity, "price": price, "quote": trade.price, "fees": trade.fees,
            "symbol": match['symbol'] if match else None,
            "asset_name": match['name'] if match else None,
            "asset_id": match['asset_id'] if match else None,
            "status": 'new',
        }
        if not valid or match is None:
            entry["status"] = 'unknown'
        elif _already_booked(user_id, match['asset_id'], trade.type, trade.trade_date, trade.quantity):
            entry["status"] = 'duplicate'
        else:
            holding_key = match['asset_id'] or match['symbol']
            if trade.type == 'buy':
                holdings[holding_key] += trade.quantity
            elif holdings[holding_key] + QUANTITY_EPSILON < trade.quantity:
                entry["status"] = 'insufficient'
            else:
                holdings[holding_key] -= trade.quantity
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
