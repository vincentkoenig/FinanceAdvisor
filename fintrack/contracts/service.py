"""
contracts/service.py - Verträge mit berechneten Fristen und Summen.
Gemeinsam genutzt von der API (contracts/routes.py) und dem Chat-Tool.
"""

from fintrack.contracts.terms import contract_status, term_end, today_berlin, yearly_cost
from fintrack.models import Contract


def _iso(value):
    return value.isoformat() if value else None


def serialize_contract(contract, today):
    """Gespeicherte Felder plus Status, Fristen und Kosten pro Monat/Jahr."""
    status = contract_status(contract, today)
    yearly = yearly_cost(contract)
    cancel_by = status['cancel_by']
    return {
        "id": contract.id,
        "name": contract.name,
        "provider": contract.provider,
        "category": contract.category,
        "contract_number": contract.contract_number,
        "amount": contract.amount,
        "interval": contract.interval,
        "start_date": _iso(contract.start_date),
        "min_term_months": contract.min_term_months,
        "renewal_months": contract.renewal_months,
        "notice_value": contract.notice_value,
        "notice_unit": contract.notice_unit,
        "cancelled_at": _iso(contract.cancelled_at),
        "end_date": _iso(contract.end_date),
        "notes": contract.notes,
        "status": status['status'],
        "next_term_end": _iso(status['next_term_end']),
        "cancel_by": _iso(cancel_by),
        "cancel_effective": _iso(status['cancel_effective']),
        "days_to_cancel": (cancel_by - today).days if cancel_by else None,
        "ends_on": _iso(status['ends_on']),
        # Ende der Mindestlaufzeit: bis dahin zählt eine Frist auch bei monatlicher Verlängerung
        "min_term_end": _iso(term_end(contract.start_date, contract.min_term_months)) if contract.min_term_months else None,
        "yearly_cost": yearly,
        "monthly_cost": round(yearly / 12, 2),
    }


def contracts_overview(user_id, today=None):
    """
    Alle Verträge des Nutzers, sortiert nach dem nächsten Kündigungstag
    (Verträge ohne Frist am Ende), plus Summen der noch laufenden Verträge.
    """
    today = today or today_berlin()
    contracts = [serialize_contract(c, today)
                 for c in Contract.query.filter_by(user_id=user_id).order_by(Contract.id).all()]
    contracts.sort(key=lambda c: (c['cancel_by'] is None, c['cancel_by'] or '', c['name'].lower()))

    running = [c for c in contracts if c['status'] != 'ended']
    yearly_total = round(sum(c['yearly_cost'] for c in running), 2)
    return {
        "contracts": contracts,
        "yearly_total": yearly_total,
        "monthly_total": round(yearly_total / 12, 2),
    }
