"""
fintrack - Paket der FinTrack-Web-App.
create_app() baut die Flask-App zusammen: Konfiguration laden, Datenbank
verbinden und die Blueprints der einzelnen Bereiche registrieren.
"""

import os

import click
from flask import Flask

# config zuerst importieren, damit load_dotenv() vor allen anderen Modulen läuft
from fintrack.config import get_config
from fintrack.extensions import db, migrate

# templates/, static/ und migrations/ liegen im Projektordner, nicht im Paket
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
    app = Flask(
        __name__,
        template_folder=os.path.join(PROJECT_ROOT, 'templates'),
        static_folder=os.path.join(PROJECT_ROOT, 'static'),
        instance_path=os.path.join(PROJECT_ROOT, 'instance'),
    )
    app.config.from_object(get_config(config_name))
    app.config.update(config_overrides or {})

    # SQLAlchemy und Alembic mit der Flask App verbinden
    db.init_app(app)
    migrate.init_app(app, db, directory=os.path.join(PROJECT_ROOT, 'migrations'))

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

    from fintrack import pages
    from fintrack.admin import routes as admin_routes
    from fintrack.auth import routes as auth_routes
    from fintrack.budget import routes as budget_routes
    from fintrack.chat import routes as chat_routes
    from fintrack.insights import routes as insights_routes
    from fintrack.portfolio import analysis, routes as portfolio_routes

    for blueprint in (pages.bp, auth_routes.bp, portfolio_routes.bp, analysis.bp,
                      budget_routes.bp, chat_routes.bp, insights_routes.bp, admin_routes.bp):
        app.register_blueprint(blueprint)

    return app
