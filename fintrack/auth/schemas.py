"""
auth/schemas.py - Eingabe-Schemas für Registrierung, Login,
E-Mail-Verifizierung und die Anlage-Einstellungen.
Die Mindestlänge des Passworts prüft die Route selbst, weil sie aus der
Konfiguration kommt.
"""

from typing import Optional

from pydantic import Field, field_validator

from fintrack.api import RequestModel


class Credentials(RequestModel):
    email: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=200)


class VerifyEmail(RequestModel):
    email: str = Field(min_length=1, max_length=254)
    code: str = Field(min_length=1, max_length=10)


class ResendVerification(RequestModel):
    email: str = Field(min_length=1, max_length=254)


class SettingsUpdate(RequestModel):
    """Alle Felder optional - leere Eingaben werden als "nicht angegeben" gespeichert."""
    risk_profile: Optional[str] = Field(default=None, max_length=50)
    investment_experience: Optional[str] = Field(default=None, max_length=50)
    monthly_budget: Optional[float] = Field(default=None, gt=0)
    investment_horizon: Optional[str] = Field(default=None, max_length=50)

    @field_validator('risk_profile', 'investment_experience', 'investment_horizon', 'monthly_budget', mode='before')
    @classmethod
    def empty_to_none(cls, value):
        return None if value == '' else value
