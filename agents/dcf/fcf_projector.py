"""Project Free Cash Flow (FCF) for a 5-year explicit forecast horizon."""

from __future__ import annotations

from typing import Dict, List


def project_fcf(data: dict, scenario: str, config) -> List[dict]:
    """Project quarterly FCF for 5 years (20 quarters).

    Args:
      data: Output of collect_financial_data
      scenario: 'bull' | 'base' | 'bear'
      config: EgyptDCFConfig instance

    Returns:
      List of dicts with keys: quarter, year, year_frac, revenue_proj, fcf_proj
    """
    sector = data.get("sector")
    sg_rates = config.SECTOR_REVENUE_GROWTH.get(sector, config.SECTOR_REVENUE_GROWTH["default"])
    annual_revenue_growth = sg_rates.get(scenario, sg_rates.get("base", 0.0))

    # Base revenue: latest annual revenue, else inferred from market cap
    rev_hist = sorted(data.get("revenue_history", []), key=lambda x: x.get("year", 0))
    if rev_hist:
        base_revenue = rev_hist[-1].get("revenue") or 0
    elif data.get("market_cap"):
        base_revenue = data.get("market_cap") / 1.5  # assumed PS ratio
    else:
        return []

    # FCF margin: historical average or sector fallback
    fcf_margin = (data.get("fcf_margin_avg") or
                  config.SECTOR_FCF_MARGIN.get(sector) or
                  config.SECTOR_FCF_MARGIN.get("default", 0.10))

    # Scenario adjustments
    margin_adj = {"bull": 1.15, "base": 1.00, "bear": 0.80}.get(scenario, 1.0)
    fcf_margin *= margin_adj

    # Use earnings-based model for banks
    if sector == "Banking":
        return _project_bank_fcf(data, scenario, config)

    projections = []
    current_revenue = base_revenue

    for year in range(1, 6):
        current_revenue *= (1 + annual_revenue_growth)

        year_margin = fcf_margin
        if scenario == "bull":
            year_margin *= (1 + 0.02 * year)
        elif scenario == "bear":
            year_margin *= (1 - 0.01 * year)

        annual_fcf = current_revenue * year_margin
        quarterly_fcf = annual_fcf / 4

        for q in range(1, 5):
            quarter_num = (year - 1) * 4 + q
            projections.append({
                "quarter": quarter_num,
                "year": year,
                "year_frac": quarter_num / 4,
                "revenue_proj": current_revenue / 4,
                "fcf_proj": quarterly_fcf,
            })

    return projections


def _project_bank_fcf(data: dict, scenario: str, config=None) -> List[dict]:
    """Project "FCF" for banks using net income after reinvestment.

    Banks do not generate traditional free cash flow; use distributable earnings.
    """
    ni_hist = sorted(data.get("net_income_history", []), key=lambda x: x.get("year", 0))
    if not ni_hist:
        return []

    base_ni = ni_hist[-1].get("net_income") or 0
    growth = {"bull": 0.20, "base": 0.15, "bear": 0.08}.get(scenario, 0.15)
    reinvest_rate = 0.30

    projections = []
    current_ni = base_ni
    for year in range(1, 6):
        current_ni *= (1 + growth)
        distributable = current_ni * (1 - reinvest_rate)
        quarterly = distributable / 4
        for q in range(1, 5):
            qn = (year - 1) * 4 + q
            projections.append({
                "quarter": qn,
                "year": year,
                "year_frac": qn / 4,
                "fcf_proj": quarterly,
            })
    return projections
