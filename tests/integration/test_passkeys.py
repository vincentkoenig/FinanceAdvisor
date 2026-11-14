"""
test_passkeys.py - Tests für die Anmeldung per Passkey (Face ID, Touch ID, Fingerabdruck)
und die automatische Abmeldung nach 5 Minuten ohne Anfrage.
Statt eines echten Handys signiert ein kleiner Software-Authenticator mit einem
P-256-Schlüssel - genau so, wie es das Gerät nach Face ID bzw. Fingerabdruck tut.
"""

import hashlib
import json
import os
import struct

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from webauthn.helpers import bytes_to_base64url, encode_cbor

from fintrack.models import Passkey

ORIGIN = 'http://localhost'
RP_ID = 'localhost'

FLAG_UP = 0x01   # Nutzer war anwesend
FLAG_UV = 0x04   # Nutzer per Biometrie/PIN geprüft
FLAG_AT = 0x40   # Schlüssel ist angehängt (nur beim Einrichten)


class SoftAuthenticator:
    """Ein Gerät mit genau einem Passkey für eine Seite."""

    def __init__(self, rp_id=RP_ID, origin=ORIGIN):
        self.rp_id = rp_id
        self.origin = origin
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.credential_id = os.urandom(32)
        self.sign_count = 0

    def _cose_public_key(self):
        numbers = self.key.public_key().public_numbers()
        return encode_cbor({1: 2, 3: -7, -1: 1,
                            -2: numbers.x.to_bytes(32, 'big'), -3: numbers.y.to_bytes(32, 'big')})

    def _client_data(self, kind, challenge):
        return json.dumps({'type': kind, 'challenge': challenge, 'origin': self.origin,
                           'crossOrigin': False}).encode()

    def _rp_hash(self):
        return hashlib.sha256(self.rp_id.encode()).digest()

    def create(self, options, flags=FLAG_UP | FLAG_UV):
        """Antwort auf navigator.credentials.create() als JSON."""
        auth_data = (self._rp_hash() + bytes([flags | FLAG_AT]) + struct.pack('>I', 0)
                     + bytes(16) + struct.pack('>H', len(self.credential_id)) + self.credential_id
                     + self._cose_public_key())
        attestation = encode_cbor({'fmt': 'none', 'attStmt': {}, 'authData': auth_data})
        client_data = self._client_data('webauthn.create', options['challenge'])
        cid = bytes_to_base64url(self.credential_id)
        return {'id': cid, 'rawId': cid, 'type': 'public-key',
                'response': {'clientDataJSON': bytes_to_base64url(client_data),
                             'attestationObject': bytes_to_base64url(attestation),
                             'transports': ['internal', 'hybrid']}}

    def get(self, options, flags=FLAG_UP | FLAG_UV, user_id=b'1'):
        """Antwort auf navigator.credentials.get() als JSON."""
        self.sign_count += 1
        auth_data = self._rp_hash() + bytes([flags]) + struct.pack('>I', self.sign_count)
        client_data = self._client_data('webauthn.get', options['challenge'])
        signature = self.key.sign(auth_data + hashlib.sha256(client_data).digest(), ec.ECDSA(hashes.SHA256()))
        cid = bytes_to_base64url(self.credential_id)
        return {'id': cid, 'rawId': cid, 'type': 'public-key',
                'response': {'clientDataJSON': bytes_to_base64url(client_data),
                             'authenticatorData': bytes_to_base64url(auth_data),
                             'signature': bytes_to_base64url(signature),
                             'userHandle': bytes_to_base64url(user_id)}}


def register(client, device, name='iPhone'):
    options = client.post('/api/v1/me/passkeys/options').get_json()
    return client.post('/api/v1/me/passkeys', json={'credential': device.create(options), 'name': name})


def passkey_login(client, device, **kwargs):
    options = client.post('/api/v1/auth/passkey/options').get_json()
    return client.post('/api/v1/auth/passkey/login', json={'credential': device.get(options, **kwargs)})


