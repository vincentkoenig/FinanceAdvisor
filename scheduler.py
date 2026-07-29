"""
scheduler.py - Automatische Preisaktualisierung
Aktualisiert regelmäßig die Preise aller Assets und schließt dabei
automatisch Lücken in der price_history - falls z.B. mehrere Tage
nicht aktualisiert wurde, werden alle fehlenden Tage nachgeladen.
Der heutige Preis wird zusätzlich immer explizit über die Live-Preis-
Funktionen gesetzt, da yfinance's historische Preis-Range den
aktuellen, noch nicht abgeschlossenen Handelstag oft nicht liefert.
"""

from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from api_services import (
    get_stock_price, get_crypto_price, get_metal_price,
    get_stock_historical_range, get_crypto_historical_range
)
from models import db, Asset, PriceHistory

# yfinance Symbole für Edelmetalle
METAL_SYMBOLS = {
    "GOLD": "GC=F",
    "SILVER": "SI=F"
}


def update_prices(flask_app):
    """
    Aktualisiert die Preise aller Assets.
    1. Schließt Lücken zwischen dem letzten gültigen (nicht-NULL) Preis
       und heute über die historische Preis-Range.
    2. Setzt für heute zusätzlich immer den aktuellen Live-Preis,
       damit der heutige Tag garantiert einen Preis hat.
    """
    with flask_app.app_context():
        assets = db.session.execute(db.select(Asset)).scalars().all()
        today = datetime.now().date()
        today_datetime = datetime.combine(today, datetime.min.time())

        for asset in assets:
            # Letzten Preis mit einem gültigen Wert holen - NULL-Einträge
            # werden hier bewusst ausgeschlossen, damit sie nicht als
            # aktuellster Stand gezählt werden
            last_entry = PriceHistory.query.filter_by(asset_id=asset.id) \
                .filter(PriceHistory.price.isnot(None)) \
                .order_by(PriceHistory.date.desc()).first()

            last_date = last_entry.date.date() if last_entry else today - timedelta(days=1)

            # ─── Lücke bis heute schließen ───
            if last_date < today:
                start_date = last_date + timedelta(days=1)
                historical = []

                if asset.asset_type in ("stock", "etf"):
                    historical = get_stock_historical_range(asset.symbol, start_date, today)
                elif asset.asset_type == "metal":
                    symbol = METAL_SYMBOLS.get(asset.symbol, asset.symbol)
                    historical = get_stock_historical_range(symbol, start_date, today)
                elif asset.asset_type == "crypto":
                    from_ts = int(datetime.combine(start_date, datetime.min.time()).timestamp())
                    to_ts = int(datetime.combine(today, datetime.min.time()).timestamp())
                    historical = get_crypto_historical_range(asset.symbol, from_ts, to_ts)

                for entry in historical:
                    if entry.get('price') is None:
                        continue

                    entry_date = datetime.strptime(entry['date'], '%Y-%m-%d')
                    existing = PriceHistory.query.filter_by(
                        asset_id=asset.id, date=entry_date
                    ).first()

                    if existing:
                        # Bestehenden Eintrag nur aktualisieren, wenn er
                        # noch keinen Preis hat
                        if existing.price is None:
                            existing.price = entry['price']
                    else:
                        db.session.add(PriceHistory(
                            asset_id=asset.id,
                            date=entry_date,
                            price=entry['price'],
                            currency=asset.currency
                        ))

            # ─── Heutigen Preis über die Live-Funktion setzen ───
            if asset.asset_type in ("stock", "etf"):
                current_price = get_stock_price(asset.symbol)
            elif asset.asset_type == "crypto":
                current_price = get_crypto_price(asset.symbol)
            elif asset.asset_type == "metal":
                current_price = get_metal_price(asset.symbol)
            else:
                current_price = None

            if current_price is not None:
                today_entry = PriceHistory.query.filter_by(
                    asset_id=asset.id, date=today_datetime
                ).first()

                if today_entry:
                    today_entry.price = current_price
                else:
                    db.session.add(PriceHistory(
                        asset_id=asset.id,
                        date=today_datetime,
                        price=current_price,
                        currency=asset.currency
                    ))

        db.session.commit()
        print(f"Prices updated successfully at {datetime.now()}")


def start_scheduler(flask_app):
    """Startet den Scheduler - aktualisiert die Preise täglich um 18:00 Uhr."""
    scheduler = BackgroundScheduler()
    scheduler.add_job(update_prices, 'cron', hour=18, minute=0, args=[flask_app])
    scheduler.start()
    print("Scheduler started - prices will update daily at 18:00")