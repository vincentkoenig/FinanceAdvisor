"""
test_bank_import.py - Tests für den Import von Kontoumsätzen
(POST /api/v1/me/import/bank/preview und /commit): Vorschau ohne Speichern,
Abgleich mit wiederkehrenden Buchungen, Kategorievorschläge, keine Dubletten.
"""

import sys
import os
import io
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from fintrack.extensions import db
from fintrack.models import Category, Transaction

CSV = (
    'Buchungsdatum;Empfänger;Verwendungszweck;Betrag\n'
    '01.10.2026;Beispiel Arbeitgeber GmbH;Gehalt Oktober;3.000,00\n'
    '02.10.2026;Vermieter Müller;Miete Oktober;-1.200,00\n'
    '05.10.2026;REWE Markt;Kartenzahlung;-54,90\n'
    '07.10.2026;Café Mitte;Kartenzahlung;-3,20\n'
    '07.10.2026;Café Mitte;Kartenzahlung;-3,20\n'
).encode('cp1252')


@pytest.fixture
def account(make_user, login_client):
    """Nutzer mit Kategorien, wiederkehrender Miete und einem früheren REWE-Einkauf."""
    user = make_user('a@test.com')
    income = Category(user_id=user.id, name='Gehalt', type='income')
    rent = Category(user_id=user.id, name='Miete', type='fixed_expense')
    food = Category(user_id=user.id, name='Lebensmittel', type='variable_expense')
    db.session.add_all([income, rent, food])
    db.session.flush()
    db.session.add_all([
        Transaction(user_id=user.id, category_id=rent.id, amount=1200, description='Miete',
                    date=datetime(2026, 1, 1), is_recurring=True),
        Transaction(user_id=user.id, category_id=food.id, amount=40, description='Rewe',
                    date=datetime(2026, 9, 10)),
    ])
    db.session.commit()
    return login_client('a@test.com'), user, {'income': income.id, 'rent': rent.id, 'food': food.id}


def preview(client, data=CSV, mapping=None):
    form = {'file': (io.BytesIO(data), 'umsaetze.csv')}
    if mapping is not None:
        form['mapping'] = json.dumps({'columns': mapping})
    return client.post('/api/v1/me/import/bank/preview', data=form, content_type='multipart/form-data')


def commit_body(rows, categories):
    return {'rows': [{**{k: r[k] for k in ('date', 'amount', 'counterparty', 'purpose', 'occurrence', 'description')},
                      'category_id': categories} for r in rows]}


class TestPreview:

    def test_statuses_and_suggestions_without_saving(self, account):
        client, user, cats = account
        count_before = Transaction.query.count()

        response = preview(client)

        data = response.get_json()
        assert response.status_code == 200
        rows = {(r['counterparty'], r['occurrence']): r for r in data['rows']}
        # Miete läuft schon als wiederkehrende Buchung
        assert rows[('Vermieter Müller', 0)]['status'] == 'covered'
        assert rows[('Vermieter Müller', 0)]['covered_by']['description'] == 'Miete'
        # REWE kennt FinTrack aus einer früheren Buchung
        assert rows[('REWE Markt', 0)]['category_id'] == cats['food']
        assert rows[('Beispiel Arbeitgeber GmbH', 0)]['category_id'] is None
        # Zwei gleiche Kaffees am selben Tag sind zwei Umsätze, keine Dublette
        assert rows[('Café Mitte', 0)]['key'] != rows[('Café Mitte', 1)]['key']
        assert data['counts'] == {'new': 4, 'covered': 1, 'duplicate': 0}
        assert Transaction.query.count() == count_before

    def test_covered_only_in_months_the_booking_runs(self, account):
        client, _, _ = account
        data = 'Buchungsdatum;Empfänger;Verwendungszweck;Betrag\n02.12.2025;Vermieter Müller;Miete;-1.200,00\n'

        rows = preview(client, data.encode()).get_json()['rows']

        assert rows[0]['status'] == 'new'

    def test_unknown_columns_return_column_names(self, account):
        client, _, _ = account
        data = 'Tag;Wer;Wie viel\n01.10.2026;Laden;-10,00\n'.encode()

        response = preview(client, data)

        assert response.status_code == 400
        assert response.get_json()['columns'] == ['Tag', 'Wer', 'Wie viel']
        mapped = preview(client, data, {'date': 0, 'counterparty': 1, 'amount': 2})
        assert mapped.status_code == 200
        assert mapped.get_json()['rows'][0]['amount'] == -10.0

    def test_file_as_request_body_with_mapping_in_url(self, account):
        """So schickt das Frontend die Datei: roh, Windows-1252 bleibt erhalten"""
        client, _, _ = account
        data = 'Tag;Wer;Wie viel\n01.10.2026;Café;-10,00\n'.encode('cp1252')
        mapping = json.dumps({'columns': {'date': 0, 'counterparty': 1, 'amount': 2}})

        response = client.post(f'/api/v1/me/import/bank/preview?mapping={mapping}', data=data,
                               content_type='text/csv')

        assert response.status_code == 200
        assert response.get_json()['rows'][0]['counterparty'] == 'Café'

    def test_bad_mapping_and_missing_file(self, account):
        client, _, _ = account

        assert preview(client, CSV, {'datum': 0}).status_code == 400
        response = client.post('/api/v1/me/import/bank/preview', data={}, content_type='multipart/form-data')
        assert response.status_code == 400 and 'CSV-Datei' in response.get_json()['error']


