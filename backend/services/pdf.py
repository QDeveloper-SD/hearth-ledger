from __future__ import annotations

import io
from collections import OrderedDict
from datetime import datetime, timezone
from xml.sax.saxutils import escape

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from backend.services.metrics import (
    asset_values,
    business_stake,
    fixed_income_value,
    monthly_income,
    net_worth,
    position_value,
)

NAVY = colors.HexColor("#1e3a5f")
INK = colors.HexColor("#1f2937")
MUTED = colors.HexColor("#6b7280")
ZEBRA = colors.HexColor("#f3f6fb")
RULE = colors.HexColor("#d5dce8")
RED = colors.HexColor("#b91c1c")
GREEN = colors.HexColor("#15803d")
PALETTE = [
    colors.HexColor("#1e3a5f"),
    colors.HexColor("#2f80b7"),
    colors.HexColor("#4cb5a0"),
    colors.HexColor("#e0a030"),
    colors.HexColor("#c0564b"),
    colors.HexColor("#8a6fb5"),
]

MARGIN = 0.75 * inch
CONTENT_W = LETTER[0] - 2 * MARGIN

_base = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=_base["Title"], fontName="Helvetica-Bold", fontSize=20,
                    leading=24, textColor=NAVY, alignment=0, spaceAfter=2)
SUB = ParagraphStyle("Sub", parent=_base["Normal"], fontSize=9, textColor=MUTED, spaceAfter=10)
H2 = ParagraphStyle("H2", parent=_base["Heading2"], fontName="Helvetica-Bold", fontSize=13,
                    textColor=NAVY, spaceBefore=14, spaceAfter=6)
H3 = ParagraphStyle("H3", parent=_base["Heading3"], fontName="Helvetica-Bold", fontSize=10,
                    textColor=INK, spaceBefore=8, spaceAfter=4)
BODY = ParagraphStyle("Body", parent=_base["Normal"], fontSize=9, textColor=INK)
EMPTY = ParagraphStyle("Empty", parent=BODY, textColor=MUTED, fontName="Helvetica-Oblique",
                       spaceAfter=6)
CELL = ParagraphStyle("Cell", parent=BODY, fontSize=8.5, leading=10.5)
CARD_LABEL = ParagraphStyle("CardLabel", parent=BODY, fontSize=7.5, textColor=MUTED, leading=9)
CARD_VALUE = ParagraphStyle("CardValue", parent=BODY, fontName="Helvetica-Bold", fontSize=15, leading=19)
RIGHT = ParagraphStyle("Right", parent=CELL, alignment=TA_RIGHT)


def _num(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def money(v) -> str:
    v = _num(v)
    s = f"${abs(v):,.2f}"
    return f"-{s}" if round(v, 2) < 0 else s


def _money_cell(v) -> Paragraph:
    """Money paragraph, red when negative."""
    col = "#b91c1c" if round(_num(v), 2) < 0 else "#1f2937"
    return Paragraph(f'<font color="{col}">{escape(money(v))}</font>', RIGHT)


def _txt(v, limit: int | None = None) -> Paragraph:
    s = str(v if v is not None else "")
    if limit and len(s) > limit:
        s = s[: limit - 1] + "…"
    return Paragraph(escape(s), CELL)


def _table(header: list[str], rows: list[list], widths: list[float], right_cols: set[int],
           footer: list | None = None) -> Table:
    head = [Paragraph(f'<font color="white"><b>{escape(h)}</b></font>',
                      RIGHT if i in right_cols else CELL) for i, h in enumerate(header)]
    data = [head] + rows + ([footer] if footer else [])
    t = Table(data, colWidths=widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, RULE),
    ]
    body_end = -2 if footer else -1
    if len(data) > 1:
        style.append(("ROWBACKGROUNDS", (0, 1), (-1, body_end), [colors.white, ZEBRA]))
    if footer:
        style += [("LINEABOVE", (0, -1), (-1, -1), 1, NAVY),
                  ("BACKGROUND", (0, -1), (-1, -1), colors.white)]
    t.setStyle(TableStyle(style))
    return t


def _scale(widths: list[float]) -> list[float]:
    total = sum(widths)
    return [w / total * CONTENT_W for w in widths]


# ---------------------------------------------------------------- figures

def _assets(doc: dict) -> list[tuple[str, float]]:
    """Asset allocation (assets only); same valuation as net worth, so everything agrees."""
    v = asset_values(doc)
    out = [("Public.com", v["public"]), ("Investments (other)", v["manual"]),
           ("IBKR", v["ibkr"]), ("Other brokers", v["other_brokers"]),
           ("Fixed income", v["fixed_income"]), ("Real estate", v["real_estate"]),
           ("Businesses", v["businesses"]), ("Cash", v["cash"])]
    return [(n, x) for n, x in out if x > 0]


