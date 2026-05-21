from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from backend.routers.deps import SessionUser, Storedep
from backend.storage.schema import IncomeSource

router = APIRouter(prefix="/api/income", tags=["income"])


class IncomeIn(BaseModel):
    name: str
    amount: float
    cadence: str


@router.get("")
async def list_income(store: Storedep, _user: SessionUser) -> dict:
    doc = store.read()
    return {"data": doc.get("income_sources", []), "error": None}


@router.post("", status_code=status.HTTP_201_CREATED)
async def add_income(body: IncomeIn, store: Storedep, _user: SessionUser) -> dict:
    item = IncomeSource(**body.model_dump())

    def _apply(d: dict) -> None:
        d["income_sources"].append(item.model_dump())

    store.mutate(_apply)
    return {"data": item.model_dump(), "error": None}


@router.patch("/{income_id}")
async def edit_income(income_id: str, body: IncomeIn, store: Storedep, _user: SessionUser) -> dict:
    updated: dict | None = None

    def _apply(d: dict) -> None:
        nonlocal updated
        for item in d["income_sources"]:
            if item["id"] == income_id:
                item.update(body.model_dump())
                updated = item
                return

    store.mutate(_apply)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Income source not found")
    return {"data": updated, "error": None}


@router.delete("/{income_id}")
async def delete_income(income_id: str, store: Storedep, _user: SessionUser) -> dict:
    found = False

    def _apply(d: dict) -> None:
        nonlocal found
        before = len(d["income_sources"])
        d["income_sources"] = [item for item in d["income_sources"] if item["id"] != income_id]
        found = len(d["income_sources"]) < before

    store.mutate(_apply)
    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Income source not found")
    return {"data": None, "error": None}
