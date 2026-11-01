"""
test_bank_pdf_import.py - Tests für Kontoauszüge als PDF (POST /api/v1/me/import/bank/pdf/preview):
nur maskierter Text geht raus, Umsätze laufen durch dieselbe Vorschau wie beim CSV-Import
und lassen sich über /bank/commit übernehmen. Das Sprachmodell wird ersetzt.
"""

import sys
import os
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from fintrack.extensions import db
from fintrack.imports.bank_pdf import ExtractedBankRow, ExtractedStatement
from fintrack.models import Category, Transaction
from tests.integration.test_depot_import import make_pdf

STATEMENT = [
    'HypoVereinsbank',
    'Frau Erika Musterfrau',
    'Musterweg 3',
    '80331 München',
    'Kontoauszug 10/2026  Kontonummer 1234567890',
    'IBAN DE89 3704 0044 0532 0130 00',
    '01.10. Gutschrift Beispiel Arbeitgeber GmbH Gehalt 3.000,00 H',
    '02.10. Lastschrift Vermieter Müller Miete -1.200,00 S',
    '05.10. Kartenzahlung REWE Markt -54,90 S',
    'Neuer Kontostand 1.745,10',
]


@pytest.fixture
def account(make_user, login_client):
    user = make_user('a@test.com')
    rent = Category(user_id=user.id, name='Miete', type='fixed_expense')
    food = Category(user_id=user.id, name='Lebensmittel', type='variable_expense')
    db.session.add_all([rent, food])
    db.session.flush()
    db.session.add(Transaction(user_id=user.id, category_id=rent.id, amount=1200, description='Miete',
                               date=datetime(2026, 1, 1), is_recurring=True))
    db.session.commit()
    return login_client('a@test.com'), food


def row(day, amount, counterparty, purpose):
    return ExtractedBankRow(booking_date=day, amount=amount, counterparty=counterparty, purpose=purpose)


@pytest.fixture
def ai(mocker):
    fake = mocker.patch('fintrack.imports.routes.read_statement')
    fake.return_value = ExtractedStatement(is_bank_statement=True, note=None, rows=[
        row(date(2026, 10, 1), 3000, 'Beispiel Arbeitgeber GmbH', 'Gehalt'),
        row(date(2026, 10, 2), -1200, 'Vermieter Müller', 'Miete'),
        row(date(2026, 10, 5), -54.9, 'REWE Markt', 'Kartenzahlung'),
        row(date(2026, 10, 6), 0, 'Kontoführung', 'Entgelt'),
    ])
    return fake


def preview(client, pdf=None):
    return client.post('/api/v1/me/import/bank/pdf/preview', data=pdf or make_pdf(STATEMENT),
                       content_type='application/pdf')


class TestBankPdf:

    def test_masked_text_rows_and_same_preview_as_csv(self, account, ai):
        client, _ = account

        response = preview(client)

        data = response.get_json()
        sent = ai.call_args.args[0]
        assert response.status_code == 200
        for secret in ('Musterfrau', 'Musterweg', '80331', '1234567890', 'DE89'):
            assert secret not in sent
        assert 'REWE Markt' in sent and '-54,90' in sent
        assert data['sent_text'] == sent
        # Nullbetrag fällt weg, Miete ist schon als wiederkehrende Buchung erfasst
        assert [(r['counterparty'], r['status']) for r in data['rows']] == [
            ('Beispiel Arbeitgeber GmbH', 'new'), ('Vermieter Müller', 'covered'), ('REWE Markt', 'new')]
        assert data['counts'] == {'new': 2, 'covered': 1, 'duplicate': 0}

    def test_commit_and_second_import_is_duplicate(self, account, ai):
        client, food = account
        rewe = [r for r in preview(client).get_json()['rows'] if r['counterparty'] == 'REWE Markt'][0]

        body = {'rows': [{**{k: rewe[k] for k in ('date', 'amount', 'counterparty', 'purpose', 'occurrence', 'description')},
                          'category_id': food.id}]}
        assert client.post('/api/v1/me/import/bank/commit', json=body).status_code == 201

        statuses = {r['counterparty']: r['status'] for r in preview(client).get_json()['rows']}
        assert statuses['REWE Markt'] == 'duplicate'

    @pytest.mark.parametrize('statement,message', [
        (ExtractedStatement(is_bank_statement=False, rows=[], note='Depotauszug'), 'kein Kontoauszug (Depotauszug)'),
        (ExtractedStatement(is_bank_statement=True, rows=[], note=None), 'keine Umsätze'),
    ])
    def test_not_a_statement_or_empty(self, account, ai, statement, message):
        client, _ = account
        ai.return_value = statement

        response = preview(client)

        assert response.status_code == 400 and message in response.get_json()['error']

    def test_broken_pdf_and_ai_failure(self, account, ai):
        client, _ = account

        assert preview(client, b'kein pdf').status_code == 400
        ai.assert_not_called()

        ai.side_effect = RuntimeError('OpenAI weg')
        response = preview(client)
        assert response.status_code == 502 and 'gleich noch einmal' in response.get_json()['error']
