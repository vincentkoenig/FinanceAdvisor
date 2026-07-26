"""
scheduler.py - Automatische Preisaktualisierung
Aktualisiert regelmäßig die Preise aller Assets und schließt dabei
automatisch Lücken in der price_history - falls z.B. mehrere Tage
nicht aktualisiert wurde, werden alle fehlenden Tage nachgeladen.
"""

from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from api_services import get_stock_historical_range, get_crypto_historical_range
from models import db, Asset, PriceHistory

# yfinance Symbole für Edelmetalle
METAL_SYMBOLS = {
    "GOLD": "GC=F",
    "SILVER": "SI=F"
}


def update_prices(flask_app):
    """
    Aktualisiert die Preise aller Assets.
    Prüft für jedes Asset das Datum des letzten gespeicherten Preises
    und lädt alle fehlenden Tage bis heute nach - dadurch entstehen
    keine Lücken im Chart, auch wenn der Scheduler mal ein paar Tage
    nicht lief oder manuell über /update-prices getriggert wird.
    """
    with flask_app.app_context():
        assets = db.session.execute(db.select(Asset)).scalars().all()
        today = datetime.now().date()

        for asset in assets:
            # Letzten gespeicherten Preis für dieses Asset holen
            last_entry = PriceHistory.query.filter_by(asset_id=asset.id) \
                .order_by(PriceHistory.date.desc()).first()

            if last_entry:
                last_date = last_entry.date.date()
            else:
                # Noch kein Preis vorhanden - nur den heutigen Tag holen
                last_date = today - timedelta(days=1)

            # Wenn heute schon gespeichert ist, für dieses Asset nichts zu tun
            if last_date >= today:
                continue

            # Zeitraum: ein Tag nach dem letzten Eintrag bis heute (inklusive)
            start_date = last_date + timedelta(days=1)
            historical = []

            if asset.asset_type in ("stock", "etf"):
                historical = get_stock_historical_range(asset.symbol, start_date, today + timedelta(days=1))

            elif asset.asset_type == "metal":
                symbol = METAL_SYMBOLS.get(asset.symbol, asset.symbol)
                historical = get_stock_historical_range(symbol, start_date, today + timedelta(days=1))

            elif asset.asset_type == "crypto":
                from_ts = int(datetime.combine(start_date, datetime.min.time()).timestamp())
                to_ts = int(datetime.combine(today, datetime.min.time()).timestamp()) + 86400
                historical = get_crypto_historical_range(asset.symbol, from_ts, to_ts)

            # Fehlende Preise in die DB einfügen
            for entry in historical:
                # Einträge ohne gültigen Preis überspringen
                if entry.get('price') is None:
                    continue

                entry_date = datetime.strptime(entry['date'], '%Y-%m-%d')

                exists = PriceHistory.query.filter_by(
                    asset_id=asset.id, date=entry_date
                ).first()

                if not exists:
                    new_price = PriceHistory(
                        asset_id=asset.id,
                        date=entry_date,
                        price=entry['price'],
                        currency=asset.currency
                    )
                    db.session.add(new_price)

        db.session.commit()
        print(f"Prices updated successfully at {datetime.now()}")


def start_scheduler(flask_app):
    """Startet den Scheduler - aktualisiert die Preise täglich um 18:00 Uhr."""
    scheduler = BackgroundScheduler()
    scheduler.add_job(update_prices, 'cron', hour=18, minute=0, args=[flask_app])
    scheduler.start()
    print("Scheduler started - prices will update daily at 18:00")