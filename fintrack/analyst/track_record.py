"""
analyst/track_record.py - Wie gut lag der Analyst? Jede Einschätzung (AnalystSignal)
wird 30 und 90 Tage nach dem Lauf mit dem tatsächlichen Kursverlauf verglichen, aus
den gespeicherten Schlusskursen; es wird nichts zusätzlich gespeichert.

Wann eine Einschätzung als Treffer zählt:
- Kaufen-Stufen (Nachkaufen, Einstieg interessant): der Kurs ist gestiegen
- Verkaufen-Stufen (Teilgewinn mitnehmen, Verkauf prüfen, Meiden): der Kurs ist gefallen
- Abwarten-Stufen (Halten, Abwarten) sagen keine Richtung voraus und zählen nicht zur
  Trefferquote; für sie gibt es nur die durchschnittliche Entwicklung

Daneben steht die Entwicklung des MSCI World (EUNL.DE) im selben Zeitraum, damit
sichtbar wird, ob ein Treffer mehr war als ein steigender Gesamtmarkt.
"""

from datetime import timedelta

from fintrack.analyst.service import STANCE_LABELS
from fintrack.contracts.terms import today_berlin
from fintrack.market.service import price_in_eur_on
from fintrack.models import AnalystSignal, Asset, db
from fintrack.portfolio.performance import BENCHMARK_NAME, benchmark_asset

HORIZONS = (30, 90)
UP_STANCES = {'add', 'entry'}
DOWN_STANCES = {'take_profit', 'review_sale', 'avoid'}


def _change(asset, start_price, start_day, end_day):
    """Entwicklung in Prozent vom Kurs der Einschätzung bis zum Schlusskurs am Ende, oder None."""
    if not asset or not start_price:
        return None
    end = price_in_eur_on(asset, end_day)
    if end is None:
        return None
    return (end / start_price - 1) * 100


def _benchmark_change(benchmark, start_day, end_day):
    if not benchmark:
        return None
    start = price_in_eur_on(benchmark, start_day)
    return _change(benchmark, start, start_day, end_day) if start else None


def _hit(stance, change):
    if stance in UP_STANCES:
        return change > 0
    if stance in DOWN_STANCES:
        return change < 0
    return None  # Halten/Abwarten: keine Richtung


def _summary(rows):
    """rows: Liste von (hit oder None, Entwicklung, Entwicklung MSCI World oder None)."""
    scored = [hit for hit, _, _ in rows if hit is not None]
    benchmark = [b for _, _, b in rows if b is not None]
    return {
        'evaluated': len(rows),
        'scored': len(scored),
        'hits': sum(scored),
        'hit_rate': round(sum(scored) / len(scored) * 100) if scored else None,
        'avg_change': round(sum(c for _, c, _ in rows) / len(rows), 1) if rows else None,
        'avg_benchmark': round(sum(benchmark) / len(benchmark), 1) if benchmark else None,
    }


def track_record(user_id, today=None):
    """
    Trefferquote nach 30 und 90 Tagen, gesamt und je Stufe, dazu wie viele
    Einschätzungen noch zu jung für eine Auswertung sind und ab wann es die erste gibt.
    """
    today = today or today_berlin()
    signals = db.session.query(AnalystSignal, Asset).join(Asset, Asset.id == AnalystSignal.asset_id) \
        .filter(AnalystSignal.user_id == user_id).order_by(AnalystSignal.run_date).all()
    benchmark = benchmark_asset(create=False)

    totals = {h: [] for h in HORIZONS}
    by_stance = {}
    for signal, asset in signals:
        for horizon in HORIZONS:
            end_day = signal.run_date + timedelta(days=horizon)
            if end_day > today:
                continue
            change = _change(asset, signal.price, signal.run_date, end_day)
            if change is None:
                continue
            row = (_hit(signal.stance, change), change, _benchmark_change(benchmark, signal.run_date, end_day))
            totals[horizon].append(row)
            by_stance.setdefault(signal.stance, {h: [] for h in HORIZONS})[horizon].append(row)

    first = signals[0][0].run_date if signals else None
    return {
        'benchmark': BENCHMARK_NAME,
        'signals': len(signals),
        'first_result_on': (first + timedelta(days=HORIZONS[0])).isoformat() if first else None,
        'horizons': {str(h): _summary(totals[h]) for h in HORIZONS},
        'by_stance': [
            {'stance': stance, 'stance_label': STANCE_LABELS.get(stance, stance),
             'direction': 'up' if stance in UP_STANCES else 'down' if stance in DOWN_STANCES else None,
             'horizons': {str(h): _summary(rows[h]) for h in HORIZONS}}
            for stance, rows in sorted(by_stance.items(), key=lambda item: list(STANCE_LABELS).index(item[0])
                                       if item[0] in STANCE_LABELS else 99)
        ],
    }
