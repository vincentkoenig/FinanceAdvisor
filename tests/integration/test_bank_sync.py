"""
test_bank_sync.py - Bankabruf über Enable Banking (bank/): JWT, Umsätze lesen, abgleichen,
automatisch buchen, Prüfliste, Verbinden/Erneuern, Endpoints und Morgen-Meldungen.
Die Schnittstelle selbst ist durch FakeApi ersetzt - es geht nie etwas ins Netz.
"""

import base64
import json
from datetime import date, datetime, timedelta

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from fintrack.bank import service
from fintrack.bank.client import BankApiError, EnableBankingClient
from fintrack.extensions import db
from fintrack.models import (AccountBalance, BankAccount, BankConnection, BankTransaction, Category, CategoryRule,
                             PushLog, PushSubscription, Transaction)

TODAY = date(2026, 11, 20)


def raw(day, amount, party='', purpose='', ref=None, status='BOOK'):
    """Ein Umsatz, wie ihn die API liefert. amount < 0 = Ausgabe."""
    income = amount > 0
    data = {
        'booking_date': day, 'status': status,
        'transaction_amount': {'amount': f'{abs(amount):.2f}', 'currency': 'EUR'},
        'credit_debit_indicator': 'CRDT' if income else 'DBIT',
        ('debtor' if income else 'creditor'): {'name': party},
        'remittance_information': [purpose] if purpose else [],
    }
    if ref:
        data['entry_reference'] = ref
    return data


class FakeApi:
    def __init__(self):
        self.transactions_by_account = {}
        self.balance = {}
        self.calls = []
        self.error = None
        self.session = {'session_id': 'sess-1', 'access': {'valid_until': '2027-05-01T10:00:00+00:00'},
                        'accounts': [{'uid': 'acc-1', 'identification_hash': 'hash-1', 'name': 'Girokonto',
                                      'account_id': {'iban': 'DE89370400440532013000'}, 'currency': 'EUR'}]}
        self.deleted = []

    def aspsps(self, country):
        return [{'name': 'HypoVereinsbank', 'country': 'DE', 'maximum_consent_validity': 15552000}]

    def start_authorization(self, aspsp_name, country, redirect_url, state, valid_until):
        self.calls.append(('auth', aspsp_name, redirect_url, state, valid_until))
        return {'url': f'https://bank.example/login?state={state}'}

    def create_session(self, code):
        self.calls.append(('session', code))
        return self.session

    def delete_session(self, session_id):
        self.deleted.append(session_id)

    def transactions(self, uid, date_from, strategy=None):
        self.calls.append(('transactions', uid, date_from))
        if self.error:
            raise self.error
        return self.transactions_by_account.get(uid, [])

    def balances(self, uid):
        return [{'balance_type': 'CLBD', 'balance_amount': {'amount': str(self.balance.get(uid, 0)), 'currency': 'EUR'}}]


@pytest.fixture
def api(monkeypatch):
    fake = FakeApi()
    monkeypatch.setattr(service, 'client', lambda: fake)
    monkeypatch.setattr(service, 'today_berlin', lambda: TODAY)
    return fake


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr('fintrack.bank.routes.is_configured', lambda: True)
    monkeypatch.setattr('fintrack.bank.client.is_configured', lambda: True)


@pytest.fixture
def user(make_user):
    user = make_user('a@test.com')
    cats = {
        'salary': Category(user_id=user.id, name='Gehalt', type='income'),
        'rent': Category(user_id=user.id, name='Miete', type='fixed_expense'),
        'food': Category(user_id=user.id, name='Lebensmittel', type='variable_expense'),
        'phone': Category(user_id=user.id, name='Handy', type='fixed_expense'),
    }
    db.session.add_all(cats.values())
    db.session.flush()
    db.session.add_all([
        Transaction(user_id=user.id, category_id=cats['rent'].id, amount=1200, description='Miete',
                    date=datetime(2026, 1, 1), is_recurring=True),
        # Früherer REWE-Einkauf: derselbe Empfänger gilt als sichere Kategorie
        Transaction(user_id=user.id, category_id=cats['food'].id, amount=40, description='REWE Markt',
                    date=datetime(2026, 9, 10)),
        CategoryRule(user_id=user.id, pattern='vodafone', income=False, category_id=cats['phone'].id),
    ])
    db.session.commit()
    user.cats = {k: v.id for k, v in cats.items()}
    return user


