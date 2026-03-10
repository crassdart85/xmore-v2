"""
Gemini-powered Sentiment Analysis Module

Primary news source : Enterprise Egypt (bilingual EN/AR, EGX-focused)
Fallback 1          : Mubasher EGX RSS EN + AR (free, no key)
Fallback 2          : Finnhub API per-symbol headlines
AI model            : gemini-2.5-flash (free tier: 10 req/min, 1,500 req/day)
Scoring             : Gemini returns sentiment text -> mapped to ±0.7/0.0

Drop-in replacement for sentiment.py — same public API:
  collect_sentiment()          -> main entry point
  get_latest_sentiment(symbol) -> query DB
  get_all_latest_sentiment()   -> query DB
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta

import finnhub
import config
from database import create_tables, get_connection, log_system_run
from egx_symbols import EGX_SYMBOL_DATABASE

from ana_lyze import prompts
from ana_lyze.CallGenAI import CallGemma
from ana_lyze.ScrapeWeb import ScrapeEnterprise

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")

# ── Company name → Yahoo symbol lookup ──────────────────────────────────────
# Built from EGX_SYMBOL_DATABASE so Gemini output can be matched to a ticker
_NAME_TO_SYMBOL: dict = {}
for _ticker, _stock in EGX_SYMBOL_DATABASE.items():
    _NAME_TO_SYMBOL[_stock.name_en.lower()] = _stock.yahoo
    _NAME_TO_SYMBOL[_stock.name_ar.lower()] = _stock.yahoo
    _NAME_TO_SYMBOL[_ticker.lower()] = _stock.yahoo

# Company list JSON passed inside the Gemini prompt so it can identify tickers
_COMPANY_LIST_JSON = json.dumps(
    [
        {"name": s.name_en, "name_ar": s.name_ar, "symbol": s.yahoo}
        for s in EGX_SYMBOL_DATABASE.values()
    ],
    ensure_ascii=False,
)


# ── SQL helpers ──────────────────────────────────────────────────────────────

def _adapt_sql(sql: str) -> str:
    """Convert SQLite placeholders/syntax to PostgreSQL when DATABASE_URL is set."""
    if DATABASE_URL:
        sql = sql.replace("?", "%s")
        sql = sql.replace("INSERT OR IGNORE", "INSERT")
        if "INSERT" in sql and "ON CONFLICT" not in sql:
            sql = sql.rstrip().rstrip(")") + ") ON CONFLICT DO NOTHING"
    return sql


# ── Table management ─────────────────────────────────────────────────────────

def create_sentiment_table():
    """Create sentiment_scores table if it doesn't exist."""
    auto_id = "SERIAL PRIMARY KEY" if DATABASE_URL else "INTEGER PRIMARY KEY AUTOINCREMENT"
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS sentiment_scores (
                id {auto_id},
                symbol TEXT NOT NULL,
                date DATE NOT NULL,
                avg_sentiment REAL,
                sentiment_label TEXT,
                article_count INTEGER DEFAULT 0,
                positive_count INTEGER DEFAULT 0,
                negative_count INTEGER DEFAULT 0,
                neutral_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, date)
            )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_sentiment_symbol_date "
            "ON sentiment_scores(symbol, date)"
        )
        logger.info("Sentiment table ready")


