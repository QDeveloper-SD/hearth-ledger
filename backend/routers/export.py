from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import Response
from pydantic import BaseModel

from backend.routers.deps import SessionUser, Storedep
from backend.services.pdf import build_pdf

router = APIRouter(prefix="/api/export", tags=["export"])


class PdfRequest(BaseModel):
    sections: list[str] = ["balance", "ledger", "portfolio"]


@router.post("/pdf")
async def export_pdf(body: PdfRequest, store: Storedep, _user: SessionUser) -> Response:
    doc = store.read()
    pdf_bytes = build_pdf(doc, body.sections)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="hearth-export.pdf"'},
    )
