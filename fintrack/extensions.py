"""
extensions.py - Gemeinsam genutzte Objekte, die von mehreren Bereichen
der App gebraucht werden (Datenbank, OpenAI-Client). Liegen hier statt in
der App-Factory, damit Module sie importieren können, ohne die App selbst
zu importieren (vermeidet zirkuläre Importe).
"""

import os
from functools import lru_cache

from flask_sqlalchemy import SQLAlchemy
from openai import OpenAI

# SQLAlchemy Objekt - wird in create_app() mit der Flask App verbunden
db = SQLAlchemy()


@lru_cache(maxsize=1)
def get_openai_client():
    """
    Liefert den OpenAI-Client und legt ihn beim ersten Aufruf an.
    Erst bei Bedarf statt beim Import, damit z.B. Tests ohne
    OPENAI_API_KEY laufen können.
    """
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
