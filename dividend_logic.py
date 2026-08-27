"""
dividend_logic.py - Automatische Erkennung und Verbuchung von
Dividendenausschüttungen. Wird vom Scheduler regelmäßig aufgerufen,
gleicht yfinance-Dividendendaten mit der Kaufhistorie (AssetTransaction)
ab und legt bei neuen Ausschüttungen automatisch eine Dividend-Zeile
sowie eine passende Transaction im Haushaltsbuch an.
"""

from datetime import datetime

from models import db, User, Asset, UserAsset, AssetTransaction, Dividend, Category, Transaction
from api_services import get_dividends_since, get_exchange_rate


def calculate_shares_held_at(user_id, asset_id, target_date):
    """
    Berechnet, wie viele Stück eines Assets ein Nutzer an einem
    bestimmten Datum hielt, basierend auf der Transaktionshistorie
    bis zu diesem Zeitpunkt (Käufe addiert, Verkäufe subtrahiert).
    Falls keine Transaktionshistorie vor diesem Datum existiert (z.B.
    weil die Position vor Einführung der Transaktions-Protokollierung
    angelegt wurde), wird ersatzweise die aktuelle Bestandsmenge
    verwendet - eine Näherung, die zwischenzeitliche Käufe/Verkäufe
    nicht berücksichtigen kann, aber besser ist als 0 anzunehmen.
    """
    transactions = AssetTransaction.query.filter_by(
        user_id=user_id, asset_id=asset_id
    ).filter(AssetTransaction.date <= target_date).all()

    if not transactions:
        user_asset = UserAsset.query.filter_by(user_id=user_id, asset_id=asset_id).first()
        return user_asset.quantity if user_asset else 0

    shares = 0
    for transaction in transactions:
        if transaction.type == 'buy':
            shares += transaction.quantity
        else:
            shares -= transaction.quantity

    return shares


def process_dividends_for_user(user_id):
    holdings = UserAsset.query.filter_by(user_id=user_id).filter(UserAsset.quantity > 0).all()
    print(f"Prüfe Dividenden für {len(holdings)} gehaltene Assets")

    dividend_category = Category.query.filter_by(user_id=user_id, name="Dividenden").first()

    if not dividend_category:
        print("Keine Dividenden-Kategorie gefunden - breche ab")
        return

    for holding in holdings:
        asset = db.session.get(Asset, holding.asset_id)
        if not asset:
            continue

        print(f"\nPrüfe {asset.name} ({asset.symbol})...")

        last_dividend = Dividend.query.filter_by(
            user_id=user_id, asset_id=asset.id
        ).order_by(Dividend.ex_dividend_date.desc()).first()

        since_date = last_dividend.ex_dividend_date if last_dividend else datetime(datetime.now().year - 1, 1, 1)
        print(f"  Suche Dividenden seit {since_date}")

        new_dividends = get_dividends_since(asset.symbol, since_date)
        print(f"  Gefundene neue Dividenden: {new_dividends}")

        if not new_dividends:
            continue

        rate = get_exchange_rate("USD", "EUR")

        for entry in new_dividends:
            dividend_date = datetime.strptime(entry['date'], '%Y-%m-%d')
            amount_per_share = entry['amount_per_share'] * rate

            shares_held = calculate_shares_held_at(user_id, asset.id, dividend_date)
            print(f"    Am {dividend_date.date()}: {shares_held} Stück gehalten")

            if shares_held <= 0:
                print(f"    -> übersprungen, keine Stücke gehalten")
                continue

            total_amount = round(amount_per_share * shares_held, 2)
            print(f"    -> verbuche {total_amount} EUR")

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