from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from backend.routers.deps import SessionUser, Storedep

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsPatch(BaseModel):
    data_dir: str | None = None
    live_sync: bool | None = None
    theme: str | None = None


class ApiKeyBody(BaseModel):
    api_key: str


@router.get("")
async def get_settings(store: Storedep, _user: SessionUser) -> dict:
    doc = store.read()
    s = doc.get("settings", {})
    # Never expose the raw api key value
    return {
        "data": {
            "data_dir": s.get("data_dir"),
            "live_sync": s.get("live_sync", True),
            "theme": s.get("theme", "light"),
            "has_api_key": bool(s.get("public_api_key_enc")),
        },
        "error": None,
    }


@router.patch("")
async def update_settings(body: SettingsPatch, store: Storedep, _user: SessionUser) -> dict:
    patch = {k: v for k, v in body.model_dump().items() if v is not None}

    def _apply(d: dict) -> None:
        d["settings"].update(patch)

    store.mutate(_apply)
    return await get_settings(store, _user)


@router.post("/api-key")
async def set_api_key(body: ApiKeyBody, store: Storedep, _user: SessionUser) -> dict:
    def _apply(d: dict) -> None:
        d["settings"]["public_api_key_enc"] = body.api_key

    store.mutate(_apply)
    return {"data": {"has_api_key": True}, "error": None}
