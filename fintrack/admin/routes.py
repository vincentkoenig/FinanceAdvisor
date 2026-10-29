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
from fintrack.extensions import db
from fintrack.jobs import job_status, start_job
from fintrack.models import PriceHistory

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
    """Kurse und Wechselkurse im Hintergrund aktualisieren."""
    return _start('prices')


@bp.route('/check-dividends', methods=['POST'])
@require_admin_key
def manual_check_dividends():
    """Neue Dividenden im Hintergrund verbuchen."""
    return _start('dividends')


@bp.route('/generate-insights', methods=['POST'])
@require_admin_key
def manual_generate_insights():
    """Tägliche Insights im Hintergrund erzeugen (höchstens einer pro Nutzer und Tag)."""
    return _start('insights')


@bp.route('/run-daily-jobs', methods=['POST'])
@require_admin_key
def run_daily_jobs():
    """
    Der komplette tägliche Lauf (Kurse, Dividenden, Insights). Wird abends
    von GitHub Actions aufgerufen, damit er auch läuft, wenn der Server
    vorher geschlafen hat.
    """
    return _start('daily')


@bp.route('/jobs/status', methods=['GET'])
@require_admin_key
def jobs_status():
    """Zustand und Ergebnis des letzten Laufs - für GitHub Actions und zur Fehlersuche."""
    return jsonify(job_status()), 200


def _start(job_name):
    """Startet einen Job im Hintergrund; läuft schon einer, wird nichts doppelt gestartet."""
    if not start_job(current_app._get_current_object(), job_name):
        return jsonify({"message": "Es läuft bereits ein Job", "status": job_status()}), 409
    return jsonify({"message": "Job gestartet", "job": job_name}), 202


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
