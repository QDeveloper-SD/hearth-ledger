from __future__ import annotations

import json
import logging
import secrets
from pathlib import Path
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from backend.config import settings
from backend.storage.json_store import JsonStore

logger = logging.getLogger(__name__)

_COOKIE_NAME = "hearth_session"
_MAX_AGE = 60 * 60 * 24 * 7  # 7 days


def _load_secret(config_path: Path) -> str:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if config_path.exists():
        try:
            return json.loads(config_path.read_text())["secret"]
        except (KeyError, json.JSONDecodeError):
            pass
    secret = secrets.token_urlsafe(32)
    config_path.write_text(json.dumps({"secret": secret}, indent=2))
    return secret


def get_secret() -> str:
    return _load_secret(settings.config_json)


def get_store(request: Request) -> JsonStore:
    return request.app.state.store


def get_signer(request: Request) -> URLSafeTimedSerializer:
    return request.app.state.signer


def require_session(
    request: Request,
    hearth_session: Annotated[str | None, Cookie()] = None,
) -> str:
    signer: URLSafeTimedSerializer = request.app.state.signer
    if hearth_session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        username = signer.loads(hearth_session, max_age=_MAX_AGE)
    except (BadSignature, SignatureExpired):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session invalid or expired")
    return username


SessionUser = Annotated[str, Depends(require_session)]
Storedep = Annotated[JsonStore, Depends(get_store)]
