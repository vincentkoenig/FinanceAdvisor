"""
test_trade_republic_import.py - Tests für den Transaktionsexport von Trade Republic (CSV):
Käufe/Verkäufe erkennen, Ein- und Auszahlungen und Dividenden überspringen, Aktiensplits
auf frühere Ausführungen umrechnen und über den gemeinsamen Krypto-/Depot-Weg buchen.
Alle Daten sind erfunden.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from datetime import date

import pytest

from fintrack.imports.bank_csv import CsvImportError
from fintrack.imports.trade_republic_csv import is_trade_republic, read_trade_republic_csv
from fintrack.models import Asset, UserAsset

HEADER = ('"datetime","date","account_type","category","type","asset_class","name","symbol","shares","price",'
          '"amount","fee","tax","currency","original_amount","original_currency","fx_rate","description",'
          '"transaction_id","counterparty_name","counterparty_iban","payment_reference","mcc_code"')


def line(day, category, kind, name='', isin='', shares='', price='', amount='', fee='', asset_class='STOCK'):
    return (f'"{day}T10:00:00Z","{day}","DEFAULT","{category}","{kind}","{asset_class}","{name}","{isin}",'
            f'"{shares}","{price}","{amount}","{fee}","","EUR","","","","","id-{day}-{kind}","","","",""')


EXPORT = '\n'.join([
    HEADER,
    line('2026-01-02', 'CASH', 'CUSTOMER_INPAYMENT', name='Erika Muster', amount='500.00', asset_class=''),
    line('2026-01-05', 'TRADING', 'BUY', 'Beispiel AG', 'DE0000000001', '2.0000000000', '100.000000', '-200.00', '-1.00'),
    line('2026-01-07', 'TRADING', 'BUY', 'Welt ETF', 'IE00B4L5Y983', '1.5000000000', '80.000000', '-120.00',
         asset_class='FUND'),
    line('2026-02-01', 'CASH', 'DIVIDEND', 'Beispiel AG', 'DE0000000001', '2.0000000000', '', '1.20'),
    # 10:1-Split: aus 2 Stück werden 20, also 18 neue
    line('2026-03-01', 'CORPORATE_ACTION', 'SPLIT', 'Beispiel AG', 'DE0000000001', '18.0000000000'),
    line('2026-04-01', 'TRADING', 'SELL', 'Beispiel AG', 'DE0000000001', '-20.0000000000', '12.000000', '240.00', '-1.00'),
]).encode('utf-8-sig')


class TestReader:

    def test_recognised_by_header(self):
        assert is_trade_republic(EXPORT)
        assert not is_trade_republic(b'Datum;Typ;Coin;Menge;Kurs\n')

    def test_trades_skips_and_split(self):
        _, _, trades, skipped = read_trade_republic_csv(EXPORT)

        assert [(t.type, t.isin, t.quantity, t.price, t.fees) for t in trades] == [
            # Kauf vor dem Split auf das neue Verhältnis umgerechnet
            ('buy', 'DE0000000001', pytest.approx(20.0), 10.0, 1.0),
            ('buy', 'IE00B4L5Y983', 1.5, 80.0, 0.0),
            ('sell', 'DE0000000001', 20.0, 12.0, 1.0),
        ]
        assert [s['reason'] for s in skipped] == ['Einzahlung', 'Dividende']

    def test_without_trades(self):
        with pytest.raises(CsvImportError):
            read_trade_republic_csv('\n'.join([HEADER, line('2026-01-02', 'CASH', 'CUSTOMER_INPAYMENT')]).encode())


@pytest.fixture
def client(make_user, login_client, fake_yahoo, mocker):
    make_user('a@test.com')
    fake_yahoo.quotes['DE0000000001'] = [{'symbol': 'BSP.DE', 'quoteType': 'EQUITY', 'exchange': 'GER',
                                          'longname': 'Beispiel AG', 'exchDisp': 'XETRA'}]
    fake_yahoo.quotes['IE00B4L5Y983'] = [{'symbol': 'EUNL.DE', 'quoteType': 'ETF', 'exchange': 'GER',
                                          'longname': 'Welt ETF', 'exchDisp': 'XETRA'}]
    fake_yahoo.add_stock('BSP.DE')
    fake_yahoo.add_stock('EUNL.DE', asset_type='etf')
    mocker.patch('fintrack.market.search.prepare_new_asset', return_value=0)
    return login_client('a@test.com')


def test_preview_and_booking(client):
    data = client.post('/api/v1/me/import/crypto/preview', data=EXPORT, content_type='text/csv').get_json()

    rows = data['rows']
    assert [(r['type'], r['symbol'], r['status']) for r in rows] == [
        ('buy', 'BSP.DE', 'new'), ('buy', 'EUNL.DE', 'new'), ('sell', 'BSP.DE', 'new')]
    assert len(data['skipped']) == 2

    trades = [{'type': r['type'], 'symbol': r['symbol'], 'name': r['asset_name'], 'date': r['date'],
               'quantity': r['quantity'], 'price': r['price']} for r in rows]
    assert client.post('/api/v1/me/import/depot/commit', json={'trades': trades}).status_code == 201

    etf = Asset.query.filter_by(symbol='EUNL.DE').one()
    assert UserAsset.query.filter_by(asset_id=etf.id).one().quantity == pytest.approx(1.5)


def test_split_from_the_export_is_not_applied_twice(client, fake_yahoo):
    """Der Export rechnet den Split selbst ein; Yahoo kennt ihn auch und darf ihn nicht noch einmal anwenden."""
    fake_yahoo.splits['BSP.DE'] = [(date(2026, 2, 1), 10.0)]
    export = '\n'.join([HEADER,
        line('2026-01-05', 'TRADING', 'BUY', 'Beispiel AG', 'DE0000000001', '1', '100.0'),
        line('2026-02-01', 'CORPORATE_ACTION', 'SPLIT', 'Beispiel AG', 'DE0000000001', '9'),
    ]).encode()

    rows = client.post('/api/v1/me/import/crypto/preview', data=export, content_type='text/csv').get_json()['rows']

    assert [(r['quantity'], r['split_factor']) for r in rows] == [(pytest.approx(10.0), 1.0)]


def test_selling_everything_after_fractional_buys_and_split(client):
    """Kleine Bruchstücke + Split summieren sich als Kommazahl nicht exakt; der Verkauf von allem muss trotzdem gehen."""
    buys = [('2026-01-05', '0.0033'), ('2026-01-06', '0.0037'), ('2026-01-07', '0.0036'),
            ('2026-01-08', '0.0043'), ('2026-01-09', '0.0044')]
    export = '\n'.join([HEADER] + [line(day, 'TRADING', 'BUY', 'Beispiel AG', 'DE0000000001', shares, '2700.0')
                                   for day, shares in buys] + [
        line('2026-02-01', 'CORPORATE_ACTION', 'SPLIT', 'Beispiel AG', 'DE0000000001', '0.3667'),
        line('2026-03-01', 'TRADING', 'SELL', 'Beispiel AG', 'DE0000000001', '-0.3860', '91.57'),
    ]).encode()
    rows = client.post('/api/v1/me/import/crypto/preview', data=export, content_type='text/csv').get_json()['rows']
    assert all(r['status'] == 'new' for r in rows)

    trades = [{'type': r['type'], 'symbol': r['symbol'], 'name': r['asset_name'], 'date': r['date'],
               'quantity': r['quantity'], 'price': r['price']} for r in rows]
    response = client.post('/api/v1/me/import/depot/commit', json={'trades': trades})

    assert response.status_code == 201, response.get_json()
    asset = Asset.query.filter_by(symbol='BSP.DE').one()
    position = UserAsset.query.filter_by(asset_id=asset.id).one()
    assert (position.quantity, position.status) == (0, 'sold')
