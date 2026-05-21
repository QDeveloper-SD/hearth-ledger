from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.integrations.public_api import PublicApiClient, PublicApiError, normalize_portfolio
from backend.routers.deps import SessionUser, Storedep
from backend.services.metrics import portfolio_sharpe, portfolio_volatility
from backend.storage.schema import CashAccount, ManualHolding

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


class HoldingIn(BaseModel):
    symbol: str
    qty: float
    cost_basis: float


class CashAccountIn(BaseModel):
    name: str
    balance: float


def _build_portfolio_response(doc: dict) -> dict:
    portfolio = doc.get("portfolio", {})
    public_cache = portfolio.get("public_cache", {})
    manual_holdings = portfolio.get("manual_holdings", [])
    cash_accounts = portfolio.get("cash_accounts", [])
    public_holdings = public_cache.get("holdings", [])
    secret = (doc.get("settings") or {}).get("public_api_key_enc")

    if not secret and not manual_holdings and not cash_accounts:
        return {
            "not_configured": True,
            "series": [],
            "allocation": [],
            "holdings": [],
            "sharpe_ratio": 0,
            "volatility": 0,
            "manual_holdings": [],
            "cash_accounts": [],
        }

    if public_holdings:
        holdings = [
            {
                "symbol": h.get("symbol", ""),
                "name": h.get("name"),
                "qty": h.get("qty") or 0.0,
                "price": h.get("price"),
                "day_change": h.get("day_change"),
            }
            for h in public_holdings
        ]
        allocation = [
            {
                "name": h.get("symbol", ""),
                "value": h.get("current_value") or h.get("cost_basis_total") or 0.0,
            }
            for h in public_holdings
        ]
    else:
        holdings = [
            {
                "symbol": h.get("symbol", ""),
                "name": None,
                "qty": h.get("qty") or 0.0,
                "price": None,
                "day_change": None,
            }
            for h in manual_holdings
        ]
        allocation = [
            {
                "name": h.get("symbol", ""),
                "value": h.get("cost_basis", 0.0),
            }
            for h in manual_holdings
        ]

    sharpe = portfolio_sharpe([])
    vol = portfolio_volatility([])

    return {
        "series": [],
        "allocation": allocation,
        "holdings": holdings,
        "sharpe_ratio": sharpe if sharpe is not None else 0,
        "volatility": vol if vol is not None else 0,
        "manual_holdings": list(manual_holdings),
        "cash_accounts": list(cash_accounts),
    }


@router.get("")
async def get_portfolio(store: Storedep, _user: SessionUser) -> dict:
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

    store.mutate(_apply)
    return {"data": _build_portfolio_response(store.read()), "error": None}


# ---------------------------------------------------------------------------
# Manual holdings CRUD
# ---------------------------------------------------------------------------

@router.post("/manual")
async def create_manual_holding(body: HoldingIn, store: Storedep, _user: SessionUser) -> dict:
    holding = ManualHolding(symbol=body.symbol, qty=body.qty, cost_basis=body.cost_basis)
    holding_dict = holding.model_dump()

    def _apply(d: dict) -> None:
        d["portfolio"].setdefault("manual_holdings", []).append(holding_dict)

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
                updated = dict(h)
                break

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

    store.mutate(_apply)
    return {"data": None, "error": None}