def _total_debt(doc: dict) -> float:
    return sum(abs(_num(d.get("balance"))) for d in doc.get("debts", []))


def _monthly_flow(doc: dict, limit: int = 6) -> list[tuple[str, float, float]]:
    months: "OrderedDict[str, list[float]]" = OrderedDict()
    for e in sorted(doc.get("ledger", []), key=lambda e: e.get("date", "")):
        key = str(e.get("date", ""))[:7]
        if len(key) != 7:
            continue
        inc_exp = months.setdefault(key, [0.0, 0.0])
        a = _num(e.get("amount"))
        if a >= 0:
            inc_exp[0] += a
        else:
            inc_exp[1] += -a
    items = [(k, v[0], v[1]) for k, v in months.items()]
    return items[-limit:]


# ---------------------------------------------------------------- charts

def _pie(data: list[tuple[str, float]], w: float, h: float = 150) -> Drawing:
    d = Drawing(w, h)
    d.add(String(0, h - 10, "Asset allocation", fontName="Helvetica-Bold", fontSize=9, fillColor=INK))
    pie = Pie()
    size = 100
    pie.x, pie.y, pie.width, pie.height = 4, (h - 18 - size) / 2, size, size
    pie.data = [v for _, v in data]
    pie.labels = None
    pie.sideLabels = 0
    pie.simpleLabels = 1
    pie.slices.strokeColor = colors.white
    pie.slices.strokeWidth = 1
    for i in range(len(data)):
        pie.slices[i].fillColor = PALETTE[i % len(PALETTE)]
    d.add(pie)
    total = sum(v for _, v in data) or 1
    y = h - 40
    for i, (name, v) in enumerate(data[:6]):
        d.add(Rect(120, y, 8, 8, fillColor=PALETTE[i % len(PALETTE)], strokeColor=None))
        d.add(String(133, y, f"{name[:16]}  {v / total * 100:.0f}%", fontName="Helvetica",
                     fontSize=8, fillColor=INK))
        y -= 16
    return d


def _bars(title: str, cats: list[str], series: list[list[float]], names: list[str],
          w: float, h: float = 150) -> Drawing:
    d = Drawing(w, h)
    d.add(String(0, h - 10, title, fontName="Helvetica-Bold", fontSize=9, fillColor=INK))
    bc = VerticalBarChart()
    bc.x, bc.y, bc.width, bc.height = 44, 22, w - 54, h - 52
    bc.data = series
    bc.categoryAxis.categoryNames = cats
    bc.categoryAxis.labels.fontSize = 7
    bc.categoryAxis.labels.dy = -2
    bc.categoryAxis.strokeColor = RULE
    bc.valueAxis.labels.fontSize = 7
    bc.valueAxis.labelTextFormat = lambda v: f"${v:,.0f}"
    bc.valueAxis.valueMin = 0
    bc.valueAxis.strokeColor = RULE
    bc.valueAxis.gridStrokeColor = RULE
    bc.valueAxis.visibleGrid = 1
    bc.bars.strokeColor = None
    for i in range(len(series)):
        bc.bars[i].fillColor = PALETTE[[2, 4, 0][i] if len(series) == 2 and i < 2 else i]
    bc.groupSpacing = 6
    bc.barSpacing = 1
    d.add(bc)
    if len(series) > 1:
        x = w - 100
        for i, n in enumerate(names):
            d.add(Rect(x, h - 11, 7, 7, fillColor=bc.bars[i].fillColor, strokeColor=None))
            d.add(String(x + 10, h - 10, n, fontName="Helvetica", fontSize=7.5, fillColor=INK))
            x += 50
    return d


def _charts(doc: dict) -> Table | None:
    half = CONTENT_W / 2 - 6
    left = right = None
    assets = _assets(doc)
    if assets:
        left = _pie(assets, half)
    flow = _monthly_flow(doc)
    debts = [(d.get("name", "?"), abs(_num(d.get("balance")))) for d in doc.get("debts", [])]
    debts = [x for x in debts if x[1] > 0]
    if flow:
        right = _bars("Income vs. spending by month", [m for m, _, _ in flow],
                      [[i for _, i, _ in flow], [e for _, _, e in flow]],
                      ["Income", "Spending"], half)
    elif debts:
        debts.sort(key=lambda x: -x[1])
        debts = debts[:6]
        right = _bars("Debt by balance", [n[:10] for n, _ in debts], [[v for _, v in debts]],
                      ["Balance"], half)
    if left is None and right is None:
        return None
    t = Table([[left or "", right or ""]], colWidths=[CONTENT_W / 2] * 2)
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return t


