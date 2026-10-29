"""
portfolio/dividends.py - Automatische Erkennung und Verbuchung von
Dividendenausschüttungen. Wird vom Scheduler regelmäßig aufgerufen,
gleicht yfinance-Dividendendaten mit der Kaufhistorie (AssetTransaction)
ab und legt bei neuen Ausschüttungen automatisch eine Dividend-Zeile
sowie eine passende Transaction im Haushaltsbuch an.
Beträge kommen in der Handelswährung und werden mit dem Wechselkurs des
Ex-Tags in Euro umgerechnet - nicht mit dem von heute.
"""

from datetime import datetime

from fintrack.market import yahoo
from fintrack.market.service import fx_rate_on, update_fx_rates
from fintrack.models import db, User, Asset, UserAsset, Dividend, Category, Transaction
from fintrack.portfolio.history import shares_held_on


def calculate_shares_held_at(user_id, asset_id, target_date):
    """
    Wie viele Stück eines Assets ein Nutzer am Ende dieses Tages hielt,
    rekonstruiert aus Käufen und Verkäufen (siehe portfolio/history.py).
    """
    return shares_held_on(user_id, asset_id, target_date.date())


def process_dividends_for_user(user_id):
    holdings = UserAsset.query.filter_by(user_id=user_id).filter(UserAsset.quantity > 0).all()

    dividend_category = Category.query.filter_by(user_id=user_id, name="Dividenden").first()

    if not dividend_category:
        return

    for holding in holdings:
        asset = db.session.get(Asset, holding.asset_id)
        if not asset:
            continue


        last_dividend = Dividend.query.filter_by(
            user_id=user_id, asset_id=asset.id
        ).order_by(Dividend.ex_dividend_date.desc()).first()

        since_date = last_dividend.ex_dividend_date if last_dividend else datetime(datetime.now().year - 1, 1, 1)

        new_dividends = yahoo.fetch_dividends(asset.symbol, since_date.date())

        if not new_dividends:
            continue

        currency = asset.currency or 'EUR'
        update_fx_rates(currency)

        for ex_day, native_amount in new_dividends:
            rate = fx_rate_on(currency, ex_day)
            if rate is None:
                # Ohne Wechselkurs lieber nichts buchen als einen falschen Betrag
                continue
            dividend_date = datetime.combine(ex_day, datetime.min.time())
            amount_per_share = native_amount * rate

            shares_held = calculate_shares_held_at(user_id, asset.id, dividend_date)

            if shares_held <= 0:
                continue

            total_amount = round(amount_per_share * shares_held, 2)

            # Transaction im Haushaltsbuch anlegen
            transaction = Transaction(
                user_id=user_id,
                category_id=dividend_category.id,
                amount=total_amount,
                description=f"Dividende {asset.name}",
                date=dividend_date,
                is_recurring=False
            )
            db.session.add(transaction)
            db.session.flush()  # damit transaction.id sofort verfügbar ist

            # Dividend-Eintrag zur Nachverfolgung anlegen
            dividend = Dividend(
                user_id=user_id,
                asset_id=asset.id,
                ex_dividend_date=dividend_date,
                amount_per_share=round(amount_per_share, 4),
                shares_held=shares_held,
                total_amount=total_amount,
                transaction_id=transaction.id
            )
            db.session.add(dividend)

    db.session.commit()


def process_dividends_for_all_users():
    """Führt die Dividendenverbuchung für alle Nutzer der App aus."""
    users = User.query.all()
    for user in users:
        process_dividends_for_user(user.id)