"""
config.py - Zentrale Konfiguration der App.
Liest alle Einstellungen aus Umgebungsvariablen bzw. der .env-Datei,
damit der restliche Code nicht selbst os.getenv() für Grundeinstellungen
aufrufen muss.
"""

import os

from dotenv import load_dotenv

# .env Datei laden - muss vor jedem os.getenv() stehen!
load_dotenv()


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

    def __init__(self):
        database_url = os.getenv('DATABASE_URL')
        if database_url:
            self.SQLALCHEMY_DATABASE_URI = normalize_database_url(database_url)
        else:
            self.SQLALCHEMY_DATABASE_URI = 'sqlite:///finance_advisor.db'


class TestConfig(Config):
    """
    Tests laufen immer gegen eine isolierte In-Memory-Datenbank,
    niemals gegen die echte lokale oder Produktions-Datenbank.
    """
    TESTING = True

    def __init__(self):
        self.SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


def get_config(name=None):
    """
    Wählt die passende Konfiguration. Ohne Namen entscheidet die
    Umgebungsvariable TESTING=1 über die Testkonfiguration.
    """
    if name is None:
        name = 'testing' if os.getenv('TESTING') == '1' else 'default'
    return TestConfig() if name == 'testing' else Config()
