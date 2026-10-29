"""
budget/schemas.py - Eingabe-Schemas für Kategorien und Buchungen im
Haushaltsbuch.
"""

from datetime import date
from typing import Literal, Optional

from pydantic import Field, PositiveFloat, PositiveInt, field_validator, model_validator

from fintrack.api import RequestModel

CategoryType = Literal['income', 'fixed_expense', 'variable_expense']


class CategoryCreate(RequestModel):
    name: str = Field(min_length=1, max_length=60)
    type: CategoryType
    # Leer = Hauptkategorie, sonst ID der eigenen Hauptkategorie
    parent_id: Optional[PositiveInt] = None


class TransactionCreate(RequestModel):
    category_id: PositiveInt
    amount: PositiveFloat
    description: Optional[str] = Field(default=None, max_length=200)
    date: date
    is_recurring: bool = False
    end_date: Optional[date] = None

    @field_validator('description')
    @classmethod
    def empty_to_none(cls, value):
        return value or None

    @model_validator(mode='after')
    def end_after_start(self):
        if self.end_date and self.end_date < self.date:
            raise ValueError('Das Enddatum darf nicht vor dem Startdatum liegen')
        return self


class MonthQuery(RequestModel):
    # Optionaler Monatsfilter im Format JJJJ-MM, z.B. 2026-10
    month: Optional[str] = Field(default=None, pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
