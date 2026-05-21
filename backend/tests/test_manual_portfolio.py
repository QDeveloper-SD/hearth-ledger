from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_add_manual_holding(authed_client: AsyncClient) -> None:
    payload = {"symbol": "BTC", "qty": 0.5, "cost_basis": 15000.0}
    resp = await authed_client.post("/api/portfolio/manual", json=payload)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["symbol"] == "BTC"
    assert data["qty"] == 0.5
    assert data["cost_basis"] == 15000.0
    assert "id" in data


@pytest.mark.asyncio
async def test_manual_holding_appears_in_portfolio(authed_client: AsyncClient) -> None:
    payload = {"symbol": "ETH", "qty": 2.0, "cost_basis": 5000.0}
    create_resp = await authed_client.post("/api/portfolio/manual", json=payload)
    holding_id = create_resp.json()["data"]["id"]

    resp = await authed_client.get("/api/portfolio")
    assert resp.status_code == 200
    holdings = resp.json()["data"]["manual_holdings"]
    ids = [h["id"] for h in holdings]
    assert holding_id in ids


@pytest.mark.asyncio
async def test_edit_manual_holding(authed_client: AsyncClient) -> None:
    create_resp = await authed_client.post("/api/portfolio/manual", json={"symbol": "VTI", "qty": 10.0, "cost_basis": 2000.0})
    holding_id = create_resp.json()["data"]["id"]

    patch = {"symbol": "VTI", "qty": 20.0, "cost_basis": 4000.0}
    resp = await authed_client.patch(f"/api/portfolio/manual/{holding_id}", json=patch)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["qty"] == 20.0
    assert data["cost_basis"] == 4000.0

    # Confirm change persists
    portfolio_resp = await authed_client.get("/api/portfolio")
    holdings = portfolio_resp.json()["data"]["manual_holdings"]
    updated = next(h for h in holdings if h["id"] == holding_id)
    assert updated["qty"] == 20.0


@pytest.mark.asyncio
async def test_delete_manual_holding(authed_client: AsyncClient) -> None:
    create_resp = await authed_client.post("/api/portfolio/manual", json={"symbol": "TSLA", "qty": 5.0, "cost_basis": 1000.0})
    holding_id = create_resp.json()["data"]["id"]

    resp = await authed_client.delete(f"/api/portfolio/manual/{holding_id}")
    assert resp.status_code == 200
    assert resp.json() == {"data": None, "error": None}

    # Confirm gone
    portfolio_resp = await authed_client.get("/api/portfolio")
    holdings = portfolio_resp.json()["data"]["manual_holdings"]
    ids = [h["id"] for h in holdings]
    assert holding_id not in ids


@pytest.mark.asyncio
async def test_delete_manual_holding_not_found(authed_client: AsyncClient) -> None:
    resp = await authed_client.delete("/api/portfolio/manual/nonexistent-id")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Cash accounts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_cash_account(authed_client: AsyncClient) -> None:
    payload = {"name": "Chase Checking", "balance": 5000.0}
    resp = await authed_client.post("/api/portfolio/cash", json=payload)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["name"] == "Chase Checking"
    assert data["balance"] == 5000.0
    assert "id" in data


@pytest.mark.asyncio
async def test_cash_account_appears_in_portfolio(authed_client: AsyncClient) -> None:
    payload = {"name": "Savings", "balance": 10000.0}
    create_resp = await authed_client.post("/api/portfolio/cash", json=payload)
    cash_id = create_resp.json()["data"]["id"]

    resp = await authed_client.get("/api/portfolio")
    assert resp.status_code == 200
    accounts = resp.json()["data"]["cash_accounts"]
    ids = [c["id"] for c in accounts]
    assert cash_id in ids


@pytest.mark.asyncio
async def test_edit_cash_account(authed_client: AsyncClient) -> None:
    create_resp = await authed_client.post("/api/portfolio/cash", json={"name": "Old Name", "balance": 1000.0})
    cash_id = create_resp.json()["data"]["id"]

    patch = {"name": "New Name", "balance": 2500.0}
    resp = await authed_client.patch(f"/api/portfolio/cash/{cash_id}", json=patch)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["name"] == "New Name"
    assert data["balance"] == 2500.0

    # Confirm change persists
    portfolio_resp = await authed_client.get("/api/portfolio")
    accounts = portfolio_resp.json()["data"]["cash_accounts"]
    updated = next(c for c in accounts if c["id"] == cash_id)
    assert updated["name"] == "New Name"


@pytest.mark.asyncio
async def test_delete_cash_account(authed_client: AsyncClient) -> None:
    create_resp = await authed_client.post("/api/portfolio/cash", json={"name": "Delete me", "balance": 500.0})
    cash_id = create_resp.json()["data"]["id"]

    resp = await authed_client.delete(f"/api/portfolio/cash/{cash_id}")
    assert resp.status_code == 200
    assert resp.json() == {"data": None, "error": None}

    # Confirm gone
    portfolio_resp = await authed_client.get("/api/portfolio")
    accounts = portfolio_resp.json()["data"]["cash_accounts"]
    ids = [c["id"] for c in accounts]
    assert cash_id not in ids


@pytest.mark.asyncio
async def test_delete_cash_account_not_found(authed_client: AsyncClient) -> None:
    resp = await authed_client.delete("/api/portfolio/cash/nonexistent-id")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Net worth integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_net_worth_includes_manual_and_cash(authed_client: AsyncClient) -> None:
    # Add a manual holding
    await authed_client.post("/api/portfolio/manual", json={"symbol": "RE", "qty": 1.0, "cost_basis": 250000.0})
    # Add a cash account
    await authed_client.post("/api/portfolio/cash", json={"name": "Emergency Fund", "balance": 15000.0})

    resp = await authed_client.get("/api/dashboard")
    assert resp.status_code == 200
    net_worth = resp.json()["data"]["net_worth"]
    # Should be at least manual + cash (no debts in this fresh store)
    assert net_worth >= 250000.0 + 15000.0
