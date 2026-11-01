"""
budget/routes.py - API für das Haushaltsbuch: Kategorien, Buchungen
(einmalig und wiederkehrend) und die Gesamtübersicht.
Registriert unter /api/v1, alle Routen beziehen sich auf den angemeldeten Nutzer.
"""

# Standard Library
from datetime import datetime

# Third Party
from flask import Blueprint, jsonify
from flask_login import current_user

# Lokale Imports
from fintrack.api import ApiError, parse_body, parse_query
from fintrack.auth.session import get_own, protect_blueprint
from fintrack.budget.schemas import CategoryCreate, MonthQuery, TransactionCreate
from fintrack.budget.service import calculate_budget_summary, create_default_categories
from fintrack.extensions import db
from fintrack.models import Category, Contract, Transaction

bp = Blueprint('budget', __name__)
# Nur mit Anmeldung
protect_blueprint(bp)


# ─── KATEGORIEN ───────────────────────────────────────────────────────────────

@bp.route('/me/categories', methods=['GET'])
def get_categories():
    """Alle eigenen Kategorien inkl. Haupt-/Unterkategorie-Zuordnung."""
    categories = Category.query.filter_by(user_id=current_user.id).all()

    return jsonify([
        {
            "id": category.id,
            "name": category.name,
            "type": category.type,
            "parent_id": category.parent_id
        }
        for category in categories
    ]), 200


@bp.route('/me/categories', methods=['POST'])
def add_category():
    """
    Neue Kategorie anlegen. parent_id ist optional - leer bedeutet
    Hauptkategorie, sonst muss es eine eigene Hauptkategorie sein.
    """
    data = parse_body(CategoryCreate)

    if data.parent_id is not None:
        parent = get_own(Category, data.parent_id)
        if not parent:
            raise ApiError(404, 'Hauptkategorie nicht gefunden')
        if parent.type != data.type:
            raise ApiError(400, 'Unterkategorie muss denselben Typ wie die Hauptkategorie haben')

    category = Category(user_id=current_user.id, name=data.name, type=data.type, parent_id=data.parent_id)
    db.session.add(category)
    db.session.commit()

    return jsonify({"message": "Kategorie angelegt", "category_id": category.id}), 201


@bp.route('/me/categories/<int:category_id>', methods=['DELETE'])
def delete_category(category_id):
    """
    Eigene Kategorie löschen, samt Unterkategorien. Hängen noch Buchungen
    daran, wird das Löschen abgelehnt - sonst würden diese Buchungen ihre
    Kategorie verlieren und im Saldo falsch gezählt.
    """
    category = get_own(Category, category_id)

    if not category:
        raise ApiError(404, 'Kategorie nicht gefunden')

    sub_categories = Category.query.filter_by(parent_id=category.id).all()
    category_ids = [category.id] + [sub.id for sub in sub_categories]

    if Transaction.query.filter(Transaction.category_id.in_(category_ids)).count():
        raise ApiError(409, 'Die Kategorie enthält noch Buchungen und kann nicht gelöscht werden')

    for sub_category in sub_categories:
        db.session.delete(sub_category)
    db.session.delete(category)
    db.session.commit()

    return jsonify({"message": "Kategorie gelöscht"}), 200


@bp.route('/me/categories/init-defaults', methods=['POST'])
def init_default_categories():
    """
    Legt nachträglich die Standardkategorien an, falls der Nutzer noch
    keine hat (für Konten aus der Zeit vor der automatischen Anlage).
    """
    if Category.query.filter_by(user_id=current_user.id).count() > 0:
        return jsonify({"message": "Kategorien sind schon vorhanden"}), 200

    create_default_categories(current_user.id)

    return jsonify({"message": "Standardkategorien angelegt"}), 201


# ─── BUCHUNGEN ────────────────────────────────────────────────────────────────

