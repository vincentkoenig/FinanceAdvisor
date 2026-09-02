"""
test_diversification.py - Unit Tests für die Herfindahl-Hirschman-Index
basierte Diversifikationsscore-Berechnung aus app.py.
"""

import sys
import os

# Projekt-Root zum Python-Pfad hinzufügen, damit app.py importierbar ist
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app import calculate_diversification_score


class TestCalculateDiversificationScore:
    """Tests für calculate_diversification_score()"""

    def test_single_asset_gives_lowest_score(self):
        """Ein Portfolio mit nur einem Asset ist maximal konzentriert -> Score 1"""
        result = calculate_diversification_score([1000], 1000)
        assert result == 1

    def test_many_equal_assets_gives_high_score(self):
        """Viele gleichgewichtete Assets -> hoher Diversifikationsscore"""
        values = [100, 100, 100, 100, 100, 100, 100, 100, 100, 100]  # 10 gleiche Assets
        result = calculate_diversification_score(values, sum(values))
        assert result >= 9

    def test_two_unequal_assets(self):
        """Zwei sehr ungleich gewichtete Assets -> niedriger Score"""
        result = calculate_diversification_score([950, 50], 1000)
        assert result <= 3

    def test_empty_portfolio_returns_lowest_score(self):
        """Kein Portfolio (leere Liste) -> definiertes Verhalten statt Fehler"""
        result = calculate_diversification_score([], 0)
        assert result == 1

    def test_score_is_always_within_valid_range(self):
        """Der Score muss immer zwischen 1 und 10 liegen, unabhängig von der Verteilung"""
        result = calculate_diversification_score([500, 300, 150, 50], 1000)
        assert 1 <= result <= 10