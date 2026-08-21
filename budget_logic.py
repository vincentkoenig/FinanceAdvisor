"""
budget_logic.py - Gemeinsame Berechnungslogik für das Haushaltsbuch.
Wird sowohl von app.py (Web-Endpoint) als auch vom MCP-Server
genutzt, damit die Berechnung nur an einer Stelle existiert.
"""

from datetime import datetime

from models import db, Transaction, Category


def is_income(transaction):
    """Prüft ob eine Transaktion eine Einnahme ist, über ihre Kategorie"""
    category = db.session.get(Category, transaction.category_id)
    return category is not None and category.type == 'income'


def calculate_budget_summary(user_id):
    """
    Berechnet den kumulierten Cash-Saldo über alle Monate seit der
    ersten Buchung des Nutzers, sowie eine detaillierte Aufschlüsselung
    des aktuellen Monats (Einnahmen, Fixkosten, Variable Ausgaben, Saldo).
    Wiederkehrende Buchungen werden für jeden Monat mitgezählt,
    in dem sie aktiv waren.
    Gibt ein Dictionary zurück, unabhängig von Flask/jsonify - kann
    also sowohl im Web-Endpoint als auch im MCP-Server genutzt werden.
    """
    first_transaction = Transaction.query.filter_by(user_id=user_id) \
        .order_by(Transaction.date.asc()).first()

    if not first_transaction:
        return {
            "cumulative_balance": 0,
            "current_month_balance": 0,
            "current_month_income": 0,
            "current_month_fixed": 0,
            "current_month_variable": 0
        }

    one_time_transactions = Transaction.query.filter_by(user_id=user_id, is_recurring=False).all()
    recurring_transactions = Transaction.query.filter_by(user_id=user_id, is_recurring=True).all()

    cumulative_balance = 0
    current_month_balance = 0
    current_month_income = 0
    current_month_fixed = 0
    current_month_variable = 0

    today = datetime.now()
    current_month_start = datetime(today.year, today.month, 1)

    year = first_transaction.date.year
    month = first_transaction.date.month

    while datetime(year, month, 1) <= today:
        month_start = datetime(year, month, 1)
        month_end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)

        month_total = 0
        is_current_month = (month_start == current_month_start)

        all_relevant_transactions = []

        for transaction in one_time_transactions:
            if month_start <= transaction.date < month_end:
                all_relevant_transactions.append(transaction)

        for transaction in recurring_transactions:
            starts_before_month_end = transaction.date < month_end
            no_end_or_ends_after_month_start = transaction.end_date is None or transaction.end_date >= month_start
            if starts_before_month_end and no_end_or_ends_after_month_start:
                all_relevant_transactions.append(transaction)

        for transaction in all_relevant_transactions:
            category = db.session.get(Category, transaction.category_id)
            category_type = category.type if category else None
            sign = 1 if category_type == 'income' else -1
            month_total += sign * transaction.amount

            # Nur für den aktuellen Monat die Aufschlüsselung nach Typ befüllen
            if is_current_month:
                if category_type == 'income':
                    current_month_income += transaction.amount
                elif category_type == 'fixed_expense':
                    current_month_fixed += transaction.amount
                elif category_type == 'variable_expense':
                    current_month_variable += transaction.amount

        cumulative_balance += month_total

        if is_current_month:
            current_month_balance = month_total

        if month == 12:
            year += 1
            month = 1
        else:
            month += 1

    return {
        "cumulative_balance": round(cumulative_balance, 2),
        "current_month_balance": round(current_month_balance, 2),
        "current_month_income": round(current_month_income, 2),
        "current_month_fixed": round(current_month_fixed, 2),
        "current_month_variable": round(current_month_variable, 2)
    }