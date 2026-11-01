"""
test_crypto_import.py - Tests für den Import von Krypto-Käufen und -Verkäufen aus CSV-Exporten
(z.B. Bison): Spaltenerkennung, nur Käufe/Verkäufe, Euro-Paare, Buchen über den Depot-Import.
Die Beispieldateien sind erfunden.
"""

import sys
import os
import json
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from fintrack.imports.bank_csv import CsvImportError
from fintrack.imports.crypto_csv import read_crypto_csv
from fintrack.models import Asset, UserAsset

# Deutsch, Semikolon, Uhrzeit im Datum, Ein- und Auszahlung dazwischen
GERMAN = (
    'Transaktionsdatum;Transaktionstyp;Kryptowährung;Menge;Kurs;Betrag;Gebühr\n'
    '01.09.2026 10:15;Kauf;BTC;0,01000000;60.000,00;600,00;1,50\n'
    '02.09.2026 09:00;Einzahlung;EUR;;;500,00;0\n'
    '15.09.2026 18:30;Kauf;ETH;0,5;2.400,00;1.200,00;3,00\n'
    '01.10.2026 08:00;Verkauf;BTC;0,004;65.000,00;260,00;0,65\n'
    '05.10.2026 08:00;Auszahlung;BTC;0,001;;;0\n'
).encode('utf-8')

# Englisch, Komma, ISO-Zeitstempel, kein Kurs (nur Gesamtbetrag)
ENGLISH = (
    'Date,Transaction Type,Asset,Asset Amount,EUR Amount,Fee\n'
    '2026-09-01T10:15:00Z,Buy,btc,0.01,600.00,1.50\n'
    '2026-09-20T10:15:00Z,Staking Reward,ETH,0.001,2.40,0\n'
).encode('utf-8')


class TestReader:

    def test_german_export(self):
        _, mapping, trades, skipped = read_crypto_csv(GERMAN)

        assert [(t.type, t.isin, t.trade_date, t.quantity, t.price, t.fees) for t in trades] == [
            ('buy', 'BTC', date(2026, 9, 1), 0.01, 60000.0, 1.5),
            ('buy', 'ETH', date(2026, 9, 15), 0.5, 2400.0, 3.0),
            ('sell', 'BTC', date(2026, 10, 1), 0.004, 65000.0, 0.65),
        ]
        assert [s['reason'] for s in skipped] == ['Einzahlung', 'Auszahlung']

    def test_english_export_price_from_total(self):
        _, _, trades, skipped = read_crypto_csv(ENGLISH)

        assert [(t.isin, t.price, t.fees) for t in trades] == [('BTC', 60000.0, 1.5)]
        assert skipped == [{'line': 3, 'reason': 'Staking Reward'}]

    def test_unknown_columns_and_mapping(self):
        data = 'Wann;Was;Coin;Stk;EUR\n01.09.2026;Kauf;BTC;0,01;600\n'.encode()

        with pytest.raises(CsvImportError) as error:
            read_crypto_csv(data)
        assert error.value.columns == ['Wann', 'Was', 'Coin', 'Stk', 'EUR']

        _, _, trades, _ = read_crypto_csv(data, {'date': 0, 'type': 1, 'asset': 2, 'quantity': 3, 'total': 4})
        assert (trades[0].isin, trades[0].price) == ('BTC', 60000.0)


@pytest.fixture
def client(make_user, login_client, fake_yahoo, mocker):
    make_user('a@test.com')
    fake_yahoo.add_stock('BTC-EUR', asset_type='crypto', exchange='CCC')
    mocker.patch('fintrack.market.search.prepare_new_asset', return_value=0)
    return login_client('a@test.com')


def preview(client, data, mapping=None):
    url = '/api/v1/me/import/crypto/preview'
    if mapping:
        url += '?mapping=' + json.dumps({'columns': mapping})
    return client.post(url, data=data, content_type='text/csv')


class TestApi:

    def test_preview_finds_euro_pairs_and_books_through_depot_import(self, client):
        rows = preview(client, GERMAN).get_json()['rows']

        # ETH kennt Yahoo hier nicht -> nicht buchbar; BTC als Euro-Paar, Gebühr im Preis
        assert [(r['type'], r['symbol'], r['status']) for r in rows] == [
            ('buy', 'BTC-EUR', 'new'), ('buy', None, 'unknown'), ('sell', 'BTC-EUR', 'new')]
        assert rows[0]['price'] == 60150.0

        trades = [{'type': r['type'], 'symbol': r['symbol'], 'name': r['asset_name'], 'date': r['date'],
                   'quantity': r['quantity'], 'price': r['price']} for r in rows if r['status'] == 'new']
        response = client.post('/api/v1/me/import/depot/commit', json={'trades': trades})

        assert response.status_code == 201
        asset = Asset.query.filter_by(symbol='BTC-EUR').one()
        assert UserAsset.query.filter_by(asset_id=asset.id).one().quantity == pytest.approx(0.006)
        assert [r['status'] for r in preview(client, GERMAN).get_json()['rows'] if r['symbol']] == ['duplicate', 'duplicate']

    def test_unknown_columns_return_names(self, client):
        response = preview(client, 'Wann;Was;Coin;Stk;EUR\n01.09.2026;Kauf;BTC;0,01;600\n'.encode())

        assert response.status_code == 400
        assert response.get_json()['columns'] == ['Wann', 'Was', 'Coin', 'Stk', 'EUR']
        mapped = preview(client, 'Wann;Was;Coin;Stk;EUR\n01.09.2026;Kauf;BTC;0,01;600\n'.encode(),
                         {'date': 0, 'type': 1, 'asset': 2, 'quantity': 3, 'total': 4})
        assert mapped.status_code == 200 and mapped.get_json()['rows'][0]['symbol'] == 'BTC-EUR'

    def test_bank_fields_are_not_accepted_as_crypto_mapping(self, client):
        response = preview(client, GERMAN, {'counterparty': 0})
        assert response.status_code == 400
