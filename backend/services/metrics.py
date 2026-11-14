from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Optional


def _f(v) -> float:
    try:
        return float(v or 0.0)
    except (TypeError, ValueError):
        return 0.0


def position_value(h: dict) -> float:
    """Value of a manual brokerage position: current_value if set, else cost_basis."""
    cv = h.get("current_value")
    return _f(cv if cv is not None else h.get("cost_basis"))


def public_value(portfolio: dict) -> float:
    cache = portfolio.get("public_cache") or {}
    v = _f(cache.get("account_value"))
    if not v:
        v = sum(_f(h.get("current_value") or h.get("cost_basis_total")) for h in cache.get("holdings") or [])
    return v


def ibkr_synced_value(portfolio: dict) -> float:
    """Value of the IBKR account pulled through the Flex Web Service (positions + cash)."""
    cache = portfolio.get("ibkr_cache") or {}
    v = _f(cache.get("account_value"))
    if not v:
        v = sum(_f(h.get("current_value")) for h in cache.get("holdings") or []) + _f(cache.get("cash"))
    return v


def business_stake(b: dict) -> float:
    pct = b.get("ownership_pct")
    pct = 100.0 if pct is None else _f(pct)
    return _f(b.get("valuation")) * pct / 100.0


def fixed_income_value(f: dict) -> float:
    cv = f.get("current_value")
    return _f(cv if cv is not None else f.get("face_value"))


def asset_values(doc: dict) -> dict[str, float]:
    """Value of every asset class; the single source for net worth, dashboard, risk and PDF."""
    p = doc.get("portfolio") or {}
    manual = ibkr = other = 0.0
    for h in p.get("manual_holdings", []):
        acct = h.get("account") or "manual"
        v = position_value(h)
        if acct == "ibkr":
            ibkr += v
        elif acct == "other":
            other += v
        else:
            manual += v
    out = {
        "public": public_value(p),
        "manual": manual,
        "ibkr": ibkr + ibkr_synced_value(p),
        "other_brokers": other,
        "real_estate": sum(_f(r.get("current_value")) for r in p.get("real_estate", [])),
        "businesses": sum(business_stake(b) for b in p.get("businesses", [])),
        "fixed_income": sum(fixed_income_value(f) for f in p.get("fixed_income", [])),
        "cash": sum(_f(c.get("balance")) for c in p.get("cash_accounts", [])),
    }
    out["total"] = sum(out.values())
    return out


def investable_value(vals: dict[str, float]) -> float:
    """Market-valued holdings (excludes real estate and businesses)."""
    return (vals["public"] + vals["manual"] + vals["ibkr"] + vals["other_brokers"]
            + vals["fixed_income"] + vals["cash"])


def asset_slices(vals: dict[str, float]) -> list[dict]:
    """Non-zero asset classes for donut charts (dashboard net worth, risk exposure)."""
    inv = vals["public"] + vals["manual"] + vals["ibkr"] + vals["other_brokers"]
    items = [("Investments", inv), ("Fixed Income", vals["fixed_income"]),
             ("Real Estate", vals["real_estate"]), ("Businesses", vals["businesses"]),
             ("Cash", vals["cash"])]
    return [{"name": n, "value": v} for n, v in items if v]


def brokerage_positions(doc: dict) -> list[dict]:
    """Per-symbol values across Public.com and all manually entered brokerage positions."""
    p = doc.get("portfolio") or {}
    out = [
        {"name": h.get("symbol", ""), "value": _f(h.get("current_value") or h.get("cost_basis_total"))}
        for h in (p.get("public_cache") or {}).get("holdings") or []
        if h.get("symbol")
    ]
    out += [{"name": h.get("symbol", ""), "value": _f(h.get("current_value"))}
            for h in (p.get("ibkr_cache") or {}).get("holdings") or [] if h.get("symbol")]
    out += [{"name": h.get("symbol", ""), "value": position_value(h)}
            for h in p.get("manual_holdings", []) if h.get("symbol")]
    return out


def current_assets(doc: dict) -> float:
    return investable_value(asset_values(doc))


def total_debt(doc: dict) -> float:
    return sum(abs(_f(d.get("balance"))) for d in doc.get("debts", []))


def net_worth(doc: dict) -> float:
    return asset_values(doc)["total"] - total_debt(doc)


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


