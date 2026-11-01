"""
test_depot_import.py - Tests für den Import von Depot-Abrechnungen (PDF):
Maskieren persönlicher Angaben vor der Auswertung, Vorschau (ISIN-Suche, Gebühren,
Dubletten, Verkauf ohne Bestand) und Buchen ins Depot. Das Sprachmodell wird ersetzt.
"""

import sys
import os
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from fintrack.extensions import db
from fintrack.imports.depot_pdf import ExtractedDocument, ExtractedTrade, extract_text, mask_personal_data
from fintrack.models import Asset, AssetTransaction, UserAsset


def make_pdf(lines):
    """Kleinstes gültiges PDF mit einer Seite Text (Helvetica), ohne zusätzliche Bibliothek."""
    def escape(text):
        return text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
    stream = 'BT /F1 10 Tf 50 800 Td 14 TL ' + ' '.join(f'({escape(line)}) Tj T*' for line in lines) + ' ET'
    stream_bytes = stream.encode('latin-1')
    objects = [
        b'<< /Type /Catalog /Pages 2 0 R >>',
        b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R '
        b'/Resources << /Font << /F1 5 0 R >> >> >>',
        b'<< /Length ' + str(len(stream_bytes)).encode() + b' >>\nstream\n' + stream_bytes + b'\nendstream',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>',
    ]
    out = bytearray(b'%PDF-1.4\n')
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f'{number} 0 obj\n'.encode() + body + b'\nendobj\n'
    xref = len(out)
    out += f'xref\n0 {len(objects) + 1}\n0000000000 65535 f \n'.encode()
    for offset in offsets:
        out += f'{offset:010d} 00000 n \n'.encode()
    out += f'trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()
    return bytes(out)


STATEMENT = [
    'Beispiel Broker',
    'Herr Max Mustermann',
    'Musterstraße 12',
    '80331 München',
    'Depot 1234567890',
    'IBAN DE89 3704 0044 0532 0130 00',
    'WERTPAPIERABRECHNUNG KAUF',
    'iShares Core MSCI World ISIN IE00B4L5Y983',
    'Handelstag 01.10.2026 Stück 10 Kurs 100,00 EUR',
    'Fremdkostenzuschlag 1,00 EUR',
]


def quote(symbol, exchange, name):
    return {'symbol': symbol, 'quoteType': 'ETF', 'exchange': exchange, 'longname': name, 'exchDisp': exchange}


@pytest.fixture
def account(make_user, login_client, fake_yahoo, mocker):
    make_user('a@test.com')
    fake_yahoo.quotes['IE00B4L5Y983'] = [quote('IWDA.AS', 'AMS', 'iShares Core MSCI World'),
                                         quote('EUNL.DE', 'GER', 'iShares Core MSCI World')]
    fake_yahoo.add_stock('EUNL.DE', asset_type='etf')
    mocker.patch('fintrack.market.search.prepare_new_asset', return_value=0)
    return login_client('a@test.com')


def trade(kind='buy', day=date(2026, 10, 1), quantity=10, price=100.0, fees=1.0, isin='IE00B4L5Y983'):
    return ExtractedTrade(type=kind, isin=isin, name='iShares Core MSCI World', trade_date=day,
                          quantity=quantity, price=price, fees=fees, currency='EUR')


@pytest.fixture
def ai(mocker):
    """Ersetzt das Sprachmodell; .trades bestimmt die Antwort, .call_args zeigt den gesendeten Text."""
    fake = mocker.patch('fintrack.imports.routes.read_trades')
    fake.return_value = ExtractedDocument(is_trade_statement=True, trades=[trade()], note=None)
    return fake


def preview(client, pdf=None):
    return client.post('/api/v1/me/import/depot/preview', data=pdf or make_pdf(STATEMENT),
                       content_type='application/pdf')


class TestMasking:

    def test_pdf_text_is_read(self):
        assert 'IE00B4L5Y983' in extract_text(make_pdf(STATEMENT))

    def test_personal_data_is_removed_and_trade_data_kept(self):
        masked = mask_personal_data('\n'.join(STATEMENT))

        for secret in ('Mustermann', 'Musterstraße', '80331', 'München', '1234567890', 'DE89', '0532'):
            assert secret not in masked
        for kept in ('IE00B4L5Y983', '01.10.2026', 'Stück 10', '100,00 EUR', '1,00 EUR', 'KAUF'):
            assert kept in masked

    def test_amounts_far_below_the_letterhead_stay(self):
        lines = [''] * 20 + ['Kurswert 12345 Stück', '80000 Euro Volumen']
        assert mask_personal_data('\n'.join(lines)).endswith('Kurswert 12345 Stück\n80000 Euro Volumen')

    def test_not_a_pdf(self, account, ai):
        response = preview(account, b'kein pdf')
        assert response.status_code == 400 and 'kein lesbares PDF' in response.get_json()['error']
        ai.assert_not_called()


