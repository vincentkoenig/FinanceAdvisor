"""
account/transfer.py - Export und Import aller Daten eines Nutzers.

Export: Alle eigenen Daten als ein Dictionary im Format aus schemas.py.
Verweise laufen über fortlaufende "ref"-Nummern in fester Reihenfolge,
damit derselbe Datenbestand immer dieselbe Datei ergibt.

Import: Nur in ein Konto ohne eigene Daten (Standardkategorien sind
erlaubt und werden ersetzt). Alles läuft in einer einzigen
Datenbank-Transaktion - schlägt irgendetwas fehl, wird nichts gespeichert.
"""

import json
from datetime import datetime

from fintrack.api import ApiError
from fintrack.extensions import db
from fintrack.models import (Asset, AssetTransaction, Category, ChatHistory, Contract, DailyInsight, Dividend,
                             PortfolioAnalysis, SavingsPlan, Transaction, UserAsset, Watchlist)
from fintrack.portfolio.analysis import parse_stored_list
from fintrack.account.schemas import EXPORT_FORMAT, EXPORT_VERSION

# Tabellen mit Nutzerdaten, die beim Import leer sein müssen (Kategorien
# zählen nicht - die legt jede Registrierung automatisch an)
USER_DATA_MODELS = (Transaction, UserAsset, AssetTransaction, SavingsPlan, Watchlist,
                    Dividend, ChatHistory, PortfolioAnalysis, DailyInsight, Contract)


def _iso(value):
    return value.isoformat() if value else None


def _by_id(model, user_id):
    return model.query.filter_by(user_id=user_id).order_by(model.id).all()


def _create(model, **values):
    """
    Legt einen Datensatz an und lässt leere Werte weg. So greifen die
    Standardwerte der Spalten (z.B. created_at = jetzt), statt dass ein
    ausdrückliches None als NULL gespeichert wird.
    """
    obj = model(**{key: value for key, value in values.items() if value is not None})
    db.session.add(obj)
    return obj


