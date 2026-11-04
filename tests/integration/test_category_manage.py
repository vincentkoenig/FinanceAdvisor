"""
test_category_manage.py - Kategorien anlegen: Unterkategorie nur unter einer Hauptkategorie
gleichen Typs, kein doppelter Name an derselben Stelle.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from fintrack.extensions import db
from fintrack.models import Category


@pytest.fixture
def account(make_user, login_client):
    user = make_user('a@test.com')
    main = Category(user_id=user.id, name='Versicherungen', type='fixed_expense')
    db.session.add(main)
    db.session.flush()
    sub = Category(user_id=user.id, name='Haftpflicht', type='fixed_expense', parent_id=main.id)
    db.session.add(sub)
    db.session.commit()
    return login_client('a@test.com'), main.id, sub.id


def add(client, **body):
    return client.post('/api/v1/me/categories', json=body)


def test_sub_category_under_a_main_category(account):
    client, main, _ = account

    response = add(client, name=' BU ', type='fixed_expense', parent_id=main)

    assert response.status_code == 201
    assert db.session.get(Category, response.get_json()['category_id']).name == 'BU'


def test_no_sub_category_under_a_sub_category(account):
    client, _, sub = account
    assert add(client, name='Tief', type='fixed_expense', parent_id=sub).status_code == 400


def test_same_name_twice_in_one_place(account):
    client, main, _ = account

    assert add(client, name='haftpflicht', type='fixed_expense', parent_id=main).status_code == 409
    # Als Hauptkategorie oder in einem anderen Typ ist der Name frei
    assert add(client, name='Haftpflicht', type='fixed_expense').status_code == 201
    assert add(client, name='Versicherungen', type='variable_expense').status_code == 201


def update(client, category_id, **body):
    return client.put(f'/api/v1/me/categories/{category_id}', json=body)


class TestUpdate:

    def test_rename_and_move_keeps_bookings(self, account):
        from datetime import datetime
        from fintrack.models import Transaction
        client, main, sub = account
        other = Category(user_id=Category.query.get(main).user_id, name='Verträge', type='variable_expense')
        db.session.add(other)
        db.session.flush()
        booking = Transaction(user_id=other.user_id, category_id=sub, amount=10, description='HUK', date=datetime(2026, 10, 1))
        db.session.add(booking)
        db.session.commit()

        response = update(client, sub, name=' Privathaftpflicht ', parent_id=other.id)

        assert response.status_code == 200
        moved = db.session.get(Category, sub)
        # Übernimmt die Art der neuen Hauptkategorie, die Buchung hängt weiter dran
        assert (moved.name, moved.parent_id, moved.type) == ('Privathaftpflicht', other.id, 'variable_expense')
        assert db.session.get(Transaction, booking.id).category_id == sub

    def test_sub_becomes_main(self, account):
        client, _, sub = account
        assert update(client, sub, name='Haftpflicht').status_code == 200
        assert db.session.get(Category, sub).parent_id is None

    @pytest.mark.parametrize('case', ['main with subs', 'income', 'under itself', 'under a sub'])
    def test_invalid_moves(self, account, case):
        client, main, sub = account
        user_id = db.session.get(Category, main).user_id
        income = Category(user_id=user_id, name='Einkommen', type='income')
        lonely = Category(user_id=user_id, name='Solo', type='fixed_expense')
        db.session.add_all([income, lonely])
        db.session.commit()
        moves = {
            'main with subs': (main, lonely.id),
            'income': (sub, income.id),
            'under itself': (lonely.id, lonely.id),
            'under a sub': (lonely.id, sub),
        }
        category, parent = moves[case]

        assert update(client, category, name='X', parent_id=parent).status_code == 400

    def test_duplicate_name_at_the_target(self, account):
        client, main, sub = account
        user_id = db.session.get(Category, main).user_id
        db.session.add(Category(user_id=user_id, name='BU', type='fixed_expense', parent_id=main))
        db.session.commit()

        assert update(client, sub, name='bu', parent_id=main).status_code == 409
        # Nur Groß-/Kleinschreibung am eigenen Namen ändern geht
        assert update(client, sub, name='HAFTPFLICHT', parent_id=main).status_code == 200
