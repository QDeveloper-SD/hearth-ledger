from __future__ import annotations

import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://api.public.com"
TOKEN_PATH = "/userapiauthservice/personal/access-tokens"
TOKEN_VALIDITY_MINUTES = 1440  # 24h — family polls occasionally, no need for short-lived tokens
TOKEN_REFRESH_SKEW_SECONDS = 60


class PublicApiError(RuntimeError):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"Public.com API error {status_code}: {message}")
        self.status_code = status_code


class PublicApiClient:
    def __init__(self, secret: str, *, http_client: httpx.AsyncClient | None = None) -> None:
        if not secret:
            raise PublicApiError(0, "Missing API secret")
        self._secret = secret
        self._http = http_client or httpx.AsyncClient(base_url=BASE_URL, timeout=15.0)
        self._owns_client = http_client is None
        self._token: str | None = None
        self._token_expires_at: float = 0.0

    async def aclose(self) -> None:
        if self._owns_client:
            await self._http.aclose()

    async def __aenter__(self) -> "PublicApiClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def _ensure_token(self) -> str:
        now = time.time()
        if self._token and now < self._token_expires_at - TOKEN_REFRESH_SKEW_SECONDS:
            return self._token

        resp = await self._http.post(
            TOKEN_PATH,
            json={"validityInMinutes": TOKEN_VALIDITY_MINUTES, "secret": self._secret},
            headers={"Content-Type": "application/json"},
        )
        if resp.status_code != 200:
            raise PublicApiError(resp.status_code, resp.text)
        body = resp.json()
        token = body.get("accessToken")
        if not token:
            raise PublicApiError(resp.status_code, "Token response missing accessToken")
        self._token = token
        self._token_expires_at = now + TOKEN_VALIDITY_MINUTES * 60
        return token

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        token = await self._ensure_token()
        resp = await self._http.get(
            path,
            params=params,
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code == 401:
            # token rotated server-side; mint once more then retry
            self._token = None
            token = await self._ensure_token()
            resp = await self._http.get(
                path,
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
        if resp.status_code >= 400:
            raise PublicApiError(resp.status_code, resp.text)
        return resp.json()

    async def list_accounts(self) -> list[dict]:
        body = await self._get("/userapigateway/trading/account")
        return body.get("accounts", [])

    async def get_portfolio(self, account_id: str) -> dict:
        return await self._get(f"/userapigateway/trading/{account_id}/portfolio/v2")

    async def get_history(
        self,
        account_id: str,
        *,
        start: str | None = None,
        end: str | None = None,
        page_size: int | None = None,
        next_token: str | None = None,
    ) -> dict:
        params: dict[str, Any] = {}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        if page_size:
            params["pageSize"] = page_size
        if next_token:
            params["nextToken"] = next_token
        return await self._get(f"/userapigateway/trading/{account_id}/history", params=params)


def normalize_portfolio(raw: dict) -> dict:
    """Reduce the Public.com portfolio payload to the shape the UI expects.

    The UI cares about: account value, cash, list of holdings with symbol/qty/value/gain.
    """
    equity = raw.get("equity") or []
    account_value = sum((_to_float(e.get("value")) or 0.0) for e in equity)
    buying_power = (raw.get("buyingPower") or {}).get("cashOnlyBuyingPower")

    holdings: list[dict] = []
    for pos in raw.get("positions") or []:
        instrument = pos.get("instrument") or {}
        cost = pos.get("costBasis") or {}
        last = pos.get("lastPrice") or {}
        gain = pos.get("instrumentGain") or {}
        holdings.append(
            {
                "symbol": instrument.get("symbol"),
                "name": instrument.get("name"),
                "type": instrument.get("type"),
                "qty": _to_float(pos.get("quantity")),
                "current_value": _to_float(pos.get("currentValue")),
                "price": _to_float(last.get("lastPrice")),
                "cost_basis_total": _to_float(cost.get("totalCost")),
                "gain_value": _to_float(gain.get("gainValue")),
                "day_change": _to_float(gain.get("gainPercentage")),
                "percent_of_portfolio": _to_float(pos.get("percentOfPortfolio")),
            }
        )

    return {
        "account_value": account_value,
        "cash": _to_float(buying_power),
        "holdings": holdings,
    }


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
