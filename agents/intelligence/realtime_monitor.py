"""
Real-time Monitor — Polls EGX announcements every 15 min during trading hours.
Runs as a standalone process (not GitHub Actions). Start with:
  python agents/intelligence/realtime_monitor.py
"""
import logging
import os
import time
import requests
from datetime import datetime

try:
    import schedule
    from zoneinfo import ZoneInfo
except ImportError:
    schedule = None
    ZoneInfo = None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

INTERNAL_API    = os.environ.get("INTERNAL_API_URL", "https://xmore-project.onrender.com")
INTERNAL_SECRET = os.environ.get("INTERNAL_API_SECRET", "")


def check_announcements():
    if ZoneInfo is None:
        return
    CAIRO = ZoneInfo("Africa/Cairo")
    now   = datetime.now(CAIRO)
    # Sun–Thu only (weekday 6=Sun in Python's Monday=0 convention... actually 0=Mon, 6=Sun)
    # EGX trades Sun-Thu → Python weekdays: Sun=6, Mon=0, ..., Thu=3
    if now.weekday() not in (6, 0, 1, 2, 3):
        return
    if not (9 <= now.hour < 15):
        return

    from agents.intelligence.egx_announcements_agent import fetch_egx_announcements
    items    = fetch_egx_announcements(hours_back=0.3)
    material = [i for i in items if i.get("is_material")]

    for item in material:
        ticker = item.get("ticker", "")
        logger.warning(f"[REALTIME] Material event: {ticker} — {item.get('headline','')[:60]}")
        # Store to DB
        try:
            from database import get_connection
            from agents.intelligence.news_aggregator import aggregate_and_store
            with get_connection() as conn:
                aggregate_and_store(conn, [item])
        except Exception as e:
            logger.error(f"[REALTIME] DB store failed: {e}")
        # Trigger rescore via internal API
        try:
            requests.post(
                f"{INTERNAL_API}/api/internal/rescore",
                json={"ticker": ticker, "reason": item.get("headline", "")},
                headers={"X-Internal-Secret": INTERNAL_SECRET},
                timeout=5,
            )
        except Exception as e:
            logger.error(f"[REALTIME] Rescore trigger failed: {e}")


def run_realtime_monitor():
    if schedule is None:
        logger.error("[REALTIME] schedule package not installed — pip install schedule")
        return

    schedule.every(15).minutes.do(check_announcements)
    logger.info("[REALTIME] Monitor started — polling every 15 min during market hours")
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    run_realtime_monitor()