def _cards(doc: dict) -> Table:
    nw = net_worth(doc)
    debt = _total_debt(doc)
    assets = nw + debt
    items = [("NET WORTH", nw), ("TOTAL ASSETS", assets), ("TOTAL DEBT", -debt),
             ("MONTHLY INCOME", monthly_income(doc))]
    cells = []
    for label, v in items:
        col = "#b91c1c" if round(v, 2) < 0 else "#1e3a5f"
        cells.append([Paragraph(label, CARD_LABEL),
                      Paragraph(f'<font color="{col}">{escape(money(v))}</font>', CARD_VALUE)])
    gap = 8
    w = (CONTENT_W - 3 * gap) / 4
    row, widths = [], []
    for i, c in enumerate(cells):
        inner = Table([[c[0]], [c[1]]], colWidths=[w])
        inner.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.6, RULE),
            ("BACKGROUND", (0, 0), (-1, -1), ZEBRA),
            ("LINEABOVE", (0, 0), (-1, 0), 2.5, NAVY),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        row.append(inner)
        widths.append(w)
        if i < 3:
            row.append("")
            widths.append(gap)
    t = Table([row], colWidths=widths)
    t.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                           ("TOPPADDING", (0, 0), (-1, -1), 0),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    return t


# ---------------------------------------------------------------- sections

def _empty(msg: str) -> Paragraph:
    return Paragraph(msg, EMPTY)


def _balance(doc: dict) -> list:
    out: list = [Paragraph("Balance Sheet", H2)]
    pf = doc.get("portfolio", {}) or {}
    assets = _assets(doc)
    out.append(Paragraph("Assets", H3))
    if assets:
        rows = [[_txt(n), _money_cell(v)] for n, v in assets]
        foot = [Paragraph("<b>Total assets</b>", CELL),
                Paragraph(f"<b>{escape(money(sum(v for _, v in assets)))}</b>", RIGHT)]
        out.append(_table(["Category", "Value"], rows, _scale([3, 1.2]), {1}, foot))
    else:
        out.append(_empty("No entries yet."))
    cash = pf.get("cash_accounts", [])
    if cash:
        out.append(Paragraph("Cash accounts", H3))
        out.append(_table(["Account", "Balance"],
                          [[_txt(c.get("name")), _money_cell(c.get("balance"))] for c in cash],
                          _scale([3, 1.2]), {1}))
    debts = doc.get("debts", [])
    out.append(Paragraph("Debts", H3))
    if debts:
        rows = [[_txt(d.get("name")), _money_cell(-abs(_num(d.get("balance")))),
                 Paragraph(f"{_num(d.get('rate')) * 100:.2f}%", RIGHT),
                 _money_cell(d.get("min_payment"))] for d in debts]
        foot = [Paragraph("<b>Total debt</b>", CELL),
                Paragraph(f'<font color="#b91c1c"><b>{escape(money(-_total_debt(doc)))}</b></font>', RIGHT),
                "", Paragraph(f"<b>{escape(money(sum(_num(d.get('min_payment')) for d in debts)))}</b>", RIGHT)]
        out.append(_table(["Name", "Balance", "Rate", "Min payment"], rows,
                          _scale([3, 1.4, 0.8, 1.4]), {1, 2, 3}, foot))
    else:
        out.append(_empty("No debt accounts yet."))
    return out


def _income(doc: dict) -> list:
    out: list = [Paragraph("Income Sources", H2)]
    src = doc.get("income_sources", [])
    if not src:
        out.append(_empty("No entries yet."))
        return out
    rows = [[_txt(s.get("name")), _txt(str(s.get("cadence", "")).title()),
             _money_cell(s.get("amount"))] for s in src]
    foot = [Paragraph("<b>Monthly equivalent</b>", CELL), "",
            Paragraph(f"<b>{escape(money(monthly_income(doc)))}</b>", RIGHT)]
    out.append(_table(["Source", "Cadence", "Amount"], rows, _scale([3, 1.2, 1.4]), {2}, foot))
    return out


