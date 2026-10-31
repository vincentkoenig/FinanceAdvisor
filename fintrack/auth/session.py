"""
auth/session.py - Anmeldung über das Session-Cookie: Nutzer aus dem Cookie
laden, nicht angemeldete Anfragen abweisen und Datensätze nur laden, wenn
sie dem angemeldeten Nutzer gehören.
"""

from functools import wraps
from urllib.parse import urlparse

from flask import jsonify, request
from flask_login import current_user

from fintrack.extensions import db, login_manager
from fintrack.models import User

# Schutz vor gestohlenen Cookies: "basic" prüft Browser-Merkmale, ohne
# bei wechselnder IP (z.B. Handy im Mobilfunknetz) abzumelden
login_manager.session_protection = 'basic'


@login_manager.user_loader
def load_user(cookie_id):
    """
    Lädt den Nutzer zum Wert aus dem Anmelde-Cookie ("<id>:<session_token>").
    Passt das Token nicht mehr (z.B. nach Passwortänderung), gilt die
    Anmeldung als ungültig.
    """
    user_id, _, token = str(cookie_id).partition(':')
    if not user_id.isdigit() or not token:
        return None
    user = db.session.get(User, int(user_id))
    if user is None or user.session_token != token:
        return None
    return user


@login_manager.unauthorized_handler
def unauthorized():
    """
    Nicht angemeldet: 401, das React-Frontend zeigt dann die Anmeldung.
    """
    return jsonify({"error": "Bitte melde dich an"}), 401


def require_login():
    """
    before_request-Hook für alle Blueprints mit Nutzerdaten: ohne Anmeldung
    401. Welche Daten zurückkommen, bestimmt danach allein current_user -
    die URLs enthalten keine User-IDs (alles unter /api/v1/me/...).
    """
    if not current_user.is_authenticated:
        return unauthorized()
    return None


def protect_blueprint(blueprint):
    """Hängt require_login() an alle Routen eines Blueprints."""
    blueprint.before_request(require_login)


def current_user_key():
    """
    Schlüssel für die Begrenzung pro Nutzer (statt pro IP), z.B. für den
    Chat, damit OpenAI-Kosten pro Konto gedeckelt sind.
    """
    if current_user.is_authenticated:
        return f'user:{current_user.id}'
    return f'ip:{request.remote_addr}'


def get_own(model, object_id):
    """
    Lädt einen Datensatz (z.B. Buchung, Kategorie, Sparplan) nur, wenn er
    dem angemeldeten Nutzer gehört. Gibt sonst None zurück - der Aufrufer
    antwortet dann mit 404, egal ob es den Datensatz gar nicht gibt oder
    er jemand anderem gehört.
    """
    if object_id is None:
        return None
    obj = db.session.get(model, object_id)
    if obj is None or obj.user_id != current_user.id:
        return None
    return obj


def login_required_api(view):
    """
    Wie protect_blueprint(), aber für einzelne Routen - für Blueprints, die
    auch öffentliche Routen haben (z.B. Login und Registrierung).
    """
    @wraps(view)
    def wrapper(*args, **kwargs):
        denied = require_login()
        if denied is not None:
            return denied
        return view(*args, **kwargs)
    return wrapper


def reject_cross_site_requests():
    """
    Zusätzlicher Schutz gegen CSRF: Ändernde Anfragen (POST, PUT, DELETE)
    mit Origin-Header einer fremden Seite werden abgewiesen. Das
    SameSite-Cookie verhindert das meiste bereits, das hier ist die
    zweite Absicherung.
    """
    if request.method in ('GET', 'HEAD', 'OPTIONS'):
        return None
    origin = request.headers.get('Origin')
    if origin and urlparse(origin).netloc != request.host:
        return jsonify({"error": "Anfrage von fremder Seite abgelehnt"}), 403
    return None
