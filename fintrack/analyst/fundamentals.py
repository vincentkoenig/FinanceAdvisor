"""
analyst/fundamentals.py - Fundamentaldaten einer Einzelaktie für den Analysten:
Bewertung (KGV heute und erwartet, Kurs-Buchwert), Wachstum (Umsatz, Gewinn zum
Vorjahr), Qualität (Gewinnmarge, Eigenkapitalrendite, Verschuldung, Free Cashflow)
und der Konsens der Bank-Analysten (Empfehlung, Anzahl, mittleres Kursziel).

Quelle ist yfinance (market/yahoo.py), einmal pro Woche im Analysten-Lauf. ETFs und
Kryptowährungen haben keine Fundamentaldaten und bekommen keine. Was fehlt, bleibt
weg; der Analyst soll nichts schätzen oder erfinden.
"""

from fintrack.market import yahoo

RECOMMENDATIONS = {
    'strong_buy': 'Starker Kauf', 'buy': 'Kaufen', 'hold': 'Halten',
    'underperform': 'Unterdurchschnittlich', 'sell': 'Verkaufen', 'strong_sell': 'Starker Verkauf',
}


def _number(values, key, factor=1.0, digits=1):
    value = values.get(key)
    if not isinstance(value, (int, float)) or value != value:  # auch NaN aussortieren
        return None
    return round(value * factor, digits)


def collect(asset):
    """
    Aufbereitete Fundamentaldaten (Prozentwerte schon als Prozent) oder None, wenn
    der Wert keine Einzelaktie ist oder yfinance nichts liefert.
    """
    if asset.asset_type != 'stock':
        return None
    raw = yahoo.fetch_fundamentals(asset.symbol)
    if not raw:
        return None
    price, target = raw.get('currentPrice'), raw.get('targetMeanPrice')
    target_pct = round((target / price - 1) * 100, 1) if price and target else None
    data = {
        'pe': _number(raw, 'trailingPE'),
        'forward_pe': _number(raw, 'forwardPE'),
        'price_to_book': _number(raw, 'priceToBook'),
        'revenue_growth_pct': _number(raw, 'revenueGrowth', 100),
        'earnings_growth_pct': _number(raw, 'earningsGrowth', 100),
        'profit_margin_pct': _number(raw, 'profitMargins', 100),
        'return_on_equity_pct': _number(raw, 'returnOnEquity', 100),
        # yfinance nennt Schulden zu Eigenkapital in Prozent (22.8 = 0,23)
        'debt_to_equity': _number(raw, 'debtToEquity', 0.01, 2),
        'free_cashflow_positive': None if raw.get('freeCashflow') is None else raw['freeCashflow'] > 0,
        'recommendation': RECOMMENDATIONS.get(raw.get('recommendationKey')),
        'analysts': raw.get('numberOfAnalystOpinions'),
        'target_pct': target_pct,
    }
    data = {key: value for key, value in data.items() if value is not None}
    return data or None


def _fmt(value, suffix=''):
    return 'unbekannt' if value is None else f'{value}{suffix}'


def _signed(value):
    """Prozentwert mit Vorzeichen, damit Richtung eindeutig ist: +13.2 %, -5.0 %."""
    return 'unbekannt' if value is None else f'{value:+} %'


def prompt_lines(data):
    """Abschnitt für die Anfrage an das Modell; fehlende Werte heißen ausdrücklich "unbekannt"."""
    get = data.get
    fcf = get('free_cashflow_positive')
    consensus = 'unbekannt' if not get('recommendation') else (
        f'{get("recommendation")} ({_fmt(get("analysts"))} Analysten, mittleres Kursziel '
        f'{_signed(get("target_pct"))} zum aktuellen Kurs)')
    return [
        'Fundamentaldaten (yfinance):',
        f'- Bewertung: KGV {_fmt(get("pe"))}, erwartetes KGV {_fmt(get("forward_pe"))}, '
        f'Kurs-Buchwert {_fmt(get("price_to_book"))}',
        f'- Wachstum zum Vorjahr: Umsatz {_signed(get("revenue_growth_pct"))}, '
        f'Gewinn {_signed(get("earnings_growth_pct"))}',
        f'- Qualität: Gewinnmarge {_fmt(get("profit_margin_pct"), " %")}, '
        f'Eigenkapitalrendite {_fmt(get("return_on_equity_pct"), " %")}, '
        f'Schulden zu Eigenkapital {_fmt(get("debt_to_equity"))}, '
        f'Free Cashflow {"positiv" if fcf else "negativ" if fcf is False else "unbekannt"}',
        f'- Analystenkonsens: {consensus}',
    ]
