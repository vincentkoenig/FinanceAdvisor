"""
test_price_changes.py - Preisänderungen bei Verträgen und wiederkehrenden Buchungen
(contracts/prices.py) samt Endpoints.
"""

from datetime import date, datetime

import pytest

from fintrack.contracts.prices import price_changes
from fintrack.extensions import db
from fintrack.models import BankTransaction, Category, Contract, Transaction

TODAY = date(2026, 11, 20)


@pytest.fixture
def user(make_user, monkeypatch):
    monkeypatch.setattr('fintrack.contracts.prices.today_berlin', lambda: TODAY)
    user = make_user('a@test.com')
    abo = Category(user_id=user.id, name='Streaming/Abos', type='fixed_expense')
    rent = Category(user_id=user.id, name='Miete', type='fixed_expense')
    insurance = Category(user_id=user.id, name='Versicherung', type='fixed_expense')
    db.session.add_all([abo, rent, insurance])
    db.session.commit()
    user.cat = {'abo': abo.id, 'rent': rent.id, 'insurance': insurance.id}
    return user


def contract(user, name, amount, interval='monthly', provider=None, transaction_id=None):
    c = Contract(user_id=user.id, name=name, provider=provider, category='subscription', amount=amount,
                 interval=interval, start_date=date(2024, 1, 1), notice_value=1, notice_unit='months',
                 transaction_id=transaction_id)
    db.session.add(c)
    db.session.commit()
    return c


def charge(user, day, amount, text, category='abo'):
    db.session.add(Transaction(user_id=user.id, category_id=user.cat[category], amount=amount, description=text,
                               date=datetime.fromisoformat(day), import_hash=f'h-{day}-{text}-{amount}'))
    db.session.commit()


def recurring(user, text, amount, category='rent', start='2025-01-01'):
    booking = Transaction(user_id=user.id, category_id=user.cat[category], amount=amount, description=text,
                          date=datetime.fromisoformat(start), is_recurring=True)
    db.session.add(booking)
    db.session.commit()
    return booking


def covered(user, day, amount, party, n):
    db.session.add(BankTransaction(user_id=user.id, ext_key=f'k{n}', date=date.fromisoformat(day), amount=-amount,
                                   counterparty=party, purpose='', status='covered'))
    db.session.commit()


class TestDetection:

    def test_monthly_needs_two_charges_at_the_new_price(self, app, user):
        contract(user, 'Netflix', 12.99)
        charge(user, '2026-09-15', 12.99, 'NETFLIX INTERNATIONAL')
        charge(user, '2026-10-15', 13.99, 'NETFLIX INTERNATIONAL')
        assert price_changes(user.id, TODAY) == []

        charge(user, '2026-11-15', 13.99, 'NETFLIX INTERNATIONAL')
        [change] = price_changes(user.id, TODAY)

        assert (change['kind'], change['old_amount'], change['new_amount']) == ('contract', 12.99, 13.99)
        assert change['since'] == '2026-10-15' and change['charges'] == 2
        assert change['yearly_difference'] == 12.0

    def test_single_outlier_is_not_a_new_price(self, app, user):
        contract(user, 'Netflix', 12.99)
        charge(user, '2026-10-15', 15.99, 'Netflix')
        charge(user, '2026-11-15', 12.99, 'Netflix')

        assert price_changes(user.id, TODAY) == []

    def test_yearly_contract_needs_one_charge(self, app, user):
        contract(user, 'Hausrat', 120.0, interval='yearly', provider='Allianz')
        charge(user, '2026-03-01', 132.0, 'ALLIANZ VERSICHERUNGS-AG', 'insurance')

        [change] = price_changes(user.id, TODAY)

        assert change['new_amount'] == 132.0 and change['yearly_difference'] == 12.0

    def test_hidden_bank_charges_reveal_a_recurring_booking_price(self, app, user):
        recurring(user, 'Miete Vermieter Müller', 1200)
        covered(user, '2026-10-01', 1250, 'Vermieter Müller', 1)
        covered(user, '2026-11-01', 1250, 'Vermieter Müller', 2)

        [change] = price_changes(user.id, TODAY)

        assert (change['kind'], change['new_amount'], change['since']) == ('booking', 1250, '2026-10-01')

    def test_generic_words_and_implausible_amounts_do_not_match(self, app, user):
        contract(user, 'Haftpflicht Versicherung', 5.0)
        charge(user, '2026-10-10', 7.5, 'Versicherung Kfz', 'insurance')
        charge(user, '2026-11-10', 7.5, 'Versicherung Kfz', 'insurance')
        contract(user, 'Spotify', 10.99)
        charge(user, '2026-10-10', 99.0, 'Spotify Gutschein')
        charge(user, '2026-11-10', 99.0, 'Spotify Gutschein')

        assert price_changes(user.id, TODAY) == []

    def test_old_charges_do_not_count(self, app, user):
        contract(user, 'Netflix', 12.99)
        charge(user, '2026-06-15', 13.99, 'Netflix')
        charge(user, '2026-07-15', 13.99, 'Netflix')

        assert price_changes(user.id, TODAY) == []


