"""
test_account_balances.py - Eingetragene Kontostände: Cash-Bestand von dort aus, Abweichung zu den
Buchungen, Vermögensverlauf, Rechte und Export.
"""

import sys
import os
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from fintrack.budget import service
from fintrack.budget.service import CashLedger, calculate_budget_summary, wealth_series
from fintrack.extensions import db
from fintrack.models import AccountBalance, Category, Transaction

TODAY = date.today()


def days_ago(days):
    return TODAY - timedelta(days=days)


@pytest.fixture
def account(make_user, login_client):
    user = make_user('a@test.com')
    income = Category(user_id=user.id, name='Gehalt', type='income')
    food = Category(user_id=user.id, name='Essen', type='variable_expense')
    db.session.add_all([income, food])
    db.session.commit()

    def book(amount, day, category=food, **fields):
        db.session.add(Transaction(user_id=user.id, category_id=category.id, amount=amount,
                                   date=datetime.combine(day, datetime.min.time()), **fields))
        db.session.commit()

    def balance(amount, day):
        db.session.add(AccountBalance(user_id=user.id, date=day, amount=amount))
        db.session.commit()

    return login_client('a@test.com'), user, income, book, balance


def test_without_balance_cash_is_unknown_not_the_booking_sum(account):
    _, user, _, book, _ = account
    book(20000, days_ago(10))
    summary = calculate_budget_summary(user.id)
    assert summary['cash_balance'] is None
    assert summary['cash_as_of'] is None
    assert summary['last_booking'] == days_ago(10).isoformat()
    assert summary['cumulative_balance'] == -20000
    assert wealth_series(user.id) == []


def test_balance_counts_only_later_bookings(account):
    _, user, income, book, balance = account
    book(500, days_ago(20))  # vor dem Kontostand: steckt schon darin
    balance(1000, days_ago(10))
    book(100, days_ago(10))  # am selben Tag: der Kontostand gilt zum Tagesende
    book(200, days_ago(5))
    book(50, days_ago(4), income)
    summary = calculate_budget_summary(user.id)
    assert summary['cash_balance'] == 850
    assert summary['cash_as_of'] == days_ago(10).isoformat()


def test_balance_may_be_negative(account):
    _, user, _, book, balance = account
    balance(-300, days_ago(3))
    book(100, days_ago(1))
    assert calculate_budget_summary(user.id)['cash_balance'] == -400


def test_cash_works_without_any_booking(account):
    _, user, _, _, balance = account
    balance(1500, TODAY)
    assert calculate_budget_summary(user.id)['cash_balance'] == 1500


def test_newest_balance_wins_and_difference_shows_the_gap(account):
    _, user, _, book, balance = account
    balance(1000, days_ago(30))
    book(100, days_ago(20))
    balance(700, days_ago(10))  # Buchungen erwarten 900, also fehlen 200
    book(50, days_ago(5))

    assert calculate_budget_summary(user.id)['cash_balance'] == 650
    newest, oldest = CashLedger(user.id).entries()
    assert (newest['expected'], newest['difference']) == (900, -200)
    assert (oldest['expected'], oldest['difference']) == (None, None)


def test_recurring_booking_counts_from_its_day_and_never_in_the_future(account):
    _, user, _, book, balance = account
    today = date(2026, 3, 15)
    balance(1000, date(2026, 1, 1))
    book(100, date(2025, 12, 31), is_recurring=True)  # 31.01., 28.02.; der 31.03. liegt noch vor uns
    book(10, date(2026, 1, 15), is_recurring=True)  # 15.01., 15.02., 15.03. (heute)
    assert CashLedger(user.id, today).on(today) == 770
    assert CashLedger(user.id, today).on(date(2026, 1, 31)) == 890


