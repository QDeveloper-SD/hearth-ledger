from __future__ import annotations

import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app import create_app
from backend.services.metrics import asset_values, net_worth
from backend.services.pdf import build_pdf
from backend.storage.schema import HearthDoc

RE = {"name": "Home", "address": "1 Main St", "current_value": 500000, "purchase_price": 400000}
BIZ = {"name": "Shop", "valuation": 200000, "ownership_pct": 25}
FI = {"name": "T-Bill", "issuer": "US Treasury", "face_value": 10000, "coupon_rate": 4.5,
      "maturity_date": "2030-01-15"}


def _rich_doc() -> dict:
    d = HearthDoc().model_dump()
    p = d["portfolio"]
    p["public_cache"]["account_value"] = 1000
    p["manual_holdings"] = [
        {"id": "1", "symbol": "A", "qty": 1, "cost_basis": 100, "current_value": None, "account": "manual", "broker": None},
        {"id": "2", "symbol": "B", "qty": 1, "cost_basis": 100, "current_value": 150, "account": "ibkr", "broker": None},
        {"id": "3", "symbol": "C", "qty": 1, "cost_basis": 300, "current_value": None, "account": "other", "broker": "Fidelity"},
    ]
    p["cash_accounts"] = [{"id": "c", "name": "Chk", "balance": 50}]
    p["real_estate"] = [{"id": "r", **RE, "notes": None}]
    p["businesses"] = [{"id": "b", **BIZ, "notes": None}]
    p["fixed_income"] = [{"id": "f", **FI, "current_value": 9800}]
    d["debts"] = [{"id": "d", "name": "Mortgage", "balance": 100000, "rate": 0.04, "min_payment": 1000}]
    return d


def test_asset_values_and_net_worth() -> None:
    v = asset_values(_rich_doc())
    assert v["public"] == 1000 and v["manual"] == 100 and v["ibkr"] == 150 and v["other_brokers"] == 300
    assert v["real_estate"] == 500000 and v["businesses"] == 50000
    assert v["fixed_income"] == 9800 and v["cash"] == 50
    assert v["total"] == pytest.approx(1000 + 100 + 150 + 300 + 500000 + 50000 + 9800 + 50)
    assert net_worth(_rich_doc()) == pytest.approx(v["total"] - 100000)


def test_fixed_income_defaults_to_face_value() -> None:
    d = _rich_doc()
    d["portfolio"]["fixed_income"][0]["current_value"] = None
    assert asset_values(d)["fixed_income"] == 10000


def test_pdf_with_new_assets() -> None:
    out = build_pdf(_rich_doc(), ["balance", "portfolio"])
    assert out.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_legacy_doc_endpoints(tmp_path: Path) -> None:
    legacy = HearthDoc().model_dump()
    for k in ("real_estate", "businesses", "fixed_income"):
        legacy["portfolio"].pop(k)
    legacy["portfolio"]["manual_holdings"] = [{"id": "1", "symbol": "OLD", "qty": 2, "cost_basis": 400}]
    (tmp_path / "hearth.json").write_text(json.dumps(legacy))
    app = create_app(data_dir=tmp_path)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        assert (await c.post("/api/auth/login", json={"username": "admin", "password": "password"})).status_code == 200
        pf = (await c.get("/api/portfolio")).json()["data"]
        assert pf["real_estate"] == [] and pf["totals"]["manual"] == 400
        assert pf["not_configured"] is True
        assert (await c.get("/api/dashboard")).json()["data"]["net_worth"] == 400
        assert (await c.get("/api/risk")).status_code == 200
        r = await c.post("/api/export/pdf", json={"sections": ["balance", "portfolio"]})
        assert r.status_code == 200 and r.content.startswith(b"%PDF")
        # creating a new-collection item on a legacy doc works
        assert (await c.post("/api/portfolio/real-estate", json=RE)).status_code == 200
        assert (await c.get("/api/portfolio")).json()["data"]["totals"]["real_estate"] == 500000


