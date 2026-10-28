"""
portfolio/routes.py - Assets, Positionen (Kauf/Verkauf), Wertverlauf,
Watchlist, Sparpläne und verbuchte Dividenden.
"""

# Standard Library
from datetime import datetime

# Third Party
import yfinance as yf
from flask import Blueprint, request, jsonify

# Lokale Imports
from fintrack.extensions import db
from fintrack.market.data import get_historical_prices
from fintrack.market.prices import get_current_price
from fintrack.models import (Asset, AssetTransaction, Dividend, PriceHistory,
                             SavingsPlan, UserAsset, Watchlist)

bp = Blueprint('portfolio', __name__)


@bp.route('/assets/<asset_id>', methods=['GET'])
def get_asset(asset_id):
    """
    Asset Details abrufen inkl. aktuellem Preis.
    Preis wird live von yfinance oder CoinGecko geholt.
    """
    asset = db.session.get(Asset, asset_id)

    if not asset:
        return jsonify({"error": "Asset not found"}), 404

    # Aktuellen Preis je nach Asset-Typ holen
    current_price = get_current_price(asset)

    return jsonify({
        "id": asset.id,
        "name": asset.name,
        "symbol": asset.symbol,
        "asset_type": asset.asset_type,
        "current_price": current_price
    }), 200


@bp.route('/assets/search', methods=['GET'])
def search_asset():
    """
    Asset suchen - zuerst in DB, dann mit yfinance.
    Nutzer kann Name oder Symbol eingeben z.B. 'Tesla' oder 'TSLA'.
    Wenn Asset nicht in DB ist wird es automatisch erstellt.
    """
    query = request.args.get('query')

    # Erst versuchen, direkt per Symbol in der DB zu finden -
    # deckt den Fall ab, dass der Nutzer bereits das exakte Symbol eintippt
    asset = Asset.query.filter_by(symbol=query.upper()).first()

    if not asset:
        try:
            # Mit yfinance nach Name oder Symbol suchen, um das
            # kanonische Ticker-Symbol zu ermitteln
            search = yf.Search(query)
            quotes = search.quotes

            if not quotes:
                return jsonify({"error": f"Asset '{query}' nicht gefunden!"}), 404

            first_result = quotes[0]
            symbol = first_result['symbol']
            name = first_result.get('longname', first_result.get('shortname', symbol))

            # Jetzt, mit dem von yfinance aufgelösten Symbol, NOCHMAL in
            # der DB nachschauen - verhindert Duplikate, wenn der Nutzer
            # z.B. "Nvidia" statt "NVDA" eingegeben hat, das Asset aber
            # bereits unter dem Symbol NVDA existiert
            asset = Asset.query.filter_by(symbol=symbol).first()

            if not asset:
                # Preis validieren um sicherzustellen dass das Asset handelbar ist
                ticker = yf.Ticker(symbol)
                price = ticker.fast_info['lastPrice']

                asset = Asset(
                    name=name,
                    symbol=symbol,
                    asset_type='stock',
                    currency='EUR'
                )
                db.session.add(asset)
                db.session.commit()

                historical_prices = get_historical_prices(symbol)

                if historical_prices:
                    for price_data in historical_prices:
                        new_price = PriceHistory(
                            asset_id=asset.id,
                            date=datetime.strptime(price_data['date'], '%Y-%m-%d'),
                            price=price_data['price'],
                            currency='EUR'
                        )
                        db.session.add(new_price)
                    db.session.commit()
                    print(f"Historische Preise für {symbol} gespeichert!")

        except Exception as e:
            print(f"Error searching asset: {e}")
            return jsonify({"error": f"Asset '{query}' nicht gefunden!"}), 404

    return jsonify({
        "id": asset.id,
        "name": asset.name,
        "symbol": asset.symbol,
        "asset_type": asset.asset_type
    }), 200


@bp.route('/assets/<asset_id>/prices', methods=['POST'])
def add_prices(asset_id):
    """Neuen Preis für ein Asset hinzufügen"""
    data = request.json
    # Datum von String in Python datetime Objekt umwandeln
    date = datetime.strptime(data['date'], '%Y-%m-%d')
    price = data['price']
    currency = data['currency']

    new_price = PriceHistory(asset_id=asset_id, date=date, price=price, currency=currency)
    db.session.add(new_price)
    db.session.commit()

    return jsonify({"message": "Price successfully added"}), 201