def export_user_data(user):
    """Alle Daten des Nutzers als JSON-fähiges Dictionary."""
    user_id = user.id

    # Kategorien: Hauptkategorien zuerst, damit parent_ref immer auf einen
    # früheren Eintrag zeigt
    categories = sorted(_by_id(Category, user_id), key=lambda c: (c.parent_id is not None, c.id))
    category_ref = {c.id: index for index, c in enumerate(categories, start=1)}

    transactions = _by_id(Transaction, user_id)
    transaction_ref = {t.id: index for index, t in enumerate(transactions, start=1)}

    positions = _by_id(UserAsset, user_id)
    asset_transactions = _by_id(AssetTransaction, user_id)
    savings_plans = _by_id(SavingsPlan, user_id)
    watchlist = _by_id(Watchlist, user_id)
    dividends = _by_id(Dividend, user_id)

    # Nur Assets, auf die der Nutzer verweist
    used_asset_ids = sorted({row.asset_id for rows in (positions, asset_transactions, savings_plans,
                                                       watchlist, dividends) for row in rows})
    assets = [db.session.get(Asset, asset_id) for asset_id in used_asset_ids]
    asset_ref = {asset.id: index for index, asset in enumerate(assets, start=1)}

    return {
        "format": EXPORT_FORMAT,
        "version": EXPORT_VERSION,
        "exported_at": datetime.now().replace(microsecond=0).isoformat(),
        "profile": {
            "risk_profile": user.risk_profile,
            "investment_experience": user.investment_experience,
            "monthly_budget": user.monthly_budget,
            "investment_horizon": user.investment_horizon,
        },
        "categories": [
            {"ref": category_ref[c.id], "name": c.name, "type": c.type,
             "parent_ref": category_ref.get(c.parent_id)}
            for c in categories
        ],
        "transactions": [
            {"ref": transaction_ref[t.id], "category_ref": category_ref.get(t.category_id),
             "amount": t.amount, "description": t.description, "date": _iso(t.date),
             "is_recurring": bool(t.is_recurring), "end_date": _iso(t.end_date),
             "is_paused": bool(t.is_paused), "paused_at": _iso(t.paused_at)}
            for t in transactions
        ],
        "assets": [
            {"ref": asset_ref[a.id], "symbol": a.symbol, "name": a.name,
             "asset_type": a.asset_type, "currency": a.currency}
            for a in assets
        ],
        "positions": [
            {"asset_ref": asset_ref[p.asset_id], "quantity": p.quantity, "avg_buy_price": p.avg_buy_price,
             "bought_at": _iso(p.bought_at), "status": p.status}
            for p in positions
        ],
        "asset_transactions": [
            {"asset_ref": asset_ref[t.asset_id], "type": t.type, "quantity": t.quantity,
             "price": t.price, "date": _iso(t.date)}
            for t in asset_transactions
        ],
        "savings_plans": [
            {"asset_ref": asset_ref[p.asset_id], "amount": p.amount, "day_of_month": p.day_of_month,
             "start_date": _iso(p.start_date), "last_executed": _iso(p.last_executed),
             "active": bool(p.active)}
            for p in savings_plans
        ],
        "watchlist": [
            {"asset_ref": asset_ref[w.asset_id], "price_added": w.price_added, "added_at": _iso(w.added_at)}
            for w in watchlist
        ],
        "dividends": [
            {"asset_ref": asset_ref[d.asset_id], "ex_dividend_date": _iso(d.ex_dividend_date),
             "amount_per_share": d.amount_per_share, "shares_held": d.shares_held,
             "total_amount": d.total_amount, "transaction_ref": transaction_ref.get(d.transaction_id),
             "booked_at": _iso(d.booked_at)}
            for d in dividends
        ],
        "chat_history": [
            {"role": m.role, "message": m.message, "created_at": _iso(m.created_at)}
            for m in _by_id(ChatHistory, user_id)
        ],
        "analyses": [
            {"total_value": a.total_value, "risk_assessment": a.risk_assessment,
             "diversification_score": a.diversification_score, "summary": a.summary,
             "recommendations": parse_stored_list(a.recommendations),
             "allocation": parse_stored_list(a.allocation), "created_at": _iso(a.created_at)}
            for a in _by_id(PortfolioAnalysis, user_id)
        ],
        "insights": [
            {"content": i.content, "created_at": _iso(i.created_at)}
            for i in _by_id(DailyInsight, user_id)
        ],
        "contracts": [
            {"name": c.name, "provider": c.provider, "category": c.category,
             "contract_number": c.contract_number, "amount": c.amount, "interval": c.interval,
             "start_date": _iso(c.start_date), "min_term_months": c.min_term_months,
             "renewal_months": c.renewal_months, "notice_value": c.notice_value,
             "notice_unit": c.notice_unit, "cancelled_at": _iso(c.cancelled_at),
             "end_date": _iso(c.end_date), "notes": c.notes,
             "transaction_ref": transaction_ref.get(c.transaction_id), "created_at": _iso(c.created_at)}
            for c in _by_id(Contract, user_id)
        ],
    }


def ensure_account_is_empty(user_id):
    """Import nur in ein Konto ohne eigene Daten - sonst entstehen Dubletten."""
    for model in USER_DATA_MODELS:
        if model.query.filter_by(user_id=user_id).count():
            raise ApiError(409, 'Import ist nur in ein leeres Konto möglich. '
                                'Dein Konto enthält bereits Buchungen, Verträge oder Portfolio-Daten.')


def _find_or_create_asset(entry):
    """Assets sind für alle Nutzer gleich - vorhandene werden über das Symbol wiederverwendet."""
    asset = Asset.query.filter_by(symbol=entry.symbol).first()
    if asset:
        return asset, False
    asset = Asset(symbol=entry.symbol, name=entry.name, asset_type=entry.asset_type, currency=entry.currency)
    db.session.add(asset)
    db.session.flush()
    return asset, True


