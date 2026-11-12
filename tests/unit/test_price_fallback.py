"""
test_price_fallback.py - Ersatzquellen für Kurse (market/fallback.py) und die Kette
yfinance -> Ersatzquelle (market/quotes.py). Das Netz ist durch Fake-Antworten ersetzt.
"""

from datetime import date, datetime, timezone

import pytest

from fintrack.market import fallback, quotes


class FakeResponse:
    def __init__(self, status_code=200, text='', data=None):
        self.status_code = status_code
        self.text = text
        self._data = data

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f'HTTP {self.status_code}')


class FakeRequests:
    """Antwortet je nach URL-Teil; merkt sich alle Abfragen."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        for part, response in self.routes.items():
            if part in url:
                return response
        raise AssertionError(f'Unerwartete Abfrage: {url}')


@pytest.fixture
def network(monkeypatch):
    def install(routes):
        fake = FakeRequests(routes)
        monkeypatch.setattr(fallback, 'requests', fake)
        return fake
    return install


def utc_millis(year, month, day, hour=0):
    return datetime(year, month, day, hour, tzinfo=timezone.utc).timestamp() * 1000


class TestEcb:

    def test_rates_are_inverted_to_value_in_euro(self, network):
        """Die EZB nennt 1 EUR = 1,25 USD, die App braucht 1 USD = 0,8 EUR"""
        network({'EXR/D.USD.EUR': FakeResponse(text=(
            'KEY,TIME_PERIOD,OBS_VALUE\nEXR.D.USD.EUR.SP00.A,2026-11-04,1.25\n'
            'EXR.D.USD.EUR.SP00.A,2026-11-03,1.0\n'))})

        assert fallback.fetch_fx_closes('USD', date(2026, 11, 3)) == [
            (date(2026, 11, 3), 1.0), (date(2026, 11, 4), 0.8)]

    def test_unknown_currency_gives_nothing(self, network):
        network({'EXR/D.XYZ.EUR': FakeResponse(status_code=404)})

        assert fallback.fetch_fx_closes('XYZ', date(2026, 11, 3)) == []
        assert fallback.fetch_latest_fx('XYZ') is None

    def test_fx_symbol_routes_to_ecb(self, network):
        network({'EXR/D.GBP.EUR': FakeResponse(text='TIME_PERIOD,OBS_VALUE\n2026-11-04,0.8\n')})

        assert fallback.fetch_last_price('GBPEUR=X') == (1.25, 'EUR')


class TestCoinGecko:

    def test_midnight_value_is_close_of_previous_day(self, network, monkeypatch):
        network({'/market_chart': FakeResponse(data={'prices': [
            [utc_millis(2026, 11, 10), 100.0],      # Schluss 9.11.
            [utc_millis(2026, 11, 11), 110.0],      # Schluss 10.11.
            [utc_millis(2026, 11, 11, 15), 120.0],  # aktueller Kurs am 11.11.
        ]})})

        closes, source = fallback.fetch_daily_closes('BTC-EUR', date(2026, 11, 10), date(2026, 11, 11))

        assert source == 'coingecko'
        assert closes == [(date(2026, 11, 10), 110.0, 'EUR'), (date(2026, 11, 11), 120.0, 'EUR')]

    def test_unknown_ticker_is_found_by_search(self, network):
        fake = network({
            '/search': FakeResponse(data={'coins': [
                {'id': 'kleiner-coin', 'symbol': 'ABC', 'market_cap_rank': 900},
                {'id': 'grosser-coin', 'symbol': 'abc', 'market_cap_rank': 40},
                {'id': 'anderer', 'symbol': 'ABCD', 'market_cap_rank': 1}]}),
            '/simple/price': FakeResponse(data={'grosser-coin': {'usd': 2.5}}),
        })

        assert fallback.fetch_last_price('ABC-USD') == (2.5, 'USD')
        assert fake.calls[-1][1]['ids'] == 'grosser-coin'

    def test_stock_symbols_get_no_live_price(self, network):
        """Live-Kurse für Aktien würden das kleine Alpha-Vantage-Kontingent verbrauchen"""
        fake = network({})

        assert fallback.fetch_last_price('SAP.DE') is None
        assert fake.calls == []


class TestAlphaVantage:

    @pytest.mark.parametrize('symbol, expected', [
        ('SAP.DE', ('SAP.DEX', 'EUR')),
        ('MC.PA', ('MC.PAR', 'EUR')),
        ('ASML.AS', ('ASML.AMS', 'EUR')),
        ('AAPL', ('AAPL', 'USD')),
        ('VUSA.L', None),     # London: Pence oder Pfund, nicht eindeutig
        ('GC=F', None),
        ('^GDAXI', None),
    ])
    def test_symbol_mapping(self, symbol, expected):
        assert fallback.alphavantage_symbol(symbol) == expected

    def test_daily_closes(self, network, monkeypatch):
        monkeypatch.setenv('ALPHAVANTAGE_API_KEY', 'test')
        monkeypatch.setattr(fallback, 'ALPHAVANTAGE_PAUSE_SECONDS', 0)
        fake = network({'alphavantage': FakeResponse(data={'Time Series (Daily)': {
            '2026-11-11': {'4. close': '210.5'}, '2026-11-10': {'4. close': '208.0'},
            '2026-10-01': {'4. close': '190.0'}}})})

        closes, source = fallback.fetch_daily_closes('SAP.DE', date(2026, 11, 5), date(2026, 11, 11))

        assert source == 'alphavantage'
        assert closes == [(date(2026, 11, 10), 208.0, 'EUR'), (date(2026, 11, 11), 210.5, 'EUR')]
        assert fake.calls[0][1]['symbol'] == 'SAP.DEX'

    def test_limit_message_gives_nothing(self, network, monkeypatch):
        monkeypatch.setenv('ALPHAVANTAGE_API_KEY', 'test')
        monkeypatch.setattr(fallback, 'ALPHAVANTAGE_PAUSE_SECONDS', 0)
        network({'alphavantage': FakeResponse(data={'Information': 'Thank you for using Alpha Vantage!'})})

        assert fallback.fetch_daily_closes('AAPL', date(2026, 11, 5)) == ([], 'alphavantage')

    def test_daily_limit_stops_asking(self, network, monkeypatch):
        monkeypatch.setenv('ALPHAVANTAGE_API_KEY', 'test')
        monkeypatch.setattr(fallback, 'ALPHAVANTAGE_PAUSE_SECONDS', 0)
        monkeypatch.setattr(fallback, 'ALPHAVANTAGE_DAILY_LIMIT', 2)
        fake = network({'alphavantage': FakeResponse(data={'Time Series (Daily)': {}})})

        for _ in range(4):
            fallback.fetch_daily_closes('AAPL', date(2026, 11, 5))

        assert len(fake.calls) == 2

    def test_without_key_nothing_is_asked(self, network):
        fake = network({})

        assert fallback.fetch_daily_closes('AAPL', date(2026, 11, 5)) == ([], 'alphavantage')
        assert fake.calls == []


class TestChain:

    def test_yahoo_result_is_used_first(self, fake_yahoo, monkeypatch):
        fake_yahoo.closes['SAP.DE'] = [(date(2026, 11, 11), 210.0, 'EUR')]
        monkeypatch.setattr(fallback, 'fetch_daily_closes',
                            lambda *args: pytest.fail('Ersatzquelle darf nicht gefragt werden'))

        assert quotes.fetch_daily_closes_with_source('SAP.DE', date(2026, 11, 5)) == (
            [(date(2026, 11, 11), 210.0, 'EUR')], 'yfinance')

    def test_yahoo_error_switches_to_fallback(self, fake_yahoo, monkeypatch):
        def broken(*args):
            raise KeyError('exchangeTimezoneName')
        monkeypatch.setattr('fintrack.market.yahoo.fetch_daily_closes', broken)
        monkeypatch.setattr(fallback, 'fetch_daily_closes',
                            lambda symbol, start, end=None: ([(start, 5.0, 'EUR')], 'alphavantage'))

        assert quotes.fetch_daily_closes_with_source('SAP.DE', date(2026, 11, 5)) == (
            [(date(2026, 11, 5), 5.0, 'EUR')], 'alphavantage')

    def test_alias_is_resolved_before_fallback(self, monkeypatch):
        """GOLD steht für Gold (GC=F), nicht für die Aktie von Barrick Gold"""
        asked = []
        monkeypatch.setattr(fallback, 'fetch_daily_closes',
                            lambda symbol, start, end=None: asked.append(symbol) or ([], None))

        quotes.fetch_daily_closes('GOLD', date(2026, 11, 5))

        assert asked == ['GC=F']

    def test_fx_falls_back_to_ecb(self, monkeypatch):
        monkeypatch.setattr(fallback, 'fetch_fx_closes',
                            lambda currency, start, end=None: [(start, 0.9)])

        assert quotes.fetch_fx_closes_with_source('USD', date(2026, 11, 5)) == (
            [(date(2026, 11, 5), 0.9)], 'ezb')

    def test_nothing_anywhere(self):
        assert quotes.fetch_daily_closes_with_source('WEG', date(2026, 11, 5)) == ([], None)
        assert quotes.fetch_last_price('WEG') is None