@bp.route('/users/<user_id>/assets/transactions', methods=['GET'])
def get_asset_transactions(user_id):
    """
    Vollständige Kauf-/Verkaufshistorie eines Nutzers über alle Assets,
    neueste zuerst. Enthält Asset-Name und -Symbol, damit das Frontend
    nicht pro Zeile einen zusätzlichen Request braucht.
    """
    transactions = AssetTransaction.query.filter_by(user_id=user_id) \
        .order_by(AssetTransaction.date.desc()).all()

    result = []
    for transaction in transactions:
        asset = db.session.get(Asset, transaction.asset_id)

        result.append({
            "id": transaction.id,
            "asset_id": transaction.asset_id,
            "asset_name": asset.name if asset else "Unbekannt",
            "asset_symbol": asset.symbol if asset else "-",
            "type": transaction.type,
            "quantity": transaction.quantity,
            "price": transaction.price,
            "total": round(transaction.quantity * transaction.price, 2),
            "date": transaction.date.strftime('%Y-%m-%d')
        })

    return jsonify(result), 200


@bp.route('/users/<user_id>/assets', methods=['GET'])
def get_user_assets(user_id):
    """
    Alle Assets des Nutzers abrufen.
    Nur Assets mit quantity > 0 werden zurückgegeben.
    Aktueller Preis wird live von yfinance oder CoinGecko geholt.
    """
    # Nur Assets mit quantity > 0 holen - verkaufte Assets ausblenden
    user_assets = UserAsset.query.filter_by(user_id=user_id).filter(UserAsset.quantity > 0).all()

    result = []

    for user_asset in user_assets:
        # Asset aus DB holen um Name und Symbol zu bekommen
        asset = db.session.get(Asset, user_asset.asset_id)

        # Aktuellen Preis je nach Asset-Typ holen
        current_price = get_current_price(asset, unknown_type_default=user_asset.avg_buy_price)

        result.append({
            "asset_id": user_asset.asset_id,
            "name": asset.name,
            "symbol": asset.symbol,
            "quantity": user_asset.quantity,
            "avg_buy_price": user_asset.avg_buy_price,
            "bought_at": user_asset.bought_at,
            "status": user_asset.status,
            "current_price": current_price
        })

    return jsonify(result), 200


@bp.route('/users/<user_id>/assets', methods=['POST'])
def add_user_asset(user_id):
    """
    Neues Asset dem Nutzer zuweisen.
    Legt zusätzlich den ersten Kauf in der Transaktionshistorie an.
    """
    data = request.json
    asset_id = data['asset_id']
    quantity = data['quantity']
    avg_buy_price = data['avg_buy_price']
    bought_at = datetime.strptime(data['bought_at'], '%Y-%m-%d')
    status = data['status']

    user_asset = UserAsset(
        user_id=user_id,
        asset_id=asset_id,
        quantity=quantity,
        avg_buy_price=avg_buy_price,
        bought_at=bought_at,
        status=status
    )
    db.session.add(user_asset)

    # Ersten Kauf zusätzlich in der Transaktionshistorie protokollieren
    transaction = AssetTransaction(
        user_id=user_id,
        asset_id=asset_id,
        type='buy',
        quantity=float(quantity),
        price=float(avg_buy_price),
        date=bought_at
    )
    db.session.add(transaction)

    db.session.commit()

    return jsonify({"message": "User asset successfully added"}), 201


@bp.route('/users/<user_id>/assets/<asset_id>/buy', methods=['PUT'])
def add_buy(user_id, asset_id):
    """
    Weiteren Kauf eines Assets hinzufügen.
    Berechnet neuen Durchschnittspreis basierend auf altem und neuem Kauf,
    und protokolliert den Kauf zusätzlich in der Transaktionshistorie.
    """
    data = request.json
    quantity = data['quantity']
    price = data['price']

    user_asset = UserAsset.query.filter_by(user_id=user_id, asset_id=asset_id).first()

    if not user_asset:
        return jsonify({"error": "Asset not found"}), 404

    # Neuen Durchschnittspreis berechnen
    old_value = user_asset.quantity * user_asset.avg_buy_price
    new_value = float(quantity) * float(price)
    new_quantity = user_asset.quantity + float(quantity)
    new_avg_price = (old_value + new_value) / new_quantity

    user_asset.quantity = new_quantity
    user_asset.avg_buy_price = round(new_avg_price, 2)

    # Kauf zusätzlich in der Transaktionshistorie protokollieren
    transaction = AssetTransaction(
        user_id=user_id,
        asset_id=asset_id,
        type='buy',
        quantity=float(quantity),
        price=float(price)
    )
    db.session.add(transaction)

    db.session.commit()

    return jsonify({"message": "Buy successfully added"}), 200


