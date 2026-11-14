from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_fresh_install_requires_setup_and_has_no_default_login(app) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        assert (await c.get("/api/auth/status")).json()["data"] == {"needs_setup": True}
        # the old default credentials must not work
        r = await c.post("/api/auth/login", json={"username": "admin", "password": "password"})
        assert r.status_code == 403
        assert (await c.get("/api/settings")).status_code == 401

        assert (await c.post("/api/auth/setup", json={"username": " ", "password": "longenough"})).status_code == 400
        assert (await c.post("/api/auth/setup", json={"username": "fam", "password": "short"})).status_code == 400
        assert (await c.get("/api/auth/status")).json()["data"] == {"needs_setup": True}

        r = await c.post("/api/auth/setup", json={"username": " fam ", "password": "correct horse"})
        assert r.status_code == 200 and r.json()["data"]["username"] == "fam"
        # setup signs in
        assert (await c.get("/api/settings")).json()["data"]["username"] == "fam"
        assert (await c.get("/api/auth/status")).json()["data"] == {"needs_setup": False}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # setup cannot be used to take over an existing install
        r = await c.post("/api/auth/setup", json={"username": "evil", "password": "another one"})
        assert r.status_code == 409
        assert (await c.post("/api/auth/login", json={"username": "evil", "password": "another one"})).status_code == 401
        assert (await c.post("/api/auth/login", json={"username": "fam", "password": "correct horse"})).status_code == 200
