"""
health.py - Statuspunkt für Docker, den Webserver davor und Überwachungsdienste.

GET /healthz antwortet, sobald die App Anfragen annimmt, und fasst die
Datenbank bewusst nicht an: Docker fragt alle 30 Sekunden, und jede
Datenbankabfrage würde Neon wecken. Auf dem kostenlosen Tarif pausiert Neon
nach 5 Minuten ohne Zugriff; ein Dauer-Ping hielte die Datenbank rund um die
Uhr wach und verbrauchte das monatliche Kontingent an Rechenzeit.

GET /healthz?db=1 prüft zusätzlich die Verbindung zur Datenbank - für den
Test nach einem Deploy, nicht für regelmäßige Abfragen.
Beide Antworten enthalten keine Nutzerdaten und brauchen keine Anmeldung.
"""

from flask import Blueprint, jsonify, request
from sqlalchemy import text

from fintrack.extensions import db

bp = Blueprint('health', __name__)


@bp.route('/healthz')
def healthz():
    if request.args.get('db') != '1':
        return jsonify({"status": "ok"}), 200

    try:
        db.session.execute(text('SELECT 1'))
    except Exception:
        db.session.rollback()
        # Keine Details nach außen - die stehen im Server-Log
        return jsonify({"status": "error", "database": "nicht erreichbar"}), 503
    return jsonify({"status": "ok", "database": "ok"}), 200