@bp.route('/users/<user_id>/assets/<asset_id>/sell', methods=['PUT'])
def add_sell(user_id, asset_id):
    """
    Verkauf eines Assets hinzufügen.
    Reduziert die Menge - wenn alles verkauft wird Status auf 'sold' gesetzt.
    Protokolliert den Verkauf zusätzlich in der Transaktionshistorie.
    """
    data = request.json
    quantity = data['quantity']
    price = data.get('price')  # Verkaufspreis, optional falls Frontend ihn noch nicht schickt

    user_asset = UserAsset.query.filter_by(user_id=user_id, asset_id=asset_id).first()

    if not user_asset:
        return jsonify({"error": "Asset not found"}), 404

    if float(quantity) > user_asset.quantity:
        return jsonify({"error": "Nicht genug Anteile!"}), 400

    user_asset.quantity -= float(quantity)

    if user_asset.quantity == 0:
        user_asset.status = "sold"

    # Verkauf zusätzlich in der Transaktionshistorie protokollieren
    transaction = AssetTransaction(
        user_id=user_id,
        asset_id=asset_id,
        type='sell',
        quantity=float(quantity),
        price=float(price) if price else user_asset.avg_buy_price
    )
    db.session.add(transaction)

    db.session.commit()

    return jsonify({"message": "Sell successfully added"}), 200


@bp.route('/users/<user_id>/portfolio/history', methods=['GET'])
def get_portfolio_history(user_id):
    """
    Preishistorie aller aktiven Assets des Nutzers abrufen.
    Wird für den Liniendiagramm auf dem Dashboard verwendet.
    Nur Assets mit quantity > 0 werden berücksichtigt.
    """
    # Nur aktive Assets holen - verkaufte Assets ausblenden
    user_assets = UserAsset.query.filter_by(user_id=user_id).filter(UserAsset.quantity > 0).all()

    result = {}

    for user_asset in user_assets:
        asset = db.session.get(Asset, user_asset.asset_id)

        # Preishistorie für dieses Asset holen - älteste zuerst
        prices = PriceHistory.query.filter_by(asset_id=user_asset.asset_id) \
            .order_by(PriceHistory.date.asc()).all()

        # Preis × Menge = Portfoliowert für dieses Asset
        result[asset.name] = [
            {
                "date": price.date.strftime('%Y-%m-%d'),
                "price": price.price * user_asset.quantity
            }
            for price in prices
            if price.price is not None
        ]

    return jsonify(result), 200


@bp.route('/users/<user_id>/watchlist', methods=['POST'])
def add_to_watchlist(user_id):
    """Asset zur Watchlist hinzufügen mit aktuellem Preis"""
    data = request.json
    asset_id = data['asset_id']

    # Asset aus DB holen um den aktuellen Preis zu speichern
    asset = db.session.get(Asset, asset_id)

    # Aktuellen Preis holen je nach Asset-Typ
    price_added = get_current_price(asset)

    # added_at wird automatisch auf aktuelle Zeit gesetzt
    new_watchlist = Watchlist(user_id=user_id, asset_id=asset_id, price_added=price_added)
    db.session.add(new_watchlist)
    db.session.commit()

    return jsonify({"message": "Watchlist successfully updated"}), 201


@bp.route('/users/<user_id>/watchlist', methods=['GET'])
def get_watchlist(user_id):
    """Alle Assets der Watchlist eines Nutzers abrufen"""
    assets = Watchlist.query.filter_by(user_id=user_id).all()

    result = []
    for asset in assets:
        result.append({
            "user_id": asset.user_id,
            "asset_id": asset.asset_id,
            "price_added": asset.price_added,
            "added_at": asset.added_at.strftime('%d.%m.%Y') if asset.added_at else '-'
        })

    return jsonify(result), 200


@bp.route('/users/<user_id>/watchlist/<asset_id>', methods=['DELETE'])
def delete_asset_from_watchlist(user_id, asset_id):
    """Asset aus der Watchlist entfernen"""
    watchlist_item = Watchlist.query.filter_by(user_id=user_id, asset_id=asset_id).first()

    if not watchlist_item:
        return jsonify({"error": "Item not found"}), 404

    db.session.delete(watchlist_item)
    db.session.commit()

    return jsonify({"message": "Watchlist successfully updated"}), 200


@bp.route('/users/<user_id>/savings-plans', methods=['POST'])
def add_savings_plan(user_id):
    """Neuen Sparplan anlegen"""
    data = request.json
    asset_id = data['asset_id']
    amount = data['amount']
    day_of_month = data['day_of_month']

    plan = SavingsPlan(
        user_id=user_id,
        asset_id=asset_id,
        amount=amount,
        day_of_month=day_of_month
    )
    db.session.add(plan)
    db.session.commit()

    return jsonify({"message": "Sparplan erfolgreich angelegt"}), 201


