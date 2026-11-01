"""
account/schemas.py - Format der Export-Datei ("fintrack-export", Version 1).

Die Datei ist bewusst unabhängig von der Datenbank: Statt Datenbank-IDs
verweisen Einträge über "ref" aufeinander (z.B. eine Buchung über
category_ref auf ihre Kategorie). Assets werden über ihr Symbol
zugeordnet, Kurshistorien sind nicht enthalten - die lädt die App selbst.
Damit lässt sich ein Export in jede andere FinTrack-Datenbank einspielen.

Beim Import prüft dasselbe Schema die Datei, bevor irgendetwas
gespeichert wird.
"""

from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, NonNegativeFloat, PositiveInt, model_validator

EXPORT_FORMAT = 'fintrack-export'
EXPORT_VERSION = 1


class _Entry(BaseModel):
    # Unbekannte Felder ignorieren: spätere Versionen dürfen Felder ergänzen
    model_config = ConfigDict(extra='ignore')


class ExportProfile(_Entry):
    risk_profile: Optional[str] = None
    investment_experience: Optional[str] = None
    monthly_budget: Optional[float] = None
    investment_horizon: Optional[str] = None


class ExportCategory(_Entry):
    ref: PositiveInt
    name: str = Field(min_length=1, max_length=60)
    type: Literal['income', 'fixed_expense', 'variable_expense']
    parent_ref: Optional[PositiveInt] = None


class ExportTransaction(_Entry):
    ref: PositiveInt
    category_ref: PositiveInt
    amount: float = Field(gt=0)
    description: Optional[str] = None
    date: datetime
    is_recurring: bool = False
    end_date: Optional[datetime] = None
    is_paused: bool = False
    paused_at: Optional[datetime] = None
    import_hash: Optional[str] = Field(default=None, max_length=40)


class ExportAsset(_Entry):
    ref: PositiveInt
    symbol: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1)
    asset_type: Optional[str] = None
    currency: Optional[str] = None


class ExportPosition(_Entry):
    asset_ref: PositiveInt
    quantity: NonNegativeFloat
    avg_buy_price: NonNegativeFloat
    bought_at: Optional[datetime] = None
    status: Optional[str] = None


class ExportAssetTransaction(_Entry):
    asset_ref: PositiveInt
    type: Literal['buy', 'sell']
    quantity: float = Field(gt=0)
    price: NonNegativeFloat
    date: Optional[datetime] = None


class ExportSavingsPlan(_Entry):
    asset_ref: PositiveInt
    amount: float = Field(gt=0)
    day_of_month: int = Field(ge=1, le=31)
    start_date: Optional[datetime] = None
    last_executed: Optional[datetime] = None
    active: bool = True


class ExportWatchlistItem(_Entry):
    asset_ref: PositiveInt
    price_added: Optional[float] = None
    added_at: Optional[datetime] = None


class ExportDividend(_Entry):
    asset_ref: PositiveInt
    ex_dividend_date: datetime
    amount_per_share: float
    shares_held: float
    total_amount: float
    transaction_ref: Optional[PositiveInt] = None
    booked_at: Optional[datetime] = None


class ExportChatMessage(_Entry):
    role: Literal['user', 'assistant']
    message: str
    created_at: Optional[datetime] = None


class ExportAnalysis(_Entry):
    total_value: Optional[float] = None
    risk_assessment: Optional[str] = None
    diversification_score: Optional[int] = None
    summary: Optional[str] = None
    recommendations: List[str] = []
    allocation: list = []
    created_at: Optional[datetime] = None


class ExportInsight(_Entry):
    content: str
    created_at: Optional[datetime] = None


class ExportContract(_Entry):
    name: str = Field(min_length=1, max_length=80)
    provider: Optional[str] = None
    category: Literal['insurance', 'energy', 'telecom', 'subscription', 'fitness', 'loan', 'other']
    contract_number: Optional[str] = None
    amount: float = Field(gt=0)
    interval: Literal['monthly', 'quarterly', 'half_yearly', 'yearly']
    start_date: date
    min_term_months: Optional[PositiveInt] = None
    renewal_months: Optional[PositiveInt] = None
    notice_value: int = Field(ge=0)
    notice_unit: Literal['days', 'weeks', 'months']
    cancelled_at: Optional[date] = None
    end_date: Optional[date] = None
    notes: Optional[str] = None
    transaction_ref: Optional[PositiveInt] = None
    created_at: Optional[datetime] = None


class ExportFile(_Entry):
    format: Literal['fintrack-export']
    version: Literal[1]
    exported_at: Optional[datetime] = None
    profile: ExportProfile = ExportProfile()
    categories: List[ExportCategory] = []
    transactions: List[ExportTransaction] = []
    assets: List[ExportAsset] = []
    positions: List[ExportPosition] = []
    asset_transactions: List[ExportAssetTransaction] = []
    savings_plans: List[ExportSavingsPlan] = []
    watchlist: List[ExportWatchlistItem] = []
    dividends: List[ExportDividend] = []
    chat_history: List[ExportChatMessage] = []
    analyses: List[ExportAnalysis] = []
    insights: List[ExportInsight] = []
    # Seit Verträge dazukamen; ältere Dateien haben den Abschnitt nicht
    contracts: List[ExportContract] = []

    @model_validator(mode='after')
    def references_exist(self):
        """Jeder Verweis muss auf einen Eintrag in derselben Datei zeigen."""
        def refs(items):
            seen = [item.ref for item in items]
            if len(seen) != len(set(seen)):
                raise ValueError('Doppelte ref-Werte in der Datei')
            return set(seen)

        category_refs = refs(self.categories)
        transaction_refs = refs(self.transactions)
        asset_refs = refs(self.assets)

        main_category_refs = {c.ref for c in self.categories if c.parent_ref is None}
        for category in self.categories:
            if category.parent_ref is not None and category.parent_ref not in main_category_refs:
                raise ValueError(f'Kategorie "{category.name}" verweist auf keine gültige Hauptkategorie')
        for transaction in self.transactions:
            if transaction.category_ref not in category_refs:
                raise ValueError('Eine Buchung verweist auf eine unbekannte Kategorie')
        for name, items in (('Position', self.positions), ('Kauf/Verkauf', self.asset_transactions),
                            ('Sparplan', self.savings_plans), ('Watchlist-Eintrag', self.watchlist),
                            ('Dividende', self.dividends)):
            for item in items:
                if item.asset_ref not in asset_refs:
                    raise ValueError(f'{name} verweist auf ein unbekanntes Asset')
        for dividend in self.dividends:
            if dividend.transaction_ref is not None and dividend.transaction_ref not in transaction_refs:
                raise ValueError('Eine Dividende verweist auf eine unbekannte Buchung')
        for contract in self.contracts:
            if contract.transaction_ref is not None and contract.transaction_ref not in transaction_refs:
                raise ValueError(f'Vertrag "{contract.name}" verweist auf eine unbekannte Buchung')

        # Pro Asset gibt es nur eine Position und einen Watchlist-Eintrag
        # (ältere Exporte von vor dieser Regel könnten Doppelte enthalten)
        for name, items in (('Position', self.positions), ('Watchlist-Eintrag', self.watchlist)):
            asset_refs_used = [item.asset_ref for item in items]
            if len(asset_refs_used) != len(set(asset_refs_used)):
                raise ValueError(f'Doppelter {name} für dasselbe Asset in der Datei')
        symbols = [asset.symbol for asset in self.assets]
        if len(symbols) != len(set(symbols)):
            raise ValueError('Ein Asset-Symbol kommt in der Datei mehrfach vor')
        return self