class TestPreview:

    def test_only_masked_text_is_sent_and_isin_is_matched(self, account, ai):
        response = preview(account)

        data = response.get_json()
        sent = ai.call_args.args[0]
        assert 'Mustermann' not in sent and '1234567890' not in sent and 'IE00B4L5Y983' in sent
        assert data['sent_text'] == sent
        row = data['rows'][0]
        # Euro-Börse zuerst, Kurs inklusive Gebühren je Stück
        assert (row['symbol'], row['price'], row['quote'], row['fees'], row['status']) == ('EUNL.DE', 100.1, 100.0, 1.0, 'new')

    def test_not_a_trade_statement(self, account, ai):
        ai.return_value = ExtractedDocument(is_trade_statement=False, trades=[], note='Depotauszug')

        data = preview(account).get_json()

        assert data['rows'] == [] and data['note'] == 'Depotauszug'

    def test_unknown_isin_and_sell_without_shares(self, account, ai, fake_yahoo):
        ai.return_value = ExtractedDocument(is_trade_statement=True, note=None, trades=[
            trade(isin='XX0000000000'),
            trade(kind='sell', quantity=5, day=date(2026, 9, 1)),
        ])

        statuses = [(r['type'], r['status']) for r in preview(account).get_json()['rows']]

        assert statuses == [('sell', 'insufficient'), ('buy', 'unknown')]

    def test_buy_then_sell_in_the_same_file(self, account, ai):
        ai.return_value = ExtractedDocument(is_trade_statement=True, note=None, trades=[
            trade(kind='sell', quantity=4, day=date(2026, 10, 1), fees=0), trade()])

        rows = preview(account).get_json()['rows']

        assert [(r['type'], r['status']) for r in rows] == [('buy', 'new'), ('sell', 'new')]

    def test_ai_failure_is_a_clear_error(self, account, ai):
        ai.side_effect = RuntimeError('OpenAI weg')

        response = preview(account)

        assert response.status_code == 502
        assert 'gleich noch einmal' in response.get_json()['error']


class TestCommit:

    def body(self, *trades):
        return {'trades': [{'type': t[0], 'symbol': 'EUNL.DE', 'name': 'iShares Core MSCI World', 'date': t[1],
                            'quantity': t[2], 'price': t[3]} for t in trades]}

    def test_books_into_the_portfolio_in_order_and_skips_duplicates(self, account, ai):
        response = account.post('/api/v1/me/import/depot/commit',
                                json=self.body(('sell', '2026-10-05', 4, 110.0), ('buy', '2026-10-01', 10, 100.1)))

        assert response.status_code == 201 and response.get_json()['booked'] == 2
        asset = Asset.query.filter_by(symbol='EUNL.DE').one()
        position = UserAsset.query.filter_by(asset_id=asset.id).one()
        assert position.quantity == 6 and position.avg_buy_price == 100.1
        trades = AssetTransaction.query.order_by(AssetTransaction.date).all()
        assert [(t.type, t.date) for t in trades] == [('buy', datetime(2026, 10, 1)), ('sell', datetime(2026, 10, 5))]

        # Dieselbe Abrechnung noch einmal: Vorschau erkennt den Kauf, Buchen überspringt ihn
        assert preview(account).get_json()['rows'][0]['status'] == 'duplicate'
        again = account.post('/api/v1/me/import/depot/commit', json=self.body(('buy', '2026-10-01', 10, 100.1)))
        assert again.get_json()['skipped'] == 1
        assert UserAsset.query.filter_by(asset_id=asset.id).one().quantity == 6

    def test_selling_more_than_owned_books_nothing(self, account, ai):
        response = account.post('/api/v1/me/import/depot/commit',
                                json=self.body(('buy', '2026-10-01', 2, 100.0), ('sell', '2026-10-02', 5, 100.0)))

        assert response.status_code == 400
        assert 'Nicht genug Anteile' in response.get_json()['error']
        db.session.expire_all()
        assert AssetTransaction.query.count() == 0 and UserAsset.query.count() == 0
