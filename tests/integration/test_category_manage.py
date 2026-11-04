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
