"""
portfolio/lots.py - Kaufposten nach FIFO und realisierte Gewinne.

Jeder Kauf ist ein eigener Kaufposten. Verkäufe verbrauchen die ältesten
Posten zuerst (FIFO, wie es das deutsche Steuerrecht für Depots vorschreibt).
Alles wird bei jeder Abfrage aus AssetTransaction berechnet, es gibt keine
eigene Tabelle. Gebühren stecken dort schon im Preis je Stück (Kauf teurer,
Verkauf billiger), deshalb fließen sie hier automatisch mit ein.

Deckt die Historie nicht den ganzen Bestand ab (z. B. eine Position, die vor
der Einzel-Historie angelegt wurde), gelten die fehlenden Stücke als ältester
Posten zum Durchschnittskaufpreis der Position ("Anfangsbestand").

Die Steuerübersicht ist bewusst eine Schätzung: Sparerpauschbetrag, getrennter
Topf für Aktienverluste, Krypto mit Haltefrist und Freigrenze. Teilfreistellung,
Vorabpauschale, Verlustvorträge aus Vorjahren und Kirchensteuer fehlen.
"""

# Standard Library
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime

# Lokale Imports
from fintrack.extensions import db
from fintrack.models import Asset, AssetTransaction, Dividend, User, UserAsset

# Sparerpauschbetrag: alleinstehend und gemeinsam veranlagt (verheiratet)
TAX_ALLOWANCE = 1000.0
TAX_ALLOWANCE_JOINT = 2000.0
# Freigrenze für private Veräußerungsgeschäfte (Krypto): darunter steuerfrei, darüber alles steuerpflichtig
CRYPTO_EXEMPTION_LIMIT = 1000.0
# Gleiche Toleranz wie portfolio/service.py: Bruchstücke summieren sich nie ganz exakt
EPSILON = 1e-6


@dataclass
class Lot:
    """Ein offener Kaufposten (Rest eines Kaufs)."""
    bought_on: date
    quantity: float
    unit_cost: float
    opening: bool = False


@dataclass
class SaleSlice:
    """Der Teil eines Verkaufs, der einen einzelnen Kaufposten verbraucht."""
    transaction_id: int | None
    sold_on: date
    quantity: float
    unit_price: float
    unit_cost: float
    # None, wenn mehr verkauft wurde als je gekauft (Einstand unbekannt, Gewinn 0)
    bought_on: date | None

    @property
    def gain(self):
        return (self.unit_price - self.unit_cost) * self.quantity


def bucket(asset_type):
    """Steuer-Topf eines Assets: Einzelaktien, Krypto oder alles andere (ETFs, Fonds, Rohstoffe)."""
    if asset_type == 'stock':
        return 'stock'
    if asset_type == 'crypto':
        return 'crypto'
    return 'other'


def held_over_a_year(bought_on, sold_on):
    """Krypto: steuerfrei, wenn zwischen Kauf und Verkauf mehr als ein Jahr liegt."""
    if bought_on is None:
        return False
    try:
        anniversary = bought_on.replace(year=bought_on.year + 1)
    except ValueError:  # 29. Februar
        anniversary = date(bought_on.year + 1, 3, 1)
    return sold_on > anniversary


def tax_free_from(bought_on):
    """Erster Tag, an dem ein Krypto-Verkauf dieses Postens steuerfrei wäre."""
    try:
        anniversary = bought_on.replace(year=bought_on.year + 1)
    except ValueError:
        anniversary = date(bought_on.year + 1, 3, 1)
    return date.fromordinal(anniversary.toordinal() + 1)


def _day(value):
    return value.date() if isinstance(value, datetime) else value


