"""
goals/service.py - Sparziele als Töpfe vom Kontostand.

Das Geld bleibt auf dem Konto, ein Topf legt es nur gedanklich zurück. Stand eines Topfs:
- Summe der Einträge (Einzahlungen positiv, Entnahmen negativ)
- plus die monatliche Rate: je angefangenem Monat seit rate_since einmal, aber nur bis zum
  Zielbetrag (ein voller Topf wächst nicht weiter)

Wird die Rate geändert, schreibt FinTrack das bisher über die Rate Angesparte als Eintrag
(kind 'rate') fest und lässt die neue Rate ab dem nächsten Monat laufen - so ändert eine neue
Rate nie rückwirkend den Stand.

Mit Zieldatum: nötiger Betrag pro Monat = was noch fehlt / Monate bis einschließlich Zielmonat
(ab dem nächsten Monat). "Im Plan", wenn die Rate mindestens so hoch ist.

Alle Töpfe zusammen werden mit dem echten Kontostand verglichen (budget/service.py): Sind sie
größer, ist mehr zurückgelegt, als auf dem Konto liegt.
"""

from datetime import date

from fintrack.api import ApiError
from fintrack.budget.service import CashLedger
from fintrack.contracts.terms import today_berlin
from fintrack.extensions import db
from fintrack.models import SavingsGoal, SavingsGoalEntry


def month_index(day):
    return day.year * 12 + day.month - 1


def first_of_next_month(day):
    return date(day.year + (day.month == 12), day.month % 12 + 1, 1)


def _entries_total(goal):
    total = db.session.query(db.func.coalesce(db.func.sum(SavingsGoalEntry.amount), 0.0)) \
        .filter(SavingsGoalEntry.goal_id == goal.id).scalar()
    return float(total or 0.0)


def rate_total(goal, entries_total, today):
    """Über die monatliche Rate Angespartes, höchstens bis zum Zielbetrag."""
    if not goal.monthly_amount or not goal.rate_since or goal.rate_since > today:
        return 0.0
    months = month_index(today) - month_index(goal.rate_since) + 1
    return max(0.0, min(goal.monthly_amount * months, goal.target_amount - entries_total))


def balance(goal, today=None):
    today = today or today_berlin()
    entries = _entries_total(goal)
    return round(entries + rate_total(goal, entries, today), 2)


def describe(goal, today=None):
    today = today or today_berlin()
    current = balance(goal, today)
    missing = max(0.0, round(goal.target_amount - current, 2))
    plan = None
    if goal.target_date and missing > 0:
        months_left = month_index(goal.target_date) - month_index(today)
        if months_left <= 0:
            plan = {"status": 'overdue', "needed_monthly": missing, "months_left": 0}
        else:
            needed = round(missing / months_left, 2)
            rate = goal.monthly_amount or 0.0
            plan = {"status": 'on_track' if rate >= needed - 0.005 else 'behind', "needed_monthly": needed,
                    "months_left": months_left, "shortfall_monthly": round(max(0.0, needed - rate), 2)}
    return {
        "id": goal.id,
        "name": goal.name,
        "target_amount": goal.target_amount,
        "target_date": goal.target_date.isoformat() if goal.target_date else None,
        "monthly_amount": goal.monthly_amount,
        "balance": current,
        "missing": missing,
        "progress": round(min(1.0, current / goal.target_amount), 4) if goal.target_amount else 0,
        "reached": missing <= 0,
        "plan": plan,
    }


def overview(user_id, today=None):
    today = today or today_berlin()
    goals = SavingsGoal.query.filter_by(user_id=user_id).order_by(SavingsGoal.id).all()
    described = [describe(g, today) for g in goals]
    total = round(sum(g['balance'] for g in described), 2)
    cash = CashLedger(user_id).on(today) if goals else None
    return {
        "goals": described,
        "total": total,
        "cash_balance": round(cash, 2) if cash is not None else None,
        # Mehr zurückgelegt, als auf dem Konto liegt
        "over_by": round(total - cash, 2) if cash is not None and total > cash + 0.005 else 0.0,
    }


def _check_reached(goal, today):
    """reached_at pflegen: setzen, wenn das Ziel voll ist, zurücksetzen, wenn wieder etwas fehlt."""
    full = balance(goal, today) >= goal.target_amount - 0.005
    if full and not goal.reached_at:
        goal.reached_at = today
    elif not full:
        goal.reached_at = None


def create_goal(user_id, data, today=None):
    today = today or today_berlin()
    goal = SavingsGoal(user_id=user_id, name=data.name, target_amount=data.target_amount,
                       target_date=data.target_date, monthly_amount=data.monthly_amount or None,
                       rate_since=today.replace(day=1) if data.monthly_amount else None)
    db.session.add(goal)
    db.session.flush()
    if data.start_amount:
        db.session.add(SavingsGoalEntry(goal_id=goal.id, user_id=user_id, date=today, amount=data.start_amount,
                                        note='Startbetrag'))
        db.session.flush()
    _check_reached(goal, today)
    db.session.commit()
    return goal


def update_goal(goal, data, today=None):
    today = today or today_berlin()
    new_rate = data.monthly_amount or None
    if new_rate != goal.monthly_amount:
        # Bisher über die Rate Angespartes festschreiben, die neue Rate gilt ab nächstem Monat
        accrued = round(rate_total(goal, _entries_total(goal), today), 2)
        if accrued:
            db.session.add(SavingsGoalEntry(goal_id=goal.id, user_id=goal.user_id, date=today, amount=accrued,
                                            kind='rate', note='Monatliche Rate bis heute'))
        goal.monthly_amount = new_rate
        goal.rate_since = first_of_next_month(today) if new_rate else None
    goal.name = data.name
    goal.target_amount = data.target_amount
    goal.target_date = data.target_date
    db.session.flush()
    _check_reached(goal, today)
    db.session.commit()
    return goal


def add_entry(goal, amount, note=None, today=None):
    """Einzahlung (positiv) oder Entnahme (negativ). Mehr entnehmen, als im Topf ist, geht nicht."""
    today = today or today_berlin()
    current = balance(goal, today)
    if amount < 0 and -amount > current + 0.005:
        raise ApiError(400, f'So viel ist nicht im Topf, dort sind nur {current:.2f} €.'.replace('.', ','))
    # Die Rate darf nach einer Entnahme nicht "nachfüllen": Angespartes vorher festschreiben
    accrued = round(rate_total(goal, _entries_total(goal), today), 2)
    if amount < 0 and accrued:
        db.session.add(SavingsGoalEntry(goal_id=goal.id, user_id=goal.user_id, date=today, amount=accrued,
                                        kind='rate', note='Monatliche Rate bis heute'))
        goal.rate_since = first_of_next_month(today)
    db.session.add(SavingsGoalEntry(goal_id=goal.id, user_id=goal.user_id, date=today, amount=round(amount, 2),
                                    note=note))
    db.session.flush()
    _check_reached(goal, today)
    db.session.commit()


def delete_goal(goal):
    SavingsGoalEntry.query.filter_by(goal_id=goal.id).delete()
    db.session.delete(goal)
    db.session.commit()


def reached_goals(user_id, today=None):
    """Ziele, die (inzwischen) voll sind - auch durch die Rate ohne eigenes Zutun. Pflegt reached_at."""
    today = today or today_berlin()
    result = []
    for goal in SavingsGoal.query.filter_by(user_id=user_id).all():
        _check_reached(goal, today)
        if goal.reached_at:
            result.append(goal)
    db.session.commit()
    return result
