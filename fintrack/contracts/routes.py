"""
contracts/routes.py - API für Verträge: anlegen, bearbeiten, löschen,
kündigen und die Übersicht mit Fristen.
Registriert unter /api/v1, alle Routen beziehen sich auf den angemeldeten Nutzer.
"""

# Third Party
from flask import Blueprint, jsonify
from flask_login import current_user

# Lokale Imports
from fintrack.api import ApiError, parse_body
from fintrack.auth.session import get_own, protect_blueprint
from fintrack.contracts.schemas import ContractCancel, ContractInput
from fintrack.contracts.service import contracts_overview, serialize_contract
from fintrack.contracts.terms import contract_status, today_berlin
from fintrack.extensions import db
from fintrack.models import Contract

bp = Blueprint('contracts', __name__)
# Nur mit Anmeldung
protect_blueprint(bp)


def _own_contract(contract_id):
    contract = get_own(Contract, contract_id)
    if not contract:
        raise ApiError(404, 'Vertrag nicht gefunden')
    return contract


@bp.route('/me/contracts', methods=['GET'])
def get_contracts():
    """Alle eigenen Verträge mit Fristen, dazu Kosten pro Monat und Jahr."""
    return jsonify(contracts_overview(current_user.id)), 200


@bp.route('/me/contracts', methods=['POST'])
def add_contract():
    data = parse_body(ContractInput)

    contract = Contract(user_id=current_user.id, **data.model_dump())
    db.session.add(contract)
    db.session.commit()

    return jsonify({"message": "Vertrag angelegt", "contract": serialize_contract(contract, today_berlin())}), 201


@bp.route('/me/contracts/<int:contract_id>', methods=['PUT'])
def update_contract(contract_id):
    """Vertrag bearbeiten. Eine Kündigung bleibt dabei bestehen."""
    contract = _own_contract(contract_id)
    data = parse_body(ContractInput)

    for field, value in data.model_dump().items():
        setattr(contract, field, value)
    db.session.commit()

    return jsonify({"message": "Vertrag gespeichert", "contract": serialize_contract(contract, today_berlin())}), 200


@bp.route('/me/contracts/<int:contract_id>', methods=['DELETE'])
def delete_contract(contract_id):
    contract = _own_contract(contract_id)

    db.session.delete(contract)
    db.session.commit()

    return jsonify({"message": "Vertrag gelöscht"}), 200


@bp.route('/me/contracts/<int:contract_id>/cancel', methods=['POST'])
def cancel_contract(contract_id):
    """
    Vertrag als gekündigt markieren. Ohne Enddatum endet er zum
    nächstmöglichen Laufzeitende, das die Kündigungsfrist noch erlaubt.
    """
    contract = _own_contract(contract_id)
    data = parse_body(ContractCancel)
    today = today_berlin()

    if contract.end_date:
        raise ApiError(409, 'Der Vertrag ist bereits gekündigt')

    end_date = data.end_date
    if end_date is None:
        status = contract_status(contract, today)
        end_date = status['cancel_effective'] or status['ends_on']
    if end_date is None:
        raise ApiError(400, 'Bitte ein Enddatum angeben')
    if end_date < contract.start_date:
        raise ApiError(400, 'Das Enddatum darf nicht vor dem Vertragsbeginn liegen')

    contract.cancelled_at = today
    contract.end_date = end_date
    db.session.commit()

    return jsonify({"message": "Vertrag gekündigt", "contract": serialize_contract(contract, today)}), 200


@bp.route('/me/contracts/<int:contract_id>/cancel', methods=['DELETE'])
def undo_cancel_contract(contract_id):
    """Kündigung zurücknehmen - der Vertrag läuft wieder normal weiter."""
    contract = _own_contract(contract_id)

    contract.cancelled_at = None
    contract.end_date = None
    db.session.commit()

    return jsonify({"message": "Kündigung zurückgenommen",
                    "contract": serialize_contract(contract, today_berlin())}), 200