class TestCommit:

    def test_commit_creates_bookings_and_second_import_finds_duplicates(self, account):
        client, user, cats = account
        rows = preview(client).get_json()['rows']
        cafes = [r for r in rows if r['counterparty'] == 'Café Mitte']

        response = client.post('/api/v1/me/import/bank/commit', json=commit_body(cafes, cats['food']))

        assert response.status_code == 201
        assert response.get_json()['created'] == 2
        imported = Transaction.query.filter(Transaction.import_hash.isnot(None)).all()
        assert sorted((t.amount, t.description, t.is_recurring) for t in imported) == [
            (3.2, 'Café Mitte', False), (3.2, 'Café Mitte', False)]
        again = preview(client).get_json()
        assert [r['status'] for r in again['rows'] if r['counterparty'] == 'Café Mitte'] == ['duplicate', 'duplicate']

    def test_only_second_of_two_equal_rows(self, account):
        """Wird von zwei gleichen Umsätzen nur der zweite übernommen, bleibt der erste beim nächsten Import neu"""
        client, _, cats = account
        rows = preview(client).get_json()['rows']
        second = [r for r in rows if r['counterparty'] == 'Café Mitte' and r['occurrence'] == 1]

        client.post('/api/v1/me/import/bank/commit', json=commit_body(second, cats['food']))

        statuses = [(r['occurrence'], r['status']) for r in preview(client).get_json()['rows']
                    if r['counterparty'] == 'Café Mitte']
        assert statuses == [(0, 'new'), (1, 'duplicate')]

    def test_committing_twice_skips(self, account):
        client, _, cats = account
        rewe = [r for r in preview(client).get_json()['rows'] if r['counterparty'] == 'REWE Markt']

        client.post('/api/v1/me/import/bank/commit', json=commit_body(rewe, cats['food']))
        response = client.post('/api/v1/me/import/bank/commit', json=commit_body(rewe, cats['food']))

        assert response.get_json() == {'message': '0 Umsätze übernommen', 'created': 0, 'skipped': 1}

    def test_wrong_direction_rejects_everything(self, account):
        """Ausgabe in eine Einkommens-Kategorie: nichts wird gespeichert, auch nicht die gültigen Zeilen davor"""
        client, _, cats = account
        rows = preview(client).get_json()['rows']
        body = commit_body([r for r in rows if r['counterparty'] == 'REWE Markt'], cats['food'])
        body['rows'] += commit_body([r for r in rows if r['counterparty'] == 'Café Mitte'], cats['income'])['rows']

        response = client.post('/api/v1/me/import/bank/commit', json=body)

        assert response.status_code == 400
        assert 'Einkommens' in response.get_json()['error']
        assert Transaction.query.filter(Transaction.import_hash.isnot(None)).count() == 0

    def test_foreign_category_is_404(self, account, make_user):
        client, _, _ = account
        other = make_user('b@test.com')
        foreign = Category(user_id=other.id, name='Fremd', type='variable_expense')
        db.session.add(foreign)
        db.session.commit()
        rows = [r for r in preview(client).get_json()['rows'] if r['counterparty'] == 'REWE Markt']

        response = client.post('/api/v1/me/import/bank/commit', json=commit_body(rows, foreign.id))

        assert response.status_code == 404
        assert Transaction.query.filter(Transaction.import_hash.isnot(None)).count() == 0
