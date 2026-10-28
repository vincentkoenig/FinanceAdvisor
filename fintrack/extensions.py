"""
extensions.py - Gemeinsam genutzte Objekte, die von mehreren Bereichen
der App gebraucht werden (Datenbank, Migrationen, OpenAI-Client). Liegen
hier statt in der App-Factory, damit Module sie importieren können, ohne
die App selbst zu importieren (vermeidet zirkuläre Importe).
"""

import os
from functools import lru_cache

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from openai import OpenAI
from sqlalchemy import MetaData

# Feste Namensregeln für Constraints und Indizes. Die Muster entsprechen
# den Standardnamen von PostgreSQL (z.B. "user_asset_user_id_fkey"), damit
# die Namen in Migrationen mit der bestehenden Produktionsdatenbank
# übereinstimmen und spätere Migrationen Constraints gezielt ändern können.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "%(table_name)s_%(column_0_name)s_key",
    "ck": "%(table_name)s_%(constraint_name)s_check",
    "fk": "%(table_name)s_%(column_0_name)s_fkey",
    "pk": "%(table_name)s_pkey",
}

# SQLAlchemy Objekt - wird in create_app() mit der Flask App verbunden
db = SQLAlchemy(metadata=MetaData(naming_convention=NAMING_CONVENTION))

# Datenbank-Migrationen (Alembic). render_as_batch ist nötig, damit
# Spaltenänderungen auch in der lokalen SQLite-Datenbank funktionieren.
migrate = Migrate(render_as_batch=True)

# Anmeldung über ein signiertes Session-Cookie (Flask-Login)
login_manager = LoginManager()

# Begrenzung der Anfragen pro IP-Adresse, z.B. gegen das Durchprobieren
# von Passwörtern oder Verifizierungscodes. Grenzen werden direkt an den
# jeweiligen Routen gesetzt, es gibt kein globales Limit.
limiter = Limiter(key_func=get_remote_address)


@lru_cache(maxsize=1)
def get_openai_client():
    """
    Liefert den OpenAI-Client und legt ihn beim ersten Aufruf an.
    Erst bei Bedarf statt beim Import, damit z.B. Tests ohne
    OPENAI_API_KEY laufen können.
    """
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
