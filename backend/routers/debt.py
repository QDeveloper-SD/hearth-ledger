from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from backend.routers.deps import SessionUser, Storedep
from backend.storage.schema import DebtAccount

router = APIRouter(prefix="/api/debts", tags=["debt"])


class DebtIn(BaseModel):
    name: str
    balance: float
    rate: float
    min_payment: float


@router.get("")
async def list_debts(store: Storedep, _user: SessionUser) -> dict:
    doc = store.read()
    return {"data": doc.get("debts", []), "error": None}


@router.post("", status_code=status.HTTP_201_CREATED)
async def add_debt(body: DebtIn, store: Storedep, _user: SessionUser) -> dict:
    item = DebtAccount(**body.model_dump())

    def _apply(d: dict) -> None:
        d["debts"].append(item.model_dump())

    store.mutate(_apply)
    return {"data": item.model_dump(), "error": None}


@router.patch("/{debt_id}")
async def edit_debt(debt_id: str, body: DebtIn, store: Storedep, _user: SessionUser) -> dict:
    updated: dict | None = None

    def _apply(d: dict) -> None:
        nonlocal updated
        for item in d["debts"]:
            if item["id"] == debt_id:
                item.update(body.model_dump())
                updated = item
                return

    store.mutate(_apply)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Debt not found")
    return {"data": updated, "error": None}


@router.delete("/{debt_id}")
async def delete_debt(debt_id: str, store: Storedep, _user: SessionUser) -> dict:
    found = False

    def _apply(d: dict) -> None:
        nonlocal found
        before = len(d["debts"])
        d["debts"] = [item for item in d["debts"] if item["id"] != debt_id]
        found = len(d["debts"]) < before

    store.mutate(_apply)
    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Debt not found")
    return {"data": None, "error": None}
