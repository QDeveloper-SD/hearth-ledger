from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from itsdangerous import URLSafeTimedSerializer

from backend.config import settings as _cfg
from backend.routers import auth, dashboard, debt, export, imports, income, ledger, planning, portfolio, risk
from backend.routers import settings as settings_router
from backend.storage.json_store import JsonStore

logger = logging.getLogger(__name__)


def _resolve_dist() -> Path:
    """Locate the built SPA: HEARTH_DIST_DIR, frozen bundle, or <repo>/dist."""
    env = os.environ.get("HEARTH_DIST_DIR")
    if env:
        return Path(env)
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        for cand in (base / "dist", Path(sys.executable).parent / "dist",
                     Path(sys.executable).parent.parent / "dist"):
            if cand.is_dir():
                return cand
        return base / "dist"
    return Path(__file__).resolve().parent.parent / "dist"


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
        imports.router,
    ]:
        app.include_router(router)

    @app.get("/api/health", include_in_schema=False)
    async def health() -> dict[str, bool]:
        return {"ok": True}

    dist = _resolve_dist()
    if (dist / "assets").is_dir():
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
