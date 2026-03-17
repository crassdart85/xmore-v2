"""Core two-stage DCF valuation engine."""

from __future__ import annotations

import logging

from agents.dcf.fcf_projector import project_fcf
from agents.dcf.wacc_calculator import calculate_wacc

logger = logging.getLogger(__name__)


def run_dcf(data: dict, scenario: str, config) -> dict | None:
    """Run a single scenario DCF valuation.

    Returns None if data is insufficient.
    """
    if not data.get("shares_outstanding"):
        logger.warning(f"[DCF:{data.get('ticker')}] No shares outstanding — skipping")
        return None

    projections = project_fcf(data, scenario, config)
    if not projections:
        logger.warning(f"[DCF:{data.get('ticker')}] No FCF projections — skipping")
        return None

    wacc_data = calculate_wacc(data, config)
    wacc = wacc_data["wacc"]

    sector = data.get("sector")
    term_g = config.SECTOR_TERMINAL_GROWTH.get(sector, config.SECTOR_TERMINAL_GROWTH["default"])

    # Stage 1: PV of projected quarterly FCF
    pv_stage1 = 0.0
    for p in projections:
        t = p["year_frac"]
        fcf = p.get("fcf_proj", 0)
        disc = (1 + wacc) ** t
        pv_stage1 += (fcf / disc) if disc else 0

    # Stage 2: Terminal value (Gordon Growth)
    year5_fcf = sum(p.get("fcf_proj", 0) for p in projections if p.get("year") == 5)
    year5_annual_fcf = year5_fcf * 4

    if wacc <= term_g:
        term_g = wacc * 0.5
        logger.warning(f"[DCF:{data.get('ticker')}]: WACC <= terminal_g; clamped g to {term_g:.2%}")

    terminal_value = year5_annual_fcf * (1 + term_g) / max(wacc - term_g, 1e-9)
    pv_terminal = terminal_value / ((1 + wacc) ** 5)

    ev = pv_stage1 + pv_terminal
    net_debt = (data.get("total_debt") or 0) - (data.get("cash_and_equivalents") or 0)
    equity_value = max(0, ev - net_debt)

    shares = data.get("shares_outstanding") or 1
    intrinsic_per_share = equity_value / shares if shares else 0

    current_price = data.get("current_price") or 0
    mos = ((intrinsic_per_share - current_price) / intrinsic_per_share) if intrinsic_per_share else -1.0

    # Labeling
    c = config
    if mos > c.DEEP_VALUE_THRESHOLD:
        label = "DEEP_VALUE"
    elif mos > c.UNDERVALUED_THRESHOLD:
        label = "UNDERVALUED"
    elif mos > -c.FAIR_VALUE_BAND:
        label = "FAIR"
    elif mos > c.OVERVALUED_THRESHOLD:
        label = "OVERVALUED"
    else:
        label = "SPECULATIVE"

    upside_pct = mos * 100

    return {
        "ticker": data.get("ticker"),
        "scenario": scenario,
        "intrinsic_per_share": round(intrinsic_per_share, 2),
        "current_price": round(current_price, 2),
        "margin_of_safety": round(mos, 4),
        "upside_pct": round(upside_pct, 2),
        "valuation_label": label,
        "dcf_confidence": data.get("data_quality", {}).get("confidence", "LOW"),
        "enterprise_value": round(ev, 0),
        "equity_value": round(equity_value, 0),
        "pv_stage1": round(pv_stage1, 0),
        "pv_terminal": round(pv_terminal, 0),
        "terminal_value_pct": round(pv_terminal / ev * 100, 1) if ev > 0 else None,
        "wacc": wacc_data.get("wacc"),
        "cost_of_equity": wacc_data.get("cost_of_equity"),
        "beta_used": wacc_data.get("beta_used"),
        "terminal_growth": term_g,
        "net_debt": round(net_debt, 0),
        "years_of_data": data.get("data_quality", {}).get("years_available"),
    }
