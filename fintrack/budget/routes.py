"""
budget/routes.py - Haushaltsbuch: Kategorien, Buchungen (einmalig und
wiederkehrend) und die Gesamtübersicht.
"""

# Standard Library
from datetime import datetime

# Third Party
from flask import Blueprint, request, jsonify

# Lokale Imports
from fintrack.budget.service import calculate_budget_summary, create_default_categories
from fintrack.extensions import db
from fintrack.models import Category, Transaction

bp = Blueprint('budget', __name__)


@bp.route('/users/<user_id>/categories', methods=['GET'])
def get_categories(user_id):
    """Alle Kategorien eines Nutzers abrufen, inkl. Haupt-/Unterkategorie-Zuordnung"""
    categories = Category.query.filter_by(user_id=user_id).all()

    result = []
    for category in categories:
        result.append({
            "id": category.id,
            "name": category.name,
            "type": category.type,
            "parent_id": category.parent_id
        })

    return jsonify(result), 200


@bp.route('/users/<user_id>/categories', methods=['POST'])
def add_category(user_id):
    """
    Neue Kategorie anlegen.
    parent_id ist optional - leer/None bedeutet Hauptkategorie.
    """
    data = request.json
    name = data['name']
    category_type = data['type']
    parent_id = data.get('parent_id')  # optional, deshalb .get() statt ['parent_id']

    new_category = Category(user_id=user_id, name=name, type=category_type, parent_id=parent_id)
    db.session.add(new_category)
    db.session.commit()

    return jsonify({"message": "Category successfully added", "category_id": new_category.id}), 201


@bp.route('/categories/<category_id>', methods=['DELETE'])
def delete_category(category_id):
    """
    Kategorie löschen.
    Falls es eine Hauptkategorie mit Unterkategorien ist, werden diese
    ebenfalls gelöscht, um verwaiste Unterkategorien zu vermeiden.
    """
    category = db.session.get(Category, category_id)

    if not category:
        return jsonify({"error": "Category not found"}), 404

    # Zugehörige Unterkategorien mitlöschen
    sub_categories = Category.query.filter_by(parent_id=category_id).all()
    for sub_category in sub_categories:
        db.session.delete(sub_category)

    db.session.delete(category)
    db.session.commit()

    return jsonify({"message": "Category successfully deleted"}), 200


@bp.route('/users/<user_id>/categories/init-defaults', methods=['POST'])
def init_default_categories(user_id):
    """
    Legt nachträglich Standardkategorien für einen bestehenden Nutzer an,
    falls er noch keine hat. Nötig für Nutzer die vor Einführung der
    automatischen Kategorien-Erstellung bei der Registrierung angelegt wurden.
    """
    existing_count = Category.query.filter_by(user_id=user_id).count()

    if existing_count > 0:
        return jsonify({"message": "Categories already exist, nothing to do"}), 200

    create_default_categories(user_id)

    return jsonify({"message": "Default categories created"}), 201


@bp.route('/users/<user_id>/transactions', methods=['GET'])
def get_transactions(user_id):
    """
    Alle Buchungen eines Nutzers abrufen, mit Kategoriename und -typ.
    Optionaler Query-Parameter 'month' filtert auf einen Monat,
    z.B. /users/1/transactions?month=2026-07
    Wiederkehrende Buchungen werden automatisch für jeden Monat
    mitgezählt, der zwischen ihrem Start- und optionalem Enddatum liegt,
    auch wenn dafür kein eigener Eintrag in der DB existiert. Pausierte
    Buchungen werden hier weiterhin mit angezeigt (mit is_paused
    gekennzeichnet), damit sie in der Liste sichtbar und über den
    Pausieren/Fortsetzen-Button wieder aktivierbar bleiben - nur bei
    der Saldo-Berechnung in budget_logic.py werden sie tatsächlich
    aus der Summe herausgerechnet.
    """
    month = request.args.get('month')

    if month:
        year, month_num = map(int, month.split('-'))
        month_start = datetime(year, month_num, 1)
        if month_num == 12:
            month_end = datetime(year + 1, 1, 1)
        else:
            month_end = datetime(year, month_num + 1, 1)

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
            "category_id": transaction.category_id,
            "category_name": category.name if category else None,
            "category_type": category.type if category else None
        })

    return jsonify(result), 200


@bp.route('/users/<user_id>/transactions', methods=['POST'])
def add_transaction(user_id):
    """
    Neue Buchung (Einnahme oder Ausgabe) anlegen.
    Wenn is_recurring True ist, wird date als Startdatum behandelt und
    die Buchung für jeden Monat ab dann automatisch mitgezählt, bis
    end_date erreicht ist (oder unbegrenzt, falls end_date leer bleibt).
    """
    data = request.json
    category_id = data['category_id']
    amount = data['amount']
    description = data.get('description')  # optional
    date = datetime.strptime(data['date'], '%Y-%m-%d')
    is_recurring = data.get('is_recurring', False)

    end_date = None
    if data.get('end_date'):
        end_date = datetime.strptime(data['end_date'], '%Y-%m-%d')

    new_transaction = Transaction(
        user_id=user_id,
        category_id=category_id,
        amount=amount,
        description=description,
        date=date,
        is_recurring=is_recurring,
        end_date=end_date
    )
    db.session.add(new_transaction)
    db.session.commit()

    return jsonify({"message": "Transaction successfully added"}), 201


@bp.route('/transactions/<transaction_id>', methods=['DELETE'])
def delete_transaction(transaction_id):
    """Buchung löschen"""
    transaction = db.session.get(Transaction, transaction_id)

    if not transaction:
        return jsonify({"error": "Transaction not found"}), 404

    db.session.delete(transaction)
    db.session.commit()

    return jsonify({"message": "Transaction successfully deleted"}), 200


@bp.route('/transactions/<transaction_id>/toggle-pause', methods=['PUT'])
def toggle_transaction_pause(transaction_id):
    """
    Pausiert eine wiederkehrende Buchung, oder setzt sie fort, falls
    sie bereits pausiert war. Beim Pausieren wird paused_at auf den
    aktuellen Zeitpunkt gesetzt, damit vergangene Monate bei der
    Budget-Berechnung unverändert korrekt bleiben.
    """
    transaction = db.session.get(Transaction, transaction_id)

    if not transaction:
        return jsonify({"error": "Transaction not found"}), 404

    if not transaction.is_recurring:
        return jsonify({"error": "Nur wiederkehrende Buchungen können pausiert werden"}), 400

    transaction.is_paused = not transaction.is_paused
    transaction.paused_at = datetime.now() if transaction.is_paused else None

    db.session.commit()

    status = "pausiert" if transaction.is_paused else "fortgesetzt"
    return jsonify({"message": f"Buchung {status}", "is_paused": transaction.is_paused}), 200


@bp.route('/users/<user_id>/budget/summary', methods=['GET'])
def get_budget_summary(user_id):
    """
    Gesamtübersicht über das Haushaltsbuch eines Nutzers.
    Nutzt die gemeinsame Berechnungslogik aus budget_logic.py,
    die auch vom MCP-Server verwendet wird.
    """
    summary = calculate_budget_summary(user_id)
    return jsonify(summary), 200
