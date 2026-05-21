from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from itsdangerous import URLSafeTimedSerializer

from backend.config import settings as _cfg
from backend.routers import auth, dashboard, debt, export, income, ledger, planning, portfolio, risk
from backend.routers import settings as settings_router
from backend.storage.json_store import JsonStore

logger = logging.getLogger(__name__)


def create_app(data_dir: Path | None = None) -> FastAPI:
    resolved_dir = data_dir or _cfg.data_path
    resolved_dir.mkdir(parents=True, exist_ok=True)

    secret = _bootstrap_secret(resolved_dir / "config.json")

    app = FastAPI(title="Hearth Ledger", version="0.1.0")
    app.state.store = JsonStore(resolved_dir)
    app.state.signer = URLSafeTimedSerializer(secret)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    for router in [
        auth.router,
        dashboard.router,
        ledger.router,
        debt.router,
        income.router,
        portfolio.router,
        risk.router,
        planning.router,
        settings_router.router,
        export.router,
    ]:
        app.include_router(router)

    dist = Path("dist")
    if dist.is_dir():
        app.mount("/assets", StaticFiles(directory=str(dist / "assets")), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(full_path: str) -> FileResponse:
            candidate = dist / full_path
            if candidate.is_file():
                return FileResponse(str(candidate))
            return FileResponse(str(dist / "index.html"))

    return app


def _bootstrap_secret(config_path: Path) -> str:
    import json
    import secrets

    config_path.parent.mkdir(parents=True, exist_ok=True)
    if config_path.exists():
        try:
            return json.loads(config_path.read_text())["secret"]
        except (KeyError, Exception):
            pass
    secret = secrets.token_urlsafe(32)
    config_path.write_text(json.dumps({"secret": secret}, indent=2))
    return secret
