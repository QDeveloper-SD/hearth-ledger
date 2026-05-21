from __future__ import annotations

import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def build_pdf(doc: dict, sections: list[str]) -> bytes:
    buffer = io.BytesIO()
    pdf = SimpleDocTemplate(buffer, pagesize=LETTER, leftMargin=inch, rightMargin=inch)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("Hearth Ledger — Export", styles["Title"]))
    story.append(Paragraph(f"Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", styles["Normal"]))
    story.append(Spacer(1, 0.2 * inch))

    _style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f4fa")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cccccc")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])

    if "balance" in sections:
        story.append(Paragraph("Balance Sheet", styles["Heading2"]))
        debts = doc.get("debts", [])
        rows = [["Name", "Balance", "Rate", "Min Payment"]]
        for d in debts:
            rows.append([
                d.get("name", ""),
                f"${d.get('balance', 0):,.2f}",
                f"{d.get('rate', 0) * 100:.2f}%",
                f"${d.get('min_payment', 0):,.2f}",
            ])
        if len(rows) > 1:
            t = Table(rows, colWidths=[2.5 * inch, 1.5 * inch, 1 * inch, 1.5 * inch])
            t.setStyle(_style)
            story.append(t)
        else:
            story.append(Paragraph("No debt accounts.", styles["Normal"]))
        story.append(Spacer(1, 0.2 * inch))

    if "ledger" in sections:
        story.append(Paragraph("Ledger", styles["Heading2"]))
        entries = doc.get("ledger", [])
        rows = [["Date", "Description", "Category", "Amount"]]
        for e in entries:
            rows.append([
                e.get("date", ""),
                e.get("desc", "")[:50],
                e.get("category", ""),
                f"${e.get('amount', 0):,.2f}",
            ])
        if len(rows) > 1:
            t = Table(rows, colWidths=[1 * inch, 3 * inch, 1.5 * inch, 1 * inch])
            t.setStyle(_style)
            story.append(t)
        else:
            story.append(Paragraph("No ledger entries.", styles["Normal"]))
        story.append(Spacer(1, 0.2 * inch))

    if "portfolio" in sections:
        story.append(Paragraph("Portfolio — Manual Holdings", styles["Heading2"]))
        holdings = doc.get("portfolio", {}).get("manual_holdings", [])
        rows = [["Symbol", "Qty", "Cost Basis"]]
        for h in holdings:
            rows.append([
                h.get("symbol", ""),
                str(h.get("qty", 0)),
                f"${h.get('cost_basis', 0):,.2f}",
            ])
        if len(rows) > 1:
            t = Table(rows, colWidths=[2 * inch, 2 * inch, 2.5 * inch])
            t.setStyle(_style)
            story.append(t)
        else:
            story.append(Paragraph("No manual holdings.", styles["Normal"]))

    pdf.build(story)
    return buffer.getvalue()
