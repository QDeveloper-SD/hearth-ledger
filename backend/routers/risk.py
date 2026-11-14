from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.routers.deps import SessionUser, Storedep
from backend.services.metrics import (
    asset_slices,
    asset_values,
    current_ratio,
    debt_to_income,
    emergency_fund_months,
    net_worth,
)

router = APIRouter(prefix="/api/risk", tags=["risk"])


class InsurancePatch(BaseModel):
    covered: bool


@router.get("")
async def get_risk(store: Storedep, _user: SessionUser) -> dict:
    doc = store.read()

    exposure = asset_slices(asset_values(doc))

    insurance = [
        {"name": p.get("name", p["name"]), "covered": p.get("covered", False)}
        for p in doc.get("insurance", [])
    ]

    # spend_series: group ledger entries with amount < 0 by YYYY-MM, sum absolute values
    monthly_spend: dict[str, float] = defaultdict(float)
    for entry in doc.get("ledger", []):
        amount = entry.get("amount", 0.0)
        if amount < 0:
            date_str = entry.get("date", "")
            if len(date_str) >= 7:
                month_key = date_str[:7]
                monthly_spend[month_key] += abs(amount)

    spend_series = [
        {"m": month, "spend": round(spend, 2)}
        for month, spend in sorted(monthly_spend.items())
    ]

    dti = debt_to_income(doc)
    em = emergency_fund_months(doc)
    cr = current_ratio(doc)

    return {
        "data": {
            "net_worth": net_worth(doc),
            # null = not enough data to compute (the UI shows a dash)
            "dti": dti,
            "emergency_months": em,
            "current_ratio": cr,
            "exposure": exposure,
            "insurance": insurance,
            "spend_series": spend_series,
        },
        "error": None,
    }


@router.patch("/insurance/{name}")
async def toggle_insurance(name: str, body: InsurancePatch, store: Storedep, _user: SessionUser) -> dict:
    doc = store.read()
    insurance_list = doc.get("insurance", [])

    # find index case-insensitively
    idx = next(
        (i for i, p in enumerate(insurance_list) if p.get("name", "").lower() == name.lower()),
        None,
    )
    if idx is None:
        raise HTTPException(status_code=404, detail=f"Insurance category '{name}' not found")

    def _apply(d: dict) -> None:
        for p in d.get("insurance", []):
            if p.get("name", "").lower() == name.lower():
                p["covered"] = body.covered
                break

    store.mutate(_apply)
    updated_doc = store.read()
    updated_insurance = [
        {"name": p.get("name", ""), "covered": p.get("covered", False)}
        for p in updated_doc.get("insurance", [])
    ]
    return {"data": updated_insurance, "error": None}