def connect(user, enabled=True, synced_until=None, valid_until=datetime(2027, 5, 1)):
    connection = BankConnection(user_id=user.id, aspsp_name='HypoVereinsbank', aspsp_country='DE', status='active',
                                session_id='sess-1', valid_until=valid_until)
    db.session.add(connection)
    db.session.flush()
    db.session.add(BankAccount(connection_id=connection.id, user_id=user.id, uid='acc-1', identification_hash='hash-1',
                               name='Girokonto', enabled=enabled, synced_until=synced_until))
    db.session.commit()
    return connection


class TestClient:

    def test_requests_carry_a_signed_jwt(self):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption())
        token = EnableBankingClient('app-123', pem)._token()

        header_b64, payload_b64, signature_b64 = token.split('.')
        decode = lambda part: base64.urlsafe_b64decode(part + '=' * (-len(part) % 4))
        assert json.loads(decode(header_b64)) == {'typ': 'JWT', 'alg': 'RS256', 'kid': 'app-123'}
        payload = json.loads(decode(payload_b64))
        assert payload['iss'] == 'enablebanking.com' and payload['aud'] == 'api.enablebanking.com'
        assert payload['exp'] - payload['iat'] == 3600
        key.public_key().verify(decode(signature_b64), f'{header_b64}.{payload_b64}'.encode(),
                                padding.PKCS1v15(), hashes.SHA256())

    def test_without_configuration_it_refuses(self, monkeypatch):
        monkeypatch.delenv('ENABLE_BANKING_APP_ID', raising=False)
        with pytest.raises(BankApiError):
            EnableBankingClient()


class TestParse:

    def test_direction_counterparty_and_pending(self):
        rows = service.parse_transactions([
            raw('2026-11-02', 3000, 'Arbeitgeber GmbH', 'Gehalt', ref='A1'),
            raw('2026-11-03', -54.9, 'REWE Markt', 'Kartenzahlung', ref='A2'),
            raw('2026-11-04', -10, 'Kiosk', status='PDNG'),
        ], 'hash-1')

        assert [(r.amount, r.counterparty, r.purpose) for r in rows] == [
            (3000, 'Arbeitgeber GmbH', 'Gehalt'), (-54.9, 'REWE Markt', 'Kartenzahlung')]

    def test_keys_are_stable_and_tell_twins_apart(self):
        twins = [raw('2026-11-07', -3.2, 'Café'), raw('2026-11-07', -3.2, 'Café')]

        first = service.parse_transactions(twins, 'hash-1')
        again = service.parse_transactions(twins, 'hash-1')

        assert first[0].ext_key != first[1].ext_key
        assert [r.ext_key for r in first] == [r.ext_key for r in again]


