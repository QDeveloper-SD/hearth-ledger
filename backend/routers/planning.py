from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from backend.routers.deps import SessionUser, Storedep
from backend.storage.schema import PlanningEvent

router = APIRouter(prefix="/api/planning", tags=["planning"])


class EventIn(BaseModel):
    title: str
    date: str
    amount: float | None = None
    notes: str | None = None


@router.get("/events")
async def list_events(store: Storedep, _user: SessionUser) -> dict:
    doc = store.read()
    return {"data": doc.get("planning", {}).get("events", []), "error": None}


@router.post("/events", status_code=status.HTTP_201_CREATED)
async def add_event(body: EventIn, store: Storedep, _user: SessionUser) -> dict:
    event = PlanningEvent(**body.model_dump())

    def _apply(d: dict) -> None:
        d["planning"]["events"].append(event.model_dump())

    store.mutate(_apply)
    return {"data": event.model_dump(), "error": None}


@router.patch("/events/{event_id}")
async def edit_event(event_id: str, body: EventIn, store: Storedep, _user: SessionUser) -> dict:
    updated: dict | None = None

    def _apply(d: dict) -> None:
        nonlocal updated
        for ev in d["planning"]["events"]:
            if ev["id"] == event_id:
                ev.update({k: v for k, v in body.model_dump().items() if v is not None})
                updated = ev
                return

    store.mutate(_apply)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return {"data": updated, "error": None}


@router.delete("/events/{event_id}")
async def delete_event(event_id: str, store: Storedep, _user: SessionUser) -> dict:
    found = False

    def _apply(d: dict) -> None:
        nonlocal found
        before = len(d["planning"]["events"])
        d["planning"]["events"] = [ev for ev in d["planning"]["events"] if ev["id"] != event_id]
        found = len(d["planning"]["events"]) < before

    store.mutate(_apply)
    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return {"data": None, "error": None}
