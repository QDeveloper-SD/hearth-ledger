from __future__ import annotations

import logging
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from backend.routers.deps import SessionUser, Storedep
from backend.storage.schema import LedgerEntry

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ledger", tags=["ledger"])


class EntryIn(BaseModel):
    date: str
    desc: str
    category: str
    amount: float


@router.get("")
async def list_entries(
    store: Storedep,
    _user: SessionUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    category: Optional[str] = None,
) -> dict:
    doc = store.read()
    entries = doc.get("ledger", [])
    if category:
        entries = [e for e in entries if e.get("category") == category]
    entries = sorted(entries, key=lambda e: e.get("date", ""), reverse=True)
    total = len(entries)
    start = (page - 1) * page_size
    return {
        "data": {
            "entries": entries[start: start + page_size],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        "error": None,
    }


@router.get("/summary")
async def ledger_summary(store: Storedep, _user: SessionUser) -> dict:
    doc = store.read()
    entries = doc.get("ledger", [])

    by_category: dict[str, float] = defaultdict(float)
    by_month: dict[str, float] = defaultdict(float)
    for e in entries:
        by_category[e.get("category", "Uncategorized")] += e.get("amount", 0.0)
        month = e.get("date", "")[:7]
        by_month[month] += e.get("amount", 0.0)

    return {
        "data": {
            "by_category": dict(by_category),
            "monthly_trend": dict(sorted(by_month.items())),
        },
        "error": None,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def add_entry(body: EntryIn, store: Storedep, _user: SessionUser) -> dict:
    entry = LedgerEntry(**body.model_dump())

    def _apply(d: dict) -> None:
        d["ledger"].append(entry.model_dump())

    store.mutate(_apply)
    return {"data": entry.model_dump(), "error": None}


@router.patch("/{entry_id}")
async def edit_entry(entry_id: str, body: EntryIn, store: Storedep, _user: SessionUser) -> dict:
    updated: dict | None = None

    def _apply(d: dict) -> None:
        nonlocal updated
        for e in d["ledger"]:
            if e["id"] == entry_id:
                e.update(body.model_dump())
                updated = e
                return

    store.mutate(_apply)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    return {"data": updated, "error": None}


@router.delete("/{entry_id}")
async def delete_entry(entry_id: str, store: Storedep, _user: SessionUser) -> dict:
    found = False

    def _apply(d: dict) -> None:
        nonlocal found
        before = len(d["ledger"])
        d["ledger"] = [e for e in d["ledger"] if e["id"] != entry_id]
        found = len(d["ledger"]) < before

    store.mutate(_apply)
    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    return {"data": None, "error": None}