def test_ended_and_paused_recurring_bookings_stop(account):
    _, user, _, book, balance = account
    today = date(2026, 3, 15)
    balance(1000, date(2026, 1, 1))
    book(100, date(2026, 1, 5), is_recurring=True, end_date=datetime(2026, 1, 31))
    book(10, date(2026, 1, 5), is_recurring=True, is_paused=True, paused_at=datetime(2026, 2, 20))
    assert CashLedger(user.id, today).on(today) == 890


def test_series_runs_backwards_before_first_balance_and_adds_depot(account, monkeypatch):
    _, user, _, book, balance = account
    book(100, days_ago(2))
    balance(1000, days_ago(1))
    monkeypatch.setattr(service, 'portfolio_value_series',
                        lambda user_id, today: [(days_ago(1), 600.0), (TODAY, 610.0)])
    assert wealth_series(user.id) == [
        {"date": days_ago(2).isoformat(), "cash": 1000, "depot": 0.0, "total": 1000},
        {"date": days_ago(1).isoformat(), "cash": 1000, "depot": 600.0, "total": 1600},
        {"date": TODAY.isoformat(), "cash": 1000, "depot": 610.0, "total": 1610},
    ]


def test_series_before_a_booking_shows_the_higher_balance(account, monkeypatch):
    _, user, _, book, balance = account
    book(100, days_ago(1))
    balance(1000, TODAY)
    book(1, days_ago(3))
    monkeypatch.setattr(service, 'portfolio_value_series', lambda user_id, today: [])
    assert [point['cash'] for point in wealth_series(user.id)] == [1100, 1100, 1000, 1000]


def test_routes_save_replace_and_delete(account):
    client, _, _, _, _ = account
    day = days_ago(1).isoformat()
    assert client.post('/api/v1/me/balances', json={'date': day, 'amount': -12.5}).status_code == 201
    assert client.post('/api/v1/me/balances', json={'date': day, 'amount': 100}).status_code == 201
    entries = client.get('/api/v1/me/balances').get_json()
    assert [(e['date'], e['amount']) for e in entries] == [(day, 100)]
    assert client.get('/api/v1/me/budget/summary').get_json()['cash_balance'] == 100
    assert client.delete(f"/api/v1/me/balances/{entries[0]['id']}").status_code == 200
    assert client.get('/api/v1/me/balances').get_json() == []


@pytest.mark.parametrize('body', [
    {'date': (TODAY + timedelta(days=1)).isoformat(), 'amount': 1},
    {'date': TODAY.isoformat()},
    {'date': TODAY.isoformat(), 'amount': 2_000_000_000},
])
def test_rejects_invalid_balance(account, body):
    client, _, _, _, _ = account
    assert client.post('/api/v1/me/balances', json=body).status_code == 400
    assert client.get('/api/v1/me/balances').get_json() == []


def test_cannot_touch_someone_elses_balance(account, make_user, login_client):
    _, _, _, _, balance = account
    balance(1000, TODAY)
    entry = AccountBalance.query.one()
    make_user('b@test.com')
    other = login_client('b@test.com')
    assert other.get('/api/v1/me/balances').get_json() == []
    assert other.delete(f'/api/v1/me/balances/{entry.id}').status_code == 404
    assert AccountBalance.query.count() == 1


def test_needs_login(app):
    client = app.test_client()
    assert client.get('/api/v1/me/balances').status_code == 401
    assert client.get('/api/v1/me/wealth/history').status_code == 401


def test_export_keeps_balances(account, make_user, login_client):
    client, _, _, _, balance = account
    balance(-250.5, date(2025, 1, 1))
    exported = client.get('/api/v1/me/export').get_json()
    assert exported['account_balances'] == [{'date': '2025-01-01', 'amount': -250.5}]

    make_user('b@test.com')
    other = login_client('b@test.com')
    assert other.post('/api/v1/me/import', json=exported).status_code == 201
    assert [(e['date'], e['amount']) for e in other.get('/api/v1/me/balances').get_json()] == [('2025-01-01', -250.5)]
