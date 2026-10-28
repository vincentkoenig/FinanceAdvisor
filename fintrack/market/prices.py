"""
prices.py - Zentraler Zugriff auf den aktuellen Preis eines Assets.
Wählt je nach Asset-Typ die passende Datenquelle (yfinance für Aktien,
ETFs und Edelmetalle, CoinGecko für Kryptowährungen). Ersetzt den
Block "Preis je nach Asset-Typ holen", der vorher an sechs Stellen
kopiert war.
"""

from fintrack.market.data import get_crypto_price, get_metal_price, get_stock_price


def get_current_price(asset, unknown_type_default=None):
    """
    Liefert den aktuellen Preis eines Assets in EUR.
    Gibt None zurück, wenn die Datenquelle keinen Preis liefert.
    unknown_type_default wird nur für Assets ohne bekannten Typ genutzt -
    manche Aufrufer setzen dort z.B. den Kaufpreis als Ersatzwert ein.
    """
    if asset.asset_type in ("stock", "etf"):
        return get_stock_price(asset.symbol)
    if asset.asset_type == "crypto":
        return get_crypto_price(asset.symbol)
    if asset.asset_type == "metal":
        return get_metal_price(asset.symbol)
    return unknown_type_default
