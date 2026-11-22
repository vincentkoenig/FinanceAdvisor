"""
contracts/prices.py - Preisänderungen bei Verträgen und wiederkehrenden Buchungen erkennen.

Grundlage sind die tatsächlichen Abbuchungen:
- importierte Umsätze (CSV, PDF, Bankabruf) - einmalige Buchungen mit import_hash
- Bank-Abbuchungen, die als "schon erfasst" (covered) gar nicht gebucht wurden, weil eine
  wiederkehrende Buchung sie abdeckt - genau dort fällt ein Preissprung sonst nie auf

Eine Abbuchung gehört zu einem Vertrag bzw. einer wiederkehrenden Buchung, wenn sie ein markantes
Wort mit dessen Namen teilt (allgemeine Wörter wie "Versicherung" zählen nicht) und ihr Betrag
plausibel ist (halb bis doppelt so hoch wie bisher).

Neuer Preis: bei monatlicher Zahlung zwei Abbuchungen hintereinander mit demselben neuen Betrag
(eine einzelne Ausnahme ist noch kein neuer Preis), bei längeren Abständen schon die erste
abweichende. Die letzte Abbuchung darf nicht zu alt sein.

Ignorieren merkt sich den Hinweis samt Betrag (ContractSuggestionDismissal, Schlüssel 'price:...');
ändert sich der Preis später noch einmal, kommt ein neuer Hinweis.
Übernehmen ändert den Vertrag; eine wiederkehrende Buchung wird geteilt: die alte endet im Monat
vor dem neuen Preis, eine neue beginnt mit ihm - so bleiben vergangene Monate richtig.
"""

import re
from datetime import date, datetime, timedelta

from fintrack.api import ApiError
from fintrack.budget.service import runs_in_month
from fintrack.contracts.booking import monthly_amount
from fintrack.contracts.terms import PAYMENTS_PER_YEAR, contract_status, today_berlin
from fintrack.extensions import db
from fintrack.imports.bank_service import words
from fintrack.models import BankTransaction, Category, Contract, ContractSuggestionDismissal, Transaction

# So weit zurück zählen Abbuchungen
LOOKBACK_DAYS = 400
# Die letzte Abbuchung darf höchstens so alt sein (Tage je Zahlweise)
MAX_AGE_DAYS = {'monthly': 45, 'quarterly': 135, 'half_yearly': 270, 'yearly': 450}
# Unter diesem Unterschied ist es derselbe Preis (Rundung)
SAME = 0.01
# Wörter, die zu vielen Verträgen passen und darum nichts zuordnen
GENERIC = {'versicherung', 'versicherungen', 'strom', 'gas', 'miete', 'abo', 'beitrag', 'beiträge', 'rechnung',
           'vertrag', 'monat', 'monatlich', 'jahr', 'kundennummer', 'mitglied', 'mitgliedschaft', 'gebühr',
           'gebuehr', 'lastschrift', 'zahlung', 'abschlag', 'energie', 'internet', 'handy', 'mobilfunk',
           'deutsche', 'bank', 'online', 'service', 'services', 'kfz', 'haftpflicht', 'leben'}


def _marks(*texts):
    """Markante Wörter eines Namens (ohne Zahlen und allgemeine Wörter)."""
    found = set()
    for text in texts:
        found |= {w for w in words(text) if w not in GENERIC and not re.fullmatch(r'\d+', w)}
    return found


def _charges(user_id, since):
    """Tatsächliche Abbuchungen (Ausgaben) seit since: [(Tag, Betrag, Wörter)]."""
    expense = {c.id for c in Category.query.filter_by(user_id=user_id).all() if c.type != 'income'}
    start = datetime.combine(since, datetime.min.time())
    result = []
    for t in Transaction.query.filter(Transaction.user_id == user_id, Transaction.import_hash.isnot(None),
                                      Transaction.is_recurring.is_(False), Transaction.date >= start).all():
        if t.category_id in expense:
            result.append((t.date.date(), round(t.amount, 2), words(t.description)))
    for row in BankTransaction.query.filter(BankTransaction.user_id == user_id, BankTransaction.status == 'covered',
                                            BankTransaction.amount < 0, BankTransaction.date >= since).all():
        result.append((row.date, round(-row.amount, 2), words(f'{row.counterparty} {row.purpose}')))
    return result


