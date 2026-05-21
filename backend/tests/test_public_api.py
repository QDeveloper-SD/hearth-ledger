from __future__ import annotations

import httpx
import pytest
from pytest_httpx import HTTPXMock

from backend.integrations.public_api import BASE_URL, PublicApiClient, normalize_portfolio


@pytest.fixture
def client() -> PublicApiClient:
    return PublicApiClient("secret-xyz", http_client=httpx.AsyncClient(base_url=BASE_URL))


@pytest.mark.asyncio
async def test_list_accounts_mints_token_then_fetches(httpx_mock: HTTPXMock, client: PublicApiClient) -> None:
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE_URL}/userapiauthservice/personal/access-tokens",
        json={"accessToken": "tok-1"},
    )
    httpx_mock.add_response(
        method="GET",
        url=f"{BASE_URL}/userapigateway/trading/account",
        json={"accounts": [{"accountId": "A1", "accountType": "BROKERAGE"}]},
    )
    accounts = await client.list_accounts()
    assert accounts == [{"accountId": "A1", "accountType": "BROKERAGE"}]
    await client.aclose()


@pytest.mark.asyncio
async def test_token_is_reused_across_calls(httpx_mock: HTTPXMock, client: PublicApiClient) -> None:
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE_URL}/userapiauthservice/personal/access-tokens",
        json={"accessToken": "tok-1"},
    )
    httpx_mock.add_response(
        method="GET",
        url=f"{BASE_URL}/userapigateway/trading/account",
        json={"accounts": []},
    )
    httpx_mock.add_response(
        method="GET",
        url=f"{BASE_URL}/userapigateway/trading/A1/portfolio/v2",
        json={"positions": [], "equity": []},
    )
    await client.list_accounts()
    await client.get_portfolio("A1")
    token_requests = [r for r in httpx_mock.get_requests() if r.url.path.endswith("/access-tokens")]
    assert len(token_requests) == 1
    await client.aclose()


@pytest.mark.asyncio
async def test_401_triggers_token_refresh_and_retry(httpx_mock: HTTPXMock, client: PublicApiClient) -> None:
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE_URL}/userapiauthservice/personal/access-tokens",
        json={"accessToken": "tok-1"},
    )
    httpx_mock.add_response(
        method="GET",
        url=f"{BASE_URL}/userapigateway/trading/account",
        status_code=401,
        text="expired",
    )
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE_URL}/userapiauthservice/personal/access-tokens",
        json={"accessToken": "tok-2"},
    )
    httpx_mock.add_response(
        method="GET",
        url=f"{BASE_URL}/userapigateway/trading/account",
        json={"accounts": [{"accountId": "A1"}]},
    )
    accounts = await client.list_accounts()
    assert accounts == [{"accountId": "A1"}]
    await client.aclose()


def test_normalize_portfolio_extracts_holdings_and_value() -> None:
    raw = {
        "buyingPower": {"cashOnlyBuyingPower": "1500.00"},
        "equity": [{"value": "10000"}, {"value": "5000"}],
        "positions": [
            {
                "instrument": {"symbol": "VTI", "name": "Vanguard Total", "type": "EQUITY"},
                "quantity": "10",
                "currentValue": "2500.00",
                "lastPrice": {"lastPrice": "250.00"},
                "instrumentGain": {"gainValue": "300", "gainPercentage": "13.6"},
                "costBasis": {"totalCost": "2200"},
                "percentOfPortfolio": "16.6",
            }
        ],
    }
    out = normalize_portfolio(raw)
    assert out["account_value"] == 15000.0
    assert out["cash"] == 1500.0
    assert len(out["holdings"]) == 1
    h = out["holdings"][0]
    assert h["symbol"] == "VTI"
    assert h["qty"] == 10.0
    assert h["day_change"] == 13.6
    assert h["price"] == 250.0