def _save_sentiment(
    symbol, date, avg_sentiment, label,
    article_count, positive_count, negative_count, neutral_count,
):
    """Upsert a sentiment record for one symbol/date."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            _adapt_sql("""
                INSERT OR IGNORE INTO sentiment_scores
                (symbol, date, avg_sentiment, sentiment_label, article_count,
                 positive_count, negative_count, neutral_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """),
            (symbol, date, avg_sentiment, label, article_count,
             positive_count, negative_count, neutral_count),
        )


# ── Public query helpers (same API as sentiment.py) ──────────────────────────

def get_latest_sentiment(symbol: str) -> dict:
    """Return most recent sentiment record for a symbol, or None."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            _adapt_sql("""
                SELECT * FROM sentiment_scores
                WHERE symbol = ?
                ORDER BY date DESC
                LIMIT 1
            """),
            (symbol,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def get_all_latest_sentiment() -> list:
    """Return the most recent sentiment record for every symbol."""
    with get_connection() as conn:
        cursor = conn.cursor()
        if DATABASE_URL:
            cursor.execute("""
                SELECT DISTINCT ON (symbol) *
                FROM sentiment_scores
                ORDER BY symbol, date DESC
            """)
        else:
            cursor.execute("""
                SELECT s.*
                FROM sentiment_scores s
                INNER JOIN (
                    SELECT symbol, MAX(date) as max_date
                    FROM sentiment_scores
                    GROUP BY symbol
                ) latest ON s.symbol = latest.symbol AND s.date = latest.max_date
            """)
        return [dict(row) for row in cursor.fetchall()]


# ── Company matching ──────────────────────────────────────────────────────────

def _match_company_to_symbol(company_name: str) -> str | None:
    """
    Map a company name returned by Gemini to a Yahoo Finance symbol.
    Tries exact match first, then substring match.
    """
    if not company_name:
        return None
    name_lower = company_name.lower().strip()
    if name_lower in _NAME_TO_SYMBOL:
        return _NAME_TO_SYMBOL[name_lower]
    for known, symbol in _NAME_TO_SYMBOL.items():
        if name_lower in known or known in name_lower:
            return symbol
    return None


# ── Fallback 1: Mubasher EGX RSS (free, no key) ──────────────────────────────

MUBASHER_EGX_RSS_EN = "http://feeds.mubasher.info/en/EGX/news"
MUBASHER_EGX_RSS_AR = "http://feeds.mubasher.info/ar/EGX/news"


def _fetch_mubasher_articles() -> list:
    """
    Free EGX-focused RSS feeds from Mubasher (EN + AR). No API key required.
    Arabic headlines are passed to Gemini as-is — it handles Arabic natively.
    Returns articles in the same format as _fetch_recent_articles().
    """
    import feedparser
    import calendar as _calendar
    _now_ts = time.time()

    articles = []
    for url, lang in [(MUBASHER_EGX_RSS_EN, "EN"), (MUBASHER_EGX_RSS_AR, "AR")]:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:25]:  # cap per feed to keep total ~50
                headline = entry.get("title", "")
                summary = entry.get("summary", "")
                if headline:
                    pub = entry.get("published_parsed")
                    days_ago = max(0.0, (_now_ts - _calendar.timegm(pub)) / 86400) if pub else 1.0
                    articles.append({"headline": headline, "text": summary[:2000],
                                     "_days_ago": days_ago})
            logger.info(f"Fetched {min(len(feed.entries), 25)} articles from Mubasher {lang} RSS")
        except Exception as e:
            logger.warning(f"Mubasher {lang} RSS fetch failed: {e}")
    return articles


# ── Supplementary Arabic sources (always run alongside Enterprise Egypt) ──────

CNN_ARABIC_RSS   = "https://arabic.cnn.com/rss"
ALBORSA_RSS      = "https://www.alborsaanews.com/feed"
ALMAL_NEWS_URL   = "https://almalnews.com/category/stocks/1/"
EIP_NEWS_URL     = "https://www.eip.gov.eg/IDSC/News/List.aspx"

_ARABIC_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ar-EG,ar;q=0.9,en;q=0.8",
}

def _fetch_arabic_sources() -> list:
    """
    Supplementary Arabic news — always run alongside Enterprise Egypt to give
    Gemini broader EGX-related Arabic context.

    Sources:
      - CNN Arabic RSS          (general Egypt economy)
      - Al Borsa News RSS       (EGX stocks & companies, direct RSS)
      - Al Mal News scraper     (EGX stocks category page)
      - EIP/IDSC scraper        (Egyptian government economic news)

    Returns articles in [{'headline': str, 'text': str}] format.
    """
    import feedparser
    import requests
    from bs4 import BeautifulSoup

    articles = []

    # ── CNN Arabic RSS ───────────────────────────────────────────────────
    try:
        feed = feedparser.parse(CNN_ARABIC_RSS)
        count = 0
        for entry in feed.entries[:25]:
            headline = entry.get("title", "")
            summary  = entry.get("summary", "")
            if headline:
                articles.append({"headline": headline, "text": summary[:2000]})
                count += 1
        logger.info(f"Fetched {count} articles from CNN Arabic RSS")
    except Exception as e:
        logger.warning(f"CNN Arabic RSS fetch failed: {e}")

    # ── Al Borsa News RSS (EGX-focused Arabic financial news) ────────────
    try:
        feed = feedparser.parse(ALBORSA_RSS)
        count = 0
        for entry in feed.entries[:25]:
            headline = entry.get("title", "")
            summary  = entry.get("summary", "")
            if headline:
                articles.append({"headline": headline, "text": summary[:2000]})
                count += 1
        logger.info(f"Fetched {count} articles from Al Borsa News RSS")
    except Exception as e:
        logger.warning(f"Al Borsa News RSS fetch failed: {e}")

    # ── Al Mal News — stocks category scraper ────────────────────────────
    try:
        resp = requests.get(ALMAL_NEWS_URL, headers=_ARABIC_HEADERS, timeout=12)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        count = 0
        for h3 in soup.find_all("h3"):
            title = h3.get_text(strip=True)
            if len(title) > 10:
                articles.append({"headline": title, "text": ""})
                count += 1
        logger.info(f"Fetched {count} articles from Al Mal News")
    except Exception as e:
        logger.warning(f"Al Mal News fetch failed: {e}")

    # ── EIP/IDSC news list ───────────────────────────────────────────────
    try:
        resp = requests.get(EIP_NEWS_URL, headers=_ARABIC_HEADERS, timeout=12)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        count = 0
        for a in soup.find_all("a", href=True):
            title = a.get_text(strip=True)
            if "View.aspx?ID=" in a.get("href", "") and len(title) > 10:
                articles.append({"headline": title, "text": ""})
                count += 1
        logger.info(f"Fetched {count} articles from EIP/IDSC news page")
    except Exception as e:
        logger.warning(f"EIP/IDSC news fetch failed: {e}")

    return articles


# ── Fallback 2: Finnhub headlines ─────────────────────────────────────────────

def _fetch_finnhub_articles(symbols: list, days_back: int = 7) -> list:
    """
    Fallback news source: Finnhub per-symbol headlines.
    Returns articles in the same format as _fetch_recent_articles().
    """
    if not FINNHUB_API_KEY:
        logger.warning("FINNHUB_API_KEY not set, skipping Finnhub fallback")
        return []

    client = finnhub.Client(api_key=FINNHUB_API_KEY)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    articles = []

    for symbol in symbols:
        clean = symbol.split(".")[0]
        try:
            news = client.company_news(
                clean,
                _from=start_date.strftime("%Y-%m-%d"),
                to=end_date.strftime("%Y-%m-%d"),
            )
            _now_ts_fin = time.time()
            for item in news:
                headline = item.get("headline", "")
                summary = item.get("summary", "")
                if headline:
                    pub_ts = item.get("datetime", _now_ts_fin)
                    days_ago = max(0.0, (_now_ts_fin - pub_ts) / 86400)
                    articles.append({
                        "headline": headline,
                        "text": summary[:2000],
                        "_symbol_hint": symbol,
                        "_days_ago": days_ago,
                    })
            time.sleep(0.5)
        except Exception as e:
            logger.warning(f"Finnhub fetch failed for {symbol}: {e}")

    logger.info(f"Fetched {len(articles)} articles from Finnhub fallback")
    return articles


# ── News fetching ─────────────────────────────────────────────────────────────

def _fetch_recent_articles(days_back: int = 2) -> list:
    """
    Fetch recent Enterprise Egypt articles.
    Returns a list of dicts: [{'headline': str, 'text': str}, ...]
    """
    scraper = ScrapeEnterprise()
    today = datetime.now().date()
    articles = []

    try:
        # Enterprise publishes AM + PM editions so days_back*2 gives enough UUIDs
        month_ids = scraper.get_month_ids(
            site=scraper.uuid_url,
            year=today.year,
            month_number=today.month,
        )
        if month_ids is None or month_ids.empty:
            logger.warning("No Enterprise Egypt editions found for current month")
            return []

        recent_uuids = month_ids["id"].dropna().head(days_back * 2).tolist()
        logger.info(f"Fetching {len(recent_uuids)} Enterprise Egypt editions")

        for edition_idx, uuid in enumerate(recent_uuids):
            try:
                day_news = scraper.get_day_news_published(uuid, scraper.news_api)
                day_news = scraper.get_html_content(day_news)

                # Enterprise publishes AM + PM editions; edition_idx 0,1 = today,
                # 2,3 = yesterday, etc.
                days_ago = edition_idx // 2

                for _, row in day_news.iterrows():
                    headline = row.get("head_en") or row.get("head_ar") or ""
                    text = row.get("c_storyContent_en") or row.get("c_storyContent_ar") or ""
                    if headline or text:
                        articles.append(
                            {"headline": str(headline), "text": str(text)[:3000],
                             "_days_ago": days_ago}
                        )

                time.sleep(1)  # polite scraping

            except Exception as e:
                logger.warning(f"Could not fetch edition {uuid}: {e}")
                continue

    except Exception as e:
        logger.error(f"Enterprise Egypt fetch failed: {e}")

    logger.info(f"Fetched {len(articles)} articles from Enterprise Egypt")
    return articles


# ── Gemini scoring ────────────────────────────────────────────────────────────

def _score_articles_with_gemini(articles: list) -> dict:
    """
    Send each article to Gemini, collect per-symbol scores.

    Returns dict: { 'COMI.CA': [0.7, 0.3], 'TMGH.CA': [-0.4], ... }
    Scores are already normalised to -1..+1 (Gemini's -10..+10 divided by 10).
    """
    if not GOOGLE_API_KEY:
        logger.error("GOOGLE_API_KEY not set — cannot run Gemini scoring")
        return {}

    gemma = CallGemma(api_key=GOOGLE_API_KEY, model="gemini-2.5-flash")
    symbol_scores: dict = {}   # symbol → list of (score, days_ago) tuples

    # Inject the EGX company list into the prompt
    system_prompt = prompts.get_gemma_response.replace(
        "{company_list}", _COMPANY_LIST_JSON
    )

    for i, article in enumerate(articles):
        article_text = f"{article['headline']}\n\n{article['text']}"[:4000]

        # If a symbol hint exists (Finnhub fallback), use a simpler scoring prompt
        symbol_hint = article.get("_symbol_hint")

        try:
            result = gemma.get_gemma_response(
                sys_prompt=system_prompt,
                news_article=article_text,
                temperature=0.05,
            )

            if isinstance(result, dict):
                result = [result]
            if not isinstance(result, list):
                # If Gemini returned nothing useful but we have a hint, use score=0
                if symbol_hint:
                    symbol_scores.setdefault(symbol_hint, []).append(0.0)
                continue

            days_ago = article.get("_days_ago", 0.0)

            for item in result:
                if not isinstance(item, dict):
                    continue

                company = item.get("company", "")
                stock_symbol = str(item.get("stock_symbol", "")).upper()

                # get_gemma_response returns 'sentiment' text; get_recommendation returns numeric 'score'
                raw_score = item.get("score", None)
                if raw_score is None:
                    sentiment_text = str(item.get("sentiment", "neutral")).lower()
                    raw_score = 7.0 if sentiment_text == "positive" else (-7.0 if sentiment_text == "negative" else 0.0)

                # Resolve to Yahoo symbol — prefer hint, then Gemini's symbol, then name match
                symbol = symbol_hint
                if not symbol:
                    clean_ticker = stock_symbol.replace(".CA", "")
                    if clean_ticker in EGX_SYMBOL_DATABASE:
                        symbol = EGX_SYMBOL_DATABASE[clean_ticker].yahoo
                if not symbol:
                    symbol = _match_company_to_symbol(company)

                if symbol and raw_score is not None:
                    try:
                        # Normalise -10..+10 → -1..+1, clamp to range
                        score = max(-1.0, min(1.0, float(raw_score) / 10.0))
                        # Store (score, days_ago) for recency-weighted aggregation
                        symbol_scores.setdefault(symbol, []).append((score, days_ago))
                    except (ValueError, TypeError):
                        pass

        except Exception as e:
            logger.warning(f"Gemini error on article {i}: {e}")

        # Free tier: 15 req/min. Pause after every 14 calls to avoid hitting the limit.
        if (i + 1) % 14 == 0:
            logger.info(f"Rate-limit pause after {i + 1} articles...")
            time.sleep(65)
        else:
            time.sleep(4)

    return symbol_scores


# ── Main entry point ──────────────────────────────────────────────────────────

def collect_sentiment(symbols: list = None, days_back: int = 2) -> int:
    """
    Fetch Enterprise Egypt news, score with Gemini, store in sentiment_scores table.

    Args:
        symbols:   Stock symbols to process (defaults to config.ALL_STOCKS)
        days_back: How many days of Enterprise Egypt editions to fetch

    Returns:
        Number of symbols successfully processed
    """
    if symbols is None:
        symbols = config.ALL_STOCKS

    logger.info(f"Starting Gemini sentiment for {len(symbols)} stocks")
    create_sentiment_table()
    today = datetime.now().strftime("%Y-%m-%d")

    # Step 1 — fetch news: Enterprise Egypt (primary) + Arabic sources (always)
    #           → Mubasher RSS → Finnhub (fallbacks if primary unavailable)
    articles = _fetch_recent_articles(days_back=days_back)
    arabic_articles = _fetch_arabic_sources()   # CNN Arabic + EIP/IDSC (always run)
    articles.extend(arabic_articles)
    if not articles:
        logger.warning("Enterprise Egypt + Arabic sources unavailable — falling back to Mubasher RSS")
        articles = _fetch_mubasher_articles()
    if not articles:
        logger.warning("Mubasher RSS unavailable — falling back to Finnhub headlines")
        articles = _fetch_finnhub_articles(symbols, days_back=7)
    if not articles:
        logger.warning("No articles fetched — recording Neutral for all stocks")
        for symbol in symbols:
            _save_sentiment(symbol, today, 0.0, "Neutral", 0, 0, 0, 0)
        return len(symbols)

    # Step 2 — score with Gemini
    symbol_scores = _score_articles_with_gemini(articles)

    # Step 3 — aggregate per symbol and persist
    success_count = 0
    for symbol in symbols:
        scores = symbol_scores.get(symbol, [])

        if not scores:
            _save_sentiment(symbol, today, 0.0, "Neutral", 0, 0, 0, 0)
            success_count += 1
            continue

        # Recency-weighted aggregation: weight = 2^(-days_ago / 1.5)
        # Half-life of 1.5 days — articles from today have weight≈1.0,
        # yesterday ≈0.63, 3 days ago ≈0.25
        weighted_sum = 0.0
        total_weight = 0.0
        positive = 0
        negative = 0
        for s, days_ago in scores:
            w = 2.0 ** (-days_ago / 1.5)
            weighted_sum += s * w
            total_weight += w
            if s > 0.1:
                positive += 1
            elif s < -0.1:
                negative += 1
        avg = weighted_sum / total_weight if total_weight > 0 else 0.0
        neutral = len(scores) - positive - negative

        label = "Bullish" if avg > 0.1 else ("Bearish" if avg < -0.1 else "Neutral")

        _save_sentiment(symbol, today, avg, label, len(scores), positive, negative, neutral)
        logger.info(f"  {symbol}: {label} (score={avg:.3f}, mentions={len(scores)})")
        success_count += 1

    return success_count


if __name__ == "__main__":
    start = time.time()
    print(f"Gemini sentiment starting at {datetime.now()}")
    print(f"Stocks: {len(config.ALL_STOCKS)}")

    create_tables()

    try:
        count = collect_sentiment()
        duration = time.time() - start
        msg = f"Gemini sentiment complete for {count} stocks"
        log_system_run("sentiment_gemini.py", "success", msg, duration)
        print(f"{msg} ({duration:.1f}s)")
    except Exception as e:
        duration = time.time() - start
        log_system_run("sentiment_gemini.py", "failure", str(e), duration)
        print(f"Failed: {e}")
        raise
