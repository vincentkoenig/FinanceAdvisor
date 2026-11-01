"""
test_contract_routes.py - Tests für die Verträge-API unter /api/v1/me/contracts:
anlegen, prüfen, bearbeiten, kündigen, Kündigung zurücknehmen, löschen und
die Übersicht mit Summen.
"""

import sys
import os
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from fintrack.extensions import db
from fintrack.models import Contract

TODAY = date(2026, 8, 1)

INSURANCE = {
    'name': 'Haftpflicht', 'provider': 'Beispiel Versicherung', 'category': 'insurance',
    'amount': 60, 'interval': 'yearly', 'start_date': '2024-01-01',
    'renewal_months': 12, 'notice_value': 3, 'notice_unit': 'months',
}


@pytest.fixture(autouse=True)
def fixed_today(mocker):
    """Fristen hängen vom heutigen Tag ab - in den Tests ist immer der 01.08.2026."""
    mocker.patch('fintrack.contracts.routes.today_berlin', return_value=TODAY)
    mocker.patch('fintrack.contracts.service.today_berlin', return_value=TODAY)


@pytest.fixture
def client(make_user, login_client):
    make_user('a@test.com')
    return login_client('a@test.com')


def create(client, **changes):
    response = client.post('/api/v1/me/contracts', json={**INSURANCE, **changes})
    assert response.status_code == 201, response.get_json()
    return response.get_json()['contract']


class TestCreate:

    def test_created_contract_has_deadlines(self, client):
        contract = create(client)

        assert contract['status'] == 'active'
        assert contract['cancel_by'] == '2026-09-30'
        assert contract['cancel_effective'] == '2026-12-31'
        assert contract['days_to_cancel'] == 60
        assert contract['yearly_cost'] == 60
        assert contract['monthly_cost'] == 5
        assert contract['min_term_end'] is None

    def test_minimum_term_end_is_reported(self, client):
        contract = create(client, category='telecom', start_date='2025-03-15', min_term_months=24, renewal_months=1)

        assert contract['min_term_end'] == '2027-03-14'

    def test_empty_optional_texts_are_stored_as_null(self, client):
        contract = create(client, provider='  ', notes='')

        assert contract['provider'] is None and contract['notes'] is None

    @pytest.mark.parametrize('changes,field', [
        ({'amount': 0}, 'amount'),
        ({'category': 'auto'}, 'category'),
        ({'interval': 'weekly'}, 'interval'),
        ({'notice_unit': 'years'}, 'notice_unit'),
        ({'start_date': '01.01.2026'}, 'start_date'),
        ({'name': ''}, 'name'),
    ])
    def test_invalid_input_is_rejected(self, client, changes, field):
        response = client.post('/api/v1/me/contracts', json={**INSURANCE, **changes})

        assert response.status_code == 400
        assert field in response.get_json()['fields']
        assert Contract.query.count() == 0

    def test_needs_some_term(self, client):
        response = client.post('/api/v1/me/contracts', json={**INSURANCE, 'renewal_months': None})

        assert response.status_code == 400
        assert 'Mindestlaufzeit oder Verlängerung' in response.get_json()['error']


class TestOverview:

    def test_sorted_by_deadline_with_totals_of_running_contracts(self, client):
        create(client, name='Strom', category='energy', amount=80, interval='monthly',
               start_date='2026-01-01', renewal_months=1, notice_value=1)
        create(client)
        create(client, name='Alter Kredit', category='loan', amount=100, interval='monthly',
               start_date='2020-01-01', min_term_months=24, renewal_months=None)

        data = client.get('/api/v1/me/contracts').get_json()

        assert [c['name'] for c in data['contracts']] == ['Strom', 'Haftpflicht', 'Alter Kredit']
        assert data['contracts'][2]['status'] == 'ended'
        # Beendete Verträge zählen nicht mehr mit
        assert data['yearly_total'] == 80 * 12 + 60
        assert data['monthly_total'] == 85