class TestActions:

    def test_accepting_a_contract_splits_its_booking(self, app, user, login_client):
        booking = recurring(user, 'Netflix', 12.99, category='abo', start='2025-01-01')
        c = contract(user, 'Netflix', 12.99, transaction_id=booking.id)
        charge(user, '2026-10-15', 13.99, 'Netflix')
        charge(user, '2026-11-15', 13.99, 'Netflix')
        client = login_client('a@test.com')
        [change] = client.get('/api/v1/me/price-changes').get_json()

        response = client.post('/api/v1/me/price-changes/accept', json={'key': change['key']})

        assert response.status_code == 200
        assert db.session.get(Contract, c.id).amount == 13.99
        old = db.session.get(Transaction, booking.id)
        assert old.amount == 12.99 and old.end_date == datetime(2026, 9, 30)
        new = db.session.get(Transaction, db.session.get(Contract, c.id).transaction_id)
        assert new.id != booking.id and new.amount == 13.99 and new.date == datetime(2026, 10, 1)
        assert client.get('/api/v1/me/price-changes').get_json() == []

    def test_accepting_a_recurring_booking(self, app, user, login_client):
        booking = recurring(user, 'Miete Vermieter Müller', 1200)
        covered(user, '2026-10-01', 1250, 'Vermieter Müller', 1)
        covered(user, '2026-11-01', 1250, 'Vermieter Müller', 2)
        client = login_client('a@test.com')
        key = client.get('/api/v1/me/price-changes').get_json()[0]['key']

        client.post('/api/v1/me/price-changes/accept', json={'key': key})

        assert db.session.get(Transaction, booking.id).end_date == datetime(2026, 9, 30)
        successor = Transaction.query.filter(Transaction.id != booking.id, Transaction.is_recurring.is_(True)).one()
        assert successor.amount == 1250 and successor.date == datetime(2026, 10, 1)

    def test_dismiss_hides_until_the_price_changes_again(self, app, user, login_client):
        contract(user, 'Netflix', 12.99)
        charge(user, '2026-09-15', 13.99, 'Netflix')
        charge(user, '2026-10-15', 13.99, 'Netflix')
        client = login_client('a@test.com')
        key = client.get('/api/v1/me/price-changes').get_json()[0]['key']

        assert client.post('/api/v1/me/price-changes/dismiss', json={'key': key}).status_code == 200
        assert client.get('/api/v1/me/price-changes').get_json() == []

        charge(user, '2026-10-25', 14.99, 'Netflix')
        charge(user, '2026-11-18', 14.99, 'Netflix')
        assert [c['new_amount'] for c in client.get('/api/v1/me/price-changes').get_json()] == [14.99]

    def test_unknown_or_foreign_keys(self, app, user, make_user, login_client):
        contract(user, 'Netflix', 12.99)
        charge(user, '2026-10-15', 13.99, 'Netflix')
        charge(user, '2026-11-15', 13.99, 'Netflix')
        key = login_client('a@test.com').get('/api/v1/me/price-changes').get_json()[0]['key']
        make_user('b@test.com')
        other = login_client('b@test.com')

        assert other.post('/api/v1/me/price-changes/accept', json={'key': key}).status_code == 404
        assert other.post('/api/v1/me/price-changes/accept', json={'key': 'irgendwas'}).status_code == 400
