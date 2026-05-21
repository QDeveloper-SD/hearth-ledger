from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from argon2 import PasswordHasher
from pydantic import BaseModel, ConfigDict, Field
from ulid import ULID

_DEFAULT_USERNAME = "admin"
_DEFAULT_PASSWORD = "password"


def new_id() -> str:
    return str(ULID())


def _default_password_hash() -> str:
    return PasswordHasher().hash(_DEFAULT_PASSWORD)


class AuthDoc(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = _DEFAULT_USERNAME
    password_hash: Optional[str] = Field(default_factory=_default_password_hash)


class SettingsDoc(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data_dir: Optional[str] = None
    live_sync: bool = True
    theme: str = "light"
    public_api_key_enc: Optional[str] = None


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
    cost_basis: float


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


class PortfolioDoc(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manual_holdings: list[ManualHolding] = Field(default_factory=list)
    cash_accounts: list[CashAccount] = Field(default_factory=list)
    public_cache: PublicCache = Field(default_factory=PublicCache)


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
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
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
