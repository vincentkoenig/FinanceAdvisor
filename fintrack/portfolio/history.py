"""
portfolio/history.py - Bestand und Wert des Portfolios in der
Vergangenheit, rekonstruiert aus den echten Käufen und Verkäufen
(AssetTransaction).

Eine Aktie, die letzte Woche gekauft wurde, zählt erst ab letzter Woche;
eine verkaufte Position zählt bis zum Verkaufstag. Genutzt vom
Wertverlauf-Chart, von den täglichen Insights und von der
Dividendenverbuchung, damit alle dieselbe Rechnung verwenden.

Altbestände: Positionen aus der Zeit vor der Transaktions-Protokollierung
haben weniger (oder gar keine) Transaktionen, als ihre Menge erklärt. Die
Differenz zählt als Anfangsbestand ab dem Kaufdatum der Position.
"""

from bisect import bisect_right
from collections import defaultdict
from datetime import date, timedelta

from fintrack.market.service import price_history_in_eur, price_in_eur_on
from fintrack.models import Asset, AssetTransaction, UserAsset, db

# Rundungsreste aus Float-Mengen (z.B. 0.1 + 0.2 - 0.3) gelten als 0
EPSILON = 1e-9


class Holdings:
    """
    Stückzahl je Asset an jedem Tag. Pro Asset eine sortierte Liste von
    Tagen, an denen sich der Bestand änderte, und dem Bestand danach.
    """

    def __init__(self, user_id, asset_id=None):
        transactions = AssetTransaction.query.filter_by(user_id=user_id)
        positions = UserAsset.query.filter_by(user_id=user_id)
        if asset_id is not None:
            transactions = transactions.filter_by(asset_id=asset_id)
            positions = positions.filter_by(asset_id=asset_id)

        changes = defaultdict(list)
        for transaction in transactions.order_by(AssetTransaction.date, AssetTransaction.id):
            sign = 1 if transaction.type == 'buy' else -1
            changes[transaction.asset_id].append((transaction.date.date(), sign * transaction.quantity))

        # Altbestand: was die aktuelle Menge über die Transaktionen hinaus erklärt
        for position in positions:
            logged = sum(delta for _, delta in changes[position.asset_id])
            missing = (position.quantity or 0) - logged
            if abs(missing) > EPSILON:
                candidates = [day for day, _ in changes[position.asset_id]]
                if position.bought_at:
                    candidates.append(position.bought_at.date())
                start = min(candidates) if candidates else date.min
                changes[position.asset_id].insert(0, (start, missing))

        self.days = {}
        self.quantities = {}
        for asset_id_, deltas in changes.items():
            deltas.sort(key=lambda change: change[0])  # stabil: gleiche Tage behalten ihre Reihenfolge
            days, quantities, running = [], [], 0.0
            for day, delta in deltas:
                running = max(running + delta, 0.0)
                if days and days[-1] == day:
                    quantities[-1] = running
                else:
                    days.append(day)
                    quantities.append(running)
            self.days[asset_id_] = days
            self.quantities[asset_id_] = quantities

    @property
    def asset_ids(self):
        return list(self.days)

    def first_day(self):
        """Erster Tag mit einem Bestand, oder None."""
        starts = [days[0] for days in self.days.values() if days]
        return min(starts) if starts else None

    def quantity_on(self, asset_id, day):
        """Stückzahl am Ende des Tages day (Käufe und Verkäufe dieses Tages zählen mit)."""
        days = self.days.get(asset_id)
        if not days:
            return 0.0
        index = bisect_right(days, day) - 1
        quantity = self.quantities[asset_id][index] if index >= 0 else 0.0
        return quantity if quantity > EPSILON else 0.0


def shares_held_on(user_id, asset_id, day):
    """Stückzahl eines Assets am Ende eines Tages."""
    return Holdings(user_id, asset_id).quantity_on(asset_id, day)


def portfolio_value_on(user_id, day):
    """Wert aller an diesem Tag gehaltenen Positionen in Euro (letzte Schlusskurse bis day)."""
    holdings = Holdings(user_id)
    total = 0.0
    for asset_id in holdings.asset_ids:
        quantity = holdings.quantity_on(asset_id, day)
        if not quantity:
            continue
        price = price_in_eur_on(db.session.get(Asset, asset_id), day)
        if price is not None:
            total += quantity * price
    return total


def portfolio_value_series(user_id, today=None):
    """
    Täglicher Portfolio-Wert in Euro vom ersten Kauf bis heute, als Liste
    von (Tag, Wert). An Wochenenden und Feiertagen gilt der letzte
    Schlusskurs. Tage, an denen für keine gehaltene Position ein Kurs
    bekannt ist, fehlen.
    """
    today = today or date.today()
    holdings = Holdings(user_id)
    first = holdings.first_day()
    if first is None:
        return []

    # Pro Asset die Schlusskurse in Euro, jeder Tag mit eigenem Wechselkurs
    prices = {}
    for asset_id in holdings.asset_ids:
        asset = db.session.get(Asset, asset_id)
        history = price_history_in_eur(asset) if asset else []
        prices[asset_id] = ([day for day, _ in history], [price for _, price in history])

    # Ohne irgendeinen Kurs vor dem Kauf beginnt der Verlauf beim ersten Kurs
    first_price = min((days[0] for days, _ in prices.values() if days), default=None)
    if first_price is None:
        return []

    series = []
    day = max(first, first_price)
    while day <= today:
        total, has_price = 0.0, False
        for asset_id, (days, values) in prices.items():
            quantity = holdings.quantity_on(asset_id, day)
            if not quantity:
                continue
            index = bisect_right(days, day) - 1
            if index < 0:
                continue  # noch kein Kurs für dieses Asset
            total += quantity * values[index]
            has_price = True
        if has_price or series:
            series.append((day, round(total, 2)))
        day += timedelta(days=1)
    return series
