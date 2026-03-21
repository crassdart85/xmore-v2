"""
KSA Argaam RSS Agent — fetches Saudi financial news from Argaam RSS feeds.
"""
import logging
import time
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)

KSA_ARGAAM_FEEDS = [
    "https://www.argaam.com/ar/rss",
    "https://www.argaam.com/en/rss",
    "https://www.argaam.com/en/rss/Saudi",
]
SOURCE_WEIGHT = 0.65
MARKET_ID     = "KSA"


def fetch_ksa_argaam(conn, hours_back: int = 25) -> list:
    """
    Fetch Argaam RSS feeds and insert articles into news table.
    Returns list of mentioned .SR ticker symbols.
    """
    try:
        import feedparser
    except ImportError:
        logger.warning("[KSA] feedparser not installed — skipping Argaam")
        return []

    from config.ksa_universe import KSA_TICKER_CODES, KSA_TICKER_SR
    import re

    cutoff = datetime.utcnow() - timedelta(hours=hours_back)
    inserted = 0
    mentioned_tickers = []

    for feed_url in KSA_ARGAAM_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:40]:
                title   = getattr(entry, "title", "")
                summary = getattr(entry, "summary", "")
                text    = f"{title} {summary}"
                pub     = getattr(entry, "published_parsed", None)
                if pub:
                    pub_dt = datetime(*pub[:6])
                    if pub_dt < cutoff:
                        continue

                # Extract 4-digit codes
                codes = re.findall(r'\b(\d{4})\b', text)
                tickers = [f"{c}.SR" for c in codes if c in KSA_TICKER_CODES and f"{c}.SR" in KSA_TICKER_SR]

                pub_str = datetime(*pub[:6]).strftime("%Y-%m-%d %H:%M:%S") if pub else datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                _insert_news(conn, title[:500], pub_str, "argaam_ksa", tickers, SOURCE_WEIGHT, getattr(entry, "link", ""))
                inserted += 1
                mentioned_tickers.extend(tickers)

            time.sleep(1.0)
        except Exception as e:
            logger.warning(f"[KSA] Argaam feed {feed_url} error: {e}")

    logger.info(f"[KSA] Argaam: {inserted} articles inserted")
    return list(set(mentioned_tickers))


def _insert_news(conn, title, date_str, source, tickers, weight, url=""):
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO news (title, date, source, market_id, ticker_mentions, channel_weight, url)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (title, date_str, source, MARKET_ID, json.dumps(tickers), weight, url))
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.debug(f"[KSA] Argaam insert error: {e}")
    finally:
        cur.close()