EXPENSE_WINDOW_DAYS = 90
_AVG_DAYS_PER_MONTH = 365.25 / 12


def _entry_date(entry: dict) -> Optional[date]:
    try:
        return date.fromisoformat(str(entry.get("date", ""))[:10])
    except ValueError:
        return None


def average_monthly_expenses(doc: dict, today: Optional[date] = None) -> Optional[float]:
    """Average monthly spending from the ledger over the trailing 90 days.

    Spending = ledger entries with a negative amount. If the ledger covers less
    than 90 days, the average is taken over the period it does cover (but never
    less than one month, so a single week of entries isn't scaled up 4x).
    """
    today = today or date.today()
    window_start = today - timedelta(days=EXPENSE_WINDOW_DAYS)
    dated = [(d, e.get("amount", 0.0)) for e in doc.get("ledger", []) if (d := _entry_date(e)) and d <= today]
    if not dated:
        return None
    spent = sum(-amt for d, amt in dated if amt < 0 and d > window_start)
    if spent <= 0:
        return None
    first = max(min(d for d, _ in dated), window_start)
    span_days = min(max((today - first).days + 1, 30), EXPENSE_WINDOW_DAYS)
    return spent / span_days * _AVG_DAYS_PER_MONTH


def liquid_assets(doc: dict) -> float:
    """Money available immediately: cash account balances (not investments)."""
    return sum(c.get("balance", 0.0) for c in doc.get("portfolio", {}).get("cash_accounts", []))


def emergency_fund_months(doc: dict, today: Optional[date] = None) -> Optional[float]:
    """Months of spending the household could cover from cash alone."""
    monthly_expense = average_monthly_expenses(doc, today)
    if not monthly_expense:
        return None
    return liquid_assets(doc) / monthly_expense


INCOME_CATEGORY = "income"


def is_income_entry(entry: dict) -> bool:
    """A ledger entry counts as income only when its category is "Income" (any case)."""
    return str(entry.get("category", "")).strip().lower() == INCOME_CATEGORY


def income_to_date(doc: dict, today: Optional[date] = None) -> tuple[float, float]:
    """(month-to-date, year-to-date) income received: ledger entries categorised "Income".

    Amounts are netted, so a negative "Income" entry (e.g. a clawback) reduces the total.
    """
    today = today or date.today()
    mtd = ytd = 0.0
    for e in doc.get("ledger", []):
        d = _entry_date(e)
        if not is_income_entry(e) or d is None or d > today or d.year != today.year:
            continue
        amt = e.get("amount", 0.0)
        ytd += amt
        if d.month == today.month:
            mtd += amt
    return mtd, ytd


def current_liabilities(doc: dict) -> float:
    """Debt due within 12 months: min(balance, 12 x min payment), or full balance if no min payment."""
    total = 0.0
    for d in doc.get("debts", []):
        bal = abs(_f(d.get("balance")))
        mp = _f(d.get("min_payment"))
        total += min(bal, 12 * mp) if mp > 0 else bal
    return total


def current_ratio(doc: dict) -> Optional[float]:
    """Liquid assets (cash, brokerage, fixed income) / debt due in the next 12 months."""
    liabilities = current_liabilities(doc)
    if liabilities <= 0:
        return None
    return current_assets(doc) / liabilities


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


TRADING_DAYS = 252
RISK_FREE_RATE = 0.04  # annual
MIN_RETURNS = 5


def history_returns(history: list[dict]) -> list[float]:
    """Simple daily returns from consecutive snapshots; zero-value days are skipped."""
    returns: list[float] = []
    prev: Optional[float] = None
    for pt in history:
        v = pt.get("value")
        if v is None:
            continue
        if prev is not None and prev > 0:
            returns.append(v / prev - 1.0)
        prev = v
    return returns


def portfolio_risk_stats(history: list[dict]) -> tuple[Optional[float], Optional[float]]:
    """Return (annualised sharpe, annualised volatility); None when history is too short."""
    returns = history_returns(history)
    if len(returns) < MIN_RETURNS:
        return None, None
    daily_vol = portfolio_volatility(returns)
    if daily_vol is None:
        return None, None
    vol = daily_vol * math.sqrt(TRADING_DAYS)
    if daily_vol == 0:
        return None, vol
    mean_annual = (sum(returns) / len(returns)) * TRADING_DAYS
    return (mean_annual - RISK_FREE_RATE) / vol, vol
