"""Marketaux Agent — English/Arabic news for the KSA/Tadawul universe."""
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

    from agents.intelligence.market_universe import TICKERS, normalize_symbol

    yesterday = (datetime.now(timezone.utc) - timedelta(hours=hours_back)).strftime("%Y-%m-%dT%H:%M")
    all_articles = []

    for i in range(0, len(TICKERS), 3):
        batch_symbols = TICKERS[i:i+3]
        batch = ",".join(batch_symbols)
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
                    ticker = normalize_symbol(entity.get("symbol", ""))
                    if not ticker:
                        continue
                    all_articles.append({
                        "source":          "marketaux",
                        "ticker":          ticker,
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

    logger.info(f"[INTEL:MARKETAUX] {len(all_articles)} articles fetched ({(len(TICKERS)+2)//3} requests)")
    return all_articles
