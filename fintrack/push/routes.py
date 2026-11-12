"""
push/routes.py - API für Push-Benachrichtigungen: Gerät anmelden, Einstellungen des
Geräts lesen und ändern, abmelden und eine Test-Meldung schicken.
Ein Gerät wird über seinen endpoint erkannt, den nur der Browser des Geräts kennt.
Registriert unter /api/v1, alle Routen beziehen sich auf den angemeldeten Nutzer.
"""

from typing import Optional

from flask import Blueprint, jsonify
from flask_login import current_user
from pydantic import Field

from fintrack.api import ApiError, RequestModel, parse_body
from fintrack.auth.session import current_user_key, protect_blueprint
from fintrack.extensions import db, limiter
from fintrack.models import PushSubscription
from fintrack.push.service import TOPICS, send, vapid_keys

bp = Blueprint('push', __name__)
# Nur mit Anmeldung
protect_blueprint(bp)


class SubscriptionKeys(RequestModel):
    p256dh: str = Field(min_length=1, max_length=200)
    auth: str = Field(min_length=1, max_length=100)


class SubscriptionInput(RequestModel):
    """Das Abo, wie es der Browser liefert (PushSubscription.toJSON()), plus die Auswahl."""
    endpoint: str = Field(min_length=1, max_length=1000, pattern=r'^https://')
    keys: SubscriptionKeys
    deadlines: bool = True
    savings_plan: bool = True
    daily_update: bool = True
    price_moves: bool = True
    watchlist: bool = True


class DeviceInput(RequestModel):
    endpoint: str = Field(min_length=1, max_length=1000)
    deadlines: Optional[bool] = None
    savings_plan: Optional[bool] = None
    daily_update: Optional[bool] = None
    price_moves: Optional[bool] = None
    watchlist: Optional[bool] = None


def _serialize(subscription):
    return {topic: getattr(subscription, topic) for topic in TOPICS}


def _own_device(endpoint):
    subscription = PushSubscription.query.filter_by(user_id=current_user.id, endpoint=endpoint).first()
    if not subscription:
        raise ApiError(404, 'Dieses Gerät ist nicht angemeldet')
    return subscription


@bp.route('/me/push', methods=['GET'])
def push_config():
    """Ob Push auf dem Server eingerichtet ist, und der öffentliche Schlüssel für den Browser."""
    keys = vapid_keys()
    return jsonify({'available': bool(keys), 'public_key': keys[0] if keys else None}), 200


@bp.route('/me/push/devices', methods=['POST'])
def subscribe():
    """
    Gerät anmelden oder seine Schlüssel erneuern. War der endpoint vorher einem anderen
    Konto zugeordnet (anderer Login auf demselben Gerät), gehört er jetzt diesem.
    """
    if not vapid_keys():
        raise ApiError(503, 'Push-Benachrichtigungen sind auf dem Server nicht eingerichtet')
    data = parse_body(SubscriptionInput)
    subscription = PushSubscription.query.filter_by(endpoint=data.endpoint).first()
    if not subscription:
        subscription = PushSubscription(endpoint=data.endpoint)
        db.session.add(subscription)
    subscription.user_id = current_user.id
    subscription.p256dh = data.keys.p256dh
    subscription.auth = data.keys.auth
    for topic in TOPICS:
        setattr(subscription, topic, getattr(data, topic))
    db.session.commit()
    return jsonify(_serialize(subscription)), 200


@bp.route('/me/push/devices/current', methods=['POST'])
def device_settings():
    """
    Einstellungen dieses Geräts lesen und, wenn mitgeschickt, ändern. POST statt GET,
    weil der endpoint nicht in die URL und damit in Logs gehört.
    """
    data = parse_body(DeviceInput)
    subscription = _own_device(data.endpoint)
    for topic in TOPICS:
        if getattr(data, topic) is not None:
            setattr(subscription, topic, getattr(data, topic))
    db.session.commit()
    return jsonify(_serialize(subscription)), 200


@bp.route('/me/push/devices/remove', methods=['POST'])
def unsubscribe():
    """Gerät abmelden. Ist es schon weg, ist das auch in Ordnung."""
    data = parse_body(DeviceInput)
    PushSubscription.query.filter_by(user_id=current_user.id, endpoint=data.endpoint).delete()
    db.session.commit()
    return jsonify({'message': 'Gerät abgemeldet'}), 200


@bp.route('/me/push/test', methods=['POST'])
@limiter.limit('10 per hour', key_func=current_user_key)
def send_test():
    """Test-Meldung an dieses Gerät."""
    data = parse_body(DeviceInput)
    subscription = _own_device(data.endpoint)
    if not send([subscription], 'FinTrack', 'Benachrichtigungen funktionieren auf diesem Gerät.',
                tag='test'):
        raise ApiError(502, 'Der Push-Dienst hat die Meldung nicht angenommen. Bitte noch einmal einschalten.')
    return jsonify({'message': 'Test-Meldung verschickt'}), 200
