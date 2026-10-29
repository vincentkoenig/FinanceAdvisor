"""
admin/routes.py - Interne Endpoints unter /api/v1/admin, um die Hintergrundjobs (Preise,
Dividenden, Insights) manuell anzustoßen. Nur mit X-Admin-Key aufrufbar.
"""

# Standard Library
import hmac     # Zeitkonstanter Vergleich von Schlüsseln (gegen Timing-Angriffe)
import os
from datetime import datetime
from functools import wraps

# Third Party
from flask import Blueprint, current_app, request, jsonify

# Lokale Imports
from fintrack.extensions import db, get_openai_client
from fintrack.insights.service import generate_insights_for_all_users
from fintrack.jobs import update_prices
from fintrack.models import PriceHistory
from fintrack.portfolio.dividends import process_dividends_for_all_users

bp = Blueprint('admin', __name__)


def require_admin_key(view):
    """
    Schützt interne Endpoints (Preise, Dividenden, Insights manuell
    anstoßen), die sonst jeder aufrufen und damit z.B. OpenAI-Kosten
    für alle Nutzer auslösen könnte. Der Aufrufer muss den Schlüssel
    aus der Umgebungsvariable ADMIN_API_KEY im Header X-Admin-Key
    mitschicken. Ist ADMIN_API_KEY nicht gesetzt, sind die Endpoints
    komplett gesperrt.
    """
    @wraps(view)
    def wrapper(*args, **kwargs):
        expected_key = os.getenv('ADMIN_API_KEY')
        provided_key = request.headers.get('X-Admin-Key', '')

        if not expected_key or not hmac.compare_digest(provided_key, expected_key):
            return jsonify({"error": "Nicht erlaubt"}), 403

        return view(*args, **kwargs)

    return wrapper


@bp.route('/update-prices', methods=['POST'])
@require_admin_key
def manual_update_prices():
    """
    Manuelle Preisaktualisierung - nützlich wenn Scheduler nicht gelaufen ist.
    Ruft update_prices() aus scheduler.py auf.
    """
    update_prices(current_app._get_current_object())
    return jsonify({"message": "Prices updated successfully"}), 200


@bp.route('/check-dividends', methods=['POST'])
@require_admin_key
def manual_check_dividends():
    """
    Manuelle Dividendenprüfung - nützlich zum Testen, ohne bis zum
    geplanten Scheduler-Zeitpunkt warten zu müssen.
    """
    process_dividends_for_all_users()
    return jsonify({"message": "Dividends checked and booked successfully"}), 200


@bp.route('/generate-insights', methods=['POST'])
@require_admin_key
def manual_generate_insights():
    """
    Manuelle Insight-Generierung - nützlich zum Testen, ohne bis
    zum geplanten Scheduler-Zeitpunkt warten zu müssen.
    """
    generate_insights_for_all_users(get_openai_client())
    return jsonify({"message": "Insights generated successfully"}), 200


@bp.route('/assets/<int:asset_id>/prices', methods=['POST'])
@require_admin_key
def add_prices(asset_id):
    """
    Manuell einen historischen Preis für ein Asset eintragen. Die
    Preistabelle gilt für alle Nutzer, deshalb nur mit X-Admin-Key.
    """
    data = request.json
    # Datum von String in Python datetime Objekt umwandeln
    date = datetime.strptime(data['date'], '%Y-%m-%d')
    price = data['price']
    currency = data['currency']

    # Pro Asset und Tag gibt es genau einen Kurs - vorhandenen überschreiben
    existing = PriceHistory.query.filter_by(asset_id=asset_id, date=date).first()
    if existing:
        existing.price = price
        existing.currency = currency
        status = 200
    else:
        db.session.add(PriceHistory(asset_id=asset_id, date=date, price=price, currency=currency))
        status = 201
    db.session.commit()

    return jsonify({"message": "Price successfully saved"}), status
