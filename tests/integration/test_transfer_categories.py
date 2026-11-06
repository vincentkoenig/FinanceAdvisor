"""
test_transfer_categories.py - Umbuchungen zwischen eigenen Konten: zählen für den Kontostand,
aber nicht als Einnahme oder Ausgabe.
"""

import sys
import os
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from fintrack.budget.service import calculate_budget_summary, create_default_categories
from fintrack.extensions import db
from fintrack.models import AccountBalance, Category, CategoryRule, Transaction


@pytest.fixture
def account(make_user, login_client):
    user = make_user('a@test.com')
    create_default_categories(user.id)
    return login_client('a@test.com'), user


def transfer(user, category_type):
    return Category.query.filter_by(user_id=user.id, type=category_type, is_transfer=True, parent_id=None).one()


def book(user, category, amount, day=None):
    entry = Transaction(user_id=user.id, category_id=category.id, amount=amount, date=day or datetime.now())
    db.session.add(entry)
    db.session.commit()
    return entry


def test_migration_gives_existing_users_the_categories(migration_app):
    from flask_migrate import upgrade
    from sqlalchemy import text

    upgrade(revision='0008_account_balance')
    with db.engine.begin() as connection:
        connection.execute(text("INSERT INTO \"user\" (id, username, email) VALUES (1, 'a', 'a@test.com'), (2, 'b', 'b@test.com')"))
        connection.execute(text("INSERT INTO category (user_id, name, type) VALUES (1, 'Essen', 'variable_expense')"))
    upgrade(revision='0009_category_is_transfer')

    with db.engine.connect() as connection:
        rows = connection.execute(text('SELECT user_id, name, type, is_transfer FROM category ORDER BY id')).fetchall()
    assert [(r[0], r[1], r[2], bool(r[3])) for r in rows] == [
        (1, 'Essen', 'variable_expense', False),
        (1, 'Umbuchungen', 'income', True),
        (1, 'Umbuchungen', 'variable_expense', True),
    ]


def test_new_accounts_get_one_transfer_category_per_direction(account):
    _, user = account
    assert transfer(user, 'income').name == 'Umbuchungen'
    assert transfer(user, 'variable_expense').name == 'Umbuchungen'


def test_transfers_move_cash_but_are_no_income_or_expense(account):
    _, user = account
    db.session.add(AccountBalance(user_id=user.id, date=date(2020, 1, 1), amount=100))
    db.session.commit()
    book(user, transfer(user, 'income'), 500)
    book(user, transfer(user, 'variable_expense'), 200)

    summary = calculate_budget_summary(user.id)
    assert summary['cash_balance'] == 400
    assert summary['current_month_income'] == 0
    assert summary['current_month_variable'] == 0
    assert summary['current_month_balance'] == 0


def test_booking_list_marks_transfers(account):
    client, user = account
    book(user, transfer(user, 'income'), 500)
    entry = client.get('/api/v1/me/transactions').get_json()[0]
    assert entry['is_transfer'] is True
    assert entry['category_type'] == 'income'


def test_incoming_transfer_can_be_imported(account):
    client, user = account
    category = transfer(user, 'income')
    response = client.post('/api/v1/me/import/bank/commit', json={'rows': [{
        'date': '2026-10-01', 'amount': 500, 'counterparty': 'Eigenes Konto', 'purpose': 'Umbuchung',
        'description': 'Eigenes Konto', 'occurrence': 0, 'category_id': category.id,
    }]})
    assert response.status_code == 201, response.get_json()
    assert Transaction.query.filter_by(category_id=category.id).count() == 1


def test_subcategory_follows_its_main_category(account):
    client, user = account
    main = transfer(user, 'income')
    created = client.post('/api/v1/me/categories', json={'name': 'Tagesgeld', 'type': 'income', 'parent_id': main.id}).get_json()
    assert db.session.get(Category, created['category_id']).is_transfer is True

    other = Category.query.filter_by(user_id=user.id, name='Einkommen').one()
    moved = client.put(f"/api/v1/me/categories/{created['category_id']}", json={'name': 'Tagesgeld', 'parent_id': other.id})
    assert moved.status_code == 200
    assert db.session.get(Category, created['category_id']).is_transfer is False


def test_main_transfer_category_stays(account):
    client, user = account
    main = transfer(user, 'income')
    other = Category.query.filter_by(user_id=user.id, name='Einkommen').one()
    assert client.delete(f'/api/v1/me/categories/{main.id}').status_code == 409
    assert client.put(f'/api/v1/me/categories/{main.id}', json={'name': 'Umbuchungen', 'parent_id': other.id}).status_code == 400
    assert client.put(f'/api/v1/me/categories/{main.id}', json={'name': 'Eigene Konten', 'parent_id': None}).status_code == 200
    assert db.session.get(Category, main.id).is_transfer is True


def test_export_keeps_transfers_and_old_files_get_the_categories(account, make_user, login_client):
    client, user = account
    book(user, transfer(user, 'income'), 500)
    exported = client.get('/api/v1/me/export').get_json()

    make_user('b@test.com')
    second = login_client('b@test.com')
    assert second.post('/api/v1/me/import', json=exported).status_code == 201
    assert second.get('/api/v1/me/transactions').get_json()[0]['is_transfer'] is True

    for category in exported['categories']:
        category.pop('is_transfer')
    exported['categories'] = [c for c in exported['categories'] if c['name'] != 'Umbuchungen']
    exported['transactions'] = []
    make_user('c@test.com')
    third = login_client('c@test.com')
    assert third.post('/api/v1/me/import', json=exported).status_code == 201
    names = [c for c in third.get('/api/v1/me/categories').get_json() if c['is_transfer']]
    assert sorted(c['type'] for c in names) == ['income', 'variable_expense']
    assert CategoryRule.query.count() == 0