def _new_price(expected, interval, charges, today):
    """(neuer Betrag, seit welchem Tag, Anzahl Abbuchungen) oder None."""
    if not charges:
        return None
    charges = sorted(charges, key=lambda c: c[0], reverse=True)
    last_day, last_amount = charges[0]
    if (today - last_day).days > MAX_AGE_DAYS[interval] or abs(last_amount - expected) <= SAME:
        return None
    if interval == 'monthly':
        if len(charges) < 2:
            return None
        before_day, before_amount = charges[1]
        # Zwei Abbuchungen mit demselben neuen Betrag, nicht im selben Monat doppelt
        if abs(before_amount - last_amount) > SAME or (last_day - before_day).days < 20:
            return None
    # Seit wann: älteste Abbuchung in Folge mit dem neuen Betrag
    since, count = last_day, 0
    for day, amount in charges:
        if abs(amount - last_amount) > SAME:
            break
        since, count = day, count + 1
    return last_amount, since, count


def _matching(marks, expected, charges):
    if not marks:
        return []
    return [(day, amount) for day, amount, text in charges
            if marks & text and expected * 0.5 <= amount <= expected * 2]


def price_changes(user_id, today=None):
    """Erkannte Preisänderungen, die weder übernommen noch ignoriert sind."""
    today = today or today_berlin()
    charges = _charges(user_id, today - timedelta(days=LOOKBACK_DAYS))
    dismissed = {d.key for d in ContractSuggestionDismissal.query.filter_by(user_id=user_id).all()}
    result = []

    contracts = Contract.query.filter_by(user_id=user_id).all()
    linked = {c.transaction_id for c in contracts if c.transaction_id}
    for contract in contracts:
        if contract_status(contract, today)['status'] == 'ended':
            continue
        found = _new_price(contract.amount, contract.interval,
                           _matching(_marks(contract.name, contract.provider), contract.amount, charges), today)
        if found:
            result.append(_entry('contract', contract.id, contract.name, contract.amount, contract.interval, found))

    month_start = datetime(today.year, today.month, 1)
    month_end = datetime(today.year + (today.month == 12), today.month % 12 + 1, 1)
    expense = {c.id for c in Category.query.filter_by(user_id=user_id).all() if c.type != 'income'}
    for booking in Transaction.query.filter_by(user_id=user_id, is_recurring=True).all():
        if booking.id in linked or booking.category_id not in expense or not runs_in_month(booking, month_start, month_end):
            continue
        found = _new_price(booking.amount, 'monthly',
                           _matching(_marks(booking.description), booking.amount, charges), today)
        if found:
            result.append(_entry('booking', booking.id, booking.description or 'Buchung', booking.amount, 'monthly', found))

    result = [r for r in result if r['key'] not in dismissed]
    result.sort(key=lambda r: -abs(r['yearly_difference']))
    return result


def _entry(kind, subject_id, name, old, interval, found):
    new, since, count = found
    per_year = PAYMENTS_PER_YEAR[interval]
    return {
        "key": f'price:{kind}:{subject_id}:{new:.2f}',
        "kind": kind, "id": subject_id, "name": name, "interval": interval,
        "old_amount": round(old, 2), "new_amount": new, "since": since.isoformat(), "charges": count,
        "yearly_difference": round((new - old) * per_year, 2),
    }


def _find(user_id, key):
    for change in price_changes(user_id):
        if change['key'] == key:
            return change
    raise ApiError(404, 'Diese Preisänderung gibt es nicht (mehr)')


def _split_booking(booking, new_amount, since):
    """Wiederkehrende Buchung ab dem Monat des neuen Preises mit neuem Betrag weiterführen."""
    start = datetime(since.year, since.month, 1)
    if booking.date >= start:
        booking.amount = new_amount
        return booking
    successor = Transaction(user_id=booking.user_id, category_id=booking.category_id, amount=new_amount,
                            description=booking.description, date=start, is_recurring=True,
                            end_date=booking.end_date, is_paused=booking.is_paused, paused_at=booking.paused_at)
    booking.end_date = start - timedelta(days=1)
    db.session.add(successor)
    db.session.flush()
    return successor


def accept_price_change(user_id, key):
    change = _find(user_id, key)
    since = date.fromisoformat(change['since'])
    if change['kind'] == 'contract':
        contract = db.session.get(Contract, change['id'])
        contract.amount = change['new_amount']
        booking = db.session.get(Transaction, contract.transaction_id) if contract.transaction_id else None
        if booking:
            contract.transaction_id = _split_booking(booking, monthly_amount(contract), since).id
    else:
        _split_booking(db.session.get(Transaction, change['id']), change['new_amount'], since)
    db.session.commit()
    return change


def dismiss_price_change(user_id, key):
    _find(user_id, key)
    db.session.add(ContractSuggestionDismissal(user_id=user_id, key=key))
    db.session.commit()
