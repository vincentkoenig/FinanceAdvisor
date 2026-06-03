"""
scheduler.py - Automatische tägliche Preisaktualisierung
Ruft täglich um 18:00 Uhr die aktuellen Preise aller Assets ab
und speichert sie in der price_history Tabelle.
"""

from apscheduler.schedulers.background import BackgroundScheduler
from api_services import get_crypto_price, get_stock_price, get_metal_price
from models import db, Asset, PriceHistory
from datetime import datetime


def update_prices(flask_app):
    with flask_app.app_context():
        assets = db.session.execute(db.select(Asset)).scalars().all()

        for asset in assets:
            if asset.asset_type == "stock" or asset.asset_type == "etf":
                current_price = get_stock_price(asset.symbol)
            elif asset.asset_type == "crypto":
                current_price = get_crypto_price(asset.symbol)
            elif asset.asset_type == "metal":
                current_price = get_metal_price(asset.symbol)

            if current_price:
                new_price = PriceHistory(
                    asset_id=asset.id,
                    price=current_price,
                    currency=asset.currency
                )
                db.session.add(new_price)

        db.session.commit()
        print(f"Prices updated successfully at {datetime.now()}")


def start_scheduler(flask_app):
    scheduler = BackgroundScheduler()
    scheduler.add_job(update_prices, 'cron', hour=18, minute=0, args=[flask_app])
    scheduler.start()
    print("Scheduler started - prices will update daily at 18:00")