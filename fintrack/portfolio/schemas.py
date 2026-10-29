"""
portfolio/schemas.py - Eingabe-Schemas für Positionen, Käufe/Verkäufe,
Watchlist, Sparpläne und die Asset-Suche.
"""

from datetime import date
from typing import Optional

from pydantic import Field, PositiveFloat, PositiveInt, field_validator

from fintrack.api import RequestModel


class AssetSearchQuery(RequestModel):
    query: str = Field(min_length=1, max_length=100)


class PositionCreate(RequestModel):
    """Erster Kauf eines Assets (oder weiterer Kauf, falls schon im Depot)."""
    asset_id: PositiveInt
    quantity: PositiveFloat
    avg_buy_price: PositiveFloat
    bought_at: date

    @field_validator('bought_at')
    @classmethod
    def not_in_future(cls, value):
        if value > date.today():
            raise ValueError('Das Kaufdatum darf nicht in der Zukunft liegen')
        return value


class BuyTrade(RequestModel):
    quantity: PositiveFloat
    price: PositiveFloat


class SellTrade(RequestModel):
    quantity: PositiveFloat
    # Optional: ohne Verkaufspreis wird der Durchschnittskaufpreis verbucht
    price: Optional[PositiveFloat] = None


class WatchlistAdd(RequestModel):
    asset_id: PositiveInt


class SavingsPlanCreate(RequestModel):
    asset_id: PositiveInt
    amount: PositiveFloat
    # Bis 28, damit der Termin in jedem Monat existiert
    day_of_month: int = Field(ge=1, le=28)