class TestRegister:

    def test_register_and_list(self, make_user, login_client):
        make_user('a@test.com')
        client = login_client('a@test.com')

        response = register(client, SoftAuthenticator())

        assert response.status_code == 201
        listed = client.get('/api/v1/me/passkeys').get_json()
        assert [p['name'] for p in listed] == ['iPhone']
        # Nur Name und Daten, nie Schlüssel oder Kennung
        assert set(listed[0]) == {'id', 'name', 'created_at', 'last_used_at'}

    def test_options_require_biometrics_and_stored_passkey(self, make_user, login_client):
        make_user('a@test.com')
        client = login_client('a@test.com')

        options = client.post('/api/v1/me/passkeys/options').get_json()

        assert options['rp']['id'] == RP_ID
        assert options['authenticatorSelection']['residentKey'] == 'required'
        assert options['authenticatorSelection']['userVerification'] == 'required'

    def test_existing_passkeys_are_excluded(self, make_user, login_client):
        """Dasselbe Gerät soll nicht doppelt eingerichtet werden"""
        make_user('a@test.com')
        client = login_client('a@test.com')
        device = SoftAuthenticator()
        register(client, device)

        options = client.post('/api/v1/me/passkeys/options').get_json()

        assert [c['id'] for c in options['excludeCredentials']] == [bytes_to_base64url(device.credential_id)]

    def test_without_biometrics_is_rejected(self, make_user, login_client):
        make_user('a@test.com')
        client = login_client('a@test.com')
        options = client.post('/api/v1/me/passkeys/options').get_json()

        response = client.post('/api/v1/me/passkeys',
                               json={'credential': SoftAuthenticator().create(options, flags=FLAG_UP)})

        assert response.status_code == 400
        assert Passkey.query.count() == 0

    def test_passkey_for_other_site_is_rejected(self, make_user, login_client):
        make_user('a@test.com')
        client = login_client('a@test.com')

        response = register(client, SoftAuthenticator(origin='https://boese.example'))

        assert response.status_code == 400

    def test_challenge_works_only_once(self, make_user, login_client):
        make_user('a@test.com')
        client = login_client('a@test.com')
        options = client.post('/api/v1/me/passkeys/options').get_json()
        device = SoftAuthenticator()
        client.post('/api/v1/me/passkeys', json={'credential': device.create(options)})

        replay = client.post('/api/v1/me/passkeys', json={'credential': SoftAuthenticator().create(options)})

        assert replay.status_code == 400
        assert Passkey.query.count() == 1

    def test_delete_only_own_passkey(self, make_user, login_client):
        make_user('a@test.com')
        make_user('b@test.com')
        client_a = login_client('a@test.com')
        passkey_id = register(client_a, SoftAuthenticator()).get_json()['id']
        client_b = login_client('b@test.com')

        assert client_b.delete(f'/api/v1/me/passkeys/{passkey_id}').status_code == 404
        assert client_a.delete(f'/api/v1/me/passkeys/{passkey_id}').status_code == 200
        assert Passkey.query.count() == 0