class TestSync:

    def test_sorts_rows_into_booked_review_covered(self, app, user, api):
        connect(user, synced_until=date(2026, 11, 1))
        api.transactions_by_account['acc-1'] = [
            raw('2026-11-02', -1200, 'Vermieter', 'Miete November', ref='R1'),      # wiederkehrend
            raw('2026-11-03', -54.9, 'REWE Markt', 'Kartenzahlung', ref='R2'),     # gleicher Empfänger
            raw('2026-11-04', -39.99, 'Vodafone GmbH', 'Rechnung', ref='R3'),      # eigene Regel
            raw('2026-11-05', -18, 'Unbekannter Laden', 'Kartenzahlung', ref='R4'),  # Prüfung
        ]
        api.balance['acc-1'] = 2345.67

        counts = service.sync_connection(BankConnection.query.one())

        assert counts['covered'] == 1 and counts['booked'] == 2 and counts['review'] == 1
        booked = Transaction.query.filter(Transaction.import_hash.isnot(None)).order_by(Transaction.date).all()
        assert [(t.description, t.amount, t.category_id) for t in booked] == [
            ('REWE Markt', 54.9, user.cats['food']), ('Vodafone GmbH', 39.99, user.cats['phone'])]
        assert AccountBalance.query.filter_by(user_id=user.id, date=TODAY).one().amount == 2345.67
        assert BankAccount.query.one().synced_until == TODAY
        # Überlappender Abruf: fünf Tage vor dem letzten Stand
        assert api.calls[-1] == ('transactions', 'acc-1', date(2026, 10, 27))

    def test_overlapping_fetch_adds_nothing(self, app, user, api):
        connect(user, synced_until=date(2026, 11, 1))
        api.transactions_by_account['acc-1'] = [raw('2026-11-03', -54.9, 'REWE Markt', 'Kartenzahlung', ref='R2')]
        connection = BankConnection.query.one()

        service.sync_connection(connection)
        counts = service.sync_connection(connection)

        assert not counts.get('booked') and BankTransaction.query.count() == 1
        assert Transaction.query.filter(Transaction.import_hash.isnot(None)).count() == 1

    def test_first_sync_starts_at_last_file_import_and_skips_lookalikes(self, app, user, api):
        db.session.add(Transaction(user_id=user.id, category_id=user.cats['food'], amount=12.5,
                                   description='Bäcker', date=datetime(2026, 11, 10), import_hash='aus-csv'))
        db.session.commit()
        connect(user)
        api.transactions_by_account['acc-1'] = [
            raw('2026-11-10', -12.5, 'BAECKEREI SCHMIDT', 'Karte', ref='X1'),  # schon per CSV da
            raw('2026-11-11', -7, 'Unbekannt', ref='X2'),
        ]

        counts = service.sync_connection(BankConnection.query.one())

        assert api.calls[-1] == ('transactions', 'acc-1', date(2026, 11, 10))
        assert counts['duplicate'] == 1 and counts['review'] == 1

    def test_expired_session_marks_the_connection(self, app, user, api):
        connect(user)
        api.error = BankApiError('abgelaufen', 401, 'EXPIRED_SESSION')

        with pytest.raises(BankApiError):
            service.sync_connection(BankConnection.query.one())

        connection = BankConnection.query.one()
        assert connection.status == 'expired' and 'neu verbinden' in connection.last_error

    def test_past_valid_until_is_expired_without_a_call(self, app, user, api):
        connect(user, valid_until=datetime(2026, 1, 1))

        service.sync_connection(BankConnection.query.one())

        assert BankConnection.query.one().status == 'expired' and api.calls == []

    def test_disabled_accounts_are_not_fetched(self, app, user, api):
        connect(user, enabled=False)

        service.sync_connection(BankConnection.query.one())

        assert api.calls == [] and AccountBalance.query.count() == 0


class TestConnect:

    def test_start_and_finish(self, app, user, api):
        url = service.start_connection(user.id, 'HypoVereinsbank', 'DE', 'https://app.test/api/v1/bank/callback')

        state = BankConnection.query.one().state
        assert url.endswith(state)
        connection = service.finish_connection(state, 'code-1')
        assert connection.status == 'active' and connection.state is None
        assert connection.valid_until == datetime(2027, 5, 1, 10, 0)
        account = BankAccount.query.one()
        assert (account.name, account.iban_last4, account.enabled) == ('Girokonto', '3000', True)

    def test_renewal_keeps_choices_and_removes_the_old_access(self, app, user, api):
        old = connect(user, enabled=False, synced_until=date(2026, 11, 1))
        service.start_connection(user.id, 'HypoVereinsbank', 'DE', 'https://app.test/cb')
        state = BankConnection.query.filter_by(status='pending').one().state
        api.session = {**api.session, 'session_id': 'sess-2',
                       'accounts': [{**api.session['accounts'][0], 'uid': 'acc-neu'}]}

        service.finish_connection(state, 'code-2')

        assert db.session.get(BankConnection, old.id) is None and api.deleted == ['sess-1']
        account = BankAccount.query.one()
        assert (account.uid, account.enabled, account.synced_until) == ('acc-neu', False, date(2026, 11, 1))

    def test_unknown_bank_is_rejected(self, app, user, api):
        from fintrack.api import ApiError
        with pytest.raises(ApiError):
            service.start_connection(user.id, 'Keine Bank', 'DE', 'https://app.test/cb')


