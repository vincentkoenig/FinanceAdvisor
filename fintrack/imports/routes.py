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
from fintrack.extensions import db, limiter
from fintrack.models import Category, CategoryRule

from fintrack.api import ApiError, parse_body
from fintrack.auth.session import get_own, protect_blueprint
from fintrack.imports.bank_csv import CsvImportError, read_bank_csv
from fintrack.imports.bank_pdf import read_statement, to_bank_rows
from fintrack.imports.bank_service import build_preview, commit_rows
from fintrack.imports.crypto_csv import read_crypto_csv
from fintrack.imports.depot_pdf import PdfImportError, extract_text, mask_personal_data, read_trades
from fintrack.imports.depot_service import build_depot_preview, commit_trades
from fintrack.imports.trade_republic_csv import is_trade_republic, read_trade_republic_csv
from fintrack.imports.categorize import suggest_categories
from fintrack.imports.schemas import (CategorizeRequest, ColumnMapping, CryptoColumnMapping, DepotCommit, ImportCommit,
                                      RuleBatch, RuleCreate)

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


@bp.route('/me/import/bank/pdf/preview', methods=['POST'])
@limiter.limit("40 per hour", key_func=current_user_key)
def preview_bank_pdf_import():
    """
    Kontoauszug als PDF (Inhalt der Anfrage): persönliche Angaben entfernen, Umsätze
    auslesen lassen, dann dieselbe Vorschau wie beim CSV-Import. Übernommen wird über
    /me/import/bank/commit. "sent_text" zeigt genau den Text, der ausgewertet wurde.
    """
    data = request.get_data()
    if not data:
        raise ApiError(400, 'Bitte einen Kontoauszug als PDF auswählen')
    try:
        masked = mask_personal_data(extract_text(data))
    except PdfImportError as error:
        raise ApiError(400, str(error))
    try:
        statement = read_statement(masked)
    except Exception:
        logger.exception('Kontoauszug konnte nicht ausgewertet werden')
        raise ApiError(502, 'Der Kontoauszug konnte gerade nicht ausgewertet werden. Bitte versuche es gleich noch einmal.')

    if not statement.is_bank_statement:
        raise ApiError(400, 'Das PDF ist kein Kontoauszug' + (f' ({statement.note})' if statement.note else '.'))
    rows = to_bank_rows(statement)
    if not rows:
        raise ApiError(400, 'Im Kontoauszug wurden keine Umsätze gefunden' + (f' ({statement.note})' if statement.note else '.'))

    entries = build_preview(current_user.id, rows)
    return jsonify({
        "columns": [],
        "mapping": {},
        "rows": entries,
        "skipped": [],
        "counts": {status: sum(e['status'] == status for e in entries) for status in ('new', 'covered', 'duplicate')},
        "note": statement.note,
        "sent_text": masked,
    }), 200


@bp.route('/me/import/bank/commit', methods=['POST'])
def commit_bank_import():
    """Übernimmt die bestätigten Umsätze als einmalige Buchungen (alles oder nichts)."""
    data = parse_body(ImportCommit)
    created, skipped = commit_rows(current_user.id, data.rows)
    return jsonify({"message": f'{created} Umsätze übernommen', "created": created, "skipped": skipped}), 201


@bp.route('/me/import/bank/categorize', methods=['POST'])
@limiter.limit("20 per hour", key_func=current_user_key)
def categorize_bank_import():
    """
    Kategorie-Vorschläge der KI für Empfänger ohne Vorschlag (JSON {"payees": [{name, income}]}).
    Geht nur mit den Namen an OpenAI, speichert nichts; die Seite setzt die Vorschläge in die Vorschau.
    """
    data = parse_body(CategorizeRequest)
    # Doppelte Namen nur einmal schicken
    payees = list({(p.name.strip(), p.income): {"name": p.name.strip(), "income": p.income}
                   for p in data.payees}.values())
    try:
        suggestions = suggest_categories(current_user.id, payees)
    except Exception:
        logger.exception('Kategorien konnten nicht vorgeschlagen werden')
        raise ApiError(502, 'Die Kategorien konnten gerade nicht vorgeschlagen werden. Bitte versuche es gleich noch einmal.')
    return jsonify({"suggestions": suggestions}), 200


