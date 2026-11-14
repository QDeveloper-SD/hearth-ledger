from __future__ import annotations

from fastapi import APIRouter

from backend.routers.deps import SessionUser, Storedep
from backend.services.metrics import (
    asset_slices,
    asset_values,
    brokerage_positions,
    income_to_date,
    monthly_income,
    net_worth as net_worth_metric,
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
async def get_dashboard(store: Storedep, _user: SessionUser) -> dict:
    doc = store.read()

    recent_ledger = sorted(doc.get("ledger", []), key=lambda e: e.get("date", ""), reverse=True)[:10]

    income_mo = monthly_income(doc)

    debts = doc.get("debts", [])
    debt_abs = sum(abs(d.get("balance", 0.0)) for d in debts)

    # Net worth donut shows ASSETS only. Debt is reported separately below — a donut
    # can't render negative slices, so including it would both visually mislead and
    # inflate the implied total.
    nwb = asset_slices(asset_values(doc))
    portfolio_breakdown = brokerage_positions(doc)

    # --- income_summary ---
    income_sources = doc.get("income_sources", [])
    # mtd / ytd = income actually received (positive ledger entries);
    # expected_monthly = what the configured sources should bring in per month;
    # sources = the per-paycheck amount with the cadence exactly as the user entered it.
    income_mtd, income_ytd = income_to_date(doc)
    income_summary = {
        "total": income_mo,
        "expected_monthly": income_mo,
        "mtd": income_mtd,
        "ytd": income_ytd,
        "sources": [
            {"name": s.get("name", ""), "amount": s.get("amount", 0.0), "cadence": s.get("cadence", "")}
            for s in income_sources
        ],
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