@bp.route('/users/<user_id>/savings-plans', methods=['GET'])
def get_savings_plans(user_id):
    """
    Alle Sparpläne eines Nutzers abrufen, inkl. Asset-Info und ob der
    Sparplan aktuell fällig ist (Tag im Monat erreicht, seit dem
    letzten Ausführen noch nicht in diesem Zyklus gebucht).
    """
    plans = SavingsPlan.query.filter_by(user_id=user_id, active=True).all()

    today = datetime.now()
    result = []

    for plan in plans:
        asset = db.session.get(Asset, plan.asset_id)

        # Fällig wenn: heutiger Tag >= geplanter Tag im Monat,
        # UND (noch nie ausgeführt ODER letzte Ausführung liegt vor
        # dem aktuellen Fälligkeitstermin dieses Monats)
        due_date_this_month = datetime(today.year, today.month, min(plan.day_of_month, 28))
        is_due = today >= due_date_this_month and (
            plan.last_executed is None or plan.last_executed < due_date_this_month
        )

        result.append({
            "id": plan.id,
            "asset_id": plan.asset_id,
            "asset_name": asset.name if asset else "Unbekannt",
            "asset_symbol": asset.symbol if asset else "-",
            "amount": plan.amount,
            "day_of_month": plan.day_of_month,
            "last_executed": plan.last_executed.strftime('%Y-%m-%d') if plan.last_executed else None,
            "is_due": is_due
        })

    return jsonify(result), 200


@bp.route('/savings-plans/<plan_id>', methods=['DELETE'])
def delete_savings_plan(plan_id):
    """Sparplan löschen"""
    plan = db.session.get(SavingsPlan, plan_id)

    if not plan:
        return jsonify({"error": "Sparplan nicht gefunden"}), 404

    db.session.delete(plan)
    db.session.commit()

    return jsonify({"message": "Sparplan gelöscht"}), 200


@bp.route('/savings-plans/<plan_id>/execute', methods=['POST'])
def execute_savings_plan(plan_id):
    """
    Führt einen fälligen Sparplan aus: holt den aktuellen Live-Preis,
    berechnet die Menge aus dem festen Euro-Betrag, legt eine normale
    Kauf-Transaktion an (inkl. UserAsset-Aktualisierung) und schreibt
    last_executed fort.
    """
    plan = db.session.get(SavingsPlan, plan_id)

    if not plan:
        return jsonify({"error": "Sparplan nicht gefunden"}), 404

    asset = db.session.get(Asset, plan.asset_id)

    current_price = get_current_price(asset)

    if not current_price:
        return jsonify({"error": "Aktueller Preis konnte nicht ermittelt werden"}), 500

    quantity = round(plan.amount / current_price, 6)

    # Bestehende Position suchen oder neu anlegen - gleiche Logik
    # wie beim manuellen Kauf über add_buy / add_user_asset
    user_asset = UserAsset.query.filter_by(user_id=plan.user_id, asset_id=plan.asset_id).first()

    if user_asset:
        old_value = user_asset.quantity * user_asset.avg_buy_price
        new_value = quantity * current_price
        new_quantity = user_asset.quantity + quantity
        user_asset.avg_buy_price = round((old_value + new_value) / new_quantity, 2)
        user_asset.quantity = new_quantity
    else:
        user_asset = UserAsset(
            user_id=plan.user_id,
            asset_id=plan.asset_id,
            quantity=quantity,
            avg_buy_price=current_price,
            status='owned'
        )
        db.session.add(user_asset)

    # Kauf in der Transaktionshistorie protokollieren
    transaction = AssetTransaction(
        user_id=plan.user_id,
        asset_id=plan.asset_id,
        type='buy',
        quantity=quantity,
        price=current_price
    )
    db.session.add(transaction)

    # Sparplan als ausgeführt markieren
    plan.last_executed = datetime.now()

    db.session.commit()

    return jsonify({
        "message": "Sparplan erfolgreich ausgeführt",
        "quantity": quantity,
        "price": current_price
    }), 200


@bp.route('/users/<user_id>/dividends', methods=['GET'])
def get_dividends(user_id):
    """
    Alle verbuchten Dividenden eines Nutzers, neueste zuerst.
    Enthält Asset-Name und -Symbol, damit das Frontend nicht pro
    Zeile einen zusätzlichen Request braucht.
    """
    dividends = Dividend.query.filter_by(user_id=user_id) \
        .order_by(Dividend.ex_dividend_date.desc()).all()

    result = []
    for dividend in dividends:
        asset = db.session.get(Asset, dividend.asset_id)

        result.append({
            "id": dividend.id,
            "asset_name": asset.name if asset else "Unbekannt",
            "asset_symbol": asset.symbol if asset else "-",
            "ex_dividend_date": dividend.ex_dividend_date.strftime('%Y-%m-%d'),
            "amount_per_share": dividend.amount_per_share,
            "shares_held": dividend.shares_held,
            "total_amount": dividend.total_amount
        })

    return jsonify(result), 200
