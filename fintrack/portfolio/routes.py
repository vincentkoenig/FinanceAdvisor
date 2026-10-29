"""
portfolio/routes.py - API für Assets, Positionen (Kauf/Verkauf),
Wertverlauf, Watchlist, Sparpläne und verbuchte Dividenden.
Registriert unter /api/v1. Alle Routen unter /me/ beziehen sich immer auf
den angemeldeten Nutzer.
"""

# Standard Library
from datetime import datetime

# Third Party
import yfinance as yf
from flask import Blueprint, jsonify
from flask_login import current_user

# Lokale Imports
from fintrack.api import ApiError, parse_body, parse_query
from fintrack.auth.session import get_own, protect_blueprint
from fintrack.extensions import db
from fintrack.market.prices import get_current_price
from fintrack.models import (Asset, AssetTransaction, Dividend, PriceHistory,
                             SavingsPlan, UserAsset, Watchlist)
from fintrack.portfolio.schemas import (AssetSearchQuery, BuyTrade, PositionCreate,
                                        SavingsPlanCreate, SellTrade, WatchlistAdd)
from fintrack.portfolio.service import load_price_history, record_buy, record_sell

bp = Blueprint('portfolio', __name__)
# Nur mit Anmeldung
protect_blueprint(bp)


def get_asset_or_404(asset_id):
    asset = db.session.get(Asset, asset_id)
    if not asset:
        raise ApiError(404, 'Asset nicht gefunden')
    return asset


# ─── ASSETS (für alle Nutzer gleich) ──────────────────────────────────────────

@bp.route('/assets/<int:asset_id>', methods=['GET'])
def get_asset(asset_id):
    """
    Asset Details abrufen inkl. aktuellem Preis.
    Preis wird live von yfinance oder CoinGecko geholt.
    """
    asset = get_asset_or_404(asset_id)

    return jsonify({
        "id": asset.id,
        "name": asset.name,
        "symbol": asset.symbol,
        "asset_type": asset.asset_type,
        "current_price": get_current_price(asset)
    }), 200


@bp.route('/assets/search', methods=['GET'])
def search_asset():
    """
    Asset suchen - zuerst in DB, dann mit yfinance.
    Nutzer kann Name oder Symbol eingeben z.B. 'Tesla' oder 'TSLA'.
    Wenn Asset nicht in DB ist wird es automatisch erstellt.
    """
    query = parse_query(AssetSearchQuery).query

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

                load_price_history(asset)

        except Exception as e:
            print(f"Error searching asset: {e}")
            return jsonify({"error": f"Asset '{query}' nicht gefunden!"}), 404

    return jsonify({
        "id": asset.id,
        "name": asset.name,
        "symbol": asset.symbol,
        "asset_type": asset.asset_type
    }), 200


# ─── POSITIONEN ───────────────────────────────────────────────────────────────

@bp.route('/me/positions', methods=['GET'])
def get_positions():
    """
    Alle Positionen des Nutzers mit Menge > 0, inkl. Live-Preis von
    yfinance oder CoinGecko.
    """
    positions = UserAsset.query.filter_by(user_id=current_user.id).filter(UserAsset.quantity > 0).all()

    result = []
    for position in positions:
        # Asset aus DB holen um Name und Symbol zu bekommen
        asset = db.session.get(Asset, position.asset_id)

        result.append({
            "asset_id": position.asset_id,
            "name": asset.name,
            "symbol": asset.symbol,
            "quantity": position.quantity,
            "avg_buy_price": position.avg_buy_price,
            "bought_at": position.bought_at,
            "status": position.status,
            "current_price": get_current_price(asset, unknown_type_default=position.avg_buy_price)
        })

    return jsonify(result), 200


@bp.route('/me/positions', methods=['POST'])
def add_position():
    """
    Kauf eines Assets erfassen. Ist das Asset schon im Depot, wird der Kauf
    zur bestehenden Position addiert (neuer Durchschnittspreis) statt eine
    zweite Position anzulegen.
    """
    data = parse_body(PositionCreate)
    get_asset_or_404(data.asset_id)

    record_buy(current_user.id, data.asset_id, data.quantity, data.avg_buy_price,
               datetime.combine(data.bought_at, datetime.min.time()))
    db.session.commit()

    return jsonify({"message": "Position gespeichert"}), 201


@bp.route('/me/positions/<int:asset_id>/buy', methods=['POST'])
def buy(asset_id):
    """Weiteren Kauf zu einer bestehenden Position erfassen."""
    data = parse_body(BuyTrade)
    position = UserAsset.query.filter_by(user_id=current_user.id, asset_id=asset_id).first()
    if not position:
        raise ApiError(404, 'Position nicht gefunden')

    record_buy(current_user.id, asset_id, data.quantity, data.price)
    db.session.commit()

    return jsonify({"message": "Kauf gespeichert"}), 200


@bp.route('/me/positions/<int:asset_id>/sell', methods=['POST'])
def sell(asset_id):
    """
    Verkauf erfassen. Reduziert die Menge - wenn alles verkauft wird,
    wird der Status auf 'sold' gesetzt.
    """
    data = parse_body(SellTrade)

    record_sell(current_user.id, asset_id, data.quantity, data.price)
    db.session.commit()

    return jsonify({"message": "Verkauf gespeichert"}), 200


@bp.route('/me/asset-transactions', methods=['GET'])
def get_asset_transactions():
    """
    Vollständige Kauf-/Verkaufshistorie über alle Assets, neueste zuerst.
    Enthält Asset-Name und -Symbol, damit das Frontend nicht pro Zeile
    einen zusätzlichen Request braucht.
    """
    transactions = AssetTransaction.query.filter_by(user_id=current_user.id) \
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


