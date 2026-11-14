"""Interactive Brokers read-only access via the Flex Web Service.

The Flex Web Service can only deliver pre-defined reports (Flex Queries); it has no
order, transfer or account-modification endpoints, so a Flex token cannot trade.

Flow: SendRequest (token + query id) -> reference code -> GetStatement (poll until ready).
"""
from __future__ import annotations

import asyncio
import logging
import xml.etree.ElementTree as ET
from typing import Any, Awaitable, Callable
from urllib.parse import urlsplit

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService"
SEND_REQUEST_URL = f"{BASE_URL}/SendRequest"
GET_STATEMENT_URL = f"{BASE_URL}/GetStatement"
API_VERSION = "3"
USER_AGENT = "HearthLedger/1.1"

# "Statement generation in progress" style codes: safe to poll again.
RETRYABLE_CODES = {"1001", "1004", "1005", "1006", "1007", "1008", "1009", "1018", "1019", "1021"}
POLL_ATTEMPTS = 10
POLL_DELAY_SECONDS = 3.0


class IbkrFlexError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"IBKR Flex error {code}: {message}" if code else message)
        self.code = code
        self.message = message


def _trusted_statement_url(url: str | None) -> str:
    """Use the URL IBKR hands back only if it is an https interactivebrokers.com host.

    The token is sent as a query parameter, so it must never follow a URL to another host.
    """
    if url:
        parts = urlsplit(url.strip())
        host = (parts.hostname or "").lower()
        if parts.scheme == "https" and (host == "interactivebrokers.com" or host.endswith(".interactivebrokers.com")):
            return url.strip()
    return GET_STATEMENT_URL


def _parse_xml(text: str) -> ET.Element:
    try:
        return ET.fromstring(text)
    except ET.ParseError as exc:
        raise IbkrFlexError("", "IBKR returned a response that could not be read.") from exc


def _status_error(root: ET.Element) -> IbkrFlexError:
    code = (root.findtext("ErrorCode") or "").strip()
    message = (root.findtext("ErrorMessage") or "").strip() or "Request was not accepted."
    return IbkrFlexError(code, message)


class IbkrFlexClient:
    def __init__(
        self,
        token: str,
        query_id: str,
        *,
        http_client: httpx.AsyncClient | None = None,
        sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep,
        poll_attempts: int = POLL_ATTEMPTS,
        poll_delay: float = POLL_DELAY_SECONDS,
    ) -> None:
        if not token or not query_id:
            raise IbkrFlexError("", "Missing Flex token or query ID")
        self._token = token
        self._query_id = query_id
        self._http = http_client or httpx.AsyncClient(timeout=30.0)
        self._owns_client = http_client is None
        self._sleep = sleep
        self._poll_attempts = poll_attempts
        self._poll_delay = poll_delay

    async def aclose(self) -> None:
        if self._owns_client:
            await self._http.aclose()

    async def __aenter__(self) -> "IbkrFlexClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def _get(self, url: str, q: str) -> str:
        try:
            resp = await self._http.get(
                url,
                params={"t": self._token, "q": q, "v": API_VERSION},
                headers={"User-Agent": USER_AGENT},
            )
        except httpx.HTTPError as exc:
            # str(exc) may contain the request URL (and so the token): never surface it.
            raise IbkrFlexError("", f"Could not reach Interactive Brokers ({type(exc).__name__}).") from None
        if resp.status_code >= 400:
            raise IbkrFlexError(str(resp.status_code), "Interactive Brokers rejected the request.")
        return resp.text

    async def fetch_statement(self) -> str:
        """Run the configured Flex Query and return the statement XML."""
        root = _parse_xml(await self._get(SEND_REQUEST_URL, self._query_id))
        if (root.findtext("Status") or "").strip() != "Success":
            raise _status_error(root)
        reference = (root.findtext("ReferenceCode") or "").strip()
        if not reference:
            raise IbkrFlexError("", "IBKR did not return a reference code.")
        statement_url = _trusted_statement_url(root.findtext("Url"))

        last: IbkrFlexError | None = None
        for attempt in range(self._poll_attempts):
            if attempt:
                await self._sleep(self._poll_delay)
            body = await self._get(statement_url, reference)
            root = _parse_xml(body)
            if root.tag == "FlexQueryResponse":
                return body
            last = _status_error(root)
            if last.code not in RETRYABLE_CODES:
                raise last
        raise last or IbkrFlexError("", "IBKR did not produce the statement in time.")


