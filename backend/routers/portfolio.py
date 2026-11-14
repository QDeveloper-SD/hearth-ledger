import copy
import logging
from datetime import date, datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator

from backend.integrations.ibkr_flex import IbkrFlexClient, IbkrFlexError, normalize_statement
from backend.integrations.public_api import PublicApiClient, PublicApiError, normalize_portfolio
from backend.routers.deps import SessionUser, Storedep
from backend.services.metrics import (
    asset_values,
    brokerage_positions,
    investable_value,
    portfolio_risk_stats,
)
from backend.storage.schema import (
    Business,
    CashAccount,
    FixedIncome,
    ManualHolding,
    RealEstate,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


class HoldingIn(BaseModel):
    symbol: str
    qty: float
    cost_basis: float
    current_value: float | None = Field(default=None, ge=0)
    account: Literal["manual", "ibkr", "other"] = "manual"
    broker: str | None = None

    @model_validator(mode="after")
    def _broker_for_other(self) -> "HoldingIn":
        if self.broker is not None:
            self.broker = self.broker.strip() or None
        if self.account == "other" and not self.broker:
            raise ValueError("broker is required for positions at other brokers")
        return self


class CashAccountIn(BaseModel):
    name: str
    balance: float


HISTORY_CAP = 1825


def record_snapshot(doc: dict, today: date | None = None) -> bool:
    """Upsert today's value point in doc['portfolio']['history']. Returns True if doc changed."""
    # Investable value only: real estate / business revaluations would look like market returns.
    total = round(investable_value(asset_values(doc)), 2)
    if total == 0:
        return False
    day = (today or date.today()).isoformat()
    history = doc["portfolio"].setdefault("history", [])
    if history and history[-1].get("date") == day:
        if history[-1].get("value") == total:
            return False
        history[-1]["value"] = total
        return True
    existing = next((pt for pt in history if pt.get("date") == day), None)
    if existing is not None:
        if existing.get("value") == total:
            return False
        existing["value"] = total
        return True
    history.append({"date": day, "value": total})
    history.sort(key=lambda pt: pt["date"])
    if len(history) > HISTORY_CAP:
        del history[: len(history) - HISTORY_CAP]
    return True


def _build_portfolio_response(doc: dict) -> dict:
    portfolio = doc.get("portfolio", {})
    public_cache = portfolio.get("public_cache", {})
    public_holdings = public_cache.get("holdings", [])
    secret = (doc.get("settings") or {}).get("public_api_key_enc")

    holdings = [
        {
            "symbol": h.get("symbol", ""),
            "name": h.get("name"),
            "qty": h.get("qty") or 0.0,
            "price": h.get("price"),
            "day_change": h.get("day_change"),
            "current_value": h.get("current_value") or h.get("cost_basis_total"),
        }
        for h in public_holdings
    ]
    allocation = [p for p in brokerage_positions(doc) if p["value"]]

    settings = doc.get("settings") or {}
    ibkr_cache = portfolio.get("ibkr_cache") or {}
    ibkr = {
        "configured": bool(settings.get("ibkr_flex_token_enc") and settings.get("ibkr_flex_query_id")),
        "fetched_at": ibkr_cache.get("fetched_at"),
        "cash": ibkr_cache.get("cash"),
        "holdings": [
            {
                "symbol": h.get("symbol", ""),
                "name": h.get("name"),
                "qty": h.get("qty") or 0.0,
                "price": h.get("price"),
                "current_value": h.get("current_value"),
                "cost_basis_total": h.get("cost_basis_total"),
                "gain_value": h.get("gain_value"),
                "currency": h.get("currency"),
            }
            for h in ibkr_cache.get("holdings") or []
        ],
    }

    history = portfolio.get("history", [])
    sharpe, vol = portfolio_risk_stats(history)

    vals = asset_values(doc)
    totals = {k: v for k, v in vals.items() if k != "total"}
    totals["total"] = vals["total"]
    totals["investable"] = investable_value(vals)

    return {
        # True when Public.com is not connected; drives only the "connect Public.com" hint.
        "not_configured": not secret,
        "series": [{"date": pt["date"], "value": pt["value"]} for pt in history],
        "allocation": allocation,
        "holdings": holdings,
        "ibkr": ibkr,
        "sharpe_ratio": sharpe,
        "volatility": vol,
        "manual_holdings": list(portfolio.get("manual_holdings", [])),
        "cash_accounts": list(portfolio.get("cash_accounts", [])),
        "real_estate": list(portfolio.get("real_estate", [])),
        "businesses": list(portfolio.get("businesses", [])),
        "fixed_income": list(portfolio.get("fixed_income", [])),
        "totals": totals,
    }


@router.get("")
async def get_portfolio(store: Storedep, _user: SessionUser) -> dict:
    doc = store.read()
    probe = copy.deepcopy(doc)
    if record_snapshot(probe):
        store.mutate(record_snapshot)
        doc = store.read()
    return {"data": _build_portfolio_response(doc), "error": None}


@router.post("/sync")
async def sync_portfolio(store: Storedep, _user: SessionUser) -> dict:
    doc = store.read()
    secret = (doc.get("settings") or {}).get("public_api_key_enc")
    if not secret:
        return {"data": _build_portfolio_response(doc), "error": "not_configured"}

    try:
        async with PublicApiClient(secret) as client:
            accounts = await client.list_accounts()
            if not accounts:
                return {"data": _build_portfolio_response(doc), "error": "no_accounts"}
            account_id = accounts[0]["accountId"]
            raw = await client.get_portfolio(account_id)
            normalized = normalize_portfolio(raw)
    except PublicApiError as exc:
        logger.warning("Public.com sync failed: %s", exc)
        return {"data": _build_portfolio_response(doc), "error": "upstream_error"}

    cache = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "account_id": account_id,
        "account_value": normalized["account_value"],
        "cash": normalized["cash"],
        "holdings": normalized["holdings"],
    }

    def _apply(d: dict) -> None:
        d["portfolio"]["public_cache"] = cache
        record_snapshot(d)

    store.mutate(_apply)
    return {"data": _build_portfolio_response(store.read()), "error": None}


