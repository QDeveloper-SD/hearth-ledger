"""Spreadsheet import (extract + transform + dedupe). Pure functions, no FastAPI."""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Callable

MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 20_000
PREVIEW_ROWS = 20
MAX_ERRORS = 100
CADENCES = ("weekly", "biweekly", "monthly", "annual")


class ImportError_(ValueError):
    """Top-level problem with the file (reported as HTTP 400)."""


def _norm_header(s: Any) -> str:
    return re.sub(r"[\s_\-]+", "", str(s or "").strip().lower())


# kind -> canonical column -> aliases (already normalised) ; required set
SPECS: dict[str, dict] = {
    "ledger": {
        "columns": {
            "date": ["date", "transactiondate", "posted", "posteddate", "day"],
            "description": ["description", "desc", "memo", "details", "payee"],
            "category": ["category", "cat", "type"],
            "amount": ["amount", "amt", "value", "total"],
        },
        "required": ["date", "description", "category", "amount"],
    },
    "debts": {
        "columns": {
            "name": ["name", "account", "debt", "creditor", "source"],
            "balance": ["balance", "owed", "amountowed", "principal", "currentbalance"],
            "rate": ["rate", "apr", "interestrate", "interest"],
            "min_payment": ["minpayment", "minimumpayment", "minpmt", "payment", "minimum"],
        },
        "required": ["name", "balance"],
    },
    "income": {
        "columns": {
            "name": ["name", "source", "account", "employer"],
            "amount": ["amount", "amt", "value", "paycheck", "pay"],
            "cadence": ["cadence", "frequency", "freq", "period"],
        },
        "required": ["name", "amount", "cadence"],
    },
}


# ---------------------------------------------------------------- parsing
def read_rows(filename: str, data: bytes) -> list[list[Any]]:
    """Return all rows (header included) as lists of raw cell values."""
    if len(data) > MAX_BYTES:
        raise ImportError_("File is too large (limit is 5 MB).")
    if not data.strip():
        raise ImportError_("The file is empty.")
    name = (filename or "").lower()
    if name.endswith(".csv"):
        rows = _read_csv(data)
    elif name.endswith(".xlsx"):
        rows = _read_xlsx(data)
    else:
        raise ImportError_("Unsupported file type. Please upload a .csv or .xlsx file.")
    if not rows:
        raise ImportError_("The file is empty.")
    if len(rows) - 1 > MAX_ROWS:
        raise ImportError_(f"Too many rows (limit is {MAX_ROWS:,} data rows).")
    return rows


def _read_csv(data: bytes) -> list[list[Any]]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("cp1252", errors="replace")
    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        delim = dialect.delimiter
    except csv.Error:
        first = sample.splitlines()[0] if sample.splitlines() else ""
        delim = ";" if first.count(";") > first.count(",") else ","
    try:
        return [list(r) for r in csv.reader(io.StringIO(text, newline=""), delimiter=delim)]
    except csv.Error as e:
        raise ImportError_(f"Could not read the CSV file: {e}")


def _read_xlsx(data: bytes) -> list[list[Any]]:
    try:
        from openpyxl import load_workbook

        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        ws = wb.worksheets[0]
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        wb.close()
    except ImportError_:
        raise
    except Exception:
        raise ImportError_("Could not read the Excel file. Is it a valid .xlsx workbook?")
    return rows


# -------------------------------------------------------------- transforms
def parse_money(v: Any) -> float:
    if isinstance(v, bool):
        raise ValueError("not a number")
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg, s = True, s[1:-1].strip()
    s = s.replace("$", "").replace(" ", "").replace(" ", "")
    if s.endswith("-"):
        neg, s = not neg, s[:-1]
    s = s.replace(",", "")
    if not re.fullmatch(r"[+-]?(\d+\.?\d*|\.\d+)", s):
        raise ValueError("not a number")
    n = float(s)
    return -n if neg else n


def parse_percent(v: Any) -> float:
    if isinstance(v, str):
        v = v.strip().rstrip("%").strip()
    return parse_money(v)


_DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y")


def parse_date(v: Any) -> str:
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    s = str(v).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError("not a valid date (use YYYY-MM-DD)")


_CADENCE_MAP = {
    "weekly": "weekly", "week": "weekly", "everyweek": "weekly",
    "biweekly": "biweekly", "everytwoweeks": "biweekly", "every2weeks": "biweekly",
    "fortnightly": "biweekly", "twiceamonth": "biweekly",
    "monthly": "monthly", "month": "monthly", "everymonth": "monthly",
    "annual": "annual", "annually": "annual", "yearly": "annual", "year": "annual",
}


def parse_cadence(v: Any) -> str:
    key = re.sub(r"[\s_\-]+", "", str(v).strip().lower())
    if key in _CADENCE_MAP:
        return _CADENCE_MAP[key]
    raise ValueError(f"cadence '{str(v).strip()}' is not recognised (use weekly, biweekly, monthly or annual)")


