"""
test_contract_suggestions.py - Erkennen von Verträgen in importierten Umsätzen
(GET /api/v1/me/contracts/suggestions) und die gelernten Kategorievorschläge beim Import.
"""

import sys
import os
import io
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from fintrack.extensions import db
from fintrack.models import Category, Contract, Transaction


@pytest.fixture
def account(make_user, login_client):
    user = make_user('a@test.com')
    insurance = Category(user_id=user.id, name='Versicherungen', type='fixed_expense')
    food = Category(user_id=user.id, name='Lebensmittel', type='variable_expense')
    income = Category(user_id=user.id, name='Gehalt', type='income')
    db.session.add_all([insurance, food, income])
    db.session.commit()
    return login_client('a@test.com'), user, {'insurance': insurance, 'food': food, 'income': income}


def imported(user, category, description, amount, *days):
    for index, day in enumerate(days):
        db.session.add(Transaction(user_id=user.id, category_id=category.id, amount=amount, description=description,
                                   date=datetime.combine(day, datetime.min.time()),
                                   import_hash=f'{description}-{day.isoformat()}'[:40]))
    db.session.commit()


def suggestions(client):
    response = client.get('/api/v1/me/contracts/suggestions')
    assert response.status_code == 200
    return response.get_json()


class TestDetection:

    def test_monthly_and_yearly_debits_are_suggested(self, account):
        client, user, cats = account
        imported(user, cats['insurance'], 'Beispiel Versicherung AG', 34.38,
                 date(2026, 7, 1), date(2026, 8, 1), date(2026, 9, 1), date(2026, 10, 1))
        imported(user, cats['insurance'], 'Hausrat Muster', 89.0, date(2025, 3, 15), date(2026, 3, 16))

        result = suggestions(client)

        assert [(s['name'], s['interval'], s['amount'], s['count'], s['kind']) for s in result] == [
            ('Hausrat Muster', 'yearly', 89.0, 2, 'insurance'),
            ('Beispiel Versicherung AG', 'monthly', 34.38, 4, 'insurance'),
        ]
        assert result[1]['first_date'] == '2026-07-01' and result[1]['category_name'] == 'Versicherungen'

    @pytest.mark.parametrize('days,amounts', [
        # Zu selten: zwei Monate reichen nicht
        ([date(2026, 9, 1), date(2026, 10, 1)], None),
        # Unregelmäßig: Supermarkt mal nach 3, mal nach 20 Tagen
        ([date(2026, 9, 1), date(2026, 9, 4), date(2026, 9, 24), date(2026, 10, 2)], None),
        # Monatlich, aber stark schwankender Betrag
        ([date(2026, 7, 1), date(2026, 8, 1), date(2026, 9, 1)], [20.0, 55.0, 90.0]),
    ])
    def test_not_regular_enough(self, account, days, amounts):
        client, user, cats = account
        for index, day in enumerate(days):
            db.session.add(Transaction(user_id=user.id, category_id=cats['food'].id,
                                       amount=amounts[index] if amounts else 50.0, description='Markt',
                                       date=datetime.combine(day, datetime.min.time()), import_hash=f'm{index}'))
        db.session.commit()

        assert suggestions(client) == []

    def test_income_manual_bookings_and_existing_contracts_are_ignored(self, account):
        client, user, cats = account
        months = (date(2026, 7, 1), date(2026, 8, 1), date(2026, 9, 1))
        imported(user, cats['income'], 'Arbeitgeber', 3000, *months)
        imported(user, cats['insurance'], 'Beispiel Versicherung AG', 34.38, *months)
        for day in months:  # von Hand gebucht, nicht importiert
            db.session.add(Transaction(user_id=user.id, category_id=cats['food'].id, amount=12, description='Abo X',
                                       date=datetime.combine(day, datetime.min.time())))
        db.session.add(Contract(user_id=user.id, name='Haftpflicht', provider='Beispiel Versicherung', category='insurance',
                                amount=34.38, interval='monthly', start_date=date(2026, 1, 1), renewal_months=12,
                                notice_value=3, notice_unit='months'))
        db.session.commit()

        assert suggestions(client) == []


class TestLearnedCategories:

    CSV = 'Buchungsdatum;Empfänger;Verwendungszweck;Betrag\n05.11.2026;REWE Markt;Kartenzahlung;-20,00\n'.encode()

    def preview(self, client):
        response = client.post('/api/v1/me/import/bank/preview', data=self.CSV, content_type='text/csv')
        return response.get_json()['rows'][0]['category_id']

    def test_latest_assignment_of_the_same_payee_wins(self, account):
        client, user, cats = account
        other = Category(user_id=user.id, name='Haushalt', type='variable_expense')
        db.session.add(other)
        db.session.commit()
        imported(user, cats['food'], 'REWE Markt', 30, date(2026, 9, 5))
        assert self.preview(client) == cats['food'].id

        imported(user, other, 'REWE Markt', 30, date(2026, 10, 5))
        assert self.preview(client) == other.id

    def test_same_payee_beats_a_shared_word(self, account):
        client, user, cats = account
        other = Category(user_id=user.id, name='Getränke', type='variable_expense')
        db.session.add(other)
        db.session.commit()
        imported(user, cats['food'], 'REWE Markt', 30, date(2026, 9, 5))
        imported(user, other, 'Markt Getränke', 30, date(2026, 10, 5))

        assert self.preview(client) == cats['food'].id