def build_book(transactions, position=None):
    """
    Rechnet die Käufe und Verkäufe eines Assets nach FIFO durch.
    transactions: AssetTransaction-Zeilen eines Assets (beliebige Reihenfolge).
    position: die UserAsset-Zeile oder None.
    Gibt (offene Posten, Verkaufsteile) zurück.
    """
    ordered = sorted(transactions, key=lambda t: (t.date or datetime.min, t.id or 0))
    lots = []
    sales = []

    # Stücke, die keine Buchung erklärt, werden zum ältesten Posten.
    # Ohne Position gilt der Bestand, den die Historie ergibt.
    booked = sum(t.quantity if t.type == 'buy' else -t.quantity for t in ordered)
    held = (position.quantity or 0.0) if position is not None else max(booked, 0.0)
    opening = held - booked
    if position is not None and opening > EPSILON:
        dates = [_day(t.date) for t in ordered if t.date]
        start = _day(position.bought_at) if position.bought_at else None
        if start is None or (dates and dates[0] < start):
            start = dates[0] if dates else date.today()
        lots.append(Lot(start, opening, position.avg_buy_price or 0.0, opening=True))

    for t in ordered:
        day = _day(t.date) or date.today()
        if t.type == 'buy':
            lots.append(Lot(day, t.quantity, t.price))
            continue
        remaining = t.quantity
        while remaining > EPSILON and lots:
            lot = lots[0]
            take = min(lot.quantity, remaining)
            sales.append(SaleSlice(t.id, day, take, t.price, lot.unit_cost, lot.bought_on))
            lot.quantity -= take
            remaining -= take
            if lot.quantity <= EPSILON:
                lots.pop(0)
        if remaining > EPSILON:
            sales.append(SaleSlice(t.id, day, remaining, t.price, t.price, None))

    # Mehr gebucht als im Bestand: die ältesten Stücke fallen weg (ohne Gewinn)
    excess = sum(lot.quantity for lot in lots) - held
    while excess > EPSILON and lots:
        take = min(lots[0].quantity, excess)
        lots[0].quantity -= take
        excess -= take
        if lots[0].quantity <= EPSILON:
            lots.pop(0)

    return lots, sales


def user_books(user_id):
    """FIFO-Bücher aller Assets eines Nutzers: {asset_id: (offene Posten, Verkaufsteile)}."""
    by_asset = defaultdict(list)
    for t in AssetTransaction.query.filter_by(user_id=user_id).all():
        by_asset[t.asset_id].append(t)
    positions = {p.asset_id: p for p in UserAsset.query.filter_by(user_id=user_id).all()}
    return {asset_id: build_book(by_asset.get(asset_id, []), positions.get(asset_id))
            for asset_id in set(by_asset) | set(positions)}


def buy_price(lots):
    """Einstand je Stück der noch offenen Posten (None ohne Bestand)."""
    quantity = sum(lot.quantity for lot in lots)
    if quantity <= EPSILON:
        return None
    return sum(lot.quantity * lot.unit_cost for lot in lots) / quantity


def open_lots(user_id, asset_id, current_price=None, asset_type=None):
    """Offene Kaufposten einer Position, mit Gewinn je Posten, wenn ein Kurs da ist."""
    transactions = AssetTransaction.query.filter_by(user_id=user_id, asset_id=asset_id).all()
    position = UserAsset.query.filter_by(user_id=user_id, asset_id=asset_id).first()
    lots, _ = build_book(transactions, position)
    crypto = bucket(asset_type) == 'crypto'
    result = []
    for lot in lots:
        cost = lot.quantity * lot.unit_cost
        value = lot.quantity * current_price if current_price is not None else None
        result.append({
            "bought_on": lot.bought_on.isoformat(),
            "quantity": round(lot.quantity, 8),
            "unit_cost": round(lot.unit_cost, 4),
            "cost": round(cost, 2),
            "value": round(value, 2) if value is not None else None,
            "gain": round(value - cost, 2) if value is not None else None,
            "gain_pct": round((value / cost - 1) * 100, 2) if value is not None and cost > 0 else None,
            "opening": lot.opening,
            "tax_free_from": tax_free_from(lot.bought_on).isoformat() if crypto else None,
        })
    return result


def _sale_rows(books, assets):
    """Verkaufsteile zu Zeilen je Verkauf zusammenfassen (Krypto getrennt nach steuerfrei/-pflichtig)."""
    rows = {}
    for asset_id, (_, sales) in books.items():
        asset = assets.get(asset_id)
        kind = bucket(asset.asset_type if asset else None)
        for part in sales:
            tax_free = kind == 'crypto' and held_over_a_year(part.bought_on, part.sold_on)
            key = (asset_id, part.transaction_id, part.sold_on, tax_free)
            row = rows.get(key)
            if row is None:
                row = rows[key] = {
                    "asset_id": asset_id,
                    "name": asset.name if asset else '?',
                    "symbol": asset.symbol if asset else '',
                    "asset_type": asset.asset_type if asset else None,
                    "bucket": kind,
                    "date": part.sold_on,
                    "quantity": 0.0, "proceeds": 0.0, "cost": 0.0,
                    "first_bought": part.bought_on,
                    "tax_free": tax_free,
                    "unknown_cost": False,
                }
            row["quantity"] += part.quantity
            row["proceeds"] += part.quantity * part.unit_price
            row["cost"] += part.quantity * part.unit_cost
            row["unknown_cost"] = row["unknown_cost"] or part.bought_on is None
            if part.bought_on and (row["first_bought"] is None or part.bought_on < row["first_bought"]):
                row["first_bought"] = part.bought_on
    return list(rows.values())


def realized_overview(user_id, year=None):
    """
    Realisierte Gewinne eines Jahres mit Steuer-Schätzung.
    Ohne year gilt das laufende Jahr. Liefert auch alle Jahre mit Verkäufen oder Dividenden.
    """
    year = year or date.today().year
    user = db.session.get(User, user_id)
    joint = bool(user and user.tax_joint)
    allowance = TAX_ALLOWANCE_JOINT if joint else TAX_ALLOWANCE
    books = user_books(user_id)
    assets = {a.id: a for a in Asset.query.filter(Asset.id.in_(list(books) or [0])).all()}
    rows = _sale_rows(books, assets)
    dividends = Dividend.query.filter_by(user_id=user_id).all()

    years = {row["date"].year for row in rows} | {_day(d.ex_dividend_date).year for d in dividends}
    years.add(date.today().year)

    sales = sorted((r for r in rows if r["date"].year == year), key=lambda r: r["date"], reverse=True)
    total = defaultdict(float)
    for row in sales:
        gain = row["proceeds"] - row["cost"]
        if row["bucket"] == 'crypto':
            total['crypto_free' if row["tax_free"] else 'crypto_taxable'] += gain
        else:
            total[row["bucket"]] += gain
    dividend_total = sum(d.total_amount for d in dividends if _day(d.ex_dividend_date).year == year)

    # Aktienverluste dürfen nur mit Aktiengewinnen verrechnet werden; allgemeine
    # Verluste (ETFs, Fonds) dagegen mit allem, auch mit Aktiengewinnen
    stock, other = total['stock'], total['other'] + dividend_total
    taxable = max(0.0, other + max(stock, 0.0))
    used = min(taxable, allowance)
    crypto_taxable = total['crypto_taxable']

    return {
        "year": year,
        "years": sorted(years, reverse=True),
        "sales": [{
            **{k: v for k, v in row.items() if k not in ('date', 'first_bought')},
            "date": row["date"].isoformat(),
            "first_bought": row["first_bought"].isoformat() if row["first_bought"] else None,
            "quantity": round(row["quantity"], 8),
            "proceeds": round(row["proceeds"], 2),
            "cost": round(row["cost"], 2),
            "gain": round(row["proceeds"] - row["cost"], 2),
        } for row in sales],
        "securities": {
            "stock_gains": round(stock, 2),
            "other_gains": round(total['other'], 2),
            "dividends": round(dividend_total, 2),
            "taxable": round(taxable, 2),
            "allowance": allowance,
            "joint": joint,
            "allowance_used": round(used, 2),
            "allowance_left": round(allowance - used, 2),
            "above_allowance": round(taxable - used, 2),
            # Aktienverlust, der dieses Jahr nicht verrechnet werden kann
            "stock_loss_carried": round(-stock, 2) if stock < 0 else 0.0,
        },
        "crypto": {
            "taxable_gains": round(crypto_taxable, 2),
            "tax_free_gains": round(total['crypto_free'], 2),
            "exemption_limit": CRYPTO_EXEMPTION_LIMIT,
            # Freigrenze: unter 1.000 € bleibt alles steuerfrei, ab 1.000 € wird alles steuerpflichtig
            "over_limit": crypto_taxable >= CRYPTO_EXEMPTION_LIMIT,
        },
    }
