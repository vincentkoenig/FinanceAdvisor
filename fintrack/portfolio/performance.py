"""
portfolio/performance.py - Rendite des Depots im Vergleich zu einem Index.

Depot: zeitgewichtete Rendite. Jeden Tag zählt nur, wie sich die Bestände
vom Vortag im Kurs bewegt haben: Wert der Vortagsbestände zu den Kursen des
Tages, geteilt durch ihren Wert zu den Kursen des Vortags. Käufe und
Verkäufe verschieben die Rendite so nicht - ein Kauf über 1.000 € ist kein
Gewinn, anders als im Wertverlauf.

Vergleich: iShares Core MSCI World (EUNL.DE, Xetra, in Euro). Der ETF
thesauriert, sein Kurs enthält also die Dividenden. Die Depot-Rendite
rechnet nur mit Kursen, ausgeschüttete Dividenden fehlen dort.
"""

import logging
from datetime import date, timedelta

from fintrack.market.search import create_asset
from fintrack.models import Asset, db
from fintrack.portfolio.history import Holdings, close_on, price_tables

logger = logging.getLogger(__name__)

BENCHMARK_SYMBOL = 'EUNL.DE'
BENCHMARK_NAME = 'MSCI World'


def benchmark_asset(create=True):
    """
    Das Asset des Vergleichsindex. Fehlt es, wird es angelegt (lädt ein Jahr
    Kurse); danach hält es der tägliche Kurslauf aktuell wie jedes Asset.
    Gibt None zurück, wenn es nicht zu bekommen ist.
    """
    asset = Asset.query.filter_by(symbol=BENCHMARK_SYMBOL).first()
    if asset or not create:
        return asset
    try:
        asset, _ = create_asset(BENCHMARK_SYMBOL, 'iShares Core MSCI World UCITS ETF')
        return asset
    except Exception:
        db.session.rollback()
        logger.exception('Vergleichsindex %s konnte nicht angelegt werden', BENCHMARK_SYMBOL)
        return None


def _value(holdings, prices, held_on, priced_on):
    """Wert der Bestände vom Tag held_on zu den Kursen vom Tag priced_on; nur Assets mit Kurs an beiden Tagen."""
    before = after = 0.0
    for asset_id, table in prices.items():
        quantity = holdings.quantity_on(asset_id, held_on)
        if not quantity:
            continue
        old, new = close_on(table, held_on), close_on(table, priced_on)
        if old is None or new is None:
            continue
        before += quantity * old
        after += quantity * new
    return before, after


def performance_series(user_id, today=None):
    """
    Täglich vom ersten Tag mit Kurs bis heute: (Tag, Depot-Faktor, Indexkurs).
    Der Depot-Faktor beginnt bei 1.0 und multipliziert die Tagesrenditen auf;
    der Indexkurs ist der Schlusskurs in Euro (None vor seinem ersten Kurs).
    Beide werden erst im Browser auf den gewählten Zeitraum umgerechnet.
    """
    today = today or date.today()
    holdings = Holdings(user_id)
    first = holdings.first_day()
    if first is None:
        return []

    prices = price_tables(holdings.asset_ids)
    benchmark = benchmark_asset()
    bench_table = price_tables([benchmark.id])[benchmark.id] if benchmark else ([], [])

    series, factor = [], 1.0
    day = first
    while day <= today:
        if series:
            before, after = _value(holdings, prices, day - timedelta(days=1), day)
            if before > 0:
                factor *= after / before
        elif _value(holdings, prices, day, day)[0] <= 0:
            day += timedelta(days=1)
            continue  # noch kein Kurs für die gehaltenen Positionen
        bench = close_on(bench_table, day)
        series.append((day, round(factor, 6), round(bench, 4) if bench is not None else None))
        day += timedelta(days=1)
    return series
