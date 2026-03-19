"""Run multiple DCF scenarios and build a composite valuation."""

from __future__ import annotations

from datetime import datetime, timezone
import logging

from agents.dcf.dcf_engine import run_dcf


logger = logging.getLogger(__name__)


def run_all_scenarios(data: dict, config) -> dict:
    """Run bull/base/bear scenarios and build a weighted composite."""
    weights = {"bull": 0.25, "base": 0.50, "bear": 0.25}

    results = {}
    for scenario in ["bull", "base", "bear"]:
        try:
            r = run_dcf(data, scenario, config)
            if r:
                results[scenario] = r
        except Exception as e:
            logger.warning("DCF scenario '%s' failed: %s", scenario, e)

    if not results:
        return {}

    # Calculate weighted intrinsic value, renormalizing weights for available scenarios
    weighted_iv = sum(results[s]["intrinsic_per_share"] * weights.get(s, 0)
                      for s in results)
    total_weight = sum(weights.get(s, 0) for s in results)
    if total_weight > 0:
        weighted_iv = weighted_iv / total_weight

    current = results.get("base", {}).get("current_price") or 0
    mos = (weighted_iv - current) / weighted_iv if weighted_iv > 0 else -1

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

    return {
        "bull": results.get("bull"),
        "base": results.get("base"),
        "bear": results.get("bear"),
        "composite": {
            "ticker": data.get("ticker"),
            "intrinsic_per_share": round(weighted_iv, 2),
            "current_price": round(current, 2),
            "margin_of_safety": round(mos, 4),
            "upside_pct": round(mos * 100, 2),
            "valuation_label": label,
            "dcf_confidence": data.get("data_quality", {}).get("confidence", "LOW"),
            "computed_at": datetime.now(timezone.utc).isoformat(),
        },
    }
