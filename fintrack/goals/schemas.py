"""goals/schemas.py - Eingabe-Schemas für Sparziele."""

from datetime import date
from typing import Optional

from pydantic import Field, PositiveFloat, field_validator

from fintrack.api import RequestModel


class GoalInput(RequestModel):
    name: str = Field(min_length=1, max_length=100)
    target_amount: PositiveFloat = Field(le=10_000_000)
    target_date: Optional[date] = None
    # Feste monatliche Rate, die automatisch in den Topf kommt (leer = keine)
    monthly_amount: Optional[float] = Field(default=None, ge=0, le=1_000_000)
    # Nur beim Anlegen: was schon zurückgelegt ist
    start_amount: Optional[float] = Field(default=None, ge=0, le=10_000_000)

    @field_validator('target_date', 'monthly_amount', 'start_amount', mode='before')
    @classmethod
    def empty_to_none(cls, value):
        return None if value == '' else value


class EntryInput(RequestModel):
    """Einzahlung (positiv) oder Entnahme (negativ)."""
    amount: float = Field(ge=-10_000_000, le=10_000_000)
    note: Optional[str] = Field(default=None, max_length=200)

    @field_validator('amount')
    @classmethod
    def not_zero(cls, value):
        if value == 0:
            raise ValueError('Bitte einen Betrag eingeben')
        return value
