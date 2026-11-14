from __future__ import annotations

import re

import httpx
import pytest
from pytest_httpx import HTTPXMock

from backend.integrations import ibkr_flex
from backend.integrations.ibkr_flex import (
    GET_STATEMENT_URL,
    SEND_REQUEST_URL,
    IbkrFlexClient,
    IbkrFlexError,
    normalize_statement,
)

SEND_OK = """<FlexStatementResponse timestamp='13 November, 2026 10:00 AM EST'>
<Status>Success</Status><ReferenceCode>987654</ReferenceCode>
<Url>https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService/GetStatement</Url>
</FlexStatementResponse>"""

NOT_READY = """<FlexStatementResponse timestamp='x'><Status>Warn</Status>
<ErrorCode>1019</ErrorCode><ErrorMessage>Statement generation in progress. Please try again shortly.</ErrorMessage>
</FlexStatementResponse>"""

BAD_TOKEN = """<FlexStatementResponse timestamp='x'><Status>Fail</Status>
<ErrorCode>1015</ErrorCode><ErrorMessage>Token is invalid.</ErrorMessage></FlexStatementResponse>"""

STATEMENT = """<FlexQueryResponse queryName="Hearth" type="AF">
<FlexStatements count="1">
<FlexStatement accountId="U0000001" fromDate="20261112" toDate="20261112">
<CashReport>
<CashReportCurrency accountId="U0000001" currency="BASE_SUMMARY" endingCash="1500.50" />
<CashReportCurrency accountId="U0000001" currency="USD" endingCash="1000" />
</CashReport>
<OpenPositions>
<OpenPosition accountId="U0000001" currency="USD" fxRateToBase="1" assetCategory="STK" symbol="VTI"
  description="VANGUARD TOTAL STOCK MKT ETF" position="10" markPrice="250" positionValue="2500"
  costBasisMoney="2000" fifoPnlUnrealized="500" levelOfDetail="SUMMARY" />
<OpenPosition accountId="U0000001" currency="USD" fxRateToBase="1" assetCategory="STK" symbol="VTI"
  description="VANGUARD TOTAL STOCK MKT ETF" position="10" markPrice="250" positionValue="2500"
  costBasisMoney="2000" fifoPnlUnrealized="500" levelOfDetail="LOT" />
<OpenPosition accountId="U0000001" currency="EUR" fxRateToBase="1.1" assetCategory="STK" symbol="SAP"
  description="SAP SE" position="4" markPrice="200" positionValue="800"
  costBasisMoney="700" fifoPnlUnrealized="100" levelOfDetail="SUMMARY" />
</OpenPositions>
</FlexStatement>
</FlexStatements>
</FlexQueryResponse>"""


async def _no_sleep(_seconds: float) -> None:
    return None


def _client(**kw) -> IbkrFlexClient:
    return IbkrFlexClient("tok-123", "555", http_client=httpx.AsyncClient(), sleep=_no_sleep, **kw)


def test_normalize_counts_summary_rows_once_and_converts_to_base() -> None:
    n = normalize_statement(STATEMENT)
    assert n["account_ids"] == ["U0000001"]
    assert [h["symbol"] for h in n["holdings"]] == ["VTI", "SAP"]
    vti, sap = n["holdings"]
    assert vti["qty"] == 10 and vti["current_value"] == 2500 and vti["cost_basis_total"] == 2000
    assert sap["current_value"] == 880 and sap["cost_basis_total"] == 770 and sap["gain_value"] == 110
    assert n["cash"] == 1500.50
    assert n["account_value"] == 2500 + 880 + 1500.50


def test_normalize_rejects_non_statement() -> None:
    with pytest.raises(IbkrFlexError):
        normalize_statement(BAD_TOKEN)
    with pytest.raises(IbkrFlexError):
        normalize_statement("not xml")


@pytest.mark.asyncio
async def test_fetch_polls_until_statement_ready(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=re.compile(re.escape(SEND_REQUEST_URL) + r"\?.*"), text=SEND_OK)
    httpx_mock.add_response(url=re.compile(re.escape(GET_STATEMENT_URL) + r"\?.*"), text=NOT_READY)
    httpx_mock.add_response(url=re.compile(re.escape(GET_STATEMENT_URL) + r"\?.*"), text=STATEMENT)
    client = _client()
    xml = await client.fetch_statement()
    await client.aclose()
    assert "<FlexQueryResponse" in xml
    reqs = httpx_mock.get_requests()
    assert all(r.method == "GET" for r in reqs)  # report retrieval only
    assert dict(reqs[0].url.params) == {"t": "tok-123", "q": "555", "v": "3"}
    assert dict(reqs[1].url.params) == {"t": "tok-123", "q": "987654", "v": "3"}


