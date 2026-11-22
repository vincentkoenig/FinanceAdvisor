"""
bank/routes.py - Bankabruf über Enable Banking unter /api/v1.

Mit Anmeldung (bp):
- GET    /me/bank                    Zugänge, Konten, Zahl wartender Umsätze
- GET    /me/bank/aspsps?country=DE  Banken zur Auswahl
- POST   /me/bank/connect            Anmeldung bei der Bank starten -> {url}
- POST   /me/bank/sync               jetzt abrufen
- PUT    /me/bank/accounts/<id>      Konto ein-/ausschalten
- DELETE /me/bank/connections/<id>   Zugang trennen
- GET    /me/bank/review             wartende Umsätze (Form der Import-Vorschau)
- POST   /me/bank/review/commit      geprüfte buchen, Rest verwerfen

Ohne Anmeldung (callback_bp): GET /bank/callback - Rücksprung von der Bank. Zugeordnet
wird über den zufälligen state; auf dem Handy springt die Bank-App oft in einen Browser
zurück, in dem man nicht angemeldet ist.
"""

import logging
import os
from datetime import datetime

from flask import Blueprint, jsonify, redirect, request
from flask_login import current_user

from fintrack.api import API_PREFIX, ApiError, parse_body
from fintrack.auth.session import current_user_key, get_own, protect_blueprint
from fintrack.bank import service
from fintrack.bank.client import BankApiError, is_configured
from fintrack.bank.schemas import AccountUpdate, ConnectRequest, ReviewCommit
from fintrack.extensions import db, limiter
from fintrack.models import BankAccount, BankConnection

logger = logging.getLogger(__name__)

bp = Blueprint('bank', __name__)
protect_blueprint(bp)
callback_bp = Blueprint('bank_callback', __name__)

# Banken ändern sich selten: einmal je Land und Serverstart reicht
_aspsp_cache = {}


def _iso(value):
    return value.isoformat(timespec='seconds') + 'Z' if isinstance(value, datetime) else None


def redirect_url():
    """Rücksprung-Adresse; muss genau so in der Enable-Banking-App eingetragen sein."""
    return os.getenv('ENABLE_BANKING_REDIRECT_URL') or f'{request.scheme}://{request.host}{API_PREFIX}/bank/callback'


def _bank_error(error):
    if error.rate_limited:
        return ApiError(429, 'Die Bank erlaubt gerade keine weiteren Abrufe. Bitte später noch einmal versuchen.')
    status = 400 if error.status and 400 <= error.status < 500 else 502
    return ApiError(status, f'Bank: {error}')


class _NoApi:
    """Ohne Konfiguration lässt sich die Sitzung nicht beenden; der Zugang wird trotzdem gelöscht."""

    def delete_session(self, session_id):
        raise BankApiError('nicht eingerichtet')


@bp.route('/me/bank', methods=['GET'])
def overview():
    connections = BankConnection.query.filter(BankConnection.user_id == current_user.id,
                                              BankConnection.status != 'pending').order_by(BankConnection.id).all()
    return jsonify({
        "configured": is_configured(),
        "redirect_url": redirect_url(),
        "review_count": service.review_count(current_user.id),
        "connections": [{
            "id": c.id, "aspsp_name": c.aspsp_name, "status": c.status,
            "valid_until": _iso(c.valid_until), "last_sync_at": _iso(c.last_sync_at), "last_error": c.last_error,
            "accounts": [{"id": a.id, "name": a.name, "iban_last4": a.iban_last4, "enabled": a.enabled,
                          "synced_until": a.synced_until.isoformat() if a.synced_until else None}
                         for a in BankAccount.query.filter_by(connection_id=c.id).order_by(BankAccount.id).all()],
        } for c in connections],
    }), 200