@router.post("/ibkr/sync")
async def sync_ibkr(store: Storedep, _user: SessionUser) -> dict:
    """Pull positions from Interactive Brokers through the report-only Flex Web Service."""
    settings = store.read().get("settings") or {}
    token = settings.get("ibkr_flex_token_enc")
    query_id = settings.get("ibkr_flex_query_id")
    if not token or not query_id:
        raise HTTPException(status_code=400, detail="IBKR is not connected. Add your Flex token and query ID in Settings.")

    try:
        async with IbkrFlexClient(token, query_id) as client:
            normalized = normalize_statement(await client.fetch_statement())
    except IbkrFlexError as exc:
        logger.warning("IBKR Flex sync failed: code=%s", exc.code or "-")
        raise HTTPException(status_code=502, detail=f"IBKR sync failed: {exc.message}") from None

    cache = {"fetched_at": datetime.now(timezone.utc).isoformat(), **normalized}

    def _apply(d: dict) -> None:
        d["portfolio"]["ibkr_cache"] = cache
        record_snapshot(d)

    store.mutate(_apply)
    return {"data": _build_portfolio_response(store.read()), "error": None}


# ---------------------------------------------------------------------------
# Manual holdings CRUD
# ---------------------------------------------------------------------------

@router.post("/manual")
async def create_manual_holding(body: HoldingIn, store: Storedep, _user: SessionUser) -> dict:
    holding = ManualHolding(**body.model_dump())
    holding_dict = holding.model_dump()

    def _apply(d: dict) -> None:
        d["portfolio"].setdefault("manual_holdings", []).append(holding_dict)
        record_snapshot(d)

    store.mutate(_apply)
    return {"data": holding_dict, "error": None}


@router.patch("/manual/{holding_id}")
async def update_manual_holding(holding_id: str, body: HoldingIn, store: Storedep, _user: SessionUser) -> dict:
    doc = store.read()
    holdings = doc.get("portfolio", {}).get("manual_holdings", [])
    if not any(h.get("id") == holding_id for h in holdings):
        raise HTTPException(status_code=404, detail="Manual holding not found")

    updated: dict = {}

    def _apply(d: dict) -> None:
        nonlocal updated
        for h in d["portfolio"]["manual_holdings"]:
            if h.get("id") == holding_id:
                h["symbol"] = body.symbol
                h["qty"] = body.qty
                h["cost_basis"] = body.cost_basis
                # optional fields: only touched when the client sent them
                for k in ("current_value", "account", "broker"):
                    if k in body.model_fields_set:
                        h[k] = getattr(body, k)
                updated = dict(h)
                break
        record_snapshot(d)

    store.mutate(_apply)
    return {"data": updated, "error": None}


@router.delete("/manual/{holding_id}")
async def delete_manual_holding(holding_id: str, store: Storedep, _user: SessionUser) -> dict:
    doc = store.read()
    holdings = doc.get("portfolio", {}).get("manual_holdings", [])
    if not any(h.get("id") == holding_id for h in holdings):
        raise HTTPException(status_code=404, detail="Manual holding not found")

    def _apply(d: dict) -> None:
        d["portfolio"]["manual_holdings"] = [
            h for h in d["portfolio"]["manual_holdings"] if h.get("id") != holding_id
        ]
        record_snapshot(d)

    store.mutate(_apply)
    return {"data": None, "error": None}


