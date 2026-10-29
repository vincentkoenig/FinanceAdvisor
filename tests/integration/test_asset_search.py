"""
test_asset_search.py - Asset-Suche mit Ergebnisliste (GET /assets/search)
und Anlegen des ausgewählten Treffers (POST /assets). yfinance ist durch
FakeYahoo aus conftest.py ersetzt.
"""

import sys
import os
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from fintrack.models import Asset, PriceHistory, db


def quote(symbol, exchange, quote_type='EQUITY', name=None, exch_disp=None):
    return {'symbol': symbol, 'exchange': exchange, 'exchDisp': exch_disp or exchange,
            'quoteType': quote_type, 'longname': name or symbol}


@pytest.fixture
def client(make_user, login_client):
    make_user('a@test.com')
    return login_client('a@test.com')


def search(client, query):
    response = client.get('/api/v1/assets/search', query_string={'query': query})
    assert response.status_code == 200, response.get_json()
    return response.get_json()['results']


class TestSearch:

    def test_euro_listing_first(self, client, fake_yahoo):
        """Bei "SAP" steht Xetra vor der NYSE, obwohl Yahoo die NYSE zuerst nennt"""
        fake_yahoo.quotes['SAP'] = [quote('SAP', 'NYQ', name='SAP SE', exch_disp='NYSE'),
                                    quote('SAP.DE', 'GER', name='SAP SE', exch_disp='XETRA'),
                                    quote('SAP.TO', 'TOR', name='Saputo Inc.')]

        results = search(client, 'SAP')

        assert [r['symbol'] for r in results] == ['SAP.DE', 'SAP', 'SAP.TO']
        assert results[0] == {'asset_id': None, 'symbol': 'SAP.DE', 'name': 'SAP SE', 'exchange': 'XETRA',
                              'asset_type': 'stock', 'eur': True}
        # Die Suche legt nichts an
        assert Asset.query.count() == 0

    def test_xetra_before_other_euro_exchanges(self, client, fake_yahoo):
        fake_yahoo.quotes['MSCI World'] = [quote('IWDA.AS', 'AMS', 'ETF'), quote('URTH', 'PCX', 'ETF'),
                                           quote('EUNL.DE', 'GER', 'ETF')]

        assert [r['symbol'] for r in search(client, 'MSCI World')] == ['EUNL.DE', 'IWDA.AS', 'URTH']

    def test_crypto_offered_in_euro(self, client, fake_yahoo):
        fake_yahoo.quotes['Bitcoin'] = [quote('BTC-USD', 'CCC', 'CRYPTOCURRENCY', 'Bitcoin USD'),
                                        quote('IBIT', 'NGM', 'ETF'),
                                        quote('BTC=F', 'CME', 'FUTURE')]

        results = search(client, 'Bitcoin')

        assert [(r['symbol'], r['name'], r['eur']) for r in results] == \
            [('BTC-EUR', 'Bitcoin EUR', True), ('IBIT', 'IBIT', False)]

    def test_gold_means_the_metal(self, client, fake_yahoo):
        """Die US-Aktie "GOLD" wird ausgeblendet, Gold-Futures heißen "Gold\""""
        fake_yahoo.quotes['Gold'] = [quote('GOLD', 'NYQ'), quote('GC=F', 'CMX', 'FUTURE', 'Gold Dec 26'),
                                     quote('MGC=F', 'CMX', 'FUTURE'), quote('^GSPC', 'SNP', 'INDEX')]

        results = search(client, 'Gold')

        assert [(r['symbol'], r['name'], r['asset_type']) for r in results] == [('GC=F', 'Gold', 'metal')]

    def test_known_asset_first_and_not_duplicated(self, client, fake_yahoo):
        db.session.add(Asset(name='SAP SE', symbol='SAP.DE', asset_type='stock', currency='EUR', exchange='GER'))
        db.session.commit()
        fake_yahoo.quotes['SAP'] = [quote('SAP', 'NYQ'), quote('SAP.DE', 'GER')]

        results = search(client, 'SAP')

        assert [(r['symbol'], bool(r['asset_id'])) for r in results] == [('SAP.DE', True), ('SAP', False)]

    def test_direct_symbol_when_search_finds_nothing(self, client, fake_yahoo):
        fake_yahoo.add_stock('TL0.DE', exchange='GER')

        results = search(client, 'tl0.de')

        assert [(r['symbol'], r['eur']) for r in results] == [('TL0.DE', True)]

    def test_nothing_found(self, client):
        assert search(client, 'xyzxyz') == []

    def test_yahoo_down_still_finds_known_assets(self, client, fake_yahoo, monkeypatch):
        db.session.add(Asset(name='Allianz SE', symbol='ALV.DE', currency='EUR'))
        db.session.commit()

        def broken(query, max_results=15):
            raise ConnectionError('offline')
        monkeypatch.setattr('fintrack.market.yahoo.search_quotes', broken)

        assert [r['symbol'] for r in search(client, 'allianz')] == ['ALV.DE']

    def test_query_required(self, client):
        assert client.get('/api/v1/assets/search').status_code == 400

    def test_login_required(self, app):
        assert app.test_client().get('/api/v1/assets/search?query=SAP').status_code == 401


class TestCreateAsset:

    def test_creates_selected_asset_with_history(self, client, fake_yahoo):
        fake_yahoo.add_stock('SAP.DE', exchange='GER')
        fake_yahoo.closes['SAP.DE'] = [(date.today(), 240.0, 'EUR')]

        response = client.post('/api/v1/assets', json={'symbol': 'SAP.DE', 'name': 'SAP SE'})

        assert response.status_code == 201
        asset = db.session.get(Asset, response.get_json()['id'])
        assert (asset.name, asset.currency, asset.exchange, asset.asset_type) == ('SAP SE', 'EUR', 'GER', 'stock')
        assert PriceHistory.query.filter_by(asset_id=asset.id).count() == 1

    def test_existing_asset_is_returned(self, client, fake_yahoo):
        db.session.add(Asset(name='SAP SE', symbol='SAP.DE', currency='EUR'))
        db.session.commit()

        response = client.post('/api/v1/assets', json={'symbol': 'sap.de'})

        assert response.status_code == 200
        assert Asset.query.count() == 1

    def test_unknown_symbol_is_rejected(self, client):
        response = client.post('/api/v1/assets', json={'symbol': 'GIBTSNICHT'})

        assert response.status_code == 404
        assert Asset.query.count() == 0

    @pytest.mark.parametrize('symbol', ['', 'SAP DE', '<script>', 'A' * 31])
    def test_invalid_symbol(self, client, symbol):
        assert client.post('/api/v1/assets', json={'symbol': symbol}).status_code == 400
