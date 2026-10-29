"""
insights/routes.py - Liefert den zuletzt generierten täglichen KI-Insight.
"""

from flask import Blueprint, jsonify
from flask_login import current_user

from fintrack.auth.session import protect_blueprint
from fintrack.models import DailyInsight

bp = Blueprint('insights', __name__)
# Nur mit Anmeldung
protect_blueprint(bp)


@bp.route('/me/insight', methods=['GET'])
def get_latest_insight():
    """Gibt den zuletzt generierten täglichen Insight des Nutzers zurück."""
    insight = DailyInsight.query.filter_by(user_id=current_user.id) \
        .order_by(DailyInsight.created_at.desc()).first()

    if not insight:
        return jsonify({"content": None}), 200

    return jsonify({
        "content": insight.content,
        "created_at": insight.created_at.strftime('%Y-%m-%d %H:%M')
    }), 200
