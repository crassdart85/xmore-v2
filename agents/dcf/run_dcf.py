"""Standalone DCF valuation pipeline (weekly cron job)."""

from __future__ import annotations

import logging
import sys
import time
from datetime import datetime, timezone

from database import get_connection
from agents.dcf.dcf_config import EgyptDCFConfig
from agents.dcf.data_collector import collect_financial_data
from agents.dcf.scenario_runner import run_all_scenarios
from agents.dcf.dcf_store import store_dcf_results
from agents.intelligence.egx_universe import EGX_TOP50

logger = logging.getLogger(__name__)


def run_dcf_pipeline(db_conn, force: bool = False) -> dict:
    """Run the full DCF pipeline for the EGX top 50 universe."""
    today = datetime.now(timezone.utc)
    if not force and today.weekday() != 6:  # Sunday=6
        logger.info("[DCF] Skipping — runs on Sundays only (use --force to override)")
        return {"skipped": True}

    logger.info("[DCF] Starting DCF valuation pipeline")
    config = EgyptDCFConfig()

    results = {
        "total": 0,
        "succeeded": 0,
        "failed": 0,
        "deep_value": [],
        "undervalued": [],
        "fair": [],
        "overvalued": [],
        "speculative": [],
        "low_confidence": [],
        "errors": [],
    }

    for ca, yahoo, name_ar, name_en, sector, *_ in EGX_TOP50:
        logger.info(f"[DCF] Processing {ca} — {name_en} ({sector})")
        results["total"] += 1

        try:
            data = collect_financial_data(ca, yahoo, sector)
            scenarios = run_all_scenarios(data, config)
            if not scenarios:
                logger.warning(f"[DCF:{ca}] No scenarios computed")
                results["failed"] += 1
                continue

            store_dcf_results(db_conn, scenarios, ca)

            composite = scenarios.get("composite")
            if composite:
                label = composite.get("valuation_label")
                conf = composite.get("dcf_confidence")
                results.setdefault(label.lower(), []).append({
                    "ticker": ca,
                    "name": name_en,
                    "iv": composite.get("intrinsic_per_share"),
                    "price": composite.get("current_price"),
                    "mos": composite.get("margin_of_safety"),
                    "upside": composite.get("upside_pct"),
                    "conf": conf,
                })
                if conf == "LOW":
                    results["low_confidence"].append(ca)

            results["succeeded"] += 1

        except Exception as e:
            logger.error(f"[DCF:{ca}] Unhandled error: {e}", exc_info=True)
            results["failed"] += 1
            results["errors"].append({"ticker": ca, "error": str(e)})

        # Rate limit yfinance
        time.sleep(1.5)

    logger.info("[DCF] Pipeline complete: %s succeeded, %s failed", results["succeeded"], results["failed"])
    return results


if __name__ == "__main__":
    # Command line runner
    force = "--force" in sys.argv
    with get_connection() as conn:
        run_dcf_pipeline(conn, force=force)
