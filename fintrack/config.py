"""
config.py - Zentrale Konfiguration der App.
Liest alle Einstellungen aus Umgebungsvariablen bzw. der .env-Datei,
damit der restliche Code nicht selbst os.getenv() für Grundeinstellungen
aufrufen muss.
"""

import os
import secrets
from datetime import timedelta

from dotenv import load_dotenv

# .env Datei laden - muss vor jedem os.getenv() stehen!
load_dotenv()


def is_production():
    """
    Läuft die App in Produktion? Render setzt automatisch RENDER=true,
    alternativ lässt sich APP_ENV=production setzen.
    """
    return os.getenv('RENDER') == 'true' or os.getenv('APP_ENV') == 'production'


def normalize_database_url(url):
    """
    Bringt eine Postgres-URL in das Format, das zu unserem installierten
    Treiber passt. Anbieter liefern unterschiedliche Schreibweisen
    ('postgres://...', 'postgresql://...' oder 'postgresql+psycopg://...').
    Ohne ausdrücklichen Treiber wählt SQLAlchemy selbst einen aus - seit
    Version 2.1 psycopg 3 statt psycopg2. Deshalb wird der Treiber hier
    fest auf psycopg2 gesetzt. Andere URLs (z.B. SQLite) bleiben unverändert.
    """
    scheme, separator, rest = url.partition('://')
    if scheme in ('postgres', 'postgresql') or scheme.startswith('postgresql+'):
        return f'postgresql+psycopg2://{rest}'
    return url


class Config:
    """
    Standardkonfiguration: Postgres in Produktion (über DATABASE_URL),
    ansonsten lokal automatisch SQLite im instance/-Ordner.
    """
    TESTING = False

    # Neon pausiert die Datenbank nach einigen Minuten ohne Zugriff und
    # trennt dabei offene Verbindungen. pool_pre_ping prüft jede Verbindung
    # kurz vor der Nutzung und baut bei Bedarf eine neue auf, statt mit
    # "SSL connection has been closed unexpectedly" abzubrechen.
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True}

    # ─── Anmeldung (Session-Cookie) ───
    # HttpOnly: Cookie ist für JavaScript unsichtbar (schützt bei XSS)
    # SameSite=Lax: Browser schickt das Cookie nicht bei Formular-Posts
    # von fremden Seiten mit (Schutz gegen CSRF)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_DURATION = timedelta(days=30)
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)

    # Mindestlänge für neue Passwörter
    PASSWORD_MIN_LENGTH = 10

    # Begrenzung der Anfragen (Flask-Limiter) - Speicher im Prozess reicht,
    # da die App mit genau einem Gunicorn-Worker läuft
    RATELIMIT_STORAGE_URI = 'memory://'
    RATELIMIT_HEADERS_ENABLED = True

    def __init__(self):
        database_url = os.getenv('DATABASE_URL')
        if database_url:
            self.SQLALCHEMY_DATABASE_URI = normalize_database_url(database_url)
        else:
            self.SQLALCHEMY_DATABASE_URI = 'sqlite:///finance_advisor.db'

        # Neue Konten nur, wenn ausdrücklich erlaubt - vorerst nutzt nur
        # der Betreiber selbst die App (siehe README)
        self.ALLOW_REGISTRATION = os.getenv('ALLOW_REGISTRATION') == '1'

        production = is_production()
        # Cookies nur über HTTPS schicken - lokal läuft die App über http
        self.SESSION_COOKIE_SECURE = production
        self.REMEMBER_COOKIE_SECURE = production
        # Hinter dem Render-Proxy kommt die echte Client-IP im Header
        # X-Forwarded-For an - wichtig für die Begrenzung pro IP
        self.TRUST_PROXY = production

        # SECRET_KEY signiert die Session-Cookies. In Produktion ist er
        # Pflicht: Ohne festen Schlüssel könnte sich jeder Neustart oder
        # ein erratbarer Wert auf die Anmeldung auswirken.
        secret_key = os.getenv('SECRET_KEY')
        if not secret_key:
            if production:
                raise RuntimeError(
                    'SECRET_KEY ist nicht gesetzt. In Produktion muss ein langer, '
                    'zufälliger Wert als Umgebungsvariable hinterlegt sein.')
            # Lokal: zufälliger Schlüssel pro Start - Anmeldungen gelten
            # dann nur bis zum Neustart des Servers
            secret_key = secrets.token_hex(32)
        self.SECRET_KEY = secret_key


class TestConfig(Config):
    """
    Tests laufen immer gegen eine isolierte In-Memory-Datenbank,
    niemals gegen die echte lokale oder Produktions-Datenbank.
    """
    TESTING = True

    def __init__(self):
        self.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
        self.SECRET_KEY = 'test-secret-key'
        self.ALLOW_REGISTRATION = True
        self.SESSION_COOKIE_SECURE = False
        self.REMEMBER_COOKIE_SECURE = False
        self.TRUST_PROXY = False
        # Begrenzung in Tests aus - einzelne Tests schalten sie gezielt ein
        self.RATELIMIT_ENABLED = False


def get_config(name=None):
    """
    Wählt die passende Konfiguration. Ohne Namen entscheidet die
    Umgebungsvariable TESTING=1 über die Testkonfiguration.
    """
    if name is None:
        name = 'testing' if os.getenv('TESTING') == '1' else 'default'
    return TestConfig() if name == 'testing' else Config()
