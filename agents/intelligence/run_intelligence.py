"""
Intelligence Pipeline Orchestrator.
Called from run_agents.py BEFORE all trading agents.
"""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def run_intelligence_pipeline(conn) -> dict:
    """
    Run all news/intelligence batch agents and store results.
    Called inside the existing `with get_connection() as conn:` block in run_agents.py.
    Returns dict with per-source counts and material_tickers list.
    """
    start     = datetime.now()
    all_items = []
    results   = {}

    # Lazy imports (avoid import-time failures)
    from agents.intelligence.marketaux_agent    import fetch_marketaux_news
    from agents.intelligence.mubasher_agent     import fetch_mubasher_news
    from agents.intelligence.egx_announcements_agent import fetch_egx_announcements
    from agents.intelligence.argaam_agent       import fetch_argaam_news
    from agents.intelligence.news_aggregator    import aggregate_and_store
    from agents.intelligence.fundamentals_agent import run_fundamentals
    from agents.intelligence.insider_agent      import fetch_insider_data

    AGENTS = [
        ("MARKETAUX", fetch_marketaux_news),
        ("MUBASHER",  fetch_mubasher_news),
        ("EGX",       fetch_egx_announcements),
        ("ARGAAM",    fetch_argaam_news),
    ]

    for name, fn in AGENTS:
        try:
            items = fn()
            all_items.extend(items)
            results[name] = len(items)
        except Exception as e:
            results[name] = 0
            logger.error(f"[INTEL:{name}] FAILED: {e}")

    # Aggregate + store
    agg = {"new_inserted": 0, "duplicates_skipped": 0, "material_events": []}
    try:
        agg = aggregate_and_store(conn, all_items)
        results["stored"]           = agg["new_inserted"]
        results["material_tickers"] = agg["material_events"]
    except Exception as e:
        logger.error(f"[INTEL:AGGREGATOR] FAILED: {e}")

    # Sunday-only agents (non-fatal)
    try:
        run_fundamentals(conn)
    except Exception as e:
        logger.error(f"[INTEL:FUNDAMENTALS] {e}")

    try:
        fetch_insider_data(conn)
    except Exception as e:
        logger.error(f"[INTEL:INSIDER] {e}")

    elapsed = (datetime.now() - start).seconds
    total   = sum(v for k, v in results.items() if isinstance(v, int) and k not in ("stored",))
    logger.info(
        f"[INTEL] ✓ Complete in {elapsed}s | "
        f"{total} fetched | {agg['new_inserted']} new | "
        f"{len(agg['material_events'])} material tickers"
    )
    return results
