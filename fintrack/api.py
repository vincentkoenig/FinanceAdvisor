"""
api.py - Gemeinsame Bausteine der JSON-API unter /api/v1:
- Eingaben mit Pydantic prüfen (parse_body, parse_query)
- einheitliche Fehlerantworten {"error": "...", "fields": {...}} auf Deutsch,
  auch für 404/405/500, damit das Frontend nie eine HTML-Fehlerseite bekommt
"""

import logging

from flask import jsonify, request
from pydantic import BaseModel, ConfigDict, ValidationError
from werkzeug.exceptions import HTTPException

API_PREFIX = '/api/v1'

logger = logging.getLogger(__name__)


class RequestModel(BaseModel):
    """
    Basis für alle Eingabe-Schemas: Leerzeichen am Rand werden entfernt,
    unbekannte Felder ignoriert (z.B. ein altes user_id-Feld im Body).
    """
    model_config = ConfigDict(str_strip_whitespace=True, extra='ignore')


class ApiError(Exception):
    """Fachlicher Fehler mit HTTP-Status, z.B. ApiError(404, 'Sparplan nicht gefunden')."""

    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def parse_body(model):
    """Prüft den JSON-Body gegen ein Schema und gibt das geprüfte Objekt zurück."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError(400, 'Die Anfrage muss ein JSON-Objekt enthalten')
    return model.model_validate(data)


def parse_query(model):
    """Prüft die URL-Parameter (?month=...) gegen ein Schema."""
    return model.model_validate(request.args.to_dict())


def _number(value):
    """0.0 -> "0", 2.5 -> "2,5" - Grenzwerte lesbar auf Deutsch."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).replace('.', ',') if isinstance(value, float) else str(value)


def _german_message(error):
    """Übersetzt die häufigsten Pydantic-Fehler ins Deutsche."""
    ctx = {key: _number(value) if isinstance(value, (int, float)) else value
           for key, value in (error.get('ctx') or {}).items()}
    messages = {
        'missing': 'Pflichtfeld fehlt',
        'string_too_short': 'darf nicht leer sein' if ctx.get('min_length') == '1'
                            else f"mindestens {ctx.get('min_length')} Zeichen",
        'string_too_long': f"höchstens {ctx.get('max_length')} Zeichen",
        'greater_than': f"muss größer als {ctx.get('gt')} sein",
        'greater_than_equal': f"muss mindestens {ctx.get('ge')} sein",
        'less_than_equal': f"darf höchstens {ctx.get('le')} sein",
        'float_parsing': 'muss eine Zahl sein',
        'float_type': 'muss eine Zahl sein',
        'int_parsing': 'muss eine ganze Zahl sein',
        'int_type': 'muss eine ganze Zahl sein',
        'int_from_float': 'muss eine ganze Zahl sein',
        'bool_parsing': 'muss wahr oder falsch sein',
        'date_from_datetime_parsing': 'muss ein Datum im Format JJJJ-MM-TT sein',
        'date_parsing': 'muss ein Datum im Format JJJJ-MM-TT sein',
        'date_type': 'muss ein Datum im Format JJJJ-MM-TT sein',
        'string_pattern_mismatch': 'hat das falsche Format',
        'literal_error': f"muss einer dieser Werte sein: {ctx.get('expected')}",
        'string_type': 'muss Text sein',
    }
    if error['type'] == 'value_error':
        # Eigene Prüfungen (field/model_validator) liefern ihre Meldung selbst
        return str(ctx.get('error', error['msg']))
    return messages.get(error['type'], error['msg'])


def validation_error_response(exc):
    fields = {}
    for error in exc.errors():
        field = '.'.join(str(part) for part in error['loc']) or 'eingabe'
        fields.setdefault(field, _german_message(error))
    summary = '; '.join(f'{field}: {message}' for field, message in fields.items())
    return jsonify({"error": f"Ungültige Eingabe – {summary}", "fields": fields}), 400


def register_error_handlers(app):
    """Hängt die einheitlichen Fehlerantworten an die App."""

    @app.errorhandler(ValidationError)
    def handle_validation_error(exc):
        return validation_error_response(exc)

    @app.errorhandler(ApiError)
    def handle_api_error(exc):
        return jsonify({"error": exc.message}), exc.status

    @app.errorhandler(HTTPException)
    def handle_http_error(exc):
        # Seiten behalten die normalen Fehlerseiten, die API antwortet mit JSON
        if not request.path.startswith(API_PREFIX):
            return exc
        messages = {
            404: 'Nicht gefunden',
            405: 'Diese Methode ist hier nicht erlaubt',
            429: 'Zu viele Anfragen. Bitte warte etwas und versuche es dann erneut.',
        }
        return jsonify({"error": messages.get(exc.code, exc.description)}), exc.code

    @app.errorhandler(Exception)
    def handle_unexpected_error(exc):
        if isinstance(exc, HTTPException):
            return handle_http_error(exc)
        logger.exception('Unerwarteter Fehler bei %s %s', request.method, request.path)
        if app.testing:
            # In Tests den echten Fehler sehen statt einer allgemeinen Meldung
            raise exc
        return jsonify({"error": "Interner Fehler. Bitte versuche es später erneut."}), 500
