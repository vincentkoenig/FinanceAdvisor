"""
imports/schemas.py - Eingaben für den Import von Kontoumsätzen.
"""

from datetime import date
from typing import Dict, List, Literal, Optional

from pydantic import Field, PositiveFloat, PositiveInt, field_validator, model_validator

from fintrack.api import RequestModel
from fintrack.imports.bank_csv import FIELDS
from fintrack.imports.crypto_csv import FIELDS as CRYPTO_FIELDS


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


class CryptoColumnMapping(RequestModel):
    """Zuordnung für Krypto-Exporte: Feld -> Spaltenindex."""
    columns: Dict[str, int]

    @field_validator('columns')
    @classmethod
    def known_fields(cls, value):
        unknown = set(value) - set(CRYPTO_FIELDS)
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


class RuleCreate(RequestModel):
    """Feste Zuordnung: Wort/Wortfolge im Empfänger oder Verwendungszweck -> Kategorie."""
    pattern: str = Field(min_length=2, max_length=100)
    income: bool
    category_id: PositiveInt

    @field_validator('pattern')
    @classmethod
    def normalized(cls, value):
        value = ' '.join(value.split()).lower()
        if len(value) < 2:
            raise ValueError('Mindestens zwei Zeichen')
        return value


class RuleBatch(RequestModel):
    rules: List[RuleCreate] = Field(min_length=1, max_length=2000)


class Payee(RequestModel):
    name: str = Field(min_length=1, max_length=200)
    income: bool


class CategorizeRequest(RequestModel):
    """Empfänger ohne Kategorie, je Name und Richtung einmal."""
    payees: List[Payee] = Field(min_length=1, max_length=1000)


class DepotTrade(RequestModel):
    """Eine bestätigte Ausführung aus der Vorschau; der Preis ist schon inklusive Gebühren je Stück."""
    type: Literal['buy', 'sell']
    symbol: str = Field(min_length=1, max_length=30, pattern=r'^[A-Za-z0-9.=^-]+$')
    name: str = Field(min_length=1, max_length=200)
    date: date
    quantity: PositiveFloat
    # Ein Verkauf kann nach Gebühren 0 € bringen (z.B. nach einer Insolvenz), ein Kauf nicht
    price: float = Field(ge=0)

    @model_validator(mode='after')
    def buy_costs_something(self):
        if self.type == 'buy' and self.price <= 0:
            raise ValueError('Ein Kauf braucht einen Preis über 0')
        return self


class DepotCommit(RequestModel):
    trades: List[DepotTrade] = Field(min_length=1, max_length=500)
