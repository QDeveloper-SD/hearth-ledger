from __future__ import annotations

from datetime import date, timedelta

import pytest
from httpx import AsyncClient

from backend.routers.portfolio import HISTORY_CAP, record_snapshot
from backend.services.metrics import portfolio_risk_stats


def _doc(cash: float = 1000.0) -> dict:
    return {
        "settings": {},
        "portfolio": {
            "manual_holdings": [{"id": "h", "symbol": "BTC", "qty": 1, "cost_basis": 500.0}],
            "cash_accounts": [{"id": "c", "name": "x", "balance": cash}],
            "public_cache": {},
        },
    }


def test_empty_portfolio_records_nothing() -> None:
    doc = {"settings": {}, "portfolio": {"manual_holdings": [], "cash_accounts": []}}
    assert record_snapshot(doc) is False
    assert doc["portfolio"].get("history", []) == []


def test_upsert_once_per_day() -> None:
    doc = _doc()
    day = date(2026, 1, 1)
    assert record_snapshot(doc, day)
    assert not record_snapshot(doc, day)
    doc["portfolio"]["cash_accounts"][0]["balance"] = 2000.0
    assert record_snapshot(doc, day)
    assert doc["portfolio"]["history"] == [{"date": "2026-01-01", "value": 2500.0}]


def test_cap() -> None:
    doc = _doc()
    start = date(2020, 1, 1)
    for i in range(HISTORY_CAP + 10):
        record_snapshot(doc, start + timedelta(days=i))
    hist = doc["portfolio"]["history"]
    assert len(hist) == HISTORY_CAP
    assert hist[-1]["date"] == (start + timedelta(days=HISTORY_CAP + 9)).isoformat()


def test_risk_stats_insufficient_and_sufficient() -> None:
    short = [{"date": f"2026-01-0{i}", "value": 100.0 + i} for i in range(1, 5)]
    assert portfolio_risk_stats(short) == (None, None)
    vals = [100, 101, 99, 102, 103, 101, 104, 105]
    long = [{"date": f"2026-01-{i + 1:02d}", "value": float(v)} for i, v in enumerate(vals)]
    sharpe, vol = portfolio_risk_stats(long)
    assert sharpe is not None and vol is not None and vol > 0


def test_zero_value_days_guarded() -> None:
    hist = [{"date": f"2026-01-{i + 1:02d}", "value": 0.0} for i in range(7)]
    assert portfolio_risk_stats(hist) == (None, None)


@pytest.mark.asyncio
async def test_series_recorded_on_changes(authed_client: AsyncClient) -> None:
    r = await authed_client.get("/api/portfolio")
    assert r.json()["data"]["series"] == []
    assert r.json()["data"]["sharpe_ratio"] is None

    r = await authed_client.post("/api/portfolio/manual", json={"symbol": "ETH", "qty": 1, "cost_basis": 300.0})
    hid = r.json()["data"]["id"]
    r = await authed_client.post("/api/portfolio/cash", json={"name": "Chk", "balance": 200.0})
    cid = r.json()["data"]["id"]
    data = (await authed_client.get("/api/portfolio")).json()["data"]
    assert len(data["series"]) == 1
    assert data["series"][0]["value"] == 500.0
    assert set(data["series"][0]) == {"date", "value"}
    assert data["sharpe_ratio"] is None and data["volatility"] is None

    await authed_client.patch(f"/api/portfolio/cash/{cid}", json={"name": "Chk", "balance": 700.0})
    data = (await authed_client.get("/api/portfolio")).json()["data"]
    assert [p["value"] for p in data["series"]] == [1000.0]

    await authed_client.delete(f"/api/portfolio/manual/{hid}")
    data = (await authed_client.get("/api/portfolio")).json()["data"]
    assert [p["value"] for p in data["series"]] == [700.0]
