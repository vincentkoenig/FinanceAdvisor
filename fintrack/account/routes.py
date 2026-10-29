"""
account/routes.py - Export und Import aller eigenen Daten als JSON-Datei.
Registriert unter /api/v1:
- GET  /me/export  lädt die Datei herunter
- POST /me/import  spielt eine solche Datei in ein leeres Konto ein
"""

import json
import logging
from datetime import date

from flask import Blueprint, Response, jsonify, request
from flask_login import current_user

from fintrack.account.schemas import ExportFile
from fintrack.account.transfer import export_user_data, import_user_data
from fintrack.api import ApiError
from fintrack.auth.session import current_user_key, protect_blueprint
from fintrack.extensions import db, limiter
from fintrack.portfolio.service import load_price_history

logger = logging.getLogger(__name__)

bp = Blueprint('account', __name__)
# Nur mit Anmeldung
protect_blueprint(bp)


@bp.route('/me/export', methods=['GET'])
@limiter.limit("30 per hour", key_func=current_user_key)
def export_data():
    """Alle eigenen Daten als JSON-Datei zum Herunterladen."""
    data = export_user_data(current_user)
    filename = f'fintrack-export-{date.today().isoformat()}.json'

    return Response(
        json.dumps(data, ensure_ascii=False, indent=2),
        mimetype='application/json',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
            # Persönliche Finanzdaten - nicht zwischenspeichern
            'Cache-Control': 'no-store',
        },
    )


@bp.route('/me/import', methods=['POST'])
@limiter.limit("10 per hour", key_func=current_user_key)
def import_data():
    """
    Spielt eine Export-Datei in das eigene Konto ein - nur wenn es noch
    keine eigenen Daten enthält. Die Datei wird vollständig geprüft, bevor
    etwas gespeichert wird; schlägt das Speichern fehl, wird alles
    zurückgenommen.
    """
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or payload.get('format') != 'fintrack-export':
        raise ApiError(400, 'Das ist keine FinTrack-Exportdatei')
    if payload.get('version') != 1:
        raise ApiError(400, f"Diese Exportversion wird nicht unterstützt: {payload.get('version')}")

    data = ExportFile.model_validate(payload)

    try:
        counts, new_assets = import_user_data(current_user, data)
    except Exception:
        db.session.rollback()
        raise

    # Kurshistorie für Assets, die es in dieser Datenbank noch nicht gab -
    # erst nach dem Import und ohne ihn zu gefährden, falls die Kursquelle
    # gerade nicht erreichbar ist
    for asset in new_assets:
        try:
            load_price_history(asset)
        except Exception:
            db.session.rollback()
            logger.exception('Kurshistorie für %s konnte nicht geladen werden', asset.symbol)

    return jsonify({"message": "Daten importiert", "imported": counts}), 201
