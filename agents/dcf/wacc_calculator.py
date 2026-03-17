"""WACC calculator tuned for Egypt (CBE rates, ERP, sector spreads)."""

from __future__ import annotations


def calculate_wacc(data: dict, config) -> dict:
    """Calculate WACC (weighted average cost of capital) and components.

    Returns dict with keys:
      wacc, cost_of_equity, cost_of_debt, beta_used, weight_equity, weight_debt
    """
    beta = data.get("beta") or 1.0
    beta = max(0.5, min(beta, 2.5))

    # CAPM cost of equity
    ke = config.RISK_FREE_RATE + beta * config.EQUITY_RISK_PREMIUM

    # Cost of debt proxyed off risk-free + credit spread
    kd = config.RISK_FREE_RATE + 0.01
    sector_spread = {
        "Banking": -0.02,
        "Technology": 0.02,
        "Real Estate": 0.01,
        "default": 0.0,
    }
    kd += sector_spread.get(data.get("sector"), 0.0)

    mktcap = data.get("market_cap") or 1.0
    debt = data.get("total_debt") or 0.0
    total_v = max(1.0, mktcap + debt)

    weight_equity = mktcap / total_v
    weight_debt = debt / total_v

    tax_rate = data.get("tax_rate", 0.225)

    wacc = (ke * weight_equity) + (kd * weight_debt * (1 - tax_rate))
    wacc = max(0.15, min(wacc, 0.40))

    return {
        "wacc": round(wacc, 4),
        "cost_of_equity": round(ke, 4),
        "cost_of_debt": round(kd, 4),
        "beta_used": round(beta, 3),
        "weight_equity": round(weight_equity, 3),
        "weight_debt": round(weight_debt, 3),
    }
