"""
test_analyst_indicators.py - Kennzahlen und Einordnung des Analysten (analyst/indicators.py)
an künstlichen Kursreihen mit bekanntem Ergebnis.
"""

from datetime import date, timedelta

import pytest

from fintrack.analyst import indicators as ind


def series(values, start=date(2025, 1, 1)):
    return [(start + timedelta(days=i), v) for i, v in enumerate(values)]


def test_moving_averages_and_distance():
    closes = series([100.0] * 199 + [120.0])

    values = ind.compute(closes)

    assert values['sma200'] == pytest.approx(100.1)
    assert values['sma50'] == pytest.approx(100.4)
    assert values['above_sma200_pct'] == pytest.approx(19.88, abs=0.01)
    assert values['trading_days'] == 200


def test_rsi_extremes():
    assert ind.compute(series([float(i) for i in range(1, 40)]))['rsi14'] == 100.0
    falling = ind.compute(series([float(100 - i) for i in range(40)]))
    assert falling['rsi14'] == pytest.approx(0.0)


def test_rsi_known_value():
    """Abwechselnd +1 und -1: Gewinne und Verluste gleich groß, RSI um 50"""
    values = [100.0 + (i % 2) for i in range(60)]
    assert ind.compute(series(values))['rsi14'] == pytest.approx(50, abs=5)


def test_short_history_has_no_long_average():
    values = ind.compute(series([10.0, 11.0, 12.0]))

    assert values['sma200'] is None and values['sma200_rising'] is None
    assert values['change_1m_pct'] is None and values['rsi14'] is None
    assert values['from_high_pct'] == 0.0
    assert ind.classify(values)['trend'] is None


def test_empty_history():
    assert ind.compute([]) is None


def uptrend_then(tail):
    """300 Tage stetig steigend, danach die angegebenen Kurse"""
    return series([100 + i * 0.5 for i in range(300)] + tail)


def test_uptrend_with_pullback():
    peak = 100 + 299 * 0.5  # 249.5
    values = ind.compute(uptrend_then([peak * 0.88] * 3))
    signals = ind.classify(values)

    assert signals['trend'] == 'up'
    assert signals['pullback'] is True
    assert signals['trend_break'] is False


def test_downtrend_is_a_trend_break():
    values = ind.compute(series([300 - i * 0.5 for i in range(300)]))
    signals = ind.classify(values)

    assert signals['trend'] == 'down'
    assert signals['trend_break'] is True
    assert signals['pullback'] is False


def test_overheated():
    closes = series([100.0] * 260 + [100 + i * 3 for i in range(1, 15)])
    signals = ind.classify(ind.compute(closes))

    assert signals['overheated'] is True
