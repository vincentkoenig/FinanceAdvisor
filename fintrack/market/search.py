"""
market/search.py - Asset-Suche für das Hinzufügen von Positionen,
Watchlist-Einträgen und Sparplänen.

Die Suche legt nichts an, sie liefert nur eine Ergebnisliste. Angelegt wird
ein Asset erst, wenn der Nutzer einen Treffer auswählt (create_asset).

Sortierung: zuerst Assets, die schon in der App existieren, dann Treffer
an Euro-Börsen (Xetra vor den übrigen), dann der Rest in der Reihenfolge
von Yahoo. Kryptowährungen werden als Euro-Paar angeboten (BTC-EUR statt
BTC-USD), Edelmetalle über die Gold- und Silber-Futures.
"""

from fintrack.api import ApiError
from fintrack.extensions import db
from fintrack.market import yahoo
from fintrack.market.service import prepare_new_asset
from fintrack.models import Asset

MAX_RESULTS = 10

# Yahoo-Börsenkürzel mit Handel in Euro
XETRA = 'GER'
EUR_EXCHANGES = {XETRA, 'FRA', 'STU', 'MUN', 'BER', 'DUS', 'HAM', 'HAN', 'TLX',
                 'AMS', 'PAR', 'MIL', 'MCE', 'BRU', 'VIE', 'LIS', 'HEL', 'ISE', 'ATH'}

# Von den Futures sind nur die Edelmetalle sinnvoll als Anlage
METAL_FUTURES = {'GC=F': 'Gold', 'SI=F': 'Silber'}

SUPPORTED_TYPES = {'EQUITY', 'ETF', 'MUTUALFUND', 'CRYPTOCURRENCY', 'FUTURE'}


def _from_quote(quote):
    """Ein Yahoo-Treffer als Suchergebnis, oder None, wenn er nicht passt."""
    symbol = quote.get('symbol')
    quote_type = quote.get('quoteType')
    if not symbol or quote_type not in SUPPORTED_TYPES:
        return None
    if symbol in yahoo.SYMBOL_ALIASES:
        # "GOLD" ist in der App das Edelmetall, nicht die gleichnamige US-Aktie
        return None
    name = quote.get('longname') or quote.get('shortname') or symbol
    exchange = quote.get('exchange')
    exchange_name = quote.get('exchDisp') or exchange

    if quote_type == 'FUTURE':
        if symbol not in METAL_FUTURES:
            return None
        name = METAL_FUTURES[symbol]
    if quote_type == 'CRYPTOCURRENCY':
        # Kryptowährungen immer als Euro-Paar
        if symbol.endswith('-USD'):
            symbol = symbol[:-4] + '-EUR'
            name = name.removesuffix(' USD') + ' EUR'
        exchange, exchange_name = 'CCC', None

    return {
        'asset_id': None,
        'symbol': symbol,
        'name': name,
        'exchange': exchange_name,
        'asset_type': yahoo.ASSET_TYPES.get(quote_type, 'other'),
        'eur': exchange in EUR_EXCHANGES or symbol.endswith('-EUR'),
        '_xetra': exchange == XETRA,
    }


def _from_asset(asset):
    return {
        'asset_id': asset.id,
        'symbol': asset.symbol,
        'name': asset.name,
        'exchange': asset.exchange,
        'asset_type': asset.asset_type,
        'eur': asset.currency == 'EUR',
        '_xetra': False,
    }


def _rank(result):
    if result['asset_id']:
        return 0
    if result['_xetra'] or (result['eur'] and result['asset_type'] == 'crypto'):
        return 1
    if result['eur']:
        return 2
    return 3


def search_assets(query):
    """Ergebnisliste für eine Eingabe wie "SAP", "Bitcoin" oder eine ISIN."""
    query = query.strip()
    pattern = f'%{query}%'
    known = Asset.query.filter(db.or_(Asset.symbol.ilike(pattern), Asset.name.ilike(pattern))) \
        .order_by(Asset.name).limit(MAX_RESULTS).all()
    results = [_from_asset(asset) for asset in known]

    try:
        quotes = yahoo.search_quotes(query)
    except Exception:
        # Ohne Yahoo bleiben wenigstens die bekannten Assets
        quotes = []

    for quote in quotes:
        result = _from_quote(quote)
        if result:
            results.append(result)

    # Direkt eingegebenes Symbol (z.B. "TL0.DE"), das die Suche nicht findet
    if not quotes and not known and ' ' not in query:
        metadata = yahoo.fetch_metadata(query.upper())
        if metadata:
            results.append({'asset_id': None, 'symbol': query.upper(), 'name': query.upper(),
                            'exchange': metadata['exchange'], 'asset_type': metadata['asset_type'],
                            'eur': metadata['currency'] == 'EUR', '_xetra': False})

    # Doppelte Symbole entfernen (bekanntes Asset gewinnt), stabil sortieren
    unique = {}
    for result in results:
        unique.setdefault(result['symbol'], result)
    ranked = sorted(unique.values(), key=_rank)[:MAX_RESULTS]
    for result in ranked:
        del result['_xetra']
    return ranked


def create_asset(symbol, name=None):
    """
    Legt das ausgewählte Asset an, falls es noch nicht existiert, und lädt
    seine Kurshistorie. Gibt (asset, neu angelegt?) zurück.
    """
    symbol = symbol.strip().upper()
    asset = Asset.query.filter_by(symbol=symbol).first()
    if asset:
        return asset, False

    metadata = yahoo.fetch_metadata(symbol)
    if not metadata:
        raise ApiError(404, f"Asset '{symbol}' nicht gefunden")

    asset = Asset(name=(name or symbol).strip()[:200], symbol=symbol, asset_type=metadata['asset_type'],
                  currency=metadata['currency'], exchange=metadata['exchange'])
    db.session.add(asset)
    db.session.commit()
    prepare_new_asset(asset)
    return asset, True
