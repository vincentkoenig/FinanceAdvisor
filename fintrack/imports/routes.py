"""
imports/routes.py - Kontoumsätze aus einer CSV-Datei ins Haushaltsbuch übernehmen.

Zwei Schritte, damit nichts ungeprüft gebucht wird:
1. POST /me/import/bank/preview  (Datei) -> Umsätze mit Status und Kategorievorschlag, speichert nichts
2. POST /me/import/bank/commit   (JSON)  -> legt die bestätigten Umsätze an
Die Datei wird nur gelesen und nirgends abgelegt.
"""

import json

from flask import Blueprint, jsonify, request
from flask_login import current_user

from fintrack.api import ApiError, parse_body
from fintrack.auth.session import protect_blueprint
from fintrack.imports.bank_csv import CsvImportError, read_bank_csv
from fintrack.imports.bank_service import build_preview, commit_rows
from fintrack.imports.schemas import ColumnMapping, ImportCommit

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
