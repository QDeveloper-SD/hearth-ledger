from __future__ import annotations

import io
from datetime import datetime

import pytest
from openpyxl import Workbook

pytestmark = pytest.mark.asyncio


def _xlsx(rows) -> bytes:
    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    b = io.BytesIO()
    wb.save(b)
    return b.getvalue()


async def _post(c, kind, content, name="f.csv", dry=True):
    if isinstance(content, str):
        content = content.encode()
    return await c.post(f"/api/import/{kind}?dry_run={'true' if dry else 'false'}", files={"file": (name, content)})


LEDGER = "date,description,category,amount\n2026-01-05,Paycheck,Income,2500\n2026-01-06,Grocery,Food,-84.32\n"


async def test_ledger_csv_dry_then_commit(authed_client):
    c = authed_client
    r = await _post(c, "ledger", LEDGER)
    d = r.json()["data"]
    assert (d["total_rows"], d["valid_count"], d["imported_count"]) == (2, 2, 0)
    assert (await c.get("/api/ledger")).json()["data"]["total"] == 0
    r = await _post(c, "ledger", LEDGER, dry=False)
    assert r.json()["data"]["imported_count"] == 2
    assert (await c.get("/api/ledger")).json()["data"]["total"] == 2
    # re-import -> duplicates
    d = (await _post(c, "ledger", LEDGER, dry=False)).json()["data"]
    assert d["imported_count"] == 0 and d["duplicate_count"] == 2
    assert (await c.get("/api/ledger")).json()["data"]["total"] == 2


async def test_ledger_xlsx_real_dates(authed_client):
    data = _xlsx([["Date", "Description", "Category", "Amount"], [datetime(2026, 3, 4), "Rent", "Housing", -1200]])
    r = await _post(authed_client, "ledger", data, "x.xlsx", dry=False)
    assert r.json()["data"]["imported_count"] == 1
    e = (await authed_client.get("/api/ledger")).json()["data"]["entries"][0]
    assert e["date"] == "2026-03-04" and e["amount"] == -1200


async def test_aliases_money_dates_and_bad_rows(authed_client):
    csv_ = (
        "DATE , Memo,CAT, Amt\n"
        "1/5/26,A,Food,\"$1,234.50\"\n"
        "01/06/2026,B,Food,(10.25)\n"
        "2026-13-40,C,Food,5\n"
        ",,,\n"
        "2026-01-07,D,Food,abc\n"
        "2026-01-08,E,Food,7-\n"
    )
    d = (await _post(authed_client, "ledger", csv_, dry=False)).json()["data"]
    assert d["imported_count"] == 3 and d["error_count"] == 2 and d["total_rows"] == 5
    assert [e["row"] for e in d["errors"]] == [4, 6]
    assert "'abc' is not a number" in d["errors"][1]["message"]
    amts = sorted(e["amount"] for e in (await authed_client.get("/api/ledger")).json()["data"]["entries"])
    assert amts == [-10.25, -7.0, 1234.5]


async def test_within_file_repeats_imported(authed_client):
    csv_ = "date,description,category,amount\n2026-01-05,Coffee,Food,-4\n2026-01-05,Coffee,Food,-4\n"
    assert (await _post(authed_client, "ledger", csv_, dry=False)).json()["data"]["imported_count"] == 2


async def test_missing_column(authed_client):
    r = await _post(authed_client, "ledger", "date,description,amount\n2026-01-01,a,1\n")
    assert r.status_code == 400
    assert "category" in r.json()["detail"] and "description" in r.json()["detail"]


async def test_debts_and_duplicates(authed_client):
    csv_ = "Name,Balance,APR,Minimum Payment\nVisa,\"-$4,200.50\",19.9%,95\nLoan,100,,\nvisa,5,1,1\n"
    d = (await _post(authed_client, "debts", csv_, dry=False)).json()["data"]
    assert d["imported_count"] == 2 and d["duplicate_count"] == 1
    debts = {x["name"]: x for x in (await authed_client.get("/api/debts")).json()["data"]}
    assert debts["Visa"]["balance"] == 4200.5 and debts["Visa"]["rate"] == 19.9
    assert debts["Loan"]["rate"] == 0 and debts["Loan"]["min_payment"] == 0
    d = (await _post(authed_client, "debts", "name,balance\nVISA,1\n", dry=False)).json()["data"]
    assert d["imported_count"] == 0 and d["duplicate_count"] == 1


async def test_income_cadence_synonyms(authed_client):
    csv_ = (
        "name,amount,frequency\nA,1,Bi-Weekly\nB,2,every two weeks\nC,3,Yearly\nD,4,annually\n"
        "E,5,MONTHLY\nF,6,semi-monthly\n"
    )
    d = (await _post(authed_client, "income", csv_, dry=False)).json()["data"]
    assert d["imported_count"] == 5 and d["error_count"] == 1
    assert "weekly, biweekly, monthly or annual" in d["errors"][0]["message"]
    cad = {x["name"]: x["cadence"] for x in (await authed_client.get("/api/income")).json()["data"]}
    assert cad == {"A": "biweekly", "B": "biweekly", "C": "annual", "D": "annual", "E": "monthly"}
    d = (await _post(authed_client, "income", "name,amount,cadence\na,1,weekly\n", dry=False)).json()["data"]
    assert d["duplicate_count"] == 1


async def test_semicolon_and_bom(authed_client):
    csv_ = "﻿date;description;category;amount\n2026-01-05;Pay;Income;2500,00\n".replace("2500,00", "2500.00")
    d = (await _post(authed_client, "ledger", csv_.encode("utf-8"), dry=False)).json()["data"]
    assert d["imported_count"] == 1


async def test_unsupported_extension_and_unknown_kind(authed_client):
    r = await _post(authed_client, "ledger", "x", "f.txt")
    assert r.status_code == 400 and ".csv" in r.json()["detail"]
    assert (await _post(authed_client, "nope", LEDGER)).status_code == 404
    assert (await _post(authed_client, "ledger", "", "e.csv")).status_code == 400
    assert (await _post(authed_client, "ledger", b"notzip", "e.xlsx")).status_code == 400


async def test_requires_auth(app):
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        assert (await _post(c, "ledger", LEDGER)).status_code == 401
