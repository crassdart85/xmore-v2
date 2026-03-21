"""
KSA Intelligence Orchestrator — runs all KSA intelligence agents in order.
Returns list of material ticker symbols for composite_score boosting.
"""
import logging
import os

logger = logging.getLogger(__name__)


def run_ksa_intelligence(conn=None) -> list:
    """
    Run all KSA intelligence agents.
    Returns list of material .SR tickers (for 1.15x composite boost in run_agents_ksa).
    """
    if conn is None:
        import psycopg2
        conn = psycopg2.connect(os.environ["DATABASE_URL"])

    material_tickers = []

    # 1. Marketaux (API-based, fast)
    try:
        from agents.intelligence.ksa_intelligence.ksa_marketaux_agent import fetch_ksa_marketaux
        from config.ksa_universe import KSA_INITIAL_UNIVERSE
        tickers = fetch_ksa_marketaux(conn, KSA_INITIAL_UNIVERSE)
        material_tickers.extend(tickers)
        logger.info(f"[KSA] Marketaux done: {len(tickers)} material tickers")
    except Exception as e:
        logger.warning(f"[KSA] Marketaux error (non-fatal): {e}")

    # 2. Official Saudi Exchange announcements
    try:
        from agents.intelligence.ksa_intelligence.ksa_announcements_agent import fetch_ksa_announcements
        tickers = fetch_ksa_announcements(conn)
        material_tickers.extend(tickers)
        logger.info(f"[KSA] Announcements done: {len(tickers)} material tickers")
    except Exception as e:
        logger.warning(f"[KSA] Announcements error (non-fatal): {e}")

    # 3. Argaam RSS
    try:
        from agents.intelligence.ksa_intelligence.ksa_argaam_agent import fetch_ksa_argaam
        tickers = fetch_ksa_argaam(conn)
        material_tickers.extend(tickers)
        logger.info(f"[KSA] Argaam done: {len(tickers)} tickers mentioned")
    except Exception as e:
        logger.warning(f"[KSA] Argaam error (non-fatal): {e}")

    # 4. Fundamentals (Sunday only — self-guards internally)
    try:
        from agents.intelligence.ksa_intelligence.ksa_fundamentals_agent import fetch_ksa_fundamentals
        fetch_ksa_fundamentals(conn)
    except Exception as e:
        logger.warning(f"[KSA] Fundamentals error (non-fatal): {e}")

    unique = list(set(material_tickers))
    logger.info(f"[KSA] Intelligence complete: {len(unique)} unique material tickers")
    return unique
