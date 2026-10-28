"""
auth/cli.py - Befehle zur Kontoverwaltung über die Kommandozeile, solange
die Registrierung geschlossen ist und es noch kein "Passwort vergessen" gibt:

    flask --app "fintrack:create_app()" create-user deine@email.de
    flask --app "fintrack:create_app()" set-password deine@email.de

Das Passwort wird verdeckt abgefragt und landet nie in der Shell-Historie.
"""

import click
from flask import current_app
from werkzeug.security import generate_password_hash

from fintrack.auth.routes import find_user_by_email, normalize_email
from fintrack.budget.service import create_default_categories
from fintrack.extensions import db
from fintrack.models import User


def _validated_password(password):
    min_length = current_app.config['PASSWORD_MIN_LENGTH']
    if len(password) < min_length:
        raise click.ClickException(f'Das Passwort muss mindestens {min_length} Zeichen lang sein.')
    return password


@click.command('create-user')
@click.argument('email')
@click.password_option('--password', prompt='Passwort', confirmation_prompt='Passwort wiederholen')
def create_user_command(email, password):
    """Legt ein bereits bestätigtes Konto inkl. Standardkategorien an."""
    email = normalize_email(email)
    if find_user_by_email(email):
        raise click.ClickException(f'Es gibt bereits ein Konto für {email}.')

    user = User(
        username=email.split('@')[0],
        email=email,
        password=generate_password_hash(_validated_password(password)),
        is_verified=True,
        verification_attempts=0
    )
    user.rotate_session_token()
    db.session.add(user)
    db.session.commit()
    create_default_categories(user.id)

    click.echo(f'Konto für {email} angelegt.')


@click.command('set-password')
@click.argument('email')
@click.password_option('--password', prompt='Neues Passwort', confirmation_prompt='Passwort wiederholen')
def set_password_command(email, password):
    """Setzt ein neues Passwort und meldet das Konto auf allen Geräten ab."""
    user = find_user_by_email(email)
    if not user:
        raise click.ClickException(f'Kein Konto für {normalize_email(email)} gefunden.')

    user.password = generate_password_hash(_validated_password(password))
    # Neues session_token: alle bestehenden Anmelde-Cookies werden ungültig
    user.rotate_session_token()
    db.session.commit()

    click.echo(f'Passwort für {user.email} geändert, alle Geräte wurden abgemeldet.')


def register_commands(app):
    app.cli.add_command(create_user_command)
    app.cli.add_command(set_password_command)
