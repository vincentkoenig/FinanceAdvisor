"""
auth/routes.py - Registrierung, Login, E-Mail-Verifizierung sowie das
Nutzerprofil mit den Anlage-Einstellungen.
"""

# Standard Library
import re       # Regular Expressions (kurz: Regex) sind Muster um Text zu durchsuchen und zu validieren
from datetime import datetime, timedelta

# Third Party
from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

# Lokale Imports
from fintrack.auth.email import generate_verification_code, send_verification_email
from fintrack.budget.service import create_default_categories
from fintrack.extensions import db
from fintrack.models import User

bp = Blueprint('auth', __name__)


@bp.route('/register', methods=['POST'])
def register():
    """
    Neuen Nutzer registrieren.
    Email wird validiert und Username automatisch aus Email abgeleitet.
    Passwort wird gehasht gespeichert. Nach der Registrierung wird ein
    6-stelliger Verifizierungscode generiert und per E-Mail verschickt -
    der Account ist erst nach Eingabe des Codes vollständig nutzbar.
    """
    data = request.json
    email = data['email']
    password = data['password']

    if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
        return jsonify({"error": "Bitte eine gültige Email eingeben"}), 400

    # Prüfen ob diese Email bereits registriert ist
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return jsonify({"error": "Diese Email ist bereits registriert"}), 400

    username = email.split('@')[0]
    hashed_password = generate_password_hash(password)

    # Verifizierungscode generieren, 15 Minuten gültig
    verification_code = generate_verification_code()
    code_expires = datetime.now() + timedelta(minutes=15)

    new_user = User(
        username=username,
        email=email,
        password=hashed_password,
        is_verified=False,
        verification_code=verification_code,
        verification_code_expires=code_expires
    )
    db.session.add(new_user)
    db.session.commit()

    create_default_categories(new_user.id)

    # Verifizierungs-E-Mail verschicken
    email_sent = send_verification_email(email, verification_code)

    if not email_sent:
        # Nutzer ist trotzdem angelegt, aber ohne verschickte Mail -
        # das teilen wir dem Frontend mit, damit es reagieren kann
        return jsonify({
            "message": "User registered, but verification email could not be sent",
            "user_id": new_user.id,
            "email_sent": False
        }), 201

    return jsonify({
        "message": "User registered successfully, verification email sent",
        "user_id": new_user.id,
        "email_sent": True
    }), 201


@bp.route('/login', methods=['POST'])
def login():
    """
    Nutzer einloggen.
    Email und Passwort werden überprüft. Ein Login ist nur möglich,
    wenn die Email zuvor per Verifizierungscode bestätigt wurde.
    Gibt user_id zurück damit Frontend sie im localStorage speichern kann.
    """
    data = request.json
    email = data['email']
    password = data['password']

    user = User.query.filter_by(email=email).first()

    if not user:
        return jsonify({"error": "User not found"}), 404

    if not check_password_hash(user.password, password):
        return jsonify({"error": "Wrong password"}), 401

    if not user.is_verified:
        return jsonify({
            "error": "Bitte bestätige zuerst deine Email-Adresse",
            "needs_verification": True,
            "user_id": user.id
        }), 403

    return jsonify({"message": "Login successful", "user_id": user.id}), 200


@bp.route('/verify-email', methods=['POST'])
def verify_email():
    """
    Prüft den vom Nutzer eingegebenen Verifizierungscode. Bei Erfolg
    wird der Account als verifiziert markiert und der Code gelöscht.
    """
    data = request.json
    user_id = data['user_id']
    code = data['code']

    user = db.session.get(User, user_id)

    if not user:
        return jsonify({"error": "Nutzer nicht gefunden"}), 404

    if user.is_verified:
        return jsonify({"message": "Account bereits verifiziert"}), 200

    if not user.verification_code or user.verification_code != code:
        return jsonify({"error": "Ungültiger Code"}), 400

    if user.verification_code_expires and datetime.now() > user.verification_code_expires:
        return jsonify({"error": "Der Code ist abgelaufen. Bitte fordere einen neuen an."}), 400

    user.is_verified = True
    user.verification_code = None
    user.verification_code_expires = None
    db.session.commit()

    return jsonify({"message": "Email erfolgreich verifiziert"}), 200


@bp.route('/resend-verification', methods=['POST'])
def resend_verification():
    """Fordert einen neuen Verifizierungscode an, falls der alte
    abgelaufen ist oder die E-Mail nicht ankam."""
    data = request.json
    user_id = data['user_id']

    user = db.session.get(User, user_id)

    if not user:
        return jsonify({"error": "Nutzer nicht gefunden"}), 404

    if user.is_verified:
        return jsonify({"message": "Account bereits verifiziert"}), 200

    new_code = generate_verification_code()
    user.verification_code = new_code
    user.verification_code_expires = datetime.now() + timedelta(minutes=15)
    db.session.commit()

    email_sent = send_verification_email(user.email, new_code)

    if not email_sent:
        return jsonify({"error": "Email konnte nicht verschickt werden"}), 500

    return jsonify({"message": "Neuer Code verschickt"}), 200


@bp.route('/users/<user_id>', methods=['GET'])
def get_user(user_id):
    """Nutzerprofil abrufen - Passwort wird nie zurückgegeben!"""
    user = db.session.get(User, user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify({
        "id": user.id,
        "username": user.username,
        "email": user.email
    }), 200


@bp.route('/users/<user_id>/settings', methods=['PUT'])
def settings(user_id):
    """
    Nutzereinstellungen aktualisieren.
    Risikoprofil, Erfahrung, Budget und Horizont werden gespeichert.
    Diese Daten werden vom LLM für personalisierte Antworten verwendet.
    """
    data = request.json
    risk_profile = data['risk_profile']
    investment_experience = data['investment_experience']
    monthly_budget = data['monthly_budget']
    investment_horizon = data['investment_horizon']

    # Leeren String zu None umwandeln, da monthly_budget ein Float-Feld ist
    if monthly_budget == '':
        monthly_budget = None

    user = db.session.get(User, user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    user.risk_profile = risk_profile
    user.investment_experience = investment_experience
    user.monthly_budget = monthly_budget
    user.investment_horizon = investment_horizon

    db.session.commit()

    return jsonify({"message": "Settings successfully updated"}), 200