def import_user_data(user, data):
    """
    Spielt eine geprüfte Export-Datei (ExportFile) in das Konto ein.
    Gibt (Anzahl pro Bereich, neu angelegte Assets) zurück. Committet erst
    ganz am Ende - bei einem Fehler macht der Aufrufer ein Rollback.
    """
    user_id = user.id
    ensure_account_is_empty(user_id)

    # Vorhandene (Standard-)Kategorien werden durch die aus der Datei ersetzt.
    # Unterkategorien zuerst und getrennt löschen - PostgreSQL prüft den
    # Verweis auf die Hauptkategorie sofort
    Category.query.filter_by(user_id=user_id).filter(Category.parent_id.isnot(None)).delete()
    Category.query.filter_by(user_id=user_id).delete()
    db.session.flush()

    profile = data.profile
    user.risk_profile = profile.risk_profile
    user.investment_experience = profile.investment_experience
    user.monthly_budget = profile.monthly_budget
    user.investment_horizon = profile.investment_horizon

    # Kategorien in zwei Durchgängen: erst Haupt-, dann Unterkategorien
    category_ids = {}
    for entry in sorted(data.categories, key=lambda c: c.parent_ref is not None):
        category = _create(Category, user_id=user_id, name=entry.name, type=entry.type,
                           parent_id=category_ids.get(entry.parent_ref))
        db.session.flush()
        category_ids[entry.ref] = category.id

    transaction_ids = {}
    for entry in data.transactions:
        transaction = _create(Transaction, user_id=user_id, category_id=category_ids[entry.category_ref],
                              amount=entry.amount, description=entry.description, date=entry.date,
                              is_recurring=entry.is_recurring, end_date=entry.end_date,
                              is_paused=entry.is_paused, paused_at=entry.paused_at)
        db.session.flush()
        transaction_ids[entry.ref] = transaction.id

    asset_ids = {}
    new_assets = []
    for entry in data.assets:
        asset, created = _find_or_create_asset(entry)
        asset_ids[entry.ref] = asset.id
        if created:
            new_assets.append(asset)

    for entry in data.positions:
        _create(UserAsset, user_id=user_id, asset_id=asset_ids[entry.asset_ref], quantity=entry.quantity,
                avg_buy_price=entry.avg_buy_price, bought_at=entry.bought_at, status=entry.status)
    for entry in data.asset_transactions:
        _create(AssetTransaction, user_id=user_id, asset_id=asset_ids[entry.asset_ref], type=entry.type,
                quantity=entry.quantity, price=entry.price, date=entry.date)
    for entry in data.savings_plans:
        _create(SavingsPlan, user_id=user_id, asset_id=asset_ids[entry.asset_ref], amount=entry.amount,
                day_of_month=entry.day_of_month, start_date=entry.start_date,
                last_executed=entry.last_executed, active=entry.active)
    for entry in data.watchlist:
        _create(Watchlist, user_id=user_id, asset_id=asset_ids[entry.asset_ref],
                price_added=entry.price_added, added_at=entry.added_at)
    for entry in data.dividends:
        _create(Dividend, user_id=user_id, asset_id=asset_ids[entry.asset_ref],
                ex_dividend_date=entry.ex_dividend_date, amount_per_share=entry.amount_per_share,
                shares_held=entry.shares_held, total_amount=entry.total_amount,
                transaction_id=transaction_ids.get(entry.transaction_ref), booked_at=entry.booked_at)
    for entry in data.chat_history:
        _create(ChatHistory, user_id=user_id, role=entry.role, message=entry.message,
                created_at=entry.created_at)
    for entry in data.analyses:
        _create(PortfolioAnalysis, user_id=user_id, total_value=entry.total_value,
                risk_assessment=entry.risk_assessment, diversification_score=entry.diversification_score,
                summary=entry.summary,
                recommendations=json.dumps(entry.recommendations, ensure_ascii=False),
                allocation=json.dumps(entry.allocation, ensure_ascii=False), created_at=entry.created_at)
    for entry in data.insights:
        _create(DailyInsight, user_id=user_id, content=entry.content, created_at=entry.created_at)
    for entry in data.contracts:
        _create(Contract, user_id=user_id, transaction_id=transaction_ids.get(entry.transaction_ref),
                **entry.model_dump(exclude={'transaction_ref'}))

    db.session.commit()

    counts = {
        "categories": len(data.categories), "transactions": len(data.transactions),
        "positions": len(data.positions), "asset_transactions": len(data.asset_transactions),
        "savings_plans": len(data.savings_plans), "watchlist": len(data.watchlist),
        "dividends": len(data.dividends), "chat_history": len(data.chat_history),
        "analyses": len(data.analyses), "insights": len(data.insights),
        "contracts": len(data.contracts),
    }
    return counts, new_assets
