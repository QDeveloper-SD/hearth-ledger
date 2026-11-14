from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from backend.routers.deps import SessionUser, Storedep
from backend.services import importer
from backend.storage.schema import DebtAccount, IncomeSource, LedgerEntry

router = APIRouter(prefix="/api/import", tags=["import"])

_MODELS = {"ledger": LedgerEntry, "debts": DebtAccount, "income": IncomeSource}


@router.post("/{kind}")
async def import_file(
    kind: str,
    store: Storedep,
    _user: SessionUser,
    file: UploadFile = File(...),
    dry_run: bool = True,
) -> dict:
    if kind not in _MODELS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown import kind '{kind}'")
    data = await file.read(importer.MAX_BYTES + 1)
    try:
        rows = importer.read_rows(file.filename or "", data)
        key = importer.store_key(kind)
        if dry_run:
            res = importer.parse_and_validate(kind, rows, store.read().get(key, []))
            imported = 0
        else:
            holder: dict = {}

            def _apply(d: dict) -> None:
                res_ = importer.parse_and_validate(kind, rows, d.get(key, []))
                holder["res"] = res_
                d.setdefault(key, []).extend(_MODELS[kind](**r).model_dump() for r in res_.valid)

            store.mutate(_apply)
            res = holder["res"]
            imported = len(res.valid)
    except importer.ImportError_ as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {
        "data": {
            "kind": kind,
            "dry_run": dry_run,
            "total_rows": res.total_rows,
            "valid_count": len(res.valid),
            "duplicate_count": res.duplicates,
            "error_count": res.error_count,
            "imported_count": imported,
            "preview": res.valid[: importer.PREVIEW_ROWS],
            "errors": res.errors,
            "errors_truncated": res.error_count > len(res.errors),
            "columns_found": res.columns_found,
        },
        "error": None,
    }
