from __future__ import annotations

import io
import re

import pytest
from httpx import AsyncClient

from backend.services.pdf import build_pdf
from backend.storage.schema import HearthDoc

ALL = ["balance", "income", "ledger", "portfolio"]


def _pages(data: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page[^s]", data))


def _populated() -> dict:
    d = HearthDoc().model_dump()
    d["debts"] = [{"id": "1", "name": "Mortgage", "balance": 200000, "rate": 0.045, "min_payment": 1500}]
    d["income_sources"] = [{"id": "1", "name": "Salary", "amount": 5000, "cadence": "monthly"}]
    d["portfolio"]["manual_holdings"] = [{"id": "1", "symbol": "VTI", "qty": 10, "cost_basis": 2500}]
    d["portfolio"]["cash_accounts"] = [{"id": "1", "name": "Checking", "balance": 3000}]
    d["portfolio"]["public_cache"]["account_value"] = 9000
    d["portfolio"]["public_cache"]["holdings"] = [
        {"symbol": "AAPL", "qty": 3, "cost_basis": 400, "current_value": 600}
    ]
    d["ledger"] = [
        {"id": "a", "date": "2026-05-01", "desc": "Pay & <bonus>", "category": "Pay", "amount": 3000},
        {"id": "b", "date": "2026-05-02", "desc": "Groceries", "category": "Food", "amount": -80.5},
    ]
    return d


def test_empty_doc() -> None:
    doc = HearthDoc().model_dump()
    assert build_pdf(doc, ALL).startswith(b"%PDF")
    assert build_pdf(doc, []).startswith(b"%PDF")
    assert build_pdf({}, ALL).startswith(b"%PDF")


def test_populated_doc() -> None:
    out = build_pdf(_populated(), ALL)
    assert out.startswith(b"%PDF")
    assert build_pdf(_populated(), ["balance"]).startswith(b"%PDF")


def test_large_ledger_multi_page() -> None:
    d = HearthDoc().model_dump()
    d["ledger"] = [
        {"id": str(i), "date": f"2026-{i % 12 + 1:02d}-{i % 28 + 1:02d}", "desc": f"Entry {i}",
         "category": "Misc", "amount": (-1) ** i * (i + 0.37)}
        for i in range(500)
    ]
    out = build_pdf(d, ["ledger"])
    assert out.startswith(b"%PDF")
    assert _pages(out) > 1


@pytest.mark.asyncio
async def test_export_endpoint(authed_client: AsyncClient) -> None:
    resp = await authed_client.post("/api/export/pdf", json={"sections": ALL})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_export_requires_session(app) -> None:
    from httpx import ASGITransport

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        assert (await c.post("/api/export/pdf", json={"sections": ALL})).status_code == 401
