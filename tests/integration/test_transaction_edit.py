"""
test_transaction_edit.py - Buchung im Haushaltsbuch nachträglich ändern (Kategorie, Beschreibung),
auf Wunsch für alle Buchungen mit derselben Beschreibung in derselben Richtung.
"""

import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from fintrack.extensions import db
from fintrack.models import Category, Transaction


@pytest.fixture
def account(make_user, login_client):
    user = make_user('a@test.com')
    salary = Category(user_id=user.id, name='Gehalt', type='income')
    phone = Category(user_id=user.id, name='Handy', type='fixed_expense')
    other = Category(user_id=user.id, name='Sonstiges', type='variable_expense')
    db.session.add_all([salary, phone, other])
    db.session.flush()

    def booking(description, category, day):
        t = Transaction(user_id=user.id, category_id=category.id, amount=40, description=description,
                        date=datetime(2026, day, 2))
        db.session.add(t)
        return t

    bookings = [booking('Vodafone GmbH', other, 1), booking('vodafone gmbh ', other, 2),
                booking('Vodafone GmbH', salary, 3), booking('REWE', other, 4)]
    db.session.commit()
    ids = {'salary': salary.id, 'phone': phone.id, 'other': other.id}
    return login_client('a@test.com'), [b.id for b in bookings], ids


def categories_of(ids):
    db.session.expire_all()
    return [db.session.get(Transaction, i).category_id for i in ids]


def test_only_this_booking(account):
    client, bookings, ids = account

    response = client.put(f'/api/v1/me/transactions/{bookings[0]}', json={'category_id': ids['phone'], 'description': 'Vodafone'})

    assert response.status_code == 200 and response.get_json()['updated'] == 1
    assert categories_of(bookings) == [ids['phone'], ids['other'], ids['salary'], ids['other']]
    assert db.session.get(Transaction, bookings[0]).description == 'Vodafone'


def test_all_with_the_same_description_in_the_same_direction(account):
    client, bookings, ids = account

    response = client.put(f'/api/v1/me/transactions/{bookings[0]}',
                          json={'category_id': ids['phone'], 'description': 'Vodafone', 'same_description': True})

    # Groß-/Kleinschreibung und Leerzeichen egal; die Einnahme mit gleichem Text und REWE bleiben
    assert response.get_json() == {'message': '2 Buchungen geändert', 'updated': 2}
    assert categories_of(bookings) == [ids['phone'], ids['phone'], ids['salary'], ids['other']]
    assert [db.session.get(Transaction, i).description for i in bookings[:2]] == ['Vodafone', 'Vodafone']


def test_direction_cannot_change(account):
    client, bookings, ids = account

    response = client.put(f'/api/v1/me/transactions/{bookings[0]}', json={'category_id': ids['salary']})

    assert response.status_code == 400
    assert categories_of(bookings[:1]) == [ids['other']]


def test_unknown_category(account):
    client, bookings, _ = account

    assert client.put(f'/api/v1/me/transactions/{bookings[0]}', json={'category_id': 9999}).status_code == 404
