"""
imports/schemas.py - Eingaben für den Import von Kontoumsätzen.
"""

from datetime import date
from typing import Dict, List, Optional

from pydantic import Field, PositiveInt, field_validator

from fintrack.api import RequestModel
from fintrack.imports.bank_csv import FIELDS


class ColumnMapping(RequestModel):
    """Von Hand zugeordnete Spalten: Feld -> Spaltenindex (0 = erste Spalte)."""
    columns: Dict[str, int]

    @field_validator('columns')
    @classmethod
    def known_fields(cls, value):
        unknown = set(value) - set(FIELDS)
        if unknown:
            raise ValueError(f'Unbekannte Felder: {", ".join(sorted(unknown))}')
        if any(index < 0 for index in value.values()):
            raise ValueError('Spaltennummern beginnen bei 0')
        return value


class ImportRow(RequestModel):
    date: date
    amount: float
    counterparty: str = Field(default='', max_length=500)
    purpose: str = Field(default='', max_length=1000)
    occurrence: int = Field(default=0, ge=0, le=999)
    description: Optional[str] = Field(default=None, max_length=200)
    category_id: PositiveInt


    @field_validator('amount')
    @classmethod
    def not_zero(cls, value):
        if value == 0:
            raise ValueError('Ein Umsatz braucht einen Betrag')
        return value


class ImportCommit(RequestModel):
    rows: List[ImportRow] = Field(min_length=1, max_length=5000)
