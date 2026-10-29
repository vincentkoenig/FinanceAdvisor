"""
auth/routes.py - Registrierung, Login/Logout, E-Mail-Verifizierung sowie
das Nutzerprofil mit den Anlage-Einstellungen.
Registriert unter /api/v1: /auth/... ist öffentlich, /me... nur mit Anmeldung.
"""

# Standard Library
import re       # Regular Expressions (kurz: Regex) sind Muster um Text zu durchsuchen und zu validieren
from datetime import datetime, timedelta

# Third Party
from flask import Blueprint, current_app, jsonify
from flask_login import current_user, login_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash

# Lokale Imports
from fintrack.api import parse_body
from fintrack.auth.email import generate_verification_code, send_verification_email
from fintrack.auth.schemas import Credentials, ResendVerification, SettingsUpdate, VerifyEmail
from fintrack.auth.session import login_required_api
from fintrack.budget.service import create_default_categories
from fintrack.extensions import db, limiter
from fintrack.models import User

bp = Blueprint('auth', __name__)

# Nach so vielen falschen Codes muss ein neuer Code angefordert werden
MAX_VERIFICATION_ATTEMPTS = 5

# Wird verglichen, wenn es die E-Mail gar nicht gibt - so dauert ein
# Login-Versuch mit unbekannter E-Mail genauso lange wie mit falschem
# Passwort, und man kann nicht über die Antwortzeit herausfinden,
# welche E-Mails registriert sind
_DUMMY_PASSWORD_HASH = generate_password_hash('kein-echtes-passwort')

LOGIN_FAILED_MESSAGE = "E-Mail oder Passwort ist falsch"


def normalize_email(value):
    """E-Mail ohne Leerzeichen und in Kleinbuchstaben vergleichen."""
    return (value or '').strip().lower()


def find_user_by_email(email):
    """Sucht einen Nutzer unabhängig von Groß-/Kleinschreibung der E-Mail."""
    return User.query.filter(db.func.lower(User.email) == normalize_email(email)).first()


def start_session(user):
    """Meldet den Nutzer an (Cookie für 30 Tage) und speichert ein neues
    session_token, falls der Nutzer noch keins hat."""
    if not user.session_token:
        user.rotate_session_token()
    db.session.commit()
    login_user(user, remember=True)


@bp.route('/auth/register', methods=['POST'])
@limiter.limit("5 per hour")
def register():
    """
    Neuen Nutzer registrieren - nur möglich, wenn ALLOW_REGISTRATION
    aktiviert ist. Email wird validiert und Username automatisch aus der
    Email abgeleitet. Passwort wird gehasht gespeichert. Nach der
    Registrierung wird ein 6-stelliger Verifizierungscode per E-Mail
    verschickt - der Account ist erst nach Eingabe des Codes nutzbar.
    """
    if not current_app.config.get('ALLOW_REGISTRATION'):
        return jsonify({"error": "Die Registrierung ist derzeit geschlossen"}), 403

    data = parse_body(Credentials)
    email = normalize_email(data.email)
    password = data.password

    if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
        return jsonify({"error": "Bitte eine gültige Email eingeben"}), 400

    min_length = current_app.config['PASSWORD_MIN_LENGTH']
    if len(password) < min_length:
        return jsonify({"error": f"Das Passwort muss mindestens {min_length} Zeichen lang sein"}), 400

    # Prüfen ob diese Email bereits registriert ist
    if find_user_by_email(email):
        return jsonify({"error": "Diese Email ist bereits registriert"}), 400

    # Verifizierungscode generieren, 15 Minuten gültig
    verification_code = generate_verification_code()

    new_user = User(
        username=email.split('@')[0],
        email=email,
        password=generate_password_hash(password),
        is_verified=False,
        verification_code=verification_code,
        verification_code_expires=datetime.now() + timedelta(minutes=15),
        verification_attempts=0
    )
    db.session.add(new_user)
    db.session.commit()

    create_default_categories(new_user.id)

    # Verifizierungs-E-Mail verschicken. Ist das fehlgeschlagen, ist der
    # Nutzer trotzdem angelegt - das Frontend bietet dann "Code erneut senden" an
    email_sent = send_verification_email(email, verification_code)

    return jsonify({
        "message": "Registriert, bitte E-Mail bestätigen",
        "email": email,
        "email_sent": email_sent
    }), 201


