"""
imports/routes.py - Kontoumsätze aus einer CSV-Datei ins Haushaltsbuch übernehmen.

Zwei Schritte, damit nichts ungeprüft gebucht wird:
1. POST /me/import/bank/preview  (Datei) -> Umsätze mit Status und Kategorievorschlag, speichert nichts
2. POST /me/import/bank/commit   (JSON)  -> legt die bestätigten Umsätze an
Genauso für Depot-Abrechnungen (PDF) unter /me/import/depot/...: Der Text wird vor
dem Auswerten durch das Sprachmodell von persönlichen Angaben befreit.
Dateien werden nur gelesen und nirgends abgelegt.
"""

import logging

import json

from flask import Blueprint, jsonify, request
from flask_login import current_user

from fintrack.auth.session import current_user_key
from fintrack.extensions import limiter

from fintrack.api import ApiError, parse_body
from fintrack.auth.session import protect_blueprint
from fintrack.imports.bank_csv import CsvImportError, read_bank_csv
from fintrack.imports.bank_service import build_preview, commit_rows
from fintrack.imports.crypto_csv import read_crypto_csv
from fintrack.imports.depot_pdf import PdfImportError, extract_text, mask_personal_data, read_trades
from fintrack.imports.depot_service import build_depot_preview, commit_trades
from fintrack.imports.schemas import ColumnMapping, CryptoColumnMapping, DepotCommit, ImportCommit

logger = logging.getLogger(__name__)

bp = Blueprint('imports', __name__)
# Nur mit Anmeldung
protect_blueprint(bp)


@bp.route('/me/import/bank/preview', methods=['POST'])
def preview_bank_import():
    """
    Liest die CSV-Datei: als Formularfeld "file" oder direkt als Inhalt der Anfrage
    (so schickt sie das Frontend). Optional "mapping" (Formularfeld oder URL-Parameter)
    als JSON {"columns": {"date": 0, "amount": 3, ...}}, wenn die Spalten nicht erkannt wurden.
    Antwort bei unbekannten Spalten: 400 mit "columns" (Namen der Spalten) zum Zuordnen.
    """
    upload = request.files.get('file')
    data = upload.read() if upload is not None else (b'' if request.form else request.get_data())
    if not data:
        raise ApiError(400, 'Bitte eine CSV-Datei auswählen')

    mapping = None
    raw_mapping = request.form.get('mapping') or request.args.get('mapping')
    if raw_mapping:
        try:
            mapping = ColumnMapping.model_validate(json.loads(raw_mapping)).columns
        except json.JSONDecodeError:
            raise ApiError(400, 'Die Spaltenzuordnung ist kein gültiges JSON')

    try:
        columns, used_mapping, rows, skipped = read_bank_csv(data, mapping)
    except CsvImportError as error:
        return jsonify({"error": str(error), "columns": error.columns}), 400

    entries = build_preview(current_user.id, rows)
    return jsonify({
        "columns": columns,
        "mapping": used_mapping,
        "rows": entries,
        "skipped": skipped,
        "counts": {status: sum(e['status'] == status for e in entries) for status in ('new', 'covered', 'duplicate')},
    }), 200


@bp.route('/me/import/bank/commit', methods=['POST'])
def commit_bank_import():
    """Übernimmt die bestätigten Umsätze als einmalige Buchungen (alles oder nichts)."""
    data = parse_body(ImportCommit)
    created, skipped = commit_rows(current_user.id, data.rows)
    return jsonify({"message": f'{created} Umsätze übernommen', "created": created, "skipped": skipped}), 201


# ─── DEPOT-ABRECHNUNGEN (PDF) ─────────────────────────────────────────────────

@bp.route('/me/import/depot/preview', methods=['POST'])
@limiter.limit("40 per hour", key_func=current_user_key)
def preview_depot_import():
    """
    Liest eine PDF-Abrechnung (Inhalt der Anfrage oder Formularfeld "file"),
    entfernt persönliche Angaben, lässt Käufe/Verkäufe auslesen und prüft sie.
    "sent_text" zeigt genau den Text, der ausgewertet wurde.
    """
    upload = request.files.get('file')
    data = upload.read() if upload is not None else request.get_data()
    if not data:
        raise ApiError(400, 'Bitte eine PDF-Abrechnung auswählen')

    try:
        masked = mask_personal_data(extract_text(data))
    except PdfImportError as error:
        raise ApiError(400, str(error))

    try:
        document = read_trades(masked)
    except Exception:
        logger.exception('Abrechnung konnte nicht ausgewertet werden')
        raise ApiError(502, 'Die Abrechnung konnte gerade nicht ausgewertet werden. Bitte versuche es gleich noch einmal.')

    rows = build_depot_preview(current_user.id, document.trades if document.is_trade_statement else [])
    return jsonify({
        "is_trade_statement": document.is_trade_statement,
        "note": document.note,
        "rows": rows,
        "sent_text": masked,
    }), 200


@bp.route('/me/import/depot/commit', methods=['POST'])
def commit_depot_import():
    """Bucht die bestätigten Käufe und Verkäufe ins Depot (alles oder nichts)."""
    data = parse_body(DepotCommit)
    booked, skipped = commit_trades(current_user.id, data.trades)
    return jsonify({"message": f'{booked} Ausführungen gebucht', "booked": booked, "skipped": skipped}), 201


# ─── KRYPTO (CSV) ─────────────────────────────────────────────────────────────

@bp.route('/me/import/crypto/preview', methods=['POST'])
def preview_crypto_import():
    """
    Liest den CSV-Export einer Krypto-App oder -Börse (z.B. Bison), ohne KI. Gleiche
    Vorschau wie bei Depot-Abrechnungen; gebucht wird über /me/import/depot/commit.
    Bei unbekannten Spalten: 400 mit "columns", dann "mapping" als URL-Parameter.
    """
    data = request.get_data()
    if not data:
        raise ApiError(400, 'Bitte eine CSV-Datei auswählen')
    mapping = None
    if request.args.get('mapping'):
        try:
            mapping = CryptoColumnMapping.model_validate(json.loads(request.args['mapping'])).columns
        except json.JSONDecodeError:
            raise ApiError(400, 'Die Spaltenzuordnung ist kein gültiges JSON')
    try:
        columns, used_mapping, trades, skipped = read_crypto_csv(data, mapping)
    except CsvImportError as error:
        return jsonify({"error": str(error), "columns": error.columns}), 400

    return jsonify({
        "columns": columns,
        "mapping": used_mapping,
        "rows": build_depot_preview(current_user.id, trades),
        "skipped": skipped,
    }), 200
