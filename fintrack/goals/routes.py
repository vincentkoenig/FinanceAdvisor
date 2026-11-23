"""
goals/routes.py - Sparziele (Töpfe vom Kontostand) unter /api/v1.

- GET    /me/goals                 alle Ziele mit Stand, Plan und Vergleich mit dem Kontostand
- POST   /me/goals                 anlegen
- PUT    /me/goals/<id>            ändern (eine neue Rate gilt ab dem nächsten Monat)
- DELETE /me/goals/<id>            löschen (das Geld bleibt ja auf dem Konto)
- POST   /me/goals/<id>/entries    einzahlen (positiv) oder entnehmen (negativ)
"""

from flask import Blueprint, jsonify
from flask_login import current_user

from fintrack.api import ApiError, parse_body
from fintrack.auth.session import get_own, protect_blueprint
from fintrack.goals import service
from fintrack.goals.schemas import EntryInput, GoalInput
from fintrack.models import SavingsGoal

bp = Blueprint('goals', __name__)
protect_blueprint(bp)


def _own_goal(goal_id):
    goal = get_own(SavingsGoal, goal_id)
    if not goal:
        raise ApiError(404, 'Sparziel nicht gefunden')
    return goal


@bp.route('/me/goals', methods=['GET'])
def list_goals():
    return jsonify(service.overview(current_user.id)), 200


@bp.route('/me/goals', methods=['POST'])
def add_goal():
    goal = service.create_goal(current_user.id, parse_body(GoalInput))
    return jsonify({"message": f'Sparziel {goal.name} angelegt', "goal": service.describe(goal)}), 201


@bp.route('/me/goals/<int:goal_id>', methods=['PUT'])
def update_goal(goal_id):
    goal = service.update_goal(_own_goal(goal_id), parse_body(GoalInput))
    return jsonify({"message": 'Sparziel geändert', "goal": service.describe(goal)}), 200


@bp.route('/me/goals/<int:goal_id>', methods=['DELETE'])
def delete_goal(goal_id):
    goal = _own_goal(goal_id)
    name = goal.name
    service.delete_goal(goal)
    return jsonify({"message": f'Sparziel {name} gelöscht'}), 200


@bp.route('/me/goals/<int:goal_id>/entries', methods=['POST'])
def add_entry(goal_id):
    goal = _own_goal(goal_id)
    data = parse_body(EntryInput)
    service.add_entry(goal, data.amount, data.note)
    verb = 'eingezahlt' if data.amount > 0 else 'entnommen'
    return jsonify({"message": f'{goal.name}: {abs(data.amount):.2f} € {verb}'.replace('.', ','),
                    "goal": service.describe(goal)}), 201
