"""
test_budget_logic.py - Unit Tests für calculate_budget_summary aus
budget_logic.py, insbesondere die korrekte Behandlung von einmaligen
und wiederkehrenden (inkl. pausierten) Buchungen.
"""

import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from models import db, Transaction
from budget_logic import calculate_budget_summary


class TestCalculateBudgetSummary:
    """Tests für calculate_budget_summary()"""

    def test_no_transactions_returns_zero(self, test_user):
        """Ein Nutzer ohne jegliche Buchungen bekommt einen leeren Summary zurück"""
        result = calculate_budget_summary(test_user.id)

        assert result['cumulative_balance'] == 0
        assert result['current_month_balance'] == 0

    def test_single_income_transaction(self, test_user, income_category):
        """Eine einzelne Einnahme im aktuellen Monat wird korrekt gezählt"""
        transaction = Transaction(
            user_id=test_user.id,
            category_id=income_category.id,
            amount=1000,
            date=datetime.now(),
            is_recurring=False
        )
        db.session.add(transaction)
        db.session.commit()

        result = calculate_budget_summary(test_user.id)

        assert result['current_month_income'] == 1000
        assert result['current_month_balance'] == 1000

    def test_income_and_expense_balance_correctly(self, test_user, income_category, expense_category):
        """Einnahme und Ausgabe im selben Monat ergeben den korrekten Saldo"""
        db.session.add(Transaction(
            user_id=test_user.id, category_id=income_category.id,
            amount=2000, date=datetime.now(), is_recurring=False
        ))
        db.session.add(Transaction(
            user_id=test_user.id, category_id=expense_category.id,
            amount=800, date=datetime.now(), is_recurring=False
        ))
        db.session.commit()

        result = calculate_budget_summary(test_user.id)

        assert result['current_month_income'] == 2000
        assert result['current_month_fixed'] == 800
        assert result['current_month_balance'] == 1200

    def test_paused_recurring_transaction_excluded_from_current_month(self, test_user, income_category):
        """Eine pausierte wiederkehrende Buchung wird ab dem Pausierungs-
        zeitpunkt nicht mehr für den aktuellen Monat mitgezählt"""
        transaction = Transaction(
            user_id=test_user.id,
            category_id=income_category.id,
            amount=500,
            date=datetime(2025, 1, 1),  # startete vor langer Zeit
            is_recurring=True,
            is_paused=True,
            paused_at=datetime.now()  # heute pausiert
        )
        db.session.add(transaction)
        db.session.commit()

        result = calculate_budget_summary(test_user.id)

        assert result['current_month_income'] == 0
        assert result['current_month_balance'] == 0