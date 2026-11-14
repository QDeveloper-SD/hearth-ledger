from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator
from ulid import ULID

_DEFAULT_USERNAME = "admin"


def new_id() -> str:
    return str(ULID())


class AuthDoc(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = _DEFAULT_USERNAME
    # None until the first-run setup screen creates the household login.
    password_hash: Optional[str] = None


class SettingsDoc(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data_dir: Optional[str] = None
    live_sync: bool = True
    theme: str = "light"
    public_api_key_enc: Optional[str] = None
    # Interactive Brokers Flex Web Service (report-only access; cannot trade)
    ibkr_flex_token_enc: Optional[str] = None
    ibkr_flex_query_id: Optional[str] = None


class LedgerEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=new_id)
    date: str
    desc: str
    category: str
    amount: float


class DebtAccount(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=new_id)
    name: str
    balance: float
    rate: float
    min_payment: float


class IncomeSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=new_id)
    name: str
    amount: float
    cadence: str


class ManualHolding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=new_id)
    symbol: str
    qty: float
    cost_basis: float  # TOTAL value paid for the position (not per share)
    current_value: Optional[float] = None
    account: Literal["manual", "ibkr", "other"] = "manual"
    broker: Optional[str] = None


def _check_date(v: Optional[str]) -> Optional[str]:
    if v in (None, ""):
        return None
    date.fromisoformat(v)  # raises ValueError -> 422
    return v


class RealEstate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=new_id)
    name: str = Field(min_length=1)
    address: Optional[str] = None
    current_value: float = Field(ge=0)
    purchase_price: Optional[float] = Field(default=None, ge=0)
    notes: Optional[str] = None


class Business(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=new_id)
    name: str = Field(min_length=1)
    valuation: float = Field(ge=0)
    ownership_pct: float = Field(default=100.0, ge=0, le=100)
    notes: Optional[str] = None


class FixedIncome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=new_id)
    name: str = Field(min_length=1)
    issuer: Optional[str] = None
    face_value: float = Field(ge=0)
    coupon_rate: Optional[float] = Field(default=None, ge=0)
    maturity_date: Optional[str] = None
    current_value: Optional[float] = Field(default=None, ge=0)

    @field_validator("maturity_date")
    @classmethod
    def _valid_date(cls, v: Optional[str]) -> Optional[str]:
        return _check_date(v)


class CashAccount(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=new_id)
    name: str
    balance: float


class PublicCache(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fetched_at: Optional[str] = None
    account_value: float = 0.0
    holdings: list[dict] = Field(default_factory=list)


class IbkrCache(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fetched_at: Optional[str] = None
    account_ids: list[str] = Field(default_factory=list)
    account_value: float = 0.0
    cash: Optional[float] = None
    holdings: list[dict] = Field(default_factory=list)


class PortfolioSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str
    value: float


class PortfolioDoc(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manual_holdings: list[ManualHolding] = Field(default_factory=list)
    cash_accounts: list[CashAccount] = Field(default_factory=list)
    real_estate: list[RealEstate] = Field(default_factory=list)
    businesses: list[Business] = Field(default_factory=list)
    fixed_income: list[FixedIncome] = Field(default_factory=list)
    public_cache: PublicCache = Field(default_factory=PublicCache)
    ibkr_cache: IbkrCache = Field(default_factory=IbkrCache)
    history: list[PortfolioSnapshot] = Field(default_factory=list)


class PlanningEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=new_id)
    title: str
    date: str
    amount: Optional[float] = None
    notes: Optional[str] = None


class PlanningDoc(BaseModel):
    model_config = ConfigDict(extra="forbid")

    events: list[PlanningEvent] = Field(default_factory=list)
    scenarios: list[dict] = Field(default_factory=list)


DEFAULT_INSURANCE = [
    {"name": "Health", "covered": False},
    {"name": "Auto",   "covered": False},
    {"name": "Home",   "covered": False},
    {"name": "Life",   "covered": False},
]


class InsurancePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    covered: bool


class HearthDoc(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = 1
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"))
    auth: AuthDoc = Field(default_factory=AuthDoc)
    settings: SettingsDoc = Field(default_factory=SettingsDoc)
    ledger: list[LedgerEntry] = Field(default_factory=list)
    debts: list[DebtAccount] = Field(default_factory=list)
    income_sources: list[IncomeSource] = Field(default_factory=list)
    portfolio: PortfolioDoc = Field(default_factory=PortfolioDoc)
    planning: PlanningDoc = Field(default_factory=PlanningDoc)
    insurance: list[InsurancePolicy] = Field(
        default_factory=lambda: [InsurancePolicy(**p) for p in DEFAULT_INSURANCE]
    )
