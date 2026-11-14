"""
analyst/routes.py - Die Einschätzungen des letzten wöchentlichen Analysten-Laufs.
Registriert unter /api/v1, alle Routen beziehen sich auf den angemeldeten Nutzer.
"""

import json

from flask import Blueprint, jsonify
from flask_login import current_user

from fintrack.analyst.service import STANCE_LABELS, model_name
from fintrack.auth.session import protect_blueprint
from fintrack.extensions import db
from fintrack.models import AnalystSignal, Asset

bp = Blueprint('analyst', __name__)
# Nur mit Anmeldung
protect_blueprint(bp)

# Nur diese Kennzahlen braucht die Anzeige
SHOWN = ('trend', 'pullback', 'overheated', 'trend_break', 'rsi14', 'above_sma200_pct', 'from_high_pct', 'sma200')


@bp.route('/me/analyst', methods=['GET'])
def latest_signals():
    """
    Die Einschätzungen des letzten Laufs, Positionen zuerst, dazu die vorherige
    Einschätzung desselben Werts, damit Änderungen auffallen.
    """
    latest = db.session.query(db.func.max(AnalystSignal.run_date)) \
        .filter(AnalystSignal.user_id == current_user.id).scalar()
    if latest is None:
        return jsonify({'run_date': None, 'model': model_name(), 'items': []}), 200

    rows = db.session.query(AnalystSignal, Asset).join(Asset, Asset.id == AnalystSignal.asset_id) \
        .filter(AnalystSignal.user_id == current_user.id, AnalystSignal.run_date == latest) \
        .order_by(AnalystSignal.kind, AnalystSignal.id).all()
    items = []
    for signal, asset in rows:
        previous = AnalystSignal.query.filter(
            AnalystSignal.user_id == current_user.id, AnalystSignal.asset_id == asset.id,
            AnalystSignal.run_date < latest).order_by(AnalystSignal.run_date.desc()).first()
        values = json.loads(signal.indicators) if signal.indicators else {}
        items.append({
            'asset_id': asset.id, 'name': asset.name, 'symbol': asset.symbol, 'kind': signal.kind,
            'stance': signal.stance, 'stance_label': STANCE_LABELS.get(signal.stance, signal.stance),
            'confidence': signal.confidence, 'reasoning': signal.reasoning, 'invalidation': signal.invalidation,
            'price': signal.price,
            'indicators': {key: values.get(key) for key in SHOWN},
            'previous_label': STANCE_LABELS.get(previous.stance, previous.stance) if previous else None,
            'changed': bool(previous and previous.stance != signal.stance),
        })
    # 'position' kommt alphabetisch vor 'watchlist'
    return jsonify({'run_date': latest.isoformat(), 'model': rows[0][0].model if rows else model_name(),
                    'items': items}), 200