@bp.route('/auth/login', methods=['POST'])
@limiter.limit("10 per minute; 50 per hour")
def login():
    """
    Nutzer einloggen und Session-Cookie setzen.
    Bei unbekannter E-Mail und falschem Passwort kommt dieselbe Meldung,
    damit niemand ausprobieren kann, welche E-Mails registriert sind.
    Ein Login ist nur möglich, wenn die Email zuvor bestätigt wurde.
    """
    data = parse_body(Credentials)
    password = data.password
    user = find_user_by_email(data.email)

    password_hash = user.password if user and user.password else _DUMMY_PASSWORD_HASH
    password_ok = check_password_hash(password_hash, password)

    if not user or not password_ok:
        return jsonify({"error": LOGIN_FAILED_MESSAGE}), 401

    if not user.is_verified:
        return jsonify({
            "error": "Bitte bestätige zuerst deine Email-Adresse",
            "needs_verification": True,
            "email": user.email
        }), 403

    start_session(user)
    return jsonify({"message": "Login successful", "user_id": user.id}), 200


@bp.route('/auth/logout', methods=['POST'])
def logout():
    """Meldet den Nutzer auf diesem Gerät ab (löscht das Session-Cookie)."""
    logout_user()
    return jsonify({"message": "Abgemeldet"}), 200


@bp.route('/me', methods=['GET'])
@login_required_api
def me():
    """Profil des angemeldeten Nutzers inkl. Anlage-Einstellungen - nie das Passwort."""
    return jsonify({
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "risk_profile": current_user.risk_profile,
        "investment_experience": current_user.investment_experience,
        "monthly_budget": current_user.monthly_budget,
        "investment_horizon": current_user.investment_horizon
    }), 200


@bp.route('/auth/verify-email', methods=['POST'])
@limiter.limit("10 per 15 minutes")
def verify_email():
    """
    Prüft den vom Nutzer eingegebenen Verifizierungscode. Bei Erfolg wird
    der Account als verifiziert markiert, der Code gelöscht und der Nutzer
    direkt angemeldet. Nach MAX_VERIFICATION_ATTEMPTS Fehlversuchen ist
    der Code ungültig und ein neuer muss angefordert werden.
    """
    data = parse_body(VerifyEmail)
    code = data.code
    user = find_user_by_email(data.email)

    # Unbekannte E-Mail und falscher Code bekommen dieselbe Antwort
    if not user or (not user.is_verified and not user.verification_code):
        return jsonify({"error": "Ungültiger Code"}), 400

    if user.is_verified:
        return jsonify({"message": "Account bereits verifiziert"}), 200

    if user.verification_attempts >= MAX_VERIFICATION_ATTEMPTS:
        return jsonify({"error": "Zu viele Fehlversuche. Bitte fordere einen neuen Code an."}), 429

    if user.verification_code_expires and datetime.now() > user.verification_code_expires:
        return jsonify({"error": "Der Code ist abgelaufen. Bitte fordere einen neuen an."}), 400

    if code != user.verification_code:
        user.verification_attempts += 1
        db.session.commit()
        return jsonify({"error": "Ungültiger Code"}), 400

    user.is_verified = True
    user.verification_code = None
    user.verification_code_expires = None
    user.verification_attempts = 0
    start_session(user)

    return jsonify({"message": "Email erfolgreich verifiziert", "user_id": user.id}), 200


@bp.route('/auth/resend-verification', methods=['POST'])
@limiter.limit("3 per 15 minutes")
def resend_verification():
    """
    Fordert einen neuen Verifizierungscode an, falls der alte abgelaufen
    ist, zu oft falsch eingegeben wurde oder die E-Mail nicht ankam.
    Antwortet für unbekannte E-Mails genauso wie für bekannte.
    """
    data = parse_body(ResendVerification)
    user = find_user_by_email(data.email)

    if user and not user.is_verified:
        new_code = generate_verification_code()
        user.verification_code = new_code
        user.verification_code_expires = datetime.now() + timedelta(minutes=15)
        user.verification_attempts = 0
        db.session.commit()

        if not send_verification_email(user.email, new_code):
            return jsonify({"error": "Email konnte nicht verschickt werden"}), 500

    return jsonify({"message": "Falls ein unbestätigtes Konto existiert, wurde ein neuer Code verschickt"}), 200


@bp.route('/me/settings', methods=['PUT'])
@login_required_api
def settings():
    """
    Eigene Anlage-Einstellungen speichern: Risikoprofil, Erfahrung,
    Budget und Horizont. Diese Daten nutzt das LLM für personalisierte
    Antworten. Leere Felder werden als "nicht angegeben" gespeichert.
    """
    data = parse_body(SettingsUpdate)

    current_user.risk_profile = data.risk_profile
    current_user.investment_experience = data.investment_experience
    current_user.monthly_budget = data.monthly_budget
    current_user.investment_horizon = data.investment_horizon
    db.session.commit()

    return jsonify({"message": "Einstellungen gespeichert"}), 200