class TestRoutes:

    def test_overview_without_configuration(self, app, user, login_client):
        body = login_client('a@test.com').get('/api/v1/me/bank').get_json()

        assert body['configured'] is False and body['connections'] == [] and body['review_count'] == 0

    def test_review_and_commit(self, app, user, api, login_client):
        connect(user)
        api.transactions_by_account['acc-1'] = [raw('2026-11-05', -18, 'Laden A', ref='R1'),
                                                raw('2026-11-06', -25, 'Laden B', ref='R2')]
        service.sync_connection(BankConnection.query.one())
        client = login_client('a@test.com')

        rows = client.get('/api/v1/me/bank/review').get_json()['rows']
        assert [r['counterparty'] for r in rows] == ['Laden B', 'Laden A']
        ids = {r['counterparty']: r['line'] for r in rows}

        response = client.post('/api/v1/me/bank/review/commit', json={
            'book': [{'id': ids['Laden A'], 'category_id': user.cats['food'], 'description': 'Laden A'}],
            'dismiss': [ids['Laden B']]})

        assert response.status_code == 201 and response.get_json()['created'] == 1
        assert {r.counterparty: r.status for r in BankTransaction.query.all()} == {'Laden A': 'booked', 'Laden B': 'dismissed'}
        assert client.get('/api/v1/me/bank').get_json()['review_count'] == 0

    def test_commit_checks_direction_and_ownership(self, app, user, api, make_user, login_client):
        connect(user)
        api.transactions_by_account['acc-1'] = [raw('2026-11-05', -18, 'Laden A', ref='R1')]
        service.sync_connection(BankConnection.query.one())
        row_id = BankTransaction.query.one().id

        wrong = login_client('a@test.com').post('/api/v1/me/bank/review/commit', json={
            'book': [{'id': row_id, 'category_id': user.cats['salary']}]})
        make_user('b@test.com')
        foreign = login_client('b@test.com').post('/api/v1/me/bank/review/commit', json={
            'book': [{'id': row_id, 'category_id': user.cats['food']}]})

        assert wrong.status_code == 400 and foreign.status_code == 404
        assert BankTransaction.query.one().status == 'review'

    def test_connect_returns_the_bank_url(self, app, user, api, configured, login_client):
        response = login_client('a@test.com').post('/api/v1/me/bank/connect', json={'aspsp_name': 'HypoVereinsbank'})

        assert response.status_code == 200 and response.get_json()['url'].startswith('https://bank.example/')
        assert api.calls[0][2] == 'http://localhost/api/v1/bank/callback'

    def test_callback_finishes_without_login(self, app, user, api):
        service.start_connection(user.id, 'HypoVereinsbank', 'DE', 'https://app.test/cb')
        state = BankConnection.query.one().state

        response = app.test_client().get(f'/api/v1/bank/callback?state={state}&code=abc')

        assert response.status_code == 302 and response.headers['Location'].endswith('/app/settings?bank=verbunden')
        assert BankConnection.query.one().status == 'active'

    def test_callback_with_unknown_state_or_cancel(self, app, user, api):
        client = app.test_client()

        assert client.get('/api/v1/bank/callback?state=falsch&code=abc').headers['Location'].endswith('bank=fehler')
        assert client.get('/api/v1/bank/callback?error=access_denied').headers['Location'].endswith('bank=abgebrochen')

    def test_disconnect(self, app, user, api, configured, login_client):
        connection = connect(user)

        response = login_client('a@test.com').delete(f'/api/v1/me/bank/connections/{connection.id}')

        assert response.status_code == 200 and BankConnection.query.count() == 0 and api.deleted == ['sess-1']

    def test_toggle_account(self, app, user, login_client):
        connect(user)
        account = BankAccount.query.one()

        login_client('a@test.com').put(f'/api/v1/me/bank/accounts/{account.id}', json={'enabled': False})

        assert db.session.get(BankAccount, account.id).enabled is False


