from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from backend.storage.json_store import JsonStore


async def _login(app, user: str, pw: str) -> int:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        return (await c.post("/api/auth/login", json={"username": user, "password": pw})).status_code


@pytest.mark.asyncio
async def test_settings_fields(authed_client: AsyncClient, tmp_path: Path) -> None:
    data = (await authed_client.get("/api/settings")).json()["data"]
    assert data["username"] == "admin"
    assert data["has_api_key"] is False
    assert data["data_dir"] == str(tmp_path.resolve())
    assert Path(data["data_dir"]).is_absolute()


def test_store_data_dir(tmp_path: Path) -> None:
    assert JsonStore(tmp_path).data_dir == tmp_path.resolve()


@pytest.mark.asyncio
async def test_api_key_save_and_delete(authed_client: AsyncClient) -> None:
    r = await authed_client.post("/api/settings/api-key", json={"api_key": "s3cret-value"})
    assert r.status_code == 200
    got = await authed_client.get("/api/settings")
    assert got.json()["data"]["has_api_key"] is True
    assert "s3cret-value" not in got.text
    assert (await authed_client.post("/api/settings/api-key", json={"key": "x"})).status_code == 422
    assert (await authed_client.post("/api/settings/api-key", json={"api_key": ""})).status_code == 422
    d = await authed_client.delete("/api/settings/api-key")
    assert d.status_code == 200
    assert (await authed_client.get("/api/settings")).json()["data"]["has_api_key"] is False


@pytest.mark.asyncio
async def test_patch_theme_and_live_sync(authed_client: AsyncClient) -> None:
    r = await authed_client.patch("/api/settings", json={"theme": "dark", "live_sync": False})
    assert r.json()["data"]["theme"] == "dark"
    assert r.json()["data"]["live_sync"] is False


@pytest.mark.asyncio
async def test_change_password_fresh_store(app, authed_client: AsyncClient) -> None:
    r = await authed_client.post(
        "/api/auth/password", json={"current_password": "password", "new_password": "new-pass-123"}
    )
    assert r.status_code == 200
    assert await _login(app, "admin", "new-pass-123") == 200
    assert await _login(app, "admin", "password") == 401


@pytest.mark.asyncio
async def test_change_password_wrong_current(app, authed_client: AsyncClient) -> None:
    r = await authed_client.post(
        "/api/auth/password", json={"current_password": "nope", "new_password": "new-pass-123"}
    )
    assert r.status_code == 400
    assert "incorrect" in r.json()["detail"].lower()
    assert await _login(app, "admin", "password") == 200


@pytest.mark.asyncio
async def test_change_password_too_short(authed_client: AsyncClient) -> None:
    r = await authed_client.post(
        "/api/auth/password", json={"current_password": "password", "new_password": "short"}
    )
    assert r.status_code == 400
    assert "8" in r.json()["detail"]


@pytest.mark.asyncio
async def test_password_and_username_require_session(app) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r1 = await c.post("/api/auth/password", json={"current_password": "password", "new_password": "abcdefgh"})
        r2 = await c.post("/api/auth/username", json={"username": "bob"})
    assert r1.status_code == 401
    assert r2.status_code == 401


@pytest.mark.asyncio
async def test_change_username(app, authed_client: AsyncClient) -> None:
    r = await authed_client.post("/api/auth/username", json={"username": "  alice  "})
    assert r.status_code == 200
    assert r.json()["data"]["username"] == "alice"
    assert "hearth_session" in r.headers.get("set-cookie", "")
    # session still valid under the new name, and settings reflect it
    got = await authed_client.get("/api/settings")
    assert got.status_code == 200
    assert got.json()["data"]["username"] == "alice"
    assert await _login(app, "alice", "password") == 200
    assert await _login(app, "admin", "password") == 401


@pytest.mark.asyncio
async def test_change_username_empty(authed_client: AsyncClient) -> None:
    r = await authed_client.post("/api/auth/username", json={"username": "   "})
    assert r.status_code == 400
