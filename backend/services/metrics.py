from __future__ import annotations

import math
from typing import Optional


def net_worth(doc: dict) -> float:
    portfolio_value = doc.get("portfolio", {}).get("public_cache", {}).get("account_value", 0.0)
    manual_value = sum(
        h.get("cost_basis", 0.0)
        for h in doc.get("portfolio", {}).get("manual_holdings", [])
    )
    cash_total = sum(
        c.get("balance", 0.0)
        for c in doc.get("portfolio", {}).get("cash_accounts", [])
    )
    debt_total = sum(abs(d.get("balance", 0.0)) for d in doc.get("debts", []))
    return portfolio_value + manual_value + cash_total - debt_total


def monthly_income(doc: dict) -> float:
    total = 0.0
    for src in doc.get("income_sources", []):
        cadence = src.get("cadence", "monthly")
        amount = src.get("amount", 0.0)
        if cadence == "monthly":
            total += amount
        elif cadence == "biweekly":
            total += amount * 26 / 12
        elif cadence == "weekly":
            total += amount * 52 / 12
        elif cadence == "annual":
            total += amount / 12
        else:
            total += amount
    return total


def monthly_debt_payment(doc: dict) -> float:
    return sum(d.get("min_payment", 0.0) for d in doc.get("debts", []))


def debt_to_income(doc: dict) -> Optional[float]:
    income = monthly_income(doc)
    if income == 0:
        return None
    return monthly_debt_payment(doc) / income


def emergency_fund_months(doc: dict) -> Optional[float]:
    expenses = sum(
        abs(e.get("amount", 0.0))
        for e in doc.get("ledger", [])
        if e.get("amount", 0.0) < 0
    )
    # Rough monthly average from ledger — use last 30 days worth of data
    if expenses == 0:
        return None
    monthly_expense = expenses / max(1, len(doc.get("ledger", []))) * 30
    if monthly_expense == 0:
        return None
    # Emergency fund approximated as liquid assets (manual holdings cost basis)
    liquid = sum(
        h.get("cost_basis", 0.0)
        for h in doc.get("portfolio", {}).get("manual_holdings", [])
    )
    return liquid / monthly_expense


def current_ratio(doc: dict) -> Optional[float]:
    total_debt = abs(sum(d.get("balance", 0.0) for d in doc.get("debts", [])))
    income = monthly_income(doc)
    if total_debt == 0:
        return None
    return income / total_debt


def portfolio_volatility(returns: list[float]) -> Optional[float]:
    if len(returns) < 2:
        return None
    n = len(returns)
    mean = sum(returns) / n
    variance = sum((r - mean) ** 2 for r in returns) / (n - 1)
    return math.sqrt(variance)


def portfolio_sharpe(returns: list[float], risk_free_rate: float = 0.0) -> Optional[float]:
    if len(returns) < 2:
        return None
    vol = portfolio_volatility(returns)
    if vol is None or vol == 0:
        return None
    mean = sum(returns) / len(returns)
    return (mean - risk_free_rate) / vol