class TestLogin:

    def test_login_with_passkey(self, app, make_user, login_client):
        user = make_user('a@test.com')
        device = SoftAuthenticator()
        register(login_client('a@test.com'), device)
        client = app.test_client()

        response = passkey_login(client, device)

        assert response.status_code == 200
        assert client.get('/api/v1/me').get_json()['id'] == user.id
        passkey = Passkey.query.one()
        assert passkey.last_used_at is not None and passkey.sign_count == 1

    def test_login_options_reveal_no_accounts(self, app):
        """Ohne E-Mail und ohne Liste von Passkeys - das Gerät wählt selbst"""
        options = app.test_client().post('/api/v1/auth/passkey/options').get_json()

        assert options.get('allowCredentials', []) == []
        assert options['userVerification'] == 'required'

    def test_unknown_passkey_is_rejected(self, app, make_user):
        make_user('a@test.com')
        client = app.test_client()

        response = passkey_login(client, SoftAuthenticator())

        assert response.status_code == 401
        assert client.get('/api/v1/me').status_code == 401

    def test_wrong_signature_is_rejected(self, app, make_user, login_client):
        """Ein anderes Gerät mit kopierter Kennung, aber ohne den passenden Schlüssel"""
        make_user('a@test.com')
        device = SoftAuthenticator()
        register(login_client('a@test.com'), device)
        impostor = SoftAuthenticator()
        impostor.credential_id = device.credential_id
        client = app.test_client()

        assert passkey_login(client, impostor).status_code == 401
        assert client.get('/api/v1/me').status_code == 401

    def test_without_biometrics_is_rejected(self, app, make_user, login_client):
        make_user('a@test.com')
        device = SoftAuthenticator()
        register(login_client('a@test.com'), device)

        assert passkey_login(app.test_client(), device, flags=FLAG_UP).status_code == 401

    def test_login_without_challenge_is_rejected(self, app, make_user, login_client):
        make_user('a@test.com')
        device = SoftAuthenticator()
        register(login_client('a@test.com'), device)
        credential = device.get({'challenge': bytes_to_base64url(b'selbst-ausgedacht')})

        response = app.test_client().post('/api/v1/auth/passkey/login', json={'credential': credential})

        assert response.status_code == 400

    def test_deleted_passkey_no_longer_works(self, app, make_user, login_client):
        make_user('a@test.com')
        device = SoftAuthenticator()
        client = login_client('a@test.com')
        passkey_id = register(client, device).get_json()['id']
        client.delete(f'/api/v1/me/passkeys/{passkey_id}')

        assert passkey_login(app.test_client(), device).status_code == 401


class TestIdleTimeout:

    @pytest.fixture
    def clock(self, mocker):
        """Verstellbare Uhr für die Abmeldung nach 5 Minuten."""
        now = {'t': 1_000_000}
        mocker.patch('fintrack.auth.session.time.time', side_effect=lambda: now['t'])
        return now

    def test_logged_out_after_five_idle_minutes(self, make_user, login_client, clock):
        make_user('a@test.com')
        client = login_client('a@test.com')

        clock['t'] += 5 * 60 + 1

        assert client.get('/api/v1/me').status_code == 401
        # Auch danach bleibt man abgemeldet
        clock['t'] += 1
        assert client.get('/api/v1/me').status_code == 401

    def test_each_request_counts_as_activity(self, make_user, login_client, clock):
        make_user('a@test.com')
        client = login_client('a@test.com')

        for _ in range(3):
            clock['t'] += 4 * 60
            assert client.get('/api/v1/me').status_code == 200

    def test_no_permanent_remember_cookie(self, app, make_user):
        """Kein 30-Tage-Cookie mehr, das die Anmeldung still erneuert"""
        from tests.conftest import TEST_PASSWORD
        make_user('a@test.com')

        response = app.test_client().post('/api/v1/auth/login',
                                          json={'email': 'a@test.com', 'password': TEST_PASSWORD})

        cookies = ' '.join(response.headers.getlist('Set-Cookie'))
        assert 'remember_token' not in cookies

    def test_old_session_without_timestamp_is_expired(self, make_user, login_client):
        """Anmeldungen von vor dieser Regel haben keinen Zeitstempel und laufen ab"""
        make_user('a@test.com')
        client = login_client('a@test.com')
        with client.session_transaction() as session:
            session.pop('last_seen')

        assert client.get('/api/v1/me').status_code == 401

    def test_passkey_login_after_timeout(self, app, make_user, login_client, clock):
        make_user('a@test.com')
        device = SoftAuthenticator()
        client = login_client('a@test.com')
        register(client, device)
        clock['t'] += 10 * 60
        assert client.get('/api/v1/me').status_code == 401

        assert passkey_login(client, device).status_code == 200
        assert client.get('/api/v1/me').status_code == 200