def _ledger(doc: dict) -> list:
    out: list = [Paragraph("Ledger", H2)]
    entries = sorted(doc.get("ledger", []), key=lambda e: e.get("date", ""), reverse=True)
    if not entries:
        out.append(_empty("No entries yet."))
        return out
    inc = sum(_num(e.get("amount")) for e in entries if _num(e.get("amount")) > 0)
    exp = sum(_num(e.get("amount")) for e in entries if _num(e.get("amount")) < 0)
    out.append(Paragraph(
        f'{len(entries):,} entries &nbsp;|&nbsp; income {escape(money(inc))} &nbsp;|&nbsp; '
        f'spending <font color="#b91c1c">{escape(money(exp))}</font>', SUB))
    rows = [[_txt(e.get("date")), _txt(e.get("desc"), 60), _txt(e.get("category"), 24),
             _money_cell(e.get("amount"))] for e in entries]
    out.append(_table(["Date", "Description", "Category", "Amount"], rows,
                      _scale([0.9, 3.2, 1.5, 1.2]), {3}))
    return out


def _positions_table(rows_in: list[dict], with_broker: bool = False) -> Table:
    header = ["Symbol"] + (["Broker"] if with_broker else []) + ["Qty", "Cost basis", "Current value"]
    rows = []
    for h in rows_in:
        rows.append([_txt(h.get("symbol"))] + ([_txt(h.get("broker") or "")] if with_broker else [])
                    + [Paragraph(f"{_num(h.get('qty')):,.4g}", RIGHT), _money_cell(h.get("cost_basis")),
                       _money_cell(position_value(h))])
    n = len(header)
    foot = [Paragraph("<b>Total</b>", CELL)] + [""] * (n - 2) + [
        Paragraph(f"<b>{escape(money(sum(position_value(h) for h in rows_in)))}</b>", RIGHT)]
    widths = _scale([2, 1.6, 1.2, 1.5, 1.5] if with_broker else [2, 1.2, 1.5, 1.5])
    return _table(header, rows, widths, {n - 3, n - 2, n - 1}, foot)


def _portfolio(doc: dict) -> list:
    out: list = [Paragraph("Portfolio", H2)]
    pf = doc.get("portfolio", {}) or {}
    cache = pf.get("public_cache", {}) or {}
    pub = cache.get("holdings") or []
    positions = pf.get("manual_holdings", [])
    manual = [h for h in positions if (h.get("account") or "manual") == "manual"]
    ibkr = [h for h in positions if h.get("account") == "ibkr"]
    other = [h for h in positions if h.get("account") == "other"]
    real_estate = pf.get("real_estate", [])
    businesses = pf.get("businesses", [])
    fixed = pf.get("fixed_income", [])
    cash = pf.get("cash_accounts", [])
    ibkr_cache = pf.get("ibkr_cache", {}) or {}
    ibkr_synced = ibkr_cache.get("holdings") or []
    if not (pub or ibkr_synced or positions or cash or real_estate or businesses or fixed):
        out.append(_empty("No entries yet."))
        return out
    out.append(Paragraph("Public.com holdings", H3))
    if pub:
        if cache.get("fetched_at"):
            out.append(Paragraph(f"Synced {escape(str(cache['fetched_at']))}", SUB))
        rows = []
        for h in pub:
            val = h.get("current_value")
            rows.append([_txt(h.get("symbol")), Paragraph(f"{_num(h.get('qty', h.get('quantity'))):,.4g}", RIGHT),
                         _money_cell(h.get("cost_basis")),
                         _money_cell(val if val is not None else h.get("cost_basis"))])
        out.append(_table(["Symbol", "Qty", "Cost basis", "Current value"], rows,
                          _scale([2, 1.2, 1.5, 1.5]), {1, 2, 3}))
    else:
        out.append(_empty("No synced brokerage holdings."))
    if ibkr_synced:
        out.append(Paragraph("IBKR holdings (synced)", H3))
        if ibkr_cache.get("fetched_at"):
            out.append(Paragraph(f"Synced {escape(str(ibkr_cache['fetched_at']))}", SUB))
        rows = [[_txt(h.get("symbol")), Paragraph(f"{_num(h.get('qty')):,.4g}", RIGHT),
                 _money_cell(h.get("cost_basis_total")), _money_cell(h.get("current_value"))]
                for h in ibkr_synced]
        if ibkr_cache.get("cash") is not None:
            rows.append([_txt("Cash"), Paragraph("", RIGHT), Paragraph("", RIGHT), _money_cell(ibkr_cache["cash"])])
        out.append(_table(["Symbol", "Qty", "Cost basis", "Current value"], rows,
                          _scale([2, 1.2, 1.5, 1.5]), {1, 2, 3}))
    for title, items, broker, msg in [
        ("Investments not on Public", manual, False, "No manual holdings."),
        ("IBKR", ibkr, False, None),
        ("Other brokers", other, True, None),
    ]:
        if items:
            out.append(Paragraph(title, H3))
            out.append(_positions_table(items, broker))
        elif msg:
            out.append(Paragraph(title, H3))
            out.append(_empty(msg))
    if fixed:
        out.append(Paragraph("Fixed-income securities", H3))
        rows = [[_txt(f.get("name")), _txt(f.get("issuer") or ""), _txt(f.get("maturity_date") or ""),
                 _money_cell(f.get("face_value")), _money_cell(fixed_income_value(f))] for f in fixed]
        foot = ["", "", "", "", Paragraph(f"<b>{escape(money(sum(fixed_income_value(f) for f in fixed)))}</b>", RIGHT)]
        out.append(_table(["Name", "Issuer", "Maturity", "Face value", "Current value"], rows,
                          _scale([2, 1.5, 1.1, 1.3, 1.3]), {3, 4}, foot))
    if real_estate:
        out.append(Paragraph("Real estate", H3))
        rows = [[_txt(r.get("name")), _txt(r.get("address") or "", 40),
                 _money_cell(r.get("purchase_price")) if r.get("purchase_price") is not None else _txt(""),
                 _money_cell(r.get("current_value"))] for r in real_estate]
        foot = ["", "", "", Paragraph(f"<b>{escape(money(sum(_num(r.get('current_value')) for r in real_estate)))}</b>", RIGHT)]
        out.append(_table(["Property", "Address", "Purchase price", "Current value"], rows,
                          _scale([2, 2.4, 1.4, 1.4]), {2, 3}, foot))
    if businesses:
        out.append(Paragraph("Businesses", H3))
        rows = [[_txt(b.get("name")), _money_cell(b.get("valuation")),
                 Paragraph(f"{_num(b.get('ownership_pct', 100)):.4g}%", RIGHT),
                 _money_cell(business_stake(b))] for b in businesses]
        foot = ["", "", "", Paragraph(f"<b>{escape(money(sum(business_stake(b) for b in businesses)))}</b>", RIGHT)]
        out.append(_table(["Business", "Valuation", "Ownership", "Your stake"], rows,
                          _scale([2.6, 1.5, 1, 1.5]), {1, 2, 3}, foot))
    out.append(Paragraph("Cash accounts", H3))
    if cash:
        rows = [[_txt(c.get("name")), _money_cell(c.get("balance"))] for c in cash]
        out.append(_table(["Account", "Balance"], rows, _scale([3, 1.5]), {1}))
    else:
        out.append(_empty("No cash accounts."))
    return out


