"""
analyst/indicators.py - Kennzahlen eines Werts aus seiner Kurshistorie, rein gerechnet,
ohne KI. Grundlage der wöchentlichen Einschätzung (analyst/service.py):

- Trend: 50- und 200-Tage-Linie und ob die 200-Tage-Linie steigt
- Rücksetzer: Abstand zum Jahreshoch, RSI (14 Tage, nach Wilder)
- Überhitzung: Abstand über der 200-Tage-Linie bei hohem RSI
- Entwicklung über 1, 3 und 12 Monate, Schwankung (annualisiert, 60 Tage)

Dazu eine Einordnung nach dem Ansatz "Trend + Rücksetzer" (classify), die der KI als
Ausgangspunkt dient. Die Schwellen stehen hier, damit sie an einer Stelle nachvollziehbar sind.
"""

from math import sqrt

# Handelstage
SMA_SHORT, SMA_LONG = 50, 200
SLOPE_LOOKBACK = 20
RSI_DAYS = 14
VOLATILITY_DAYS = 60
YEAR = 252

PULLBACK_RSI = 40
PULLBACK_FROM_HIGH = -10.0   # Prozent unter dem Jahreshoch
OVERHEATED_RSI = 75
OVERHEATED_ABOVE_SMA = 20.0  # Prozent über der 200-Tage-Linie


def _sma(values, days, end=None):
    end = len(values) if end is None else end
    if end < days:
        return None
    window = values[end - days:end]
    return sum(window) / days


def _rsi(values, days=RSI_DAYS):
    """RSI nach Wilder: geglättete durchschnittliche Gewinne gegen Verluste."""
    if len(values) <= days:
        return None
    changes = [b - a for a, b in zip(values, values[1:])]
    gains = [max(c, 0) for c in changes]
    losses = [max(-c, 0) for c in changes]
    avg_gain = sum(gains[:days]) / days
    avg_loss = sum(losses[:days]) / days
    for gain, loss in zip(gains[days:], losses[days:]):
        avg_gain = (avg_gain * (days - 1) + gain) / days
        avg_loss = (avg_loss * (days - 1) + loss) / days
    if avg_loss == 0:
        return 100.0
    return 100 - 100 / (1 + avg_gain / avg_loss)


def _change(values, days):
    if len(values) <= days or values[-1 - days] <= 0:
        return None
    return (values[-1] / values[-1 - days] - 1) * 100


def _volatility(values, days=VOLATILITY_DAYS):
    if len(values) <= days:
        return None
    window = values[-days - 1:]
    returns = [b / a - 1 for a, b in zip(window, window[1:]) if a > 0]
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    return sqrt(variance) * sqrt(YEAR) * 100


def _round(value, digits=2):
    return None if value is None else round(value, digits)


def compute(closes):
    """
    closes: Tagesschlusskurse in Euro, älteste zuerst (Liste von (Datum, Kurs)).
    Gibt ein dict mit den Kennzahlen zurück; was mangels Historie nicht geht, ist None.
    """
    values = [price for _, price in closes if price and price > 0]
    if not values:
        return None
    price = values[-1]
    sma_long = _sma(values, SMA_LONG)
    sma_long_before = _sma(values, SMA_LONG, len(values) - SLOPE_LOOKBACK)
    year = values[-YEAR:]
    high = max(year)
    return {
        'as_of': closes[-1][0].isoformat(),
        'price': _round(price, 4),
        'sma50': _round(_sma(values, SMA_SHORT), 4),
        'sma200': _round(sma_long, 4),
        'sma200_rising': None if sma_long is None or sma_long_before is None else sma_long > sma_long_before,
        'above_sma200_pct': None if not sma_long else _round((price / sma_long - 1) * 100),
        'rsi14': _round(_rsi(values)),
        'high_52w': _round(high, 4),
        'from_high_pct': _round((price / high - 1) * 100),
        'change_1m_pct': _round(_change(values, 21)),
        'change_3m_pct': _round(_change(values, 63)),
        'change_12m_pct': _round(_change(values, YEAR)),
        'volatility_pct': _round(_volatility(values)),
        'trading_days': len(values),
    }


def classify(indicators):
    """
    Einordnung nach "Trend + Rücksetzer" als Hinweis für die KI:
    trend ('up', 'down', 'sideways' oder None ohne 200-Tage-Linie) und Signale:
    pullback (Rücksetzer im Aufwärtstrend), overheated, trend_break (unter fallender
    oder frisch durchbrochener 200-Tage-Linie).
    """
    if not indicators or indicators['sma200'] is None:
        return {'trend': None, 'pullback': False, 'overheated': False, 'trend_break': False}
    above = indicators['above_sma200_pct']
    rising = indicators['sma200_rising']
    rsi = indicators['rsi14']
    if above > 0 and rising:
        trend = 'up'
    elif above < 0 and not rising:
        trend = 'down'
    else:
        trend = 'sideways'
    pullback = trend == 'up' and (
        (rsi is not None and rsi < PULLBACK_RSI) or indicators['from_high_pct'] <= PULLBACK_FROM_HIGH)
    overheated = rsi is not None and rsi > OVERHEATED_RSI and above >= OVERHEATED_ABOVE_SMA
    trend_break = above < 0 and (not rising or indicators['change_1m_pct'] is not None
                                 and indicators['change_1m_pct'] < 0)
    return {'trend': trend, 'pullback': pullback, 'overheated': overheated, 'trend_break': trend_break}