@bp.route('/me/portfolio/history', methods=['GET'])
def get_portfolio_history():
    """
    Preishistorie aller aktiven Positionen für den Wertverlauf-Chart.
    Nur Positionen mit Menge > 0 werden berücksichtigt.
    """
    positions = UserAsset.query.filter_by(user_id=current_user.id).filter(UserAsset.quantity > 0).all()

    result = {}

    for position in positions:
        asset = db.session.get(Asset, position.asset_id)

        # Preishistorie für dieses Asset holen - älteste zuerst
        prices = PriceHistory.query.filter_by(asset_id=position.asset_id) \
            .order_by(PriceHistory.date.asc()).all()

        # Preis × Menge = Portfoliowert für dieses Asset
        result[asset.name] = [
            {
                "date": price.date.strftime('%Y-%m-%d'),
                "price": price.price * position.quantity
            }
            for price in prices
            if price.price is not None
        ]

    return jsonify(result), 200


# ─── WATCHLIST ────────────────────────────────────────────────────────────────

@bp.route('/me/watchlist', methods=['POST'])
def add_to_watchlist():
    """Asset zur Watchlist hinzufügen und den aktuellen Preis merken."""
    data = parse_body(WatchlistAdd)
    asset = get_asset_or_404(data.asset_id)

    existing = Watchlist.query.filter_by(user_id=current_user.id, asset_id=asset.id).first()
    if existing:
        return jsonify({"message": "Asset ist bereits auf der Watchlist"}), 200

    # added_at wird automatisch auf aktuelle Zeit gesetzt
    db.session.add(Watchlist(user_id=current_user.id, asset_id=asset.id,
                             price_added=get_current_price(asset)))
    db.session.commit()

    return jsonify({"message": "Zur Watchlist hinzugefügt"}), 201


@bp.route('/me/watchlist', methods=['GET'])
def get_watchlist():
    """Alle Assets der eigenen Watchlist."""
    items = Watchlist.query.filter_by(user_id=current_user.id).all()

    return jsonify([
        {
            "asset_id": item.asset_id,
            "price_added": item.price_added,
            "added_at": item.added_at.strftime('%d.%m.%Y') if item.added_at else '-'
        }
        for item in items
    ]), 200


@bp.route('/me/watchlist/<int:asset_id>', methods=['DELETE'])
def delete_from_watchlist(asset_id):
    """Asset von der eigenen Watchlist entfernen."""
    item = Watchlist.query.filter_by(user_id=current_user.id, asset_id=asset_id).first()

    if not item:
        raise ApiError(404, 'Nicht auf der Watchlist')

    db.session.delete(item)
    db.session.commit()

    return jsonify({"message": "Von der Watchlist entfernt"}), 200


# ─── SPARPLÄNE ────────────────────────────────────────────────────────────────

@bp.route('/me/savings-plans', methods=['POST'])
def add_savings_plan():
    """Neuen Sparplan anlegen."""
    data = parse_body(SavingsPlanCreate)
    get_asset_or_404(data.asset_id)

    db.session.add(SavingsPlan(user_id=current_user.id, asset_id=data.asset_id,
                               amount=data.amount, day_of_month=data.day_of_month))
    db.session.commit()

    return jsonify({"message": "Sparplan erfolgreich angelegt"}), 201


@bp.route('/me/savings-plans', methods=['GET'])
def get_savings_plans():
    """
    Alle aktiven Sparpläne inkl. Asset-Info und ob der Sparplan aktuell
    fällig ist (Tag im Monat erreicht, seit dem letzten Ausführen noch
    nicht in diesem Zyklus gebucht).
    """
    plans = SavingsPlan.query.filter_by(user_id=current_user.id, active=True).all()

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


@bp.route('/me/savings-plans/<int:plan_id>', methods=['DELETE'])
def delete_savings_plan(plan_id):
    """Eigenen Sparplan löschen."""
    plan = get_own(SavingsPlan, plan_id)

    if not plan:
        raise ApiError(404, 'Sparplan nicht gefunden')

    db.session.delete(plan)
    db.session.commit()

    return jsonify({"message": "Sparplan gelöscht"}), 200


@bp.route('/me/savings-plans/<int:plan_id>/execute', methods=['POST'])
def execute_savings_plan(plan_id):
    """
    Führt einen fälligen Sparplan aus: holt den aktuellen Live-Preis,
    berechnet die Menge aus dem festen Euro-Betrag, verbucht einen ganz
    normalen Kauf und schreibt last_executed fort.
    """
    plan = get_own(SavingsPlan, plan_id)

    if not plan:
        raise ApiError(404, 'Sparplan nicht gefunden')

    asset = db.session.get(Asset, plan.asset_id)
    current_price = get_current_price(asset)

    if not current_price:
        raise ApiError(502, 'Aktueller Preis konnte nicht ermittelt werden')

    quantity = round(plan.amount / current_price, 6)
    record_buy(current_user.id, plan.asset_id, quantity, current_price)

    # Sparplan als ausgeführt markieren
    plan.last_executed = datetime.now()
    db.session.commit()

    return jsonify({
        "message": "Sparplan erfolgreich ausgeführt",
        "quantity": quantity,
        "price": current_price
    }), 200


# ─── DIVIDENDEN ───────────────────────────────────────────────────────────────

@bp.route('/me/dividends', methods=['GET'])
def get_dividends():
    """
    Alle verbuchten Dividenden, neueste zuerst. Enthält Asset-Name und
    -Symbol, damit das Frontend nicht pro Zeile einen zusätzlichen
    Request braucht.
    """
    dividends = Dividend.query.filter_by(user_id=current_user.id) \
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
