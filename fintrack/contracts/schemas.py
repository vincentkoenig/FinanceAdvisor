"""
contracts/schemas.py - Eingabe-Schemas für Verträge.
"""

from datetime import date
from typing import Literal, Optional

from pydantic import Field, PositiveFloat, PositiveInt, field_validator, model_validator

from fintrack.api import RequestModel

ContractCategory = Literal['insurance', 'energy', 'telecom', 'subscription', 'fitness', 'loan', 'other']
PaymentInterval = Literal['monthly', 'quarterly', 'half_yearly', 'yearly']
NoticeUnit = Literal['days', 'weeks', 'months']


class ContractInput(RequestModel):
    """Anlegen und Bearbeiten - beim Bearbeiten wird immer der ganze Vertrag geschickt."""
    name: str = Field(min_length=1, max_length=80)
    provider: Optional[str] = Field(default=None, max_length=80)
    category: ContractCategory
    contract_number: Optional[str] = Field(default=None, max_length=60)
    amount: PositiveFloat
    interval: PaymentInterval
    start_date: date
    # Leer = erste Laufzeit so lang wie eine Verlängerung
    min_term_months: Optional[int] = Field(default=None, ge=1, le=120)
    # Leer = keine Verlängerung, der Vertrag endet nach der ersten Laufzeit
    renewal_months: Optional[int] = Field(default=12, ge=1, le=120)
    notice_value: int = Field(default=3, ge=0, le=365)
    notice_unit: NoticeUnit = 'months'
    notes: Optional[str] = Field(default=None, max_length=1000)

    @field_validator('provider', 'contract_number', 'notes')
    @classmethod
    def empty_to_none(cls, value):
        return value or None

    @model_validator(mode='after')
    def has_a_term(self):
        if not self.min_term_months and not self.renewal_months:
            raise ValueError('Mindestlaufzeit oder Verlängerung angeben')
        return self


class ContractBooking(RequestModel):
    """Entweder eine neue Buchung in dieser Fixkosten-Kategorie oder eine vorhandene wiederkehrende Buchung."""
    category_id: Optional[PositiveInt] = None
    transaction_id: Optional[PositiveInt] = None

    @model_validator(mode='after')
    def exactly_one(self):
        if (self.category_id is None) == (self.transaction_id is None):
            raise ValueError('Entweder eine Kategorie für eine neue Buchung oder eine vorhandene Buchung angeben')
        return self


class ContractCancel(RequestModel):
    # Leer = zum nächstmöglichen Laufzeitende
    end_date: Optional[date] = None