def _to_float(v: Any) -> float | None:
    if v in (None, ""):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def normalize_statement(xml_text: str) -> dict:
    """Reduce an Activity Flex statement to account value, cash and a list of holdings.

    All money is converted to the account's base currency with ``fxRateToBase``.
    """
    root = _parse_xml(xml_text)
    if root.tag != "FlexQueryResponse":
        raise IbkrFlexError("", "Unexpected response from IBKR (not a Flex statement).")

    account_ids: list[str] = []
    merged: dict[tuple[str, str], dict] = {}
    cash_total = 0.0
    has_cash = False

    for stmt in root.iter("FlexStatement"):
        acct = stmt.get("accountId")
        if acct and acct not in account_ids:
            account_ids.append(acct)

        for pos in stmt.iter("OpenPosition"):
            # A query can emit both a summary row and per-lot rows; count each position once.
            if (pos.get("levelOfDetail") or "SUMMARY").upper() != "SUMMARY":
                continue
            symbol = pos.get("symbol") or pos.get("description") or ""
            if not symbol:
                continue
            fx = _to_float(pos.get("fxRateToBase")) or 1.0
            qty = _to_float(pos.get("position")) or 0.0
            price = _to_float(pos.get("markPrice"))
            value = _to_float(pos.get("positionValue"))
            if value is None and price is not None:
                value = qty * price * (_to_float(pos.get("multiplier")) or 1.0)
            cost = _to_float(pos.get("costBasisMoney"))
            gain = _to_float(pos.get("fifoPnlUnrealized"))
            key = (symbol, pos.get("assetCategory") or "")
            row = merged.setdefault(key, {
                "symbol": symbol,
                "name": pos.get("description"),
                "type": pos.get("assetCategory"),
                "currency": pos.get("currency"),
                "qty": 0.0,
                "price": price,
                "current_value": 0.0,
                "cost_basis_total": None,
                "gain_value": None,
            })
            row["qty"] += qty
            row["current_value"] += (value or 0.0) * fx
            if cost is not None:
                row["cost_basis_total"] = (row["cost_basis_total"] or 0.0) + cost * fx
            if gain is not None:
                row["gain_value"] = (row["gain_value"] or 0.0) + gain * fx

        base_rows = [c for c in stmt.iter("CashReportCurrency") if (c.get("currency") or "").upper() == "BASE_SUMMARY"]
        for c in base_rows:
            v = _to_float(c.get("endingCash"))
            if v is not None:
                cash_total += v
                has_cash = True

    holdings = []
    for row in merged.values():
        row["qty"] = round(row["qty"], 6)
        row["current_value"] = round(row["current_value"], 2)
        for k in ("cost_basis_total", "gain_value"):
            if row[k] is not None:
                row[k] = round(row[k], 2)
        if row["gain_value"] is None and row["cost_basis_total"] is not None:
            row["gain_value"] = round(row["current_value"] - row["cost_basis_total"], 2)
        holdings.append(row)
    holdings.sort(key=lambda h: -abs(h["current_value"]))

    cash = round(cash_total, 2) if has_cash else None
    return {
        "account_ids": account_ids,
        "account_value": round(sum(h["current_value"] for h in holdings) + (cash or 0.0), 2),
        "cash": cash,
        "holdings": holdings,
    }
