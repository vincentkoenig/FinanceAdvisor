"""
portfolio/service.py - Fachlogik für Positionen: Käufe und Verkäufe
verbuchen, Durchschnittskaufpreis berechnen und jede Bewegung in der
Transaktionshistorie (AssetTransaction) festhalten.
Wird von den Routen und vom Sparplan genutzt, damit die Rechnung nur an
einer Stelle existiert.
"""

from datetime import datetime

from fintrack.api import ApiError
from fintrack.extensions import db
from fintrack.models import AssetTransaction, UserAsset


def record_buy(user_id, asset_id, quantity, price, date=None):
    """
    Verbucht einen Kauf. Gibt es schon eine Position, wird die Menge erhöht
    und der Durchschnittskaufpreis neu berechnet, sonst wird eine neue
    Position angelegt. Der Aufrufer committet.
    """
    date = date or datetime.now()
    position = UserAsset.query.filter_by(user_id=user_id, asset_id=asset_id).first()

    if position and position.quantity and position.quantity > 0:
        old_value = position.quantity * position.avg_buy_price
        new_quantity = position.quantity + quantity
        position.avg_buy_price = round((old_value + quantity * price) / new_quantity, 2)
        position.quantity = new_quantity
        position.status = 'owned'
    elif position:
        # Früher komplett verkaufte Position wird wiederbelebt
        position.quantity = quantity
        position.avg_buy_price = price
        position.bought_at = date
        position.status = 'owned'
    else:
        position = UserAsset(user_id=user_id, asset_id=asset_id, quantity=quantity,
                             avg_buy_price=price, bought_at=date, status='owned')
        db.session.add(position)

    db.session.add(AssetTransaction(user_id=user_id, asset_id=asset_id, type='buy',
                                    quantity=quantity, price=price, date=date))
    return position


def record_sell(user_id, asset_id, quantity, price=None):
    """
    Verbucht einen Verkauf. Ohne Verkaufspreis wird der
    Durchschnittskaufpreis verbucht. Der Aufrufer committet.
    """
    position = UserAsset.query.filter_by(user_id=user_id, asset_id=asset_id).first()

    if not position or not position.quantity:
        raise ApiError(404, 'Position nicht gefunden')
    if quantity > position.quantity:
        raise ApiError(400, 'Nicht genug Anteile!')

    position.quantity -= quantity
    if position.quantity == 0:
        position.status = 'sold'

    # Zeitpunkt ausdrücklich setzen (wie bei record_buy), statt die
    # Datenbank-Uhr zu nutzen - sonst können Kauf und Verkauf je nach
    # Zeitzone in falscher Reihenfolge in der Historie stehen
    db.session.add(AssetTransaction(user_id=user_id, asset_id=asset_id, type='sell',
                                    quantity=quantity, date=datetime.now(),
                                    price=price if price is not None else position.avg_buy_price))
    return position
