"""
test_api_services.py - Unit Tests für die externen Abfragen mit gemockten
Netzwerk-Calls: yahoo.py (yfinance) und der CoinGecko-Preis für den Chat.
"""

import sys
import os
from datetime import date
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pandas as pd

from fintrack.market import data as api_services
# Direkt importiert, bevor die FakeYahoo-Fixture die Funktionen im Modul ersetzt
from fintrack.market.yahoo import (fetch_daily_closes, fetch_dividends, fetch_last_price,
                                   fetch_metadata, normalize_currency, yahoo_symbol)


def fake_ticker(fast_info, history=None, dividends=None):
    ticker = MagicMock()
    ticker.fast_info = fast_info
    ticker.history.return_value = history if history is not None else pd.DataFrame()
    ticker.dividends = dividends if dividends is not None else pd.Series(dtype=float)
    return ticker


class TestYahoo:
    """yfinance-Antworten werden richtig in Hauptwährung und App-Typen übersetzt"""

    def test_minor_units_become_main_currency(self):
        assert normalize_currency('GBp') == ('GBP', 0.01)
        assert normalize_currency('ZAc') == ('ZAR', 0.01)
        assert normalize_currency('usd') == ('USD', 1.0)
        assert normalize_currency(None) == ('EUR', 1.0)

    def test_metal_aliases(self):
        assert yahoo_symbol('GOLD') == 'GC=F'
        assert yahoo_symbol('SILVER') == 'SI=F'
        assert yahoo_symbol('SAP.DE') == 'SAP.DE'

    @patch('fintrack.market.yahoo.yf.Ticker')
    def test_metadata_maps_type_and_currency(self, ticker_class):
        ticker_class.return_value = fake_ticker({'currency': 'GBp', 'quoteType': 'ETF', 'exchange': 'LSE'})

        assert fetch_metadata('VUSA.L') == {'currency': 'GBP', 'raw_currency': 'GBp',
                                            'asset_type': 'etf', 'exchange': 'LSE'}

    @patch('fintrack.market.yahoo.yf.Ticker')
    def test_metadata_unknown_symbol(self, ticker_class):
        ticker_class.return_value = fake_ticker({'currency': None})

        assert fetch_metadata('GIBTSNICHT') is None

    @patch('fintrack.market.yahoo.yf.Ticker')
    def test_last_price_in_pence_is_converted_to_pounds(self, ticker_class):
        ticker_class.return_value = fake_ticker({'currency': 'GBp', 'lastPrice': 8150.0})

        assert fetch_last_price('VUSA.L') == (81.5, 'GBP')

    @patch('fintrack.market.yahoo.yf.Ticker')
    def test_gold_uses_futures_symbol(self, ticker_class):
        ticker_class.return_value = fake_ticker({'currency': 'USD', 'lastPrice': 2000.0})

        assert fetch_last_price('GOLD') == (2000.0, 'USD')
        ticker_class.assert_called_once_with('GC=F')

    @patch('fintrack.market.yahoo.yf.Ticker')
    def test_daily_closes_skip_days_without_trading(self, ticker_class):
        index = pd.to_datetime(['2026-10-26', '2026-10-27', '2026-10-28']).tz_localize('Europe/Berlin')
        history = pd.DataFrame({'Close': [100.0, float('nan'), 102.5]}, index=index)
        ticker_class.return_value = fake_ticker({'currency': 'EUR'}, history=history)

        closes = fetch_daily_closes('SAP.DE', date(2026, 10, 26), date(2026, 10, 28))

        assert closes == [(date(2026, 10, 26), 100.0, 'EUR'), (date(2026, 10, 28), 102.5, 'EUR')]
        # Unbereinigte Kurse, und das Enddatum zählt mit
        ticker_class.return_value.history.assert_called_once_with(
            start='2026-10-26', end='2026-10-29', auto_adjust=False)

    @patch('fintrack.market.yahoo.yf.Ticker')
    def test_dividends_after_date_only(self, ticker_class):
        index = pd.to_datetime(['2025-05-01', '2026-05-01'])
        ticker_class.return_value = fake_ticker({'currency': 'EUR'},
                                                dividends=pd.Series([2.2, 2.35], index=index))

        assert fetch_dividends('SAP.DE', date(2025, 12, 31)) == [(date(2026, 5, 1), 2.35)]


class TestGetCryptoPrice:
    """Tests für get_crypto_price() mit gemocktem CoinGecko-Zugriff"""

    def setup_method(self):
        api_services._price_cache.clear()

    @patch('fintrack.market.data.requests.get')
    def test_returns_price_in_eur(self, mock_get):
        """Der Preis einer Kryptowährung wird korrekt aus der
        CoinGecko-Antwort extrahiert"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"bitcoin": {"eur": 55000.0}}
        mock_get.return_value = mock_response

        result = api_services.get_crypto_price("bitcoin")

        assert result == 55000.0

    @patch('fintrack.market.data.requests.get')
    def test_returns_none_on_error(self, mock_get):
        """Bei einem Fehler beim externen API-Aufruf wird None zurückgegeben"""
        mock_get.side_effect = Exception("Verbindungsfehler")

        result = api_services.get_crypto_price("bitcoin")

        assert result is None