# ---------------------------------------------------------------------------
# Cash accounts CRUD
# ---------------------------------------------------------------------------

@router.post("/cash")
async def create_cash_account(body: CashAccountIn, store: Storedep, _user: SessionUser) -> dict:
    account = CashAccount(name=body.name, balance=body.balance)
    account_dict = account.model_dump()

    def _apply(d: dict) -> None:
        d["portfolio"].setdefault("cash_accounts", []).append(account_dict)
        record_snapshot(d)

    store.mutate(_apply)
    return {"data": account_dict, "error": None}


@router.patch("/cash/{cash_id}")
async def update_cash_account(cash_id: str, body: CashAccountIn, store: Storedep, _user: SessionUser) -> dict:
    doc = store.read()
    accounts = doc.get("portfolio", {}).get("cash_accounts", [])
    if not any(c.get("id") == cash_id for c in accounts):
        raise HTTPException(status_code=404, detail="Cash account not found")

    updated: dict = {}

    def _apply(d: dict) -> None:
        nonlocal updated
        for c in d["portfolio"]["cash_accounts"]:
            if c.get("id") == cash_id:
                c["name"] = body.name
                c["balance"] = body.balance
                updated = dict(c)
                break
        record_snapshot(d)

    store.mutate(_apply)
    return {"data": updated, "error": None}


@router.delete("/cash/{cash_id}")
async def delete_cash_account(cash_id: str, store: Storedep, _user: SessionUser) -> dict:
    doc = store.read()
    accounts = doc.get("portfolio", {}).get("cash_accounts", [])
    if not any(c.get("id") == cash_id for c in accounts):
        raise HTTPException(status_code=404, detail="Cash account not found")

    def _apply(d: dict) -> None:
        d["portfolio"]["cash_accounts"] = [
            c for c in d["portfolio"]["cash_accounts"] if c.get("id") != cash_id
        ]
        record_snapshot(d)

    store.mutate(_apply)
    return {"data": None, "error": None}


# ---------------------------------------------------------------------------
# Real estate / businesses / fixed income CRUD (one factory, three collections)
# ---------------------------------------------------------------------------

def _register_collection(path: str, key: str, model: type[BaseModel], label: str) -> None:
    @router.get(f"/{path}", name=f"list_{key}")
    async def list_items(store: Storedep, _user: SessionUser) -> dict:
        return {"data": list(store.read().get("portfolio", {}).get(key, [])), "error": None}

    @router.post(f"/{path}", name=f"create_{key}")
    async def create_item(body: model, store: Storedep, _user: SessionUser) -> dict:  # type: ignore[valid-type]
        item = model(**{**body.model_dump(exclude={"id"})}).model_dump()

        def _apply(d: dict) -> None:
            d["portfolio"].setdefault(key, []).append(item)
            record_snapshot(d)

        store.mutate(_apply)
        return {"data": item, "error": None}

    @router.patch(f"/{path}/{{item_id}}", name=f"update_{key}")
    async def update_item(item_id: str, body: model, store: Storedep, _user: SessionUser) -> dict:  # type: ignore[valid-type]
        if not any(i.get("id") == item_id for i in store.read().get("portfolio", {}).get(key, [])):
            raise HTTPException(status_code=404, detail=f"{label} not found")
        fields = body.model_dump(exclude={"id"})
        updated: dict = {}

        def _apply(d: dict) -> None:
            nonlocal updated
            for i in d["portfolio"].setdefault(key, []):
                if i.get("id") == item_id:
                    i.update(fields)
                    updated = dict(i)
                    break
            record_snapshot(d)

        store.mutate(_apply)
        return {"data": updated, "error": None}

    @router.delete(f"/{path}/{{item_id}}", name=f"delete_{key}")
    async def delete_item(item_id: str, store: Storedep, _user: SessionUser) -> dict:
        if not any(i.get("id") == item_id for i in store.read().get("portfolio", {}).get(key, [])):
            raise HTTPException(status_code=404, detail=f"{label} not found")

        def _apply(d: dict) -> None:
            d["portfolio"][key] = [i for i in d["portfolio"].get(key, []) if i.get("id") != item_id]
            record_snapshot(d)

        store.mutate(_apply)
        return {"data": None, "error": None}


_register_collection("real-estate", "real_estate", RealEstate, "Property")
_register_collection("businesses", "businesses", Business, "Business")
_register_collection("fixed-income", "fixed_income", FixedIncome, "Fixed-income security")