class TestMorningPush:

    @pytest.fixture
    def delivered(self, monkeypatch):
        from fintrack.push import service as push_service
        public, private = push_service.generate_vapid_keys()
        monkeypatch.setenv('VAPID_PUBLIC_KEY', public)
        monkeypatch.setenv('VAPID_PRIVATE_KEY', private)
        sent = []
        monkeypatch.setattr(push_service, '_deliver', lambda sub, payload, key: sent.append(payload) or 201)
        return sent

    def test_review_and_expiry_reminders_once(self, app, user, delivered):
        from fintrack.push.notify import notify_bank
        db.session.add(PushSubscription(user_id=user.id, endpoint='https://push.example/1', p256dh='k', auth='a'))
        connect(user, valid_until=datetime(2026, 11, 26, 12))
        db.session.add(BankTransaction(user_id=user.id, ext_key='k1', date=TODAY, amount=-5, status='review'))
        db.session.commit()

        assert notify_bank(user.id, TODAY) == 2
        assert notify_bank(user.id, TODAY) == 0
        titles = sorted(m['title'] for m in delivered)
        assert titles == ['Bankzugang läuft ab', 'Neue Umsätze von der Bank']
        assert PushLog.query.count() == 2


class TestConfigurationError:

    def test_broken_key_is_reported_without_its_content(self, app, user, login_client, monkeypatch):
        monkeypatch.setenv('ENABLE_BANKING_APP_ID', 'app-1')
        monkeypatch.setenv('ENABLE_BANKING_PRIVATE_KEY', '-----BEGIN PRIVATE KEY-----\nGEHEIMKAPUTT\n-----END PRIVATE KEY-----')

        body = login_client('a@test.com').get('/api/v1/me/bank').get_json()

        assert body['configured'] is True
        assert body['configuration_error'].startswith('Der private Schlüssel auf dem Server ist ungültig')
        assert 'GEHEIMKAPUTT' not in body['configuration_error']

    def test_valid_key_has_no_error(self, app, user, login_client, monkeypatch):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption()).decode().replace('\n', '\n')
        monkeypatch.setenv('ENABLE_BANKING_APP_ID', 'app-1')
        monkeypatch.setenv('ENABLE_BANKING_PRIVATE_KEY', pem)

        assert login_client('a@test.com').get('/api/v1/me/bank').get_json()['configuration_error'] is None


class TestBase64Key:

    def test_base64_key_is_used(self, app, user, login_client, monkeypatch):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption())
        monkeypatch.delenv('ENABLE_BANKING_PRIVATE_KEY', raising=False)
        monkeypatch.setenv('ENABLE_BANKING_APP_ID', 'app-1')
        monkeypatch.setenv('ENABLE_BANKING_PRIVATE_KEY_B64', base64.b64encode(pem).decode())

        body = login_client('a@test.com').get('/api/v1/me/bank').get_json()

        assert body['configured'] is True and body['configuration_error'] is None

    def test_garbled_base64_is_reported(self, app, user, login_client, monkeypatch):
        monkeypatch.setenv('ENABLE_BANKING_APP_ID', 'app-1')
        monkeypatch.setenv('ENABLE_BANKING_PRIVATE_KEY_B64', 'KEY-----')

        body = login_client('a@test.com').get('/api/v1/me/bank').get_json()

        assert body['configuration_error'].startswith('Der private Schlüssel auf dem Server ist ungültig')