@bp.route('/me/bank/aspsps', methods=['GET'])
def aspsps():
    country = (request.args.get('country') or 'DE').upper()[:2]
    if not is_configured():
        return jsonify({"configured": False, "aspsps": []}), 200
    if country not in _aspsp_cache:
        try:
            banks = service.client().aspsps(country)
        except BankApiError as error:
            raise _bank_error(error)
        _aspsp_cache[country] = sorted({b['name'] for b in banks if b.get('name')}, key=str.lower)
    return jsonify({"configured": True, "aspsps": _aspsp_cache[country]}), 200


@bp.route('/me/bank/connect', methods=['POST'])
@limiter.limit("20 per hour", key_func=current_user_key)
def connect():
    if not is_configured():
        raise ApiError(503, 'Der Bankabruf ist auf dem Server nicht eingerichtet')
    data = parse_body(ConnectRequest)
    try:
        url = service.start_connection(current_user.id, data.aspsp_name, data.country, redirect_url())
    except BankApiError as error:
        raise _bank_error(error)
    return jsonify({"url": url}), 200


@bp.route('/me/bank/sync', methods=['POST'])
@limiter.limit("6 per day", key_func=current_user_key)
def sync_now():
    if not is_configured():
        raise ApiError(503, 'Der Bankabruf ist auf dem Server nicht eingerichtet')
    counts, errors = service.sync_user(current_user.id)
    if errors and not counts:
        raise ApiError(502, errors[0])
    return jsonify({
        "booked": counts.get('booked', 0), "review": counts.get('review', 0),
        "covered": counts.get('covered', 0), "duplicate": counts.get('duplicate', 0),
        "balance": counts.get('balance'), "errors": errors,
    }), 200


@bp.route('/me/bank/accounts/<int:account_id>', methods=['PUT'])
def update_account(account_id):
    account = get_own(BankAccount, account_id)
    if not account:
        raise ApiError(404, 'Konto nicht gefunden')
    account.enabled = parse_body(AccountUpdate).enabled
    db.session.commit()
    return jsonify({"id": account.id, "enabled": account.enabled}), 200


@bp.route('/me/bank/connections/<int:connection_id>', methods=['DELETE'])
def delete_connection(connection_id):
    connection = get_own(BankConnection, connection_id)
    if not connection:
        raise ApiError(404, 'Bankzugang nicht gefunden')
    service.remove_connection(connection, service.client() if is_configured() else _NoApi())
    return jsonify({"message": "Bankzugang getrennt"}), 200


@bp.route('/me/bank/review', methods=['GET'])
def review():
    rows = service.review_rows(current_user.id)
    return jsonify({"columns": [], "mapping": {}, "rows": rows, "skipped": [],
                    "counts": {"new": len(rows), "covered": 0, "duplicate": 0}}), 200


@bp.route('/me/bank/review/commit', methods=['POST'])
def commit_review():
    data = parse_body(ReviewCommit)
    if not data.book and not data.dismiss:
        raise ApiError(400, 'Nichts zu übernehmen')
    booked, dismissed = service.commit_review(current_user.id, data.book, data.dismiss)
    message = f'{booked} Umsätze übernommen' + (f', {dismissed} verworfen' if dismissed else '')
    return jsonify({"message": message, "created": booked, "dismissed": dismissed}), 201


@callback_bp.route('/bank/callback', methods=['GET'])
def callback():
    """Rücksprung von der Bank: Sitzung anlegen, dann zurück in die Einstellungen."""
    state, code = request.args.get('state'), request.args.get('code')
    if request.args.get('error') or not code:
        if state:
            BankConnection.query.filter_by(state=state, status='pending').delete()
            db.session.commit()
        return redirect('/app/settings?bank=abgebrochen')
    try:
        service.finish_connection(state, code)
    except (ApiError, BankApiError) as error:
        logger.warning('Rücksprung von der Bank fehlgeschlagen: %s', error)
        return redirect('/app/settings?bank=fehler')
    return redirect('/app/settings?bank=verbunden')
