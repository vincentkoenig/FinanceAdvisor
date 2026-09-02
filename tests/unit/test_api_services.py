"""
test_api_services.py - Unit Tests für api_services.py mit gemockten
externen API-Aufrufen (yfinance, CoinGecko), damit Tests schnell,
zuverlässig und ohne echte Netzwerk-Calls laufen.
"""

import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import api_services


class TestGetStockPrice:
    """Tests für get_stock_price() mit gemocktem yfinance-Zugriff"""

    def setup_method(self):
        """Cache vor jedem Test leeren, damit Tests sich nicht gegenseitig beeinflussen"""
        api_services._price_cache.clear()

    @patch('api_services.get_exchange_rate')
    @patch('api_services.yf.Ticker')
    def test_returns_price_converted_to_eur(self, mock_ticker_class, mock_exchange_rate):
        """Ein USD-Preis wird korrekt in EUR umgerechnet"""
        # yfinance-Antwort simulieren: Ticker mit fast_info['lastPrice']
        mock_ticker_instance = MagicMock()
        mock_ticker_instance.fast_info = {'lastPrice': 100.0}
        mock_ticker_class.return_value = mock_ticker_instance

        # Wechselkurs simulieren: 1 USD = 0.9 EUR
        mock_exchange_rate.return_value = 0.9

        result = api_services.get_stock_price("AAPL")

        assert result == 90.0
        mock_ticker_class.assert_called_once_with("AAPL")

    @patch('api_services.get_exchange_rate')
    @patch('api_services.yf.Ticker')
    def test_returns_none_on_error(self, mock_ticker_class, mock_exchange_rate):
        """Bei einem Fehler beim externen API-Aufruf wird None zurückgegeben,
        statt dass die Funktion mit einer Exception abbricht"""
        mock_ticker_class.side_effect = Exception("API nicht erreichbar")

        result = api_services.get_stock_price("INVALID")

        assert result is None


class TestGetCryptoPrice:
    """Tests für get_crypto_price() mit gemocktem CoinGecko-Zugriff"""

    def setup_method(self):
        api_services._price_cache.clear()

    @patch('api_services.requests.get')
    def test_returns_price_in_eur(self, mock_get):
        """Der Preis einer Kryptowährung wird korrekt aus der
        CoinGecko-Antwort extrahiert"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"bitcoin": {"eur": 55000.0}}
        mock_get.return_value = mock_response

        result = api_services.get_crypto_price("bitcoin")

        assert result == 55000.0

    @patch('api_services.requests.get')
    def test_returns_none_on_error(self, mock_get):
        """Bei einem Fehler beim externen API-Aufruf wird None zurückgegeben"""
        mock_get.side_effect = Exception("Verbindungsfehler")

        result = api_services.get_crypto_price("bitcoin")

        assert result is None


class TestGetMetalPrice:
    """Tests für get_metal_price() mit gemocktem yfinance-Zugriff"""

    def setup_method(self):
        api_services._price_cache.clear()

    @patch('api_services.get_exchange_rate')
    @patch('api_services.yf.Ticker')
    def test_gold_price_converted_to_eur(self, mock_ticker_class, mock_exchange_rate):
        """Der Goldpreis wird korrekt über das yfinance-Symbol GC=F
        abgerufen und in EUR umgerechnet"""
        mock_ticker_instance = MagicMock()
        mock_ticker_instance.fast_info = {'lastPrice': 2000.0}
        mock_ticker_class.return_value = mock_ticker_instance
        mock_exchange_rate.return_value = 0.9

        result = api_services.get_metal_price("GOLD")

        assert result == 1800.0
        mock_ticker_class.assert_called_once_with("GC=F")

    @patch('api_services.get_exchange_rate')
    @patch('api_services.yf.Ticker')
    def test_silver_price_converted_to_eur(self, mock_ticker_class, mock_exchange_rate):
        """Der Silberpreis wird korrekt über das yfinance-Symbol SI=F
        abgerufen und in EUR umgerechnet"""
        mock_ticker_instance = MagicMock()
        mock_ticker_instance.fast_info = {'lastPrice': 25.0}
        mock_ticker_class.return_value = mock_ticker_instance
        mock_exchange_rate.return_value = 0.9

        result = api_services.get_metal_price("SILVER")

        assert result == 22.5
        mock_ticker_class.assert_called_once_with("SI=F")