"""
auth/passkeys.py - Anmeldung per Face ID, Touch ID oder Fingerabdruck über Passkeys
(WebAuthn). Das Handy prüft das Gesicht bzw. den Finger selbst und signiert damit eine
Zufallszahl (challenge) vom Server. Der Server kennt nur den öffentlichen Schlüssel und
prüft die Signatur - biometrische Daten kommen nie hier an.

Ablauf jeweils in zwei Schritten, die challenge liegt dazwischen in der Flask-Session:
- Einrichten (angemeldet): /me/passkeys/options -> Gerät erzeugt Schlüssel -> /me/passkeys
- Anmelden (öffentlich): /auth/passkey/options -> Gerät signiert -> /auth/passkey/login
Registriert unter /api/v1.
"""

from datetime import datetime
from urllib.parse import urlparse

from flask import Blueprint, jsonify, request, session
from flask_login import current_user
from pydantic import Field
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.exceptions import InvalidAuthenticationResponse, InvalidRegistrationResponse
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    AuthenticatorTransport,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from fintrack.api import ApiError, RequestModel, parse_body
from fintrack.auth.session import login_required_api, start_session
from fintrack.extensions import db, limiter
from fintrack.models import Passkey, User

bp = Blueprint('passkeys', __name__)

RP_NAME = 'FinTrack'
# Eine Anmeldung per Passkey muss innerhalb von zwei Minuten abgeschlossen sein
CHALLENGE_TIMEOUT_MS = 120_000
REGISTER_CHALLENGE = 'passkey_register_challenge'
LOGIN_CHALLENGE = 'passkey_login_challenge'

PASSKEY_FAILED_MESSAGE = 'Die Anmeldung per Passkey hat nicht geklappt. Bitte melde dich mit deinem Passwort an.'


class RegisterInput(RequestModel):
    credential: dict
    name: str = Field(default='Gerät', min_length=1, max_length=100)


class LoginInput(RequestModel):
    credential: dict


def relying_party():
    """
    Domain und Origin, für die die Passkeys gelten, z.B. fintrack.vincentkoenig.ai und
    https://fintrack.vincentkoenig.ai. Sie kommen aus der Anfrage selbst (hinter dem
    Proxy dank ProxyFix mit https). Das ist sicher: Das Gerät signiert die Domain mit,
    ein Passkey für eine andere Seite passt hier also nie.
    """
    origin = f'{request.scheme}://{request.host}'
    return urlparse(origin).hostname, origin


def _options_response(options):
    """Optionen als JSON, wie sie navigator.credentials erwartet (Binärdaten als base64url)."""
    return options_to_json(options), 200, {'Content-Type': 'application/json', 'Cache-Control': 'no-store'}


def _pop_challenge(key):
    value = session.pop(key, None)
    if not value:
        raise ApiError(400, 'Die Anfrage ist abgelaufen. Bitte versuche es noch einmal.')
    return base64url_to_bytes(value)


def _transports(credential):
    """Wie das Gerät erreichbar ist (intern, hybrid, usb ...) - hilft dem Browser bei der Anmeldung."""
    values = (credential.get('response') or {}).get('transports') or []
    known = {t.value for t in AuthenticatorTransport}
    return ','.join(v for v in values if v in known) or None


def serialize(passkey):
    return {
        'id': passkey.id,
        'name': passkey.name,
        'created_at': passkey.created_at.isoformat() if passkey.created_at else None,
        'last_used_at': passkey.last_used_at.isoformat() if passkey.last_used_at else None,
    }


# ─── Einrichten (angemeldet) ─────────────────────────────────────────────────

@bp.route('/me/passkeys', methods=['GET'])
@login_required_api
def list_passkeys():
    passkeys = Passkey.query.filter_by(user_id=current_user.id).order_by(Passkey.created_at).all()
    return jsonify([serialize(p) for p in passkeys]), 200


@bp.route('/me/passkeys/options', methods=['POST'])
@login_required_api
@limiter.limit("20 per hour")
def registration_options():
    """
    Startet das Einrichten auf diesem Gerät. Bereits eingerichtete Passkeys werden
    ausgeschlossen, damit dasselbe Gerät nicht doppelt auftaucht. Der Passkey wird auf
    dem Gerät gespeichert (resident key), so geht die Anmeldung später ohne E-Mail.
    """
    rp_id, _ = relying_party()
    existing = Passkey.query.filter_by(user_id=current_user.id).all()
    options = generate_registration_options(
        rp_id=rp_id,
        rp_name=RP_NAME,
        user_id=str(current_user.id).encode(),
        user_name=current_user.email,
        user_display_name=current_user.email,
        timeout=CHALLENGE_TIMEOUT_MS,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        exclude_credentials=[
            PublicKeyCredentialDescriptor(id=base64url_to_bytes(p.credential_id)) for p in existing
        ],
    )
    session[REGISTER_CHALLENGE] = bytes_to_base64url(options.challenge)
    return _options_response(options)


@bp.route('/me/passkeys', methods=['POST'])
@login_required_api
@limiter.limit("20 per hour")
def register_passkey():
    """Prüft den neuen Schlüssel vom Gerät und speichert ihn."""
    data = parse_body(RegisterInput)
    challenge = _pop_challenge(REGISTER_CHALLENGE)
    rp_id, origin = relying_party()
    try:
        verified = verify_registration_response(
            credential=data.credential,
            expected_challenge=challenge,
            expected_rp_id=rp_id,
            expected_origin=origin,
            require_user_verification=True,
        )
    except (InvalidRegistrationResponse, ValueError, KeyError, TypeError):
        raise ApiError(400, 'Der Passkey konnte nicht eingerichtet werden. Bitte versuche es noch einmal.')

    credential_id = bytes_to_base64url(verified.credential_id)
    if Passkey.query.filter_by(credential_id=credential_id).first():
        raise ApiError(400, 'Dieser Passkey ist bereits eingerichtet.')

    passkey = Passkey(
        user_id=current_user.id,
        credential_id=credential_id,
        public_key=verified.credential_public_key,
        sign_count=verified.sign_count,
        transports=_transports(data.credential),
        name=data.name,
    )
    db.session.add(passkey)
    db.session.commit()
    return jsonify(serialize(passkey)), 201


@bp.route('/me/passkeys/<int:passkey_id>', methods=['DELETE'])
@login_required_api
def delete_passkey(passkey_id):
    """Entfernt einen Passkey. Auf dem Gerät bleibt er gespeichert, funktioniert hier aber nicht mehr."""
    passkey = db.session.get(Passkey, passkey_id)
    if passkey is None or passkey.user_id != current_user.id:
        raise ApiError(404, 'Passkey nicht gefunden')
    db.session.delete(passkey)
    db.session.commit()
    return jsonify({'message': 'Passkey entfernt'}), 200


# ─── Anmelden (öffentlich) ───────────────────────────────────────────────────

@bp.route('/auth/passkey/options', methods=['POST'])
@limiter.limit("20 per minute; 100 per hour")
def authentication_options():
    """
    Startet die Anmeldung. Ohne Liste erlaubter Passkeys: Das Gerät zeigt selbst an,
    welche FinTrack-Passkeys es hat - so muss niemand eine E-Mail eingeben, und man kann
    hier nicht herausfinden, welche Konten es gibt.
    """
    rp_id, _ = relying_party()
    options = generate_authentication_options(
        rp_id=rp_id,
        timeout=CHALLENGE_TIMEOUT_MS,
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    session[LOGIN_CHALLENGE] = bytes_to_base64url(options.challenge)
    return _options_response(options)


@bp.route('/auth/passkey/login', methods=['POST'])
@limiter.limit("10 per minute; 50 per hour")
def passkey_login():
    """Prüft die Signatur des Geräts und meldet den Nutzer an - wie nach dem Passwort-Login."""
    data = parse_body(LoginInput)
    challenge = _pop_challenge(LOGIN_CHALLENGE)
    rp_id, origin = relying_party()

    passkey = Passkey.query.filter_by(credential_id=str(data.credential.get('id', ''))).first()
    if passkey is None:
        raise ApiError(401, PASSKEY_FAILED_MESSAGE)

    try:
        verified = verify_authentication_response(
            credential=data.credential,
            expected_challenge=challenge,
            expected_rp_id=rp_id,
            expected_origin=origin,
            credential_public_key=passkey.public_key,
            credential_current_sign_count=passkey.sign_count,
            require_user_verification=True,
        )
    except (InvalidAuthenticationResponse, ValueError, KeyError, TypeError):
        raise ApiError(401, PASSKEY_FAILED_MESSAGE)

    user = db.session.get(User, passkey.user_id)
    if user is None or not user.is_verified:
        raise ApiError(401, PASSKEY_FAILED_MESSAGE)

    passkey.sign_count = verified.new_sign_count
    passkey.last_used_at = datetime.now()
    start_session(user)
    return jsonify({'message': 'Login successful', 'user_id': user.id}), 200
