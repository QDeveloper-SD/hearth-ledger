from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.routers.deps import SessionUser, Storedep
from backend.storage.schema import IbkrCache

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsPatch(BaseModel):
    live_sync: bool | None = None
    theme: str | None = None


class ApiKeyBody(BaseModel):
    api_key: str = Field(min_length=1)


class IbkrBody(BaseModel):
    token: str = Field(min_length=1, max_length=200)
    query_id: str = Field(min_length=1, max_length=40, pattern=r"^\s*\d+\s*$")


@router.get("")
async def get_settings(store: Storedep, _user: SessionUser) -> dict:
    doc = store.read()
    s = doc.get("settings", {})
    # Never expose the raw api key value
    return {
        "data": {
            "data_dir": str(store.data_dir),
            "username": doc.get("auth", {}).get("username", ""),
            "live_sync": s.get("live_sync", True),
            "theme": s.get("theme", "light"),
            "has_api_key": bool(s.get("public_api_key_enc")),
            "has_ibkr": bool(s.get("ibkr_flex_token_enc") and s.get("ibkr_flex_query_id")),
            "ibkr_query_id": s.get("ibkr_flex_query_id") or "",
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


@router.delete("/api-key")
async def delete_api_key(store: Storedep, _user: SessionUser) -> dict:
    def _apply(d: dict) -> None:
        d["settings"]["public_api_key_enc"] = None

    store.mutate(_apply)
    return {"data": {"has_api_key": False}, "error": None}


@router.post("/ibkr")
async def set_ibkr(body: IbkrBody, store: Storedep, _user: SessionUser) -> dict:
    """Store the IBKR Flex Web Service token + Flex Query ID (read-only reporting access)."""
    token, query_id = body.token.strip(), body.query_id.strip()
    if not token:
        raise HTTPException(status_code=422, detail="Flex token is required")

    def _apply(d: dict) -> None:
        d["settings"]["ibkr_flex_token_enc"] = token
        d["settings"]["ibkr_flex_query_id"] = query_id

    store.mutate(_apply)
    return {"data": {"has_ibkr": True, "ibkr_query_id": query_id}, "error": None}


@router.delete("/ibkr")
async def delete_ibkr(store: Storedep, _user: SessionUser) -> dict:
    """Disconnect IBKR: forget the token and drop the synced positions."""
    def _apply(d: dict) -> None:
        d["settings"]["ibkr_flex_token_enc"] = None
        d["settings"]["ibkr_flex_query_id"] = None
        d["portfolio"]["ibkr_cache"] = IbkrCache().model_dump()

    store.mutate(_apply)
    return {"data": {"has_ibkr": False, "ibkr_query_id": ""}, "error": None}