@pytest.mark.asyncio
@pytest.mark.parametrize("path,body,patch,field", [
    ("real-estate", RE, {**RE, "current_value": 600000}, "current_value"),
    ("businesses", BIZ, {**BIZ, "ownership_pct": 50}, "ownership_pct"),
    ("fixed-income", FI, {**FI, "face_value": 20000}, "face_value"),
])
async def test_collection_crud(authed_client: AsyncClient, path, body, patch, field) -> None:
    c = authed_client
    created = (await c.post(f"/api/portfolio/{path}", json=body)).json()["data"]
    assert created["id"]
    assert [i["id"] for i in (await c.get(f"/api/portfolio/{path}")).json()["data"]] == [created["id"]]
    upd = await c.patch(f"/api/portfolio/{path}/{created['id']}", json=patch)
    assert upd.json()["data"][field] == patch[field]
    assert (await c.get(f"/api/portfolio/{path}")).json()["data"][0][field] == patch[field]
    assert (await c.patch(f"/api/portfolio/{path}/nope", json=patch)).status_code == 404
    assert (await c.delete(f"/api/portfolio/{path}/nope")).status_code == 404
    d = await c.delete(f"/api/portfolio/{path}/{created['id']}")
    assert d.json() == {"data": None, "error": None}
    assert (await c.get(f"/api/portfolio/{path}")).json()["data"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("path,bad", [
    ("real-estate", {"name": "x"}),
    ("real-estate", {**RE, "current_value": -1}),
    ("businesses", {**BIZ, "ownership_pct": 101}),
    ("businesses", {**BIZ, "ownership_pct": -1}),
    ("fixed-income", {**FI, "maturity_date": "2030-13-45"}),
    ("fixed-income", {**FI, "face_value": -5}),
    ("fixed-income", {**FI, "bogus": 1}),
])
async def test_collection_validation(authed_client: AsyncClient, path, bad) -> None:
    assert (await authed_client.post(f"/api/portfolio/{path}", json=bad)).status_code == 422


@pytest.mark.asyncio
async def test_business_default_pct_and_totals(authed_client: AsyncClient) -> None:
    c = authed_client
    b = (await c.post("/api/portfolio/businesses", json={"name": "Co", "valuation": 1000})).json()["data"]
    assert b["ownership_pct"] == 100
    await c.post("/api/portfolio/businesses", json=BIZ)
    t = (await c.get("/api/portfolio")).json()["data"]["totals"]
    assert t["businesses"] == 51000 and t["total"] == 51000


@pytest.mark.asyncio
async def test_holdings_account_filter_and_snapshot(authed_client: AsyncClient) -> None:
    c = authed_client
    await c.post("/api/portfolio/manual", json={"symbol": "A", "qty": 1, "cost_basis": 100})
    await c.post("/api/portfolio/manual", json={"symbol": "B", "qty": 1, "cost_basis": 100, "current_value": 130, "account": "ibkr"})
    o = await c.post("/api/portfolio/manual", json={"symbol": "C", "qty": 1, "cost_basis": 50, "account": "other", "broker": "Fidelity"})
    assert o.status_code == 200
    assert (await c.post("/api/portfolio/manual", json={"symbol": "D", "qty": 1, "cost_basis": 5, "account": "other"})).status_code == 422
    assert (await c.post("/api/portfolio/manual", json={"symbol": "D", "qty": 1, "cost_basis": 5, "account": "zzz"})).status_code == 422
    # PATCH without new fields keeps account
    oid = o.json()["data"]["id"]
    p = (await c.patch(f"/api/portfolio/manual/{oid}", json={"symbol": "C", "qty": 2, "cost_basis": 60})).json()["data"]
    assert p["account"] == "other" and p["broker"] == "Fidelity"
    await c.post("/api/portfolio/real-estate", json=RE)
    await c.post("/api/portfolio/businesses", json=BIZ)
    data = (await c.get("/api/portfolio")).json()["data"]
    t = data["totals"]
    assert (t["manual"], t["ibkr"], t["other_brokers"]) == (100, 130, 60)
    assert t["total"] == 290 + 500000 + 50000
    assert t["investable"] == 290
    assert [pt["value"] for pt in data["series"]] == [290]  # excludes real estate / businesses
    dash = (await c.get("/api/dashboard")).json()["data"]
    assert {s["name"]: s["value"] for s in dash["net_worth_breakdown"]} == {
        "Investments": 290, "Real Estate": 500000, "Businesses": 50000}
    assert sorted(s["name"] for s in dash["portfolio_breakdown"]) == ["A", "B", "C"]
    assert dash["net_worth"] == 550290
    risk = (await c.get("/api/risk")).json()["data"]
    assert risk["net_worth"] == 550290 and risk["current_ratio"] is None
