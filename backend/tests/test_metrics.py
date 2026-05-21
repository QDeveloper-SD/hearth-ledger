from __future__ import annotations

import pytest

from backend.services.metrics import (
    current_ratio,
    debt_to_income,
    emergency_fund_months,
    monthly_debt_payment,
    monthly_income,
    net_worth,
    portfolio_sharpe,
    portfolio_volatility,
)


def _doc(**kwargs) -> dict:
    base = {
        "ledger": [],
        "debts": [],
        "income_sources": [],
        "portfolio": {
            "manual_holdings": [],
            "public_cache": {"account_value": 0.0, "holdings": []},
        },
    }
    base.update(kwargs)
    return base


def test_net_worth_empty() -> None:
    assert net_worth(_doc()) == 0.0


def test_net_worth_combined() -> None:
    doc = _doc(
        debts=[{"id": "1", "name": "Mortgage", "balance": 200000, "rate": 0.06, "min_payment": 1500}],
        portfolio={
            "manual_holdings": [{"symbol": "VTI", "qty": 10, "cost_basis": 5000}],
            "public_cache": {"account_value": 10000.0, "holdings": []},
        },
    )
    assert net_worth(doc) == pytest.approx(10000 + 5000 - 200000)


def test_monthly_income_biweekly() -> None:
    doc = _doc(income_sources=[{"id": "1", "name": "Salary", "amount": 2000, "cadence": "biweekly"}])
    expected = 2000 * 26 / 12
    assert monthly_income(doc) == pytest.approx(expected)


def test_monthly_income_monthly() -> None:
    doc = _doc(income_sources=[{"id": "1", "name": "Rent", "amount": 3000, "cadence": "monthly"}])
    assert monthly_income(doc) == pytest.approx(3000.0)


def test_monthly_income_annual() -> None:
    doc = _doc(income_sources=[{"id": "1", "name": "Bonus", "amount": 12000, "cadence": "annual"}])
    assert monthly_income(doc) == pytest.approx(1000.0)


def test_monthly_debt_payment() -> None:
    doc = _doc(debts=[
        {"id": "1", "name": "Mortgage", "balance": 200000, "rate": 0.06, "min_payment": 1500},
        {"id": "2", "name": "Car", "balance": 10000, "rate": 0.05, "min_payment": 300},
    ])
    assert monthly_debt_payment(doc) == pytest.approx(1800.0)


def test_debt_to_income() -> None:
    doc = _doc(
        income_sources=[{"id": "1", "name": "Salary", "amount": 5000, "cadence": "monthly"}],
        debts=[{"id": "1", "name": "Mortgage", "balance": 200000, "rate": 0.06, "min_payment": 1000}],
    )
    assert debt_to_income(doc) == pytest.approx(0.2)


def test_debt_to_income_no_income() -> None:
    doc = _doc(debts=[{"id": "1", "name": "Mortgage", "balance": 200000, "rate": 0.06, "min_payment": 1000}])
    assert debt_to_income(doc) is None


def test_current_ratio_no_debts() -> None:
    assert current_ratio(_doc()) is None


def test_current_ratio_value() -> None:
    doc = _doc(
        income_sources=[{"id": "1", "name": "Salary", "amount": 5000, "cadence": "monthly"}],
        debts=[{"id": "1", "name": "Card", "balance": 100000, "rate": 0.2, "min_payment": 200}],
    )
    assert current_ratio(doc) == pytest.approx(5000 / 100000)


def test_portfolio_volatility_insufficient() -> None:
    assert portfolio_volatility([]) is None
    assert portfolio_volatility([0.05]) is None


def test_portfolio_volatility_value() -> None:
    returns = [0.01, 0.02, -0.01, 0.03, 0.005]
    vol = portfolio_volatility(returns)
    assert vol is not None
    assert vol > 0


def test_portfolio_sharpe_insufficient() -> None:
    assert portfolio_sharpe([]) is None
    assert portfolio_sharpe([0.01]) is None


def test_portfolio_sharpe_value() -> None:
    returns = [0.01, 0.02, -0.01, 0.03, 0.005]
    sharpe = portfolio_sharpe(returns)
    assert sharpe is not None


def test_emergency_fund_no_expenses() -> None:
    assert emergency_fund_months(_doc()) is None
