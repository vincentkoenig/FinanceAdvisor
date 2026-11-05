"""
test_category_rules.py - Feste Zuordnungen beim Kontoimport: eigene Regeln, bekannte Händler,
Reihenfolge der Vorschläge, Regeln anlegen/löschen und im Export.
"""

import sys
import os
import io
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from fintrack.extensions import db
from fintrack.models import Category, CategoryRule, Transaction

CSV = (
    'Buchungsdatum;Empfänger;Verwendungszweck;Betrag\n'
    '01.10.2026;ARAL Tankstelle 123;Kartenzahlung;-60,00\n'
    '02.10.2026;Budget Autovermietung;Miete Auto;-80,00\n'
    '03.10.2026;Vodafone GmbH;Rechnung;-39,95\n'
    '04.10.2026;Erstattung;Vodafone Gutschrift;10,00\n'
    '05.10.2026;Laden;Kauf bei REWE Markt;-12,00\n'
    '06.10.2026;Unbekannt;Irgendwas;-5,00\n'
).encode('cp1252')


@pytest.fixture
def account(make_user, login_client):
    user = make_user('a@test.com')

    def add(name, type_, parent=None):
        category = Category(user_id=user.id, name=name, type=type_, parent_id=parent.id if parent else None)
        db.session.add(category)
        db.session.flush()
        return category

    mobility = add('Mobilität', 'variable_expense')
    fuel = add('Sprit', 'variable_expense', mobility)
    living = add('Lebenshaltung', 'variable_expense')
    food = add('Lebensmittel', 'variable_expense', living)
    contracts = add('Sonstige Verträge', 'fixed_expense')
    phone = add('Handy/Internet', 'fixed_expense', contracts)
    income = add('Einkommen', 'income')
    other_income = add('Sonstige Einnahmen', 'income', income)
    db.session.commit()
    ids = {'fuel': fuel.id, 'food': food.id, 'phone': phone.id, 'other_income': other_income.id}
    return login_client('a@test.com'), user, ids


def preview(client):
    form = {'file': (io.BytesIO(CSV), 'umsaetze.csv')}
    rows = client.post('/api/v1/me/import/bank/preview', data=form, content_type='multipart/form-data').get_json()['rows']
    return {r['counterparty']: (r['category_id'], r['category_source']) for r in rows}


def test_known_merchants_without_own_rules(account):
    client, _, ids = account

    found = preview(client)

    # Ganzes Wort: "aral" ja, aber kein Treffer für "jet"/"dm" in anderen Wörtern; REWE steht nur im Verwendungszweck
    assert found['ARAL Tankstelle 123'] == (ids['fuel'], 'merchant')
    assert found['Laden'] == (ids['food'], 'merchant')
    assert found['Vodafone GmbH'] == (ids['phone'], 'merchant')
    assert found['Budget Autovermietung'] == (None, None)
    # Einnahmen bekommen keine Händler-Kategorie
    assert found['Erstattung'] == (None, None)


def test_own_rules_beat_merchants_and_respect_direction(account):
    client, _, ids = account
    response = client.post('/api/v1/me/category-rules', json={'rules': [
        {'pattern': ' Unbekannt ', 'income': False, 'category_id': ids['food']},
        {'pattern': 'vodafone', 'income': True, 'category_id': ids['other_income']},
        {'pattern': 'aral', 'income': False, 'category_id': ids['food']},
    ]})
    assert response.status_code == 201 and response.get_json()['saved'] == 3

    found = preview(client)

    assert found['Unbekannt'] == (ids['food'], 'rule')
    assert found['ARAL Tankstelle 123'] == (ids['food'], 'rule')
    # "vodafone" als Einnahme-Regel trifft die Gutschrift über den Verwendungszweck, nicht die Ausgabe
    assert found['Erstattung'] == (ids['other_income'], 'rule')
    assert found['Vodafone GmbH'] == (ids['phone'], 'merchant')


def test_earlier_booking_of_the_same_payee_wins(account):
    client, user, ids = account
    db.session.add(Transaction(user_id=user.id, category_id=ids['phone'], amount=60, description='ARAL Tankstelle 123',
                               date=datetime(2026, 9, 1)))
    db.session.commit()

    assert preview(client)['ARAL Tankstelle 123'] == (ids['phone'], 'learned')


def test_rule_api(account):
    client, _, ids = account
    client.post('/api/v1/me/category-rules', json={'pattern': 'Vodafone', 'income': False, 'category_id': ids['food']})
    # Gleiches Muster in gleicher Richtung überschreibt
    client.post('/api/v1/me/category-rules', json={'pattern': 'vodafone', 'income': False, 'category_id': ids['phone']})

    rules = client.get('/api/v1/me/category-rules').get_json()

    assert [(r['pattern'], r['category_id'], r['category_label']) for r in rules] == [
        ('vodafone', ids['phone'], 'Sonstige Verträge · Handy/Internet')]
    assert client.post('/api/v1/me/category-rules', json={'pattern': 'x', 'income': False,
                                                          'category_id': ids['phone']}).status_code == 400
    # Ausgabe-Regel mit Einkommens-Kategorie
    assert client.post('/api/v1/me/category-rules', json={'pattern': 'lohn', 'income': False,
                                                          'category_id': ids['other_income']}).status_code == 400
    assert client.delete(f'/api/v1/me/category-rules/{rules[0]["id"]}').status_code == 200
    assert client.get('/api/v1/me/category-rules').get_json() == []


def test_rules_go_with_their_category_and_into_the_export(account):
    client, user, ids = account
    client.post('/api/v1/me/category-rules', json={'rules': [
        {'pattern': 'aral', 'income': False, 'category_id': ids['fuel']},
        {'pattern': 'vodafone', 'income': False, 'category_id': ids['phone']}]})

    exported = client.get('/api/v1/me/export').get_json()
    assert [(r['pattern'], r['income']) for r in exported['category_rules']] == [('aral', False), ('vodafone', False)]

    phone_main = db.session.get(Category, ids['phone']).parent_id
    assert client.delete(f'/api/v1/me/categories/{phone_main}').status_code == 200
    assert [r.pattern for r in CategoryRule.query.filter_by(user_id=user.id)] == ['aral']
