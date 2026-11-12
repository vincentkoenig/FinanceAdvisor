"""
push/service.py - Push-Benachrichtigungen verschicken (Web Push).

So funktioniert Web Push: Beim Einschalten erzeugt der Browser ein Abo mit einer
Adresse (endpoint) beim Push-Dienst seines Herstellers (Google, Apple, Mozilla) und
zwei Schlüsseln. Der Server verschlüsselt jede Nachricht mit diesen Schlüsseln und
schickt sie an die Adresse; der Push-Dienst kann sie nicht lesen und stellt sie dem
Gerät zu, auch wenn die App geschlossen ist. Damit der Push-Dienst weiß, dass die
Nachricht wirklich von FinTrack kommt, signiert der Server sie mit seinem
VAPID-Schlüsselpaar (VAPID_PRIVATE_KEY / VAPID_PUBLIC_KEY in der .env).

Inhalt der Meldungen: nie Beträge oder Kontodaten, denn sie erscheinen auf dem
Sperrbildschirm.
"""

import base64
import json
import logging
import os

from fintrack.extensions import db
from fintrack.models import PushSubscription

logger = logging.getLogger(__name__)

# Wie lange der Push-Dienst eine Meldung aufhebt, wenn das Gerät gerade offline ist
TTL_SECONDS = 24 * 60 * 60
# Arten von Meldungen; jede ist eine Spalte in PushSubscription, pro Gerät ein- und ausschaltbar
TOPICS = ('deadlines', 'savings_plan', 'daily_update')
# Antworten des Push-Dienstes, nach denen das Abo nicht mehr gilt (abgemeldet, App gelöscht)
GONE = {404, 410}


def vapid_keys():
    """(öffentlicher, privater) Schlüssel aus der Umgebung, oder None, wenn Push nicht eingerichtet ist."""
    public, private = os.getenv('VAPID_PUBLIC_KEY'), os.getenv('VAPID_PRIVATE_KEY')
    return (public, private) if public and private else None


def vapid_subject():
    """Kontakt für die Push-Dienste: eine mailto:- oder https-Adresse."""
    return os.getenv('VAPID_SUBJECT') or 'https://fintrack.vincentkoenig.ai'


def generate_vapid_keys():
    """Neues Schlüsselpaar (P-256) im Format, das Browser und pywebpush erwarten."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    def b64(raw):
        return base64.urlsafe_b64encode(raw).rstrip(b'=').decode()

    key = ec.generate_private_key(ec.SECP256R1())
    public = key.public_key().public_bytes(serialization.Encoding.X962,
                                           serialization.PublicFormat.UncompressedPoint)
    return b64(public), b64(key.private_numbers().private_value.to_bytes(32, 'big'))


def _deliver(subscription, payload, private_key):
    """
    Schickt eine Meldung an ein Gerät. Gibt den HTTP-Status des Push-Dienstes zurück
    (201 = angenommen). Eigene Funktion, damit Tests den Versand ersetzen können.
    """
    from pywebpush import WebPushException, webpush

    try:
        response = webpush(
            subscription_info={'endpoint': subscription.endpoint,
                               'keys': {'p256dh': subscription.p256dh, 'auth': subscription.auth}},
            data=json.dumps(payload),
            vapid_private_key=private_key,
            vapid_claims={'sub': vapid_subject()},
            ttl=TTL_SECONDS,
            timeout=15,
        )
        return response.status_code
    except WebPushException as error:
        return error.response.status_code if error.response is not None else 0


def send(subscriptions, title, body, url='/app/', tag=None):
    """
    Schickt eine Meldung an die angegebenen Geräte. Abos, die der Push-Dienst nicht mehr
    kennt, werden gelöscht. Gibt die Anzahl erfolgreich zugestellter Meldungen zurück.
    """
    keys = vapid_keys()
    if not keys:
        return 0
    payload = {'title': title, 'body': body, 'url': url, 'tag': tag}
    delivered = 0
    for subscription in subscriptions:
        try:
            status = _deliver(subscription, payload, keys[1])
        except Exception:
            logger.exception('Push an Gerät %s fehlgeschlagen', subscription.id)
            continue
        if status in GONE:
            db.session.delete(subscription)
        elif 200 <= status < 300:
            delivered += 1
        else:
            logger.warning('Push an Gerät %s: Push-Dienst antwortet %s', subscription.id, status)
    db.session.commit()
    return delivered


def send_to_user(user_id, topic, title, body, url='/app/', tag=None):
    """Meldung an alle Geräte eines Nutzers, die diese Art (eine aus TOPICS) eingeschaltet haben."""
    subscriptions = PushSubscription.query.filter_by(user_id=user_id) \
        .filter(getattr(PushSubscription, topic).is_(True)).all()
    return send(subscriptions, title, body, url, tag)
