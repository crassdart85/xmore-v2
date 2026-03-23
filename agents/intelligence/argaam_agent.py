"""Argaam Agent — Saudi/Tadawul RSS feeds mapped to the KSA universe."""
import logging
from datetime import datetime, timedelta, timezone

try:
    import feedparser
    import dateutil.parser
except ImportError:
    feedparser = None
    dateutil = None

logger = logging.getLogger(__name__)

FEEDS = [
    ("https://www.argaam.com/en/rss",        "en"),
    ("https://www.argaam.com/ar/rss",        "ar"),
]


def fetch_argaam_news(hours_back: int = 25) -> list:
    if feedparser is None:
        logger.warning("[INTEL:ARGAAM] feedparser not installed — skipping")
        return []

    from agents.intelligence.market_universe import match_ticker_from_text

    articles = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)

    for feed_url, lang in FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries:
                pub_dt = _parse_feed_date(entry)
                if pub_dt < cutoff:
                    continue

                title   = entry.get("title", "")
                summary = entry.get("summary", "")
                url     = entry.get("link", "")
                full    = f"{title} {summary}"

                ticker = match_ticker_from_text(full)
                if not ticker:
                    continue

                articles.append({
                    "source":          "argaam",
                    "ticker":          ticker,
                    "headline":        title[:500],
                    "snippet":         summary[:500],
                    "url":             url,
                    "published_at":    pub_dt.isoformat(),
                    "language":        lang,
                    "sentiment_score": None,
                })
        except Exception as e:
            logger.error(f"[INTEL:ARGAAM] Feed {feed_url}: {e}")

    logger.info(f"[INTEL:ARGAAM] {len(articles)} articles matched to Tadawul tickers")
    return articles


def _parse_feed_date(entry) -> datetime:
    try:
        ts = entry.get("published_parsed") or entry.get("updated_parsed")
        if ts:
            return datetime(*ts[:6], tzinfo=timezone.utc)
    except Exception as e:
        logger.debug(f"[INTEL:ARGAAM] Failed to parse feed date: {e}")
    return datetime.now(timezone.utc)