@bp.route('/me/transactions', methods=['GET'])
def get_transactions():
    """
    Alle eigenen Buchungen mit Kategoriename und -typ.
    Optionaler Query-Parameter 'month' filtert auf einen Monat,
    z.B. /api/v1/me/transactions?month=2026-07
    Wiederkehrende Buchungen werden automatisch für jeden Monat
    mitgezählt, der zwischen ihrem Start- und optionalem Enddatum liegt,
    auch wenn dafür kein eigener Eintrag in der DB existiert. Pausierte
    Buchungen werden hier weiterhin mit angezeigt (mit is_paused
    gekennzeichnet), damit sie in der Liste sichtbar und über den
    Pausieren/Fortsetzen-Button wieder aktivierbar bleiben - nur bei
    der Saldo-Berechnung in budget/service.py werden sie tatsächlich
    aus der Summe herausgerechnet.
    """
    month = parse_query(MonthQuery).month
    user_id = current_user.id

    if month:
        year, month_num = map(int, month.split('-'))
        month_start = datetime(year, month_num, 1)
        month_end = datetime(year + 1, 1, 1) if month_num == 12 else datetime(year, month_num + 1, 1)

        one_time = Transaction.query.filter_by(user_id=user_id, is_recurring=False) \
            .filter(Transaction.date >= month_start, Transaction.date < month_end).all()

        recurring = Transaction.query.filter_by(user_id=user_id, is_recurring=True) \
            .filter(Transaction.date < month_end) \
            .filter(db.or_(Transaction.end_date.is_(None), Transaction.end_date >= month_start)) \
            .all()

        transactions = one_time + recurring
    else:
        transactions = Transaction.query.filter_by(user_id=user_id).order_by(Transaction.date.desc()).all()

    result = []
    for transaction in transactions:
        category = db.session.get(Category, transaction.category_id)

        result.append({
            "id": transaction.id,
            "amount": transaction.amount,
            "description": transaction.description,
            "date": transaction.date.strftime('%Y-%m-%d'),
            "end_date": transaction.end_date.strftime('%Y-%m-%d') if transaction.end_date else None,
            "is_recurring": transaction.is_recurring,
            "is_paused": transaction.is_paused,
            # Ab wann pausiert: frühere Monate zählen die Buchung weiter mit
            "paused_at": transaction.paused_at.strftime('%Y-%m-%d') if transaction.paused_at else None,
            "category_id": transaction.category_id,
            "category_name": category.name if category else None,
            "category_type": category.type if category else None
        })

    return jsonify(result), 200


@bp.route('/me/transactions', methods=['POST'])
def add_transaction():
    """
    Neue Buchung (Einnahme oder Ausgabe) in einer eigenen Kategorie anlegen.
    Wenn is_recurring True ist, wird date als Startdatum behandelt und
    die Buchung für jeden Monat ab dann automatisch mitgezählt, bis
    end_date erreicht ist (oder unbegrenzt, falls end_date leer bleibt).
    """
    data = parse_body(TransactionCreate)

    if not get_own(Category, data.category_id):
        raise ApiError(404, 'Kategorie nicht gefunden')

    def to_datetime(value):
        return datetime.combine(value, datetime.min.time()) if value else None

    transaction = Transaction(
        user_id=current_user.id,
        category_id=data.category_id,
        amount=data.amount,
        description=data.description,
        date=to_datetime(data.date),
        is_recurring=data.is_recurring,
        end_date=to_datetime(data.end_date)
    )
    db.session.add(transaction)
    db.session.commit()

    return jsonify({"message": "Buchung gespeichert", "transaction_id": transaction.id}), 201


@bp.route('/me/transactions/<int:transaction_id>', methods=['DELETE'])
def delete_transaction(transaction_id):
    """Eigene Buchung löschen."""
    transaction = get_own(Transaction, transaction_id)

    if not transaction:
        raise ApiError(404, 'Buchung nicht gefunden')

    # Ein Vertrag dazu bleibt bestehen und verliert nur die Verknüpfung
    Contract.query.filter_by(transaction_id=transaction.id).update({Contract.transaction_id: None})
    db.session.delete(transaction)
    db.session.commit()

    return jsonify({"message": "Buchung gelöscht"}), 200


@bp.route('/me/transactions/<int:transaction_id>/toggle-pause', methods=['POST'])
def toggle_transaction_pause(transaction_id):
    """
    Pausiert eine wiederkehrende Buchung, oder setzt sie fort, falls
    sie bereits pausiert war. Beim Pausieren wird paused_at auf den
    aktuellen Zeitpunkt gesetzt, damit vergangene Monate bei der
    Budget-Berechnung unverändert korrekt bleiben.
    """
    transaction = get_own(Transaction, transaction_id)

    if not transaction:
        raise ApiError(404, 'Buchung nicht gefunden')

    if not transaction.is_recurring:
        raise ApiError(400, 'Nur wiederkehrende Buchungen können pausiert werden')

    transaction.is_paused = not transaction.is_paused
    transaction.paused_at = datetime.now() if transaction.is_paused else None

    db.session.commit()

    status = "pausiert" if transaction.is_paused else "fortgesetzt"
    return jsonify({"message": f"Buchung {status}", "is_paused": transaction.is_paused}), 200


@bp.route('/me/budget/summary', methods=['GET'])
def get_budget_summary():
    """
    Gesamtübersicht über das eigene Haushaltsbuch. Nutzt die gemeinsame
    Berechnungslogik aus budget/service.py, die auch der MCP-Server nutzt.
    """
    return jsonify(calculate_budget_summary(current_user.id)), 200
