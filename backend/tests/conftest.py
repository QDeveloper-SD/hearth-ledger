from __future__ import annotations

import json
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.app import create_app
from backend.storage.json_store import JsonStore


@pytest.fixture()
def store(tmp_path: Path) -> JsonStore:
    return JsonStore(tmp_path)


@pytest.fixture()
def app(tmp_path: Path):
    return create_app(data_dir=tmp_path)


@pytest_asyncio.fixture()
async def authed_client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/auth/login", json={"username": "admin", "password": "password"})
        assert resp.status_code == 200
        yield client
