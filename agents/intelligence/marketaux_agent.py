"""
Marketaux Agent — English/Arabic financial news with pre-scored sentiment.
Free tier: 100 req/day. Batches 3 tickers per request = ~17 requests for 50 tickers.
"""
import os
import time
import logging
import requests
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

def fetch_marketaux_news(hours_back: int = 25) -> list:
    api_key = os.environ.get("MARKETAUX_API_KEY", "")
    if not api_key:
        logger.warning("[INTEL:MARKETAUX] MARKETAUX_API_KEY not set — skipping")
        return []

    from agents.intelligence.egx_universe import CA_TICKERS, TICKER_BY_CA

    yesterday = (datetime.now(timezone.utc) - timedelta(hours=hours_back)).strftime("%Y-%m-%dT%H:%M")
    all_articles = []

    for i in range(0, len(CA_TICKERS), 3):
        batch = ",".join([f"{t}.CA" for t in CA_TICKERS[i:i+3]])
        url = (
            f"https://api.marketaux.com/v1/news/all"
            f"?symbols={batch}"
            f"&filter_entities=true"
            f"&language=en,ar"
            f"&published_after={yesterday}"
            f"&limit=3"
            f"&api_token={api_key}"
        )
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 429:
                logger.warning("[INTEL:MARKETAUX] Rate limited — sleeping 65s")
                time.sleep(65)
                resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            for article in data.get("data", []):
                for entity in article.get("entities", []):
                    ticker_raw = entity.get("symbol", "").replace(".CA", "")
                    if ticker_raw not in TICKER_BY_CA:
                        continue
                    all_articles.append({
                        "source":          "marketaux",
                        "ticker":          ticker_raw,
                        "headline":        article.get("title", ""),
                        "snippet":         article.get("snippet", ""),
                        "url":             article.get("url", ""),
                        "published_at":    article.get("published_at"),
                        "language":        article.get("language", "en"),
                        "sentiment_score": entity.get("sentiment_score"),
                        "highlight":       (entity.get("highlights") or [{}])[0].get("highlight", ""),
                    })
        except Exception as e:
            logger.error(f"[INTEL:MARKETAUX] Batch {batch}: {e}")
        time.sleep(1.0)

    logger.info(f"[INTEL:MARKETAUX] {len(all_articles)} articles fetched ({(len(CA_TICKERS)+2)//3} requests)")
    return all_articles
