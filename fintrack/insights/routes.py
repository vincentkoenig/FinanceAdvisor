"""
insights/routes.py - Liefert den zuletzt generierten täglichen KI-Insight.
"""

from flask import Blueprint, jsonify

from fintrack.models import DailyInsight

bp = Blueprint('insights', __name__)


@bp.route('/users/<user_id>/insight', methods=['GET'])
def get_latest_insight(user_id):
    """Gibt den zuletzt generierten täglichen Insight eines Nutzers zurück."""
    insight = DailyInsight.query.filter_by(user_id=user_id) \
        .order_by(DailyInsight.created_at.desc()).first()

    if not insight:
        return jsonify({"content": None}), 200

    return jsonify({
        "content": insight.content,
        "created_at": insight.created_at.strftime('%Y-%m-%d %H:%M')
    }), 200
