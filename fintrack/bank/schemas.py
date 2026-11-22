"""bank/schemas.py - Eingabe-Schemas für den Bankabruf."""

from typing import List, Optional

from pydantic import Field, PositiveInt

from fintrack.api import RequestModel


class ConnectRequest(RequestModel):
    aspsp_name: str = Field(min_length=1, max_length=200)
    country: str = Field(default='DE', min_length=2, max_length=2, pattern=r'^[A-Z]{2}$')


class AccountUpdate(RequestModel):
    enabled: bool


class ReviewBooking(RequestModel):
    id: PositiveInt
    category_id: PositiveInt
    description: Optional[str] = Field(default=None, max_length=200)


class ReviewCommit(RequestModel):
    book: List[ReviewBooking] = Field(default_factory=list, max_length=5000)
    dismiss: List[PositiveInt] = Field(default_factory=list, max_length=5000)
