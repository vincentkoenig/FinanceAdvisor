"""
fintrack - Paket der FinTrack-Web-App.
create_app() baut die Flask-App zusammen: Konfiguration laden, Datenbank
verbinden und die Blueprints der einzelnen Bereiche registrieren.
"""

import os

import click
from flask import Flask, g
from werkzeug.middleware.proxy_fix import ProxyFix

# config zuerst importieren, damit load_dotenv() vor allen anderen Modulen läuft
from fintrack.config import get_config
from fintrack.extensions import db, limiter, login_manager, migrate

# migrations/, instance/ und frontend/ liegen im Projektordner, nicht im Paket
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def create_app(config_name=None, config_overrides=None):
    """
    Erstellt und konfiguriert die Flask-App.
    config_name='testing' nutzt eine In-Memory-Datenbank; ohne Angabe
    entscheidet die Umgebungsvariable TESTING (siehe config.get_config).
    config_overrides überschreibt einzelne Einstellungen, z.B. die
    Datenbank-URL in Tests.
    Der Scheduler wird hier bewusst nicht gestartet - das macht app.py,
    damit Tests und Hilfsskripte keine Hintergrundjobs auslösen.
    Tabellen werden ebenfalls nicht angelegt: Das Schema verwaltet
    ausschließlich Alembic über "flask upgrade-db".
    """
    # Kein static-Ordner: alle Dateien der Oberfläche liefert spa.py aus frontend/dist
    app = Flask(
        __name__,
        static_folder=None,
        instance_path=os.path.join(PROJECT_ROOT, 'instance'),
    )
    app.config.from_object(get_config(config_name))
    # Gebautes React-Frontend (npm run build in frontend/), ausgeliefert unter /app
    app.config['FRONTEND_DIST'] = os.path.join(PROJECT_ROOT, 'frontend', 'dist')
    app.config.update(config_overrides or {})

    # Hinter dem Proxy (Traefik): echte Client-IP und HTTPS aus den
    # X-Forwarded-Headern übernehmen (genau ein Proxy davor)
    if app.config.get('TRUST_PROXY'):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

    # SQLAlchemy, Alembic, Anmeldung und Begrenzung mit der App verbinden
    db.init_app(app)
    migrate.init_app(app, db, directory=os.path.join(PROJECT_ROOT, 'migrations'))
    login_manager.init_app(app)
    limiter.init_app(app)

    from fintrack.auth.session import reject_cross_site_requests

    @app.before_request
    def load_user_fresh_per_request():
        """
        Flask-Login merkt sich den angemeldeten Nutzer in g. Normalerweise
        hat jeder Request ein eigenes g - läuft aber ein App-Kontext über
        mehrere Requests weiter (z.B. in Tests), würde sonst ein alter
        Nutzer weiterverwendet, obwohl sein Cookie längst ungültig ist.
        """
        g.pop('_login_user', None)

    app.before_request(reject_cross_site_requests)

    # Einheitliche JSON-Fehler für die API (Validierung, 404, 429, 500 ...)
    from fintrack.api import API_PREFIX, register_error_handlers
    register_error_handlers(app)

    from fintrack.auth.cli import register_commands
    register_commands(app)

    @app.cli.command('upgrade-db')
    def upgrade_db_command():
        """Datenbank per Migration auf den neuesten Stand bringen."""
        from fintrack.database import upgrade_database
        action = upgrade_database()
        messages = {
            'created': 'Neue Datenbank angelegt.',
            'adopted': 'Bestehende Datenbank übernommen und auf den neuesten Stand gebracht.',
            'upgraded': 'Datenbank ist auf dem neuesten Stand.',
        }
        click.echo(messages[action])

    from fintrack import health, spa
    from fintrack.account import routes as account_routes
    from fintrack.admin import routes as admin_routes
    from fintrack.auth import routes as auth_routes
    from fintrack.budget import routes as budget_routes
    from fintrack.chat import routes as chat_routes
    from fintrack.contracts import routes as contract_routes
    from fintrack.insights import routes as insights_routes
    from fintrack.portfolio import analysis, routes as portfolio_routes

    # Das React-Frontend liegt unter /app (/ leitet dorthin), die JSON-API unter /api/v1.
    # Jeder Blueprint schützt sich selbst: Bereiche mit Nutzerdaten über
    # protect_blueprint() (nur mit Anmeldung, Daten immer von current_user),
    # Auth über login_required_api an den /me-Routen, Admin über den X-Admin-Key.
    # Das Frontend selbst enthält keine Nutzerdaten und prüft die Anmeldung über /api/v1/me.
    app.register_blueprint(health.bp)
    app.register_blueprint(spa.bp)
    for blueprint in (auth_routes.bp, portfolio_routes.bp, analysis.bp, budget_routes.bp,
                      chat_routes.bp, contract_routes.bp, insights_routes.bp, account_routes.bp):
        app.register_blueprint(blueprint, url_prefix=API_PREFIX)
    app.register_blueprint(admin_routes.bp, url_prefix=f'{API_PREFIX}/admin')

    return app
