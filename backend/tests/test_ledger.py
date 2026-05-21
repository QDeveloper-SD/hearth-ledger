from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_empty(authed_client: AsyncClient) -> None:
    resp = await authed_client.get("/api/ledger")
    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] is None
    assert body["data"]["entries"] == []
    assert body["data"]["total"] == 0


@pytest.mark.asyncio
async def test_add_entry(authed_client: AsyncClient) -> None:
    payload = {"date": "2026-05-01", "desc": "Groceries", "category": "Food", "amount": -80.0}
    resp = await authed_client.post("/api/ledger", json=payload)
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["desc"] == "Groceries"
    assert "id" in data


@pytest.mark.asyncio
async def test_edit_entry(authed_client: AsyncClient) -> None:
    payload = {"date": "2026-05-01", "desc": "Coffee", "category": "Food", "amount": -5.0}
    create_resp = await authed_client.post("/api/ledger", json=payload)
    entry_id = create_resp.json()["data"]["id"]

    patch = {"date": "2026-05-01", "desc": "Coffee (updated)", "category": "Food", "amount": -6.0}
    resp = await authed_client.patch(f"/api/ledger/{entry_id}", json=patch)
    assert resp.status_code == 200
    assert resp.json()["data"]["desc"] == "Coffee (updated)"


@pytest.mark.asyncio
async def test_delete_entry(authed_client: AsyncClient) -> None:
    payload = {"date": "2026-05-01", "desc": "Delete me", "category": "Test", "amount": -1.0}
    create_resp = await authed_client.post("/api/ledger", json=payload)
    entry_id = create_resp.json()["data"]["id"]

    resp = await authed_client.delete(f"/api/ledger/{entry_id}")
    assert resp.status_code == 200
    assert resp.json() == {"data": None, "error": None}

    list_resp = await authed_client.get("/api/ledger")
    ids = [e["id"] for e in list_resp.json()["data"]["entries"]]
    assert entry_id not in ids


@pytest.mark.asyncio
async def test_delete_nonexistent(authed_client: AsyncClient) -> None:
    resp = await authed_client.delete("/api/ledger/nonexistent-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_summary(authed_client: AsyncClient) -> None:
    await authed_client.post("/api/ledger", json={"date": "2026-05-01", "desc": "A", "category": "Food", "amount": -50.0})
    await authed_client.post("/api/ledger", json={"date": "2026-05-02", "desc": "B", "category": "Food", "amount": -30.0})
    await authed_client.post("/api/ledger", json={"date": "2026-05-03", "desc": "C", "category": "Income", "amount": 1000.0})

    resp = await authed_client.get("/api/ledger/summary")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["by_category"]["Food"] == pytest.approx(-80.0)
    assert data["by_category"]["Income"] == pytest.approx(1000.0)


@pytest.mark.asyncio
async def test_pagination(authed_client: AsyncClient) -> None:
    for i in range(5):
        await authed_client.post("/api/ledger", json={"date": "2026-05-01", "desc": f"tx{i}", "category": "X", "amount": float(-i)})

    resp = await authed_client.get("/api/ledger?page=1&page_size=3")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data["entries"]) == 3
    assert data["total"] == 5


@pytest.mark.asyncio
async def test_unauthenticated_rejected(app) -> None:
    from httpx import ASGITransport, AsyncClient
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/ledger")
        assert resp.status_code == 401