def _blank(v: Any) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


def _text(v: Any) -> str:
    return v.strip() if isinstance(v, str) else str(v).strip()


# ---------------------------------------------------------------- pipeline
@dataclass
class ParseResult:
    kind: str
    columns_found: list[str]
    total_rows: int = 0
    valid: list[dict] = field(default_factory=list)
    duplicates: int = 0
    errors: list[dict] = field(default_factory=list)
    error_count: int = 0


def _map_columns(kind: str, header: list[Any]) -> tuple[dict[str, int], list[str]]:
    spec = SPECS[kind]
    found = [str(h).strip() for h in header if not _blank(h)]
    idx: dict[str, int] = {}
    for col, aliases in spec["columns"].items():
        for i, h in enumerate(header):
            if _norm_header(h) in aliases:
                idx[col] = i
                break
    missing = [c for c in spec["required"] if c not in idx]
    if missing:
        raise ImportError_(
            f"Missing required column(s): {', '.join(missing)}. "
            f"Columns found: {', '.join(found) if found else '(none)'}. "
            "The first row of the file must be the header row."
        )
    return idx, found


def _row_ledger(g: Callable[[str], Any]) -> dict:
    d = parse_date(g("date")) if not _blank(g("date")) else _req("date")
    desc, cat = g("description"), g("category")
    if _blank(desc):
        _req("description")
    if _blank(cat):
        _req("category")
    if _blank(g("amount")):
        _req("amount")
    try:
        amt = parse_money(g("amount"))
    except ValueError:
        raise ValueError(f"amount '{_text(g('amount'))}' is not a number")
    return {"date": d, "desc": _text(desc), "category": _text(cat), "amount": amt}


def _req(name: str):
    raise ValueError(f"{name} is required")


def _num(g, name, default=None, pct=False):
    v = g(name)
    if _blank(v):
        if default is None:
            _req(name)
        return default
    try:
        return parse_percent(v) if pct else parse_money(v)
    except ValueError:
        raise ValueError(f"{name} '{_text(v)}' is not a number")


def _row_debt(g) -> dict:
    if _blank(g("name")):
        _req("name")
    return {
        "name": _text(g("name")),
        "balance": abs(_num(g, "balance")),
        "rate": _num(g, "rate", 0.0, pct=True),
        "min_payment": _num(g, "min_payment", 0.0),
    }


def _row_income(g) -> dict:
    if _blank(g("name")):
        _req("name")
    amount = _num(g, "amount")
    if _blank(g("cadence")):
        _req("cadence")
    return {"name": _text(g("name")), "amount": amount, "cadence": parse_cadence(g("cadence"))}


_ROW_FNS = {"ledger": _row_ledger, "debts": _row_debt, "income": _row_income}
_STORE_KEY = {"ledger": "ledger", "debts": "debts", "income": "income_sources"}


def _dup_key(kind: str, r: dict) -> tuple:
    if kind == "ledger":
        return (r["date"], r["desc"].lower(), r["category"].lower(), round(float(r["amount"]), 2))
    return (r["name"].lower(),)


def parse_and_validate(kind: str, rows: list[list[Any]], existing: list[dict]) -> ParseResult:
    idx, found = _map_columns(kind, rows[0])
    res = ParseResult(kind=kind, columns_found=found)
    seen_existing = {_dup_key(kind, e) for e in existing if _safe_key(kind, e)}
    seen_in_file: set[tuple] = set()
    fn = _ROW_FNS[kind]
    for n, raw in enumerate(rows[1:], start=2):
        if all(_blank(c) for c in raw):
            continue
        res.total_rows += 1

        def g(col: str, raw=raw):
            i = idx.get(col)
            return raw[i] if i is not None and i < len(raw) else None

        try:
            rec = fn(g)
        except ValueError as e:
            res.error_count += 1
            if len(res.errors) < MAX_ERRORS:
                res.errors.append({"row": n, "message": f"Row {n}: {e}"})
            continue
        key = _dup_key(kind, rec)
        if key in seen_existing:
            res.duplicates += 1
            continue
        if kind != "ledger":  # same name twice in one file: only first is kept
            if key in seen_in_file:
                res.duplicates += 1
                continue
            seen_in_file.add(key)
        res.valid.append(rec)
    return res


def _safe_key(kind: str, e: dict) -> bool:
    try:
        _dup_key(kind, e)
        return True
    except Exception:
        return False


def store_key(kind: str) -> str:
    return _STORE_KEY[kind]


TEMPLATES = {
    "ledger": "date,description,category,amount\n2026-01-05,Paycheck,Income,2500.00\n2026-01-06,Grocery store,Food,-84.32\n",
    "debts": "name,balance,rate,min_payment\nVisa card,4200.50,19.9,95\nCar loan,12800,6.9,310\n",
    "income": "name,amount,cadence\nMain salary,2400,biweekly\nSide gig,300,monthly\n",
}
