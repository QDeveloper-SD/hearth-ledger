from __future__ import annotations

import pytest
from httpx import AsyncClient

EV = {"title": "Property tax", "date": "2026-06-15", "amount": 1200.0, "notes": "Due"}


async def _create(c: AsyncClient, **over) -> dict:
    resp = await c.post("/api/planning/events", json={**EV, **over})
    assert resp.status_code == 201
    return resp.json()["data"]


@pytest.mark.asyncio
async def test_list_empty(authed_client: AsyncClient) -> None:
    resp = await authed_client.get("/api/planning/events")
    assert resp.status_code == 200
    assert resp.json()["data"] == []


@pytest.mark.asyncio
async def test_create_and_list(authed_client: AsyncClient) -> None:
    ev = await _create(authed_client)
    assert ev["title"] == "Property tax" and "id" in ev
    data = (await authed_client.get("/api/planning/events")).json()["data"]
    assert [e["id"] for e in data] == [ev["id"]]


@pytest.mark.asyncio
async def test_create_minimal(authed_client: AsyncClient) -> None:
    ev = await _create(authed_client, amount=None, notes=None)
    assert ev["amount"] is None and ev["notes"] is None


@pytest.mark.asyncio
async def test_edit_partial(authed_client: AsyncClient) -> None:
    ev = await _create(authed_client)
    resp = await authed_client.patch(f"/api/planning/events/{ev['id']}", json={"title": "New"})
    assert resp.status_code == 200
    d = resp.json()["data"]
    assert d["title"] == "New" and d["amount"] == 1200.0 and d["notes"] == "Due"


@pytest.mark.asyncio
async def test_edit_clear_fields(authed_client: AsyncClient) -> None:
    ev = await _create(authed_client)
    resp = await authed_client.patch(
        f"/api/planning/events/{ev['id']}", json={"amount": None, "notes": None}
    )
    assert resp.status_code == 200
    d = resp.json()["data"]
    assert d["amount"] is None and d["notes"] is None and d["title"] == "Property tax"
    listed = (await authed_client.get("/api/planning/events")).json()["data"]
    assert listed[0]["amount"] is None


@pytest.mark.asyncio
async def test_delete(authed_client: AsyncClient) -> None:
    ev = await _create(authed_client)
    resp = await authed_client.delete(f"/api/planning/events/{ev['id']}")
    assert resp.status_code == 200
    assert (await authed_client.get("/api/planning/events")).json()["data"] == []


@pytest.mark.asyncio
async def test_404s(authed_client: AsyncClient) -> None:
    assert (await authed_client.patch("/api/planning/events/nope", json={"title": "x"})).status_code == 404
    assert (await authed_client.delete("/api/planning/events/nope")).status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", ["garbage", "2026-13-40", "06/15/2026", ""])
async def test_bad_date(authed_client: AsyncClient, bad: str) -> None:
    resp = await authed_client.post("/api/planning/events", json={**EV, "date": bad})
    assert resp.status_code == 422
    ev = await _create(authed_client)
    resp = await authed_client.patch(f"/api/planning/events/{ev['id']}", json={"date": bad})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_blank_title_rejected(authed_client: AsyncClient) -> None:
    resp = await authed_client.post("/api/planning/events", json={**EV, "title": "   "})
    assert resp.status_code == 422