# ─── REGELN ───────────────────────────────────────────────────────────────────

def _rule_json(rule, labels):
    return {"id": rule.id, "pattern": rule.pattern, "income": rule.income, "category_id": rule.category_id,
            "category_label": labels.get(rule.category_id)}


def _category_labels(user_id):
    categories = Category.query.filter_by(user_id=user_id).all()
    by_id = {c.id: c for c in categories}
    return {c.id: f'{by_id[c.parent_id].name} · {c.name}' if c.parent_id in by_id else c.name for c in categories}


def _save_rule(user_id, data):
    """Legt an oder ändert (gleiches Muster in gleicher Richtung). Kategorie muss eigene und passend sein."""
    category = get_own(Category, data.category_id)
    if not category:
        raise ApiError(404, 'Kategorie nicht gefunden')
    if (category.type == 'income') != data.income:
        raise ApiError(400, 'Einnahmen brauchen eine Einkommens-Kategorie, Ausgaben eine Ausgaben-Kategorie')
    rule = CategoryRule.query.filter_by(user_id=user_id, pattern=data.pattern, income=data.income).first()
    if rule is None:
        rule = CategoryRule(user_id=user_id, pattern=data.pattern, income=data.income)
        db.session.add(rule)
    rule.category_id = category.id
    return rule


@bp.route('/me/category-rules', methods=['GET'])
def list_rules():
    """Eigene Regeln, alphabetisch nach Muster."""
    labels = _category_labels(current_user.id)
    rules = CategoryRule.query.filter_by(user_id=current_user.id).order_by(CategoryRule.pattern).all()
    return jsonify([_rule_json(r, labels) for r in rules]), 200


@bp.route('/me/category-rules', methods=['POST'])
def save_rules():
    """
    Eine Regel ({pattern, income, category_id}) oder mehrere auf einmal ({"rules": [...]}, alles
    oder nichts). Gleiches Muster in gleicher Richtung wird überschrieben.
    """
    body = request.get_json(silent=True) or {}
    items = parse_body(RuleBatch).rules if 'rules' in body else [parse_body(RuleCreate)]
    saved = [_save_rule(current_user.id, item) for item in items]
    db.session.commit()
    message = 'Regel gespeichert' if len(saved) == 1 else f'{len(saved)} Regeln gespeichert'
    return jsonify({"message": message, "saved": len(saved)}), 201


@bp.route('/me/category-rules/<int:rule_id>', methods=['DELETE'])
def delete_rule(rule_id):
    rule = get_own(CategoryRule, rule_id)
    if not rule:
        raise ApiError(404, 'Regel nicht gefunden')
    db.session.delete(rule)
    db.session.commit()
    return jsonify({"message": "Regel gelöscht"}), 200


# ─── DEPOT-ABRECHNUNGEN (PDF) ─────────────────────────────────────────────────

# Großzügiger als der Kontoimport: Ein Archiv kann viele hundert einzelne Abrechnungen enthalten
@bp.route('/me/import/depot/preview', methods=['POST'])
@limiter.limit("600 per hour", key_func=current_user_key)
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
    Liest den CSV-Export einer Krypto-App oder -Börse (z.B. Bison) oder den Transaktionsexport
    von Trade Republic (an der Kopfzeile erkannt), ohne KI. Gleiche
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
        if mapping is None and is_trade_republic(data):
            columns, used_mapping, trades, skipped = read_trade_republic_csv(data)
        else:
            columns, used_mapping, trades, skipped = read_crypto_csv(data, mapping)
    except CsvImportError as error:
        return jsonify({"error": str(error), "columns": error.columns}), 400

    return jsonify({
        "columns": columns,
        "mapping": used_mapping,
        "rows": build_depot_preview(current_user.id, trades),
        "skipped": skipped,
    }), 200
