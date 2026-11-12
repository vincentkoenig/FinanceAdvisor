"""
portfolio/savings_plans.py - Wann ein Sparplan fällig ist. Gebraucht von der
Portfolio-Seite (portfolio/routes.py) und den Push-Meldungen (push/notify.py).
"""

from datetime import datetime


def due_date_this_month(plan, today):
    """Fälligkeitstag im Monat von today; Tage über 28 gelten als 28., damit es ihn jeden Monat gibt."""
    return datetime(today.year, today.month, min(plan.day_of_month, 28))


def is_due(plan, today):
    """
    Fällig, wenn der Tag im Monat erreicht ist und der Sparplan in diesem Monat
    noch nicht ausgeführt wurde. today ist ein datetime.
    """
    due = due_date_this_month(plan, today)
    return today >= due and (plan.last_executed is None or plan.last_executed < due)