class TestUpdateAndDelete:

    def test_update_replaces_fields(self, client):
        contract = create(client)

        response = client.put(f"/api/v1/me/contracts/{contract['id']}",
                              json={**INSURANCE, 'amount': 72, 'notice_value': 1})

        assert response.status_code == 200
        updated = response.get_json()['contract']
        assert updated['amount'] == 72
        assert updated['cancel_by'] == '2026-11-30'

    def test_delete(self, client):
        contract = create(client)

        assert client.delete(f"/api/v1/me/contracts/{contract['id']}").status_code == 200
        assert Contract.query.count() == 0

    def test_unknown_contract_is_404(self, client):
        assert client.put('/api/v1/me/contracts/999', json=INSURANCE).status_code == 404


class TestCancel:

    def test_cancel_ends_at_next_possible_date(self, client):
        contract = create(client)

        response = client.post(f"/api/v1/me/contracts/{contract['id']}/cancel", json={})

        cancelled = response.get_json()['contract']
        assert response.status_code == 200
        assert cancelled['status'] == 'cancelled'
        assert cancelled['cancelled_at'] == '2026-08-01'
        assert cancelled['end_date'] == '2026-12-31'
        assert cancelled['cancel_by'] is None

    def test_cancel_with_own_end_date(self, client):
        contract = create(client)

        response = client.post(f"/api/v1/me/contracts/{contract['id']}/cancel", json={'end_date': '2026-10-31'})

        assert response.get_json()['contract']['end_date'] == '2026-10-31'

    def test_cannot_cancel_twice(self, client):
        contract = create(client)
        client.post(f"/api/v1/me/contracts/{contract['id']}/cancel", json={})

        response = client.post(f"/api/v1/me/contracts/{contract['id']}/cancel", json={})

        assert response.status_code == 409

    def test_end_date_before_start_is_rejected(self, client):
        contract = create(client)

        response = client.post(f"/api/v1/me/contracts/{contract['id']}/cancel", json={'end_date': '2023-12-31'})

        assert response.status_code == 400
        assert db.session.get(Contract, contract['id']).end_date is None

    def test_undo_cancel(self, client):
        contract = create(client)
        client.post(f"/api/v1/me/contracts/{contract['id']}/cancel", json={})

        response = client.delete(f"/api/v1/me/contracts/{contract['id']}/cancel")

        restored = response.get_json()['contract']
        assert restored['status'] == 'active'
        assert restored['end_date'] is None and restored['cancelled_at'] is None
        assert restored['cancel_by'] == '2026-09-30'

    def test_editing_keeps_the_cancellation(self, client):
        contract = create(client)
        client.post(f"/api/v1/me/contracts/{contract['id']}/cancel", json={})

        updated = client.put(f"/api/v1/me/contracts/{contract['id']}",
                             json={**INSURANCE, 'amount': 99}).get_json()['contract']

        assert updated['status'] == 'cancelled'
        assert updated['end_date'] == '2026-12-31'


class TestChatTool:

    def test_chat_can_read_contracts(self, client, mocker):
        """Fragt das Sprachmodell nach get_contracts, bekommt es die eigenen Verträge mit Fristen"""
        from types import SimpleNamespace

        create(client)
        tool_call = SimpleNamespace(id='call_1', function=SimpleNamespace(name='get_contracts', arguments='{}'))
        first = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=[tool_call], content=None))])
        second = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='Bis 30.09. kündigen'))])
        fake_client = mocker.Mock()
        fake_client.chat.completions.create.side_effect = [first, second]
        mocker.patch('fintrack.chat.routes.get_openai_client', return_value=fake_client)

        response = client.post('/api/v1/me/chat', json={'message': 'Wann kann ich die Haftpflicht kündigen?'})

        assert response.status_code == 200
        tool_answer = fake_client.chat.completions.create.call_args_list[1].kwargs['messages'][-1]
        assert tool_answer['role'] == 'tool'
        assert 'Haftpflicht' in tool_answer['content'] and '2026-09-30' in tool_answer['content']