# ---------------------------------------------------------------- build

def _decorate(generated: str):
    def _page(canvas, pdf_doc) -> None:
        canvas.saveState()
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN, 0.6 * inch, LETTER[0] - MARGIN, 0.6 * inch)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(MUTED)
        canvas.drawString(MARGIN, 0.42 * inch, "Hearth Ledger")
        canvas.drawCentredString(LETTER[0] / 2, 0.42 * inch, generated)
        canvas.drawRightString(LETTER[0] - MARGIN, 0.42 * inch, f"Page {pdf_doc.page}")
        canvas.restoreState()
    return _page


def build_pdf(doc: dict, sections: list[str]) -> bytes:
    buffer = io.BytesIO()
    generated = datetime.now(timezone.utc).strftime("Generated %Y-%m-%d %H:%M UTC")
    pdf = SimpleDocTemplate(
        buffer, pagesize=LETTER, leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=0.7 * inch, bottomMargin=0.85 * inch,
        title="Hearth Ledger — Household Financial Report", author="Hearth Ledger",
    )
    story: list = [
        Paragraph("Hearth Ledger — Household Financial Report", H1),
        Paragraph(generated, SUB),
        Paragraph("Summary", H2),
        _cards(doc),
        Spacer(1, 10),
    ]
    charts = _charts(doc)
    if charts is not None:
        story.append(KeepTogether([charts]))

    builders = [("balance", _balance), ("income", _income),
                ("ledger", _ledger), ("portfolio", _portfolio)]
    for key, fn in builders:
        if key in sections:
            parts = fn(doc)
            # keep the heading with the first element that follows it
            story.append(KeepTogether(parts[:2]))
            story.extend(parts[2:])
    if not any(k in sections for k, _ in builders):
        story.append(_empty("No detail sections were selected."))

    pdf.build(story, onFirstPage=_decorate(generated), onLaterPages=_decorate(generated))
    return buffer.getvalue()
