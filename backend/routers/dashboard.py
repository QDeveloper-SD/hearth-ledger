from __future__ import annotations

from fastapi import APIRouter

from backend.routers.deps import SessionUser, Storedep
from backend.services.metrics import monthly_income, net_worth as net_worth_metric

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
async def get_dashboard(store: Storedep, _user: SessionUser) -> dict:
    doc = store.read()

    recent_ledger = sorted(doc.get("ledger", []), key=lambda e: e.get("date", ""), reverse=True)[:10]

    portfolio = doc.get("portfolio", {})
    public_cache = portfolio.get("public_cache", {})
    manual_holdings = portfolio.get("manual_holdings", [])
    cash_accounts = portfolio.get("cash_accounts", [])

    # portfolio value: prefer live public cache, fall back to manual cost basis
    public_holdings = public_cache.get("holdings", [])
    if public_holdings:
        portfolio_value = sum(h.get("current_value") or h.get("cost_basis", 0.0) for h in public_holdings)
    else:
        account_value = public_cache.get("account_value", 0.0)
        portfolio_value = account_value or 0.0

    income_mo = monthly_income(doc)

    debts = doc.get("debts", [])
    debt_abs = sum(abs(d.get("balance", 0.0)) for d in debts)

    # Net worth donut shows ASSETS only. Debt is reported separately below — a donut
    # can't render negative slices, so including it would both visually mislead and
    # inflate the implied total.
    manual_value = sum(h.get("cost_basis", 0.0) for h in manual_holdings)
    cash_value = sum(c.get("balance", 0.0) for c in cash_accounts)
    nwb = []
    if portfolio_value:
        nwb.append({"name": "Investments", "value": portfolio_value})
    if manual_value:
        nwb.append({"name": "Manual Holdings", "value": manual_value})
    if cash_value:
        nwb.append({"name": "Cash", "value": cash_value})

    # --- portfolio_breakdown ---
    if public_holdings:
        portfolio_breakdown = [
            {"name": h["symbol"], "value": h.get("current_value") or h.get("cost_basis", 0.0)}
            for h in public_holdings
            if h.get("symbol")
        ]
    elif manual_holdings:
        portfolio_breakdown = [
            {"name": h["symbol"], "value": h.get("cost_basis", 0.0)}
            for h in manual_holdings
            if h.get("symbol")
        ]
    else:
        portfolio_breakdown = []

    # --- income_summary ---
    income_sources = doc.get("income_sources", [])
    income_summary = {
        "total": income_mo,
        "sources": [{"name": s.get("name", ""), "amount": s.get("amount", 0.0)} for s in income_sources],
    }

    # --- debt_summary ---
    # return total as negative so the frontend can render it with text-loss
    debt_summary = {
        "total": -debt_abs,
        "accounts": [{"name": d.get("name", ""), "balance": -abs(d.get("balance", 0.0))} for d in debts],
    }

    return {
        "data": {
            "net_worth": net_worth_metric(doc),
            "net_worth_breakdown": nwb,
            "portfolio_breakdown": portfolio_breakdown,
            "income_summary": income_summary,
            "debt_summary": debt_summary,
            "recent_ledger": recent_ledger,
        },
        "error": None,
    }