@pytest.mark.asyncio
async def test_fetch_surfaces_ibkr_error_without_token(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=re.compile(re.escape(SEND_REQUEST_URL) + r"\?.*"), text=BAD_TOKEN)
    client = _client()
    with pytest.raises(IbkrFlexError) as ei:
        await client.fetch_statement()
    await client.aclose()
    assert ei.value.code == "1015" and "invalid" in ei.value.message.lower()
    assert "tok-123" not in str(ei.value)


@pytest.mark.asyncio
async def test_network_error_does_not_leak_token(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_exception(httpx.ConnectError("boom https://x/?t=tok-123"))
    client = _client()
    with pytest.raises(IbkrFlexError) as ei:
        await client.fetch_statement()
    await client.aclose()
    assert "tok-123" not in str(ei.value)


@pytest.mark.asyncio
async def test_gives_up_when_statement_never_ready(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=re.compile(re.escape(SEND_REQUEST_URL) + r"\?.*"), text=SEND_OK)
    for _ in range(3):
        httpx_mock.add_response(url=re.compile(re.escape(GET_STATEMENT_URL) + r"\?.*"), text=NOT_READY)
    client = _client(poll_attempts=3)
    with pytest.raises(IbkrFlexError) as ei:
        await client.fetch_statement()
    await client.aclose()
    assert ei.value.code == "1019"


def test_statement_url_must_stay_on_ibkr() -> None:
    f = ibkr_flex._trusted_statement_url
    assert f("https://gdcdyn.interactivebrokers.com/x/GetStatement").startswith("https://gdcdyn.")
    assert f("https://evil.example/GetStatement") == GET_STATEMENT_URL
    assert f("https://interactivebrokers.com.evil.example/x") == GET_STATEMENT_URL
    assert f("http://ndcdyn.interactivebrokers.com/x") == GET_STATEMENT_URL
    assert f(None) == GET_STATEMENT_URL


# ---- API level -------------------------------------------------------------

@pytest.mark.asyncio
async def test_settings_never_return_token_and_sync_fills_ibkr_section(authed_client, monkeypatch) -> None:
    r = await authed_client.post("/api/portfolio/ibkr/sync")
    assert r.status_code == 400

    r = await authed_client.post("/api/settings/ibkr", json={"token": "abc", "query_id": "12x"})
    assert r.status_code == 422
    r = await authed_client.post("/api/settings/ibkr", json={"token": " tok-123 ", "query_id": " 555 "})
    assert r.status_code == 200
    s = (await authed_client.get("/api/settings")).json()["data"]
    assert s["has_ibkr"] is True and s["ibkr_query_id"] == "555"
    assert "tok-123" not in (await authed_client.get("/api/settings")).text

    seen: dict = {}

    async def fake_fetch(self) -> str:
        seen["creds"] = (self._token, self._query_id)
        return STATEMENT

    monkeypatch.setattr(IbkrFlexClient, "fetch_statement", fake_fetch)
    r = await authed_client.post("/api/portfolio/ibkr/sync")
    assert r.status_code == 200
    assert seen["creds"] == ("tok-123", "555")
    data = r.json()["data"]
    assert data["ibkr"]["configured"] is True
    assert [h["symbol"] for h in data["ibkr"]["holdings"]] == ["VTI", "SAP"]
    assert data["ibkr"]["cash"] == 1500.50
    assert data["totals"]["ibkr"] == 4880.50
    assert "tok-123" not in r.text
    assert any(a["name"] == "VTI" for a in data["allocation"])

    # manual IBKR rows still add on top of the synced account
    await authed_client.post("/api/portfolio/manual", json={"symbol": "X", "qty": 1, "cost_basis": 100, "account": "ibkr"})
    assert (await authed_client.get("/api/portfolio")).json()["data"]["totals"]["ibkr"] == 4980.50

    r = await authed_client.delete("/api/settings/ibkr")
    assert r.json()["data"]["has_ibkr"] is False
    data = (await authed_client.get("/api/portfolio")).json()["data"]
    assert data["ibkr"] == {"configured": False, "fetched_at": None, "cash": None, "holdings": []}
    assert data["totals"]["ibkr"] == 100


@pytest.mark.asyncio
async def test_sync_failure_reports_ibkr_message(authed_client, monkeypatch) -> None:
    await authed_client.post("/api/settings/ibkr", json={"token": "tok-123", "query_id": "555"})

    async def boom(self) -> str:
        raise IbkrFlexError("1012", "Token has expired.")

    monkeypatch.setattr(IbkrFlexClient, "fetch_statement", boom)
    r = await authed_client.post("/api/portfolio/ibkr/sync")
    assert r.status_code == 502
    assert r.json()["detail"] == "IBKR sync failed: Token has expired."
