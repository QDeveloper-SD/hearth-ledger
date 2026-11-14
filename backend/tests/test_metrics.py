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


def _pf(**kw) -> dict:
    return {"portfolio": {"cash_accounts": [], "manual_holdings": [], "public_cache": {}, **kw}}


def test_current_ratio_value() -> None:
    doc = _doc(
        debts=[{"id": "1", "name": "Card", "balance": 100000, "rate": 0.2, "min_payment": 200}],
        **_pf(cash_accounts=[{"id": "c", "name": "C", "balance": 4800}]),
    )
    # current liabilities = min(100000, 12*200) = 2400 ; assets = 4800
    assert current_ratio(doc) == pytest.approx(2.0)


def test_current_ratio_balance_below_annual_payments() -> None:
    doc = _doc(
        debts=[{"id": "1", "name": "Loan", "balance": 500, "rate": 0.1, "min_payment": 200}],
        **_pf(cash_accounts=[{"id": "c", "name": "C", "balance": 1000}]),
    )
    assert current_ratio(doc) == pytest.approx(2.0)  # min(500, 2400) = 500


def test_current_ratio_no_min_payment_uses_full_balance() -> None:
    doc = _doc(
        debts=[{"id": "1", "name": "Loan", "balance": 2000, "rate": 0.1, "min_payment": 0}],
        **_pf(cash_accounts=[{"id": "c", "name": "C", "balance": 1000}]),
    )
    assert current_ratio(doc) == pytest.approx(0.5)


def test_current_ratio_liquid_assets_composition() -> None:
    doc = _doc(
        debts=[{"id": "1", "name": "D", "balance": 1000, "rate": 0.1, "min_payment": 0}],
        **_pf(
            cash_accounts=[{"id": "c", "name": "C", "balance": 100}],
            manual_holdings=[
                {"id": "a", "symbol": "A", "qty": 1, "cost_basis": 100},
                {"id": "b", "symbol": "B", "qty": 1, "cost_basis": 50, "current_value": 200, "account": "ibkr"},
                {"id": "o", "symbol": "O", "qty": 1, "cost_basis": 300, "account": "other", "broker": "X"},
            ],
            public_cache={"account_value": 400},
            fixed_income=[{"id": "f", "name": "T", "face_value": 500}],
            real_estate=[{"id": "r", "name": "H", "current_value": 900000}],
            businesses=[{"id": "u", "name": "B", "valuation": 1000000, "ownership_pct": 50}],
        ),
    )
    # 100 cash + 100 + 200 + 300 + 400 public + 500 FI = 1600 ; real estate/business excluded
    assert current_ratio(doc) == pytest.approx(1.6)


def test_current_ratio_none_without_liabilities() -> None:
    assert current_ratio(_doc(**_pf(cash_accounts=[{"id": "c", "name": "C", "balance": 100}]))) is None


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


def test_emergency_fund_uses_cash_over_average_spending() -> None:
    from datetime import date

    from backend.services.metrics import average_monthly_expenses

    today = date(2026, 11, 13)
    doc = _doc()
    # 90 days of history, $3,000 spent in the window -> ~$1,014.58 / month
    doc["ledger"] = [
        {"id": "1", "date": "2026-08-01", "desc": "old", "category": "x", "amount": -50.0},  # outside window
        {"id": "2", "date": "2026-09-01", "desc": "rent", "category": "x", "amount": -1000.0},
        {"id": "3", "date": "2026-10-01", "desc": "rent", "category": "x", "amount": -1000.0},
        {"id": "4", "date": "2026-11-01", "desc": "rent", "category": "x", "amount": -1000.0},
        {"id": "5", "date": "2026-11-05", "desc": "pay", "category": "x", "amount": 4000.0},  # income ignored
    ]
    doc["portfolio"]["cash_accounts"] = [{"id": "c", "name": "Savings", "balance": 6000.0}]
    doc["portfolio"]["manual_holdings"] = [{"id": "h", "symbol": "VTI", "qty": 1, "cost_basis": 99999.0}]  # not liquid
    monthly = average_monthly_expenses(doc, today)
    assert monthly == pytest.approx(3000 / 90 * 365.25 / 12)
    assert emergency_fund_months(doc, today) == pytest.approx(6000 / monthly)


def test_emergency_fund_short_history_not_scaled_up() -> None:
    from datetime import date

    from backend.services.metrics import average_monthly_expenses

    today = date(2026, 11, 13)
    doc = _doc()
    doc["ledger"] = [{"id": "1", "date": "2026-11-10", "desc": "g", "category": "x", "amount": -300.0}]
    # only 4 days of data: treated as one month's worth, not extrapolated
    assert average_monthly_expenses(doc, today) == pytest.approx(300 / 30 * 365.25 / 12)


def test_emergency_fund_none_without_recent_spending() -> None:
    from datetime import date

    doc = _doc()
    doc["ledger"] = [{"id": "1", "date": "2025-01-10", "desc": "g", "category": "x", "amount": -300.0}]
    assert emergency_fund_months(doc, date(2026, 11, 13)) is None


def test_income_to_date() -> None:
    from datetime import date

    from backend.services.metrics import income_to_date

    doc = _doc()
    doc["ledger"] = [
        {"id": "1", "date": "2025-12-31", "desc": "last year", "category": "Income", "amount": 900.0},
        {"id": "2", "date": "2026-02-01", "desc": "pay", "category": "income", "amount": 1000.0},
        {"id": "3", "date": "2026-11-01", "desc": "pay", "category": " INCOME ", "amount": 2000.0},
        {"id": "4", "date": "2026-11-02", "desc": "spend", "category": "Food", "amount": -500.0},
        {"id": "5", "date": "2026-11-03", "desc": "refund", "category": "Shopping", "amount": 75.0},  # positive, not income
        {"id": "6", "date": "2026-11-30", "desc": "future", "category": "Income", "amount": 7000.0},
    ]
    assert income_to_date(doc, date(2026, 11, 13)) == (2000.0, 3000.0)
