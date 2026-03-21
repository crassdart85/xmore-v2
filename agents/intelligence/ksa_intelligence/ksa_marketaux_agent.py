"""
KSA Marketaux News Agent — fetches Saudi market news via Marketaux API.
Exchange filter: XSAU. Batches 3 tickers per request (free tier: 100 req/day).
"""
import os
import logging
import requests
import time
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

MARKETAUX_BASE  = "https://api.marketaux.com/v1/news/all"
BATCH_SIZE      = 3    # 3 tickers per request to stay within free tier
SOURCE_WEIGHT   = 0.70
MARKET_ID       = "KSA"


def fetch_ksa_marketaux(conn, tickers: list, hours_back: int = 25) -> list:
    """
    Fetch news for KSA tickers from Marketaux API.
    Returns list of material ticker symbols.
    """
    api_key = os.environ.get("MARKETAUX_API_KEY", "")
    if not api_key:
        logger.warning("[KSA] MARKETAUX_API_KEY not set — skipping")
        return []

    since = (datetime.utcnow() - timedelta(hours=hours_back)).strftime("%Y-%m-%dT%H:%M")
    material_tickers = []
    inserted = 0

    # Strip .SR suffix for API, rebatch
    codes = [t.replace(".SR", "") for t in tickers]

    for i in range(0, len(codes), BATCH_SIZE):
        batch     = codes[i : i + BATCH_SIZE]
        batch_sr  = [f"{c}.SR" for c in batch]
        symbols   = ",".join(batch)

        params = {
            "api_token":   api_key,
            "symbols":     symbols,
            "exchange":    "XSAU",
            "published_after": since,
            "limit":       50,
            "language":    "ar,en",
        }

        try:
            r = requests.get(MARKETAUX_BASE, params=params, timeout=15)
            r.raise_for_status()
            data = r.json().get("data", [])

            for article in data:
                ticker_list = [
                    f"{e.get('symbol', '')}.SR"
                    for e in article.get("entities", [])
                    if e.get("exchange") == "XSAU"
                ]
                if not ticker_list:
                    ticker_list = batch_sr

                sentiment = article.get("sentiment_score", 0.0) or 0.0
                headline  = article.get("title", "")[:500]
                url       = article.get("url", "")
                pub_at    = article.get("published_at", "")[:19]

                _insert_news(conn, headline, pub_at, "marketaux_ksa",
                             ticker_list, sentiment, SOURCE_WEIGHT, url)
                inserted += 1

                if abs(sentiment) > 0.4:
                    material_tickers.extend(ticker_list)

        except Exception as e:
            logger.warning(f"[KSA] Marketaux batch {batch} error: {e}")

        time.sleep(1.5)  # Rate limiting

    logger.info(f"[KSA] Marketaux: {inserted} articles inserted")
    return list(set(material_tickers))


def _insert_news(conn, title, date_str, source, tickers, sentiment, weight, url=""):
    import json
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO news (title, date, source, market_id, ticker_mentions,
                              sentiment_score, channel_weight, url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (title, date_str, source, MARKET_ID, json.dumps(tickers),
              sentiment, weight, url))
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.debug(f"[KSA] News insert failed: {e}")
    finally:
        cur.close()
