"""
contracts/booking.py - Verbindung zwischen Vertrag und Haushaltsbuch.

Ein Vertrag kann zu einer wiederkehrenden Fixkosten-Buchung gehören. Das
Haushaltsbuch kennt nur monatliche Wiederholung, darum wird ein jährlicher
oder vierteljährlicher Beitrag anteilig pro Monat gebucht.

Endet der Vertrag (gekündigt oder feste Laufzeit), endet die Buchung am
selben Tag; wird die Kündigung zurückgenommen, läuft sie wieder weiter.
"""

from datetime import datetime

from fintrack.contracts.terms import contract_status, yearly_cost
from fintrack.extensions import db
from fintrack.models import Transaction


def _as_datetime(day):
    return datetime.combine(day, datetime.min.time()) if day else None


def monthly_amount(contract):
    return round(yearly_cost(contract) / 12, 2)


def create_booking(contract, category, today):
    """
    Legt die Fixkosten-Buchung zum Vertrag an. Sie beginnt frühestens im
    laufenden Monat - sonst würde ein alter Vertrag rückwirkend Monate
    belasten, in denen das Haushaltsbuch noch gar nicht geführt wurde.
    """
    start = max(contract.start_date, today.replace(day=1))
    booking = Transaction(
        user_id=contract.user_id,
        category_id=category.id,
        amount=monthly_amount(contract),
        description=contract.name,
        date=_as_datetime(start),
        is_recurring=True,
        end_date=_as_datetime(contract_status(contract, today)['ends_on']),
    )
    db.session.add(booking)
    db.session.flush()
    contract.transaction_id = booking.id
    return booking


def sync_booking_end(contract, today):
    """Enddatum der verknüpften Buchung an das Vertragsende anpassen (oder entfernen)."""
    if not contract.transaction_id:
        return
    booking = db.session.get(Transaction, contract.transaction_id)
    if booking:
        booking.end_date = _as_datetime(contract_status(contract, today)['ends_on'])
