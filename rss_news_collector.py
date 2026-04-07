"""
RSS News Collector for KSA/Tadawul Financial News

This module fetches news from Saudi financial RSS feeds and analyzes sentiment.
It supplements the NewsAPI collector with local Saudi/GCC sources that have better
coverage of Tadawul-listed companies.

Supported Sources:
- Mubasher Egypt (Arabic business news)
- Enterprise (English business news)
- Egypt Today Business (English)
- Daily News Egypt (English)
- Al-Mal News (Arabic)
"""

import feedparser
from datetime import datetime, timedelta
from typing import List, Dict
import re
import logging
import os
import html
import requests

from database import get_connection
from config.ksa_universe import KSA_TOP50
import config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _parse_bool_env(var_name: str, default: bool = False) -> bool:
    """Parse boolean feature flag from environment variables."""
    raw = os.getenv(var_name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# ============================================
# RSS FEED SOURCES
# ============================================

# Source priority order matters:
# 1) Mubasher KSA for Tadawul-specific market/news coverage
# 2) Argaam for Saudi market analysis
# 3) Other GCC/Saudi business feeds for breadth
EGYPTIAN_NEWS_FEEDS = [
    {
        "name": "Mubasher KSA",
        "url": "http://feeds.mubasher.info/en/TDWL/news",
        "language": "en",
        "focus": "markets",
        "reliability": "high"
    },
    {
        "name": "Arab News Business",
        "url": "https://www.arabnews.com/taxonomy/term/402/feed",
        "language": "en",
        "focus": "business",
        "reliability": "high"
    },
    {
        "name": "Reuters Saudi",
        "url": "https://www.reuters.com/news/archive/saudi-arabia?view=rss",
        "language": "en",
        "focus": "general",
        "reliability": "high"
    },
    {
        "name": "Google News Saudi Stock Market",
        "url": "https://news.google.com/rss/search?q=saudi+stock+market+OR+tadawul+OR+TASI&hl=en-US&gl=US&ceid=US:en",
        "language": "en",
        "focus": "markets",
        "reliability": "medium"
    },
    # ── Arabic sources ────────────────────────────────────────────────────────
    {
        "name": "CNN Arabic",
        "url": "https://arabic.cnn.com/rss",
        "language": "ar",
        "focus": "general",
        "reliability": "high"
    },
    {
        "name": "Google News Argaam Saudi",
        "url": "https://news.google.com/rss/search?q=site:argaam.com+%D8%A7%D9%84%D8%B3%D8%B9%D9%88%D8%AF%D9%8A%D8%A9+%D8%A3%D8%B3%D9%87%D9%85&hl=ar&gl=SA&ceid=SA:ar",
        "language": "ar",
        "focus": "markets",
        "reliability": "medium"
    },
    {
        "name": "Google News Tadawul Arabic",
        "url": "https://news.google.com/rss/search?q=%D8%AA%D8%A7%D8%B3%D9%8A+%D8%AA%D8%AF%D8%A7%D9%88%D9%84+%D8%A3%D8%B3%D9%87%D9%85&hl=ar&gl=SA&ceid=SA:ar",
        "language": "ar",
        "focus": "markets",
        "reliability": "medium"
    },
    {
        "name": "Google News SAMA Saudi",
        "url": "https://news.google.com/rss/search?q=%D8%A7%D9%84%D8%A8%D9%86%D9%83+%D8%A7%D9%84%D9%85%D8%B1%D9%83%D8%B2%D9%8A+%D8%A7%D9%84%D8%B3%D8%B9%D9%88%D8%AF%D9%8A+%D8%B3%D8%A7%D9%85%D8%A7&hl=ar&gl=SA&ceid=SA:ar",
        "language": "ar",
        "focus": "markets",
        "reliability": "medium"
    },
    {
        "name": "Google News Investing Saudi",
        "url": "https://news.google.com/rss/search?q=site:sa.investing.com+saudi+stocks&hl=ar&gl=SA&ceid=SA:ar",
        "language": "ar",
        "focus": "markets",
        "reliability": "medium"
    },
]


def _adapt_sql(sql: str) -> str:
    """Convert SQLite SQL to PostgreSQL when needed."""
    import os
    if os.getenv('DATABASE_URL'):
        sql = sql.replace('?', '%s')
        sql = sql.replace('INSERT OR IGNORE', 'INSERT')
        if 'INSERT' in sql and 'ON CONFLICT' not in sql:
            sql = sql.rstrip().rstrip(')') + ') ON CONFLICT DO NOTHING'
    return sql


def fetch_rss_feed(feed_url: str) -> List[Dict]:
    """
    Fetch and parse an RSS feed.

    Args:
        feed_url: URL of the RSS feed

    Returns:
        List of article dictionaries with title, link, published date, summary
    """
    try:
        feed = feedparser.parse(feed_url)

        if feed.bozo and feed.bozo_exception:
            logger.warning(f"Feed parse warning for {feed_url}: {feed.bozo_exception}")

        articles = []
        for entry in feed.entries:
            # Parse published date
            pub_date = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                pub_date = datetime(*entry.published_parsed[:6])
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                pub_date = datetime(*entry.updated_parsed[:6])
            else:
                pub_date = datetime.now()

            articles.append({
                'title': entry.get('title', ''),
                'link': entry.get('link', ''),
                'summary': entry.get('summary', entry.get('description', '')),
                'published': pub_date,
                'source': feed.feed.get('title', 'Unknown')
            })

        return articles

    except Exception as e:
        logger.error(f"Error fetching RSS feed {feed_url}: {e}")
        return []


def fetch_egx_web_news(url: str, timeout_sec: int = 12) -> List[Dict]:
    """
    Best-effort fetch of EGX website news list page.

    This adapter is optional and may fail when EGX anti-bot protections block requests.
    Returns normalized article objects compatible with downstream flow.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        )
    }
    try:
        response = requests.get(url, headers=headers, timeout=timeout_sec)
        response.raise_for_status()
        body = response.text

        blocked_markers = [
            "The requested URL was rejected",
            "Access Denied",
            "Request blocked",
        ]
        if any(marker.lower() in body.lower() for marker in blocked_markers):
            logger.warning("EGX web page rejected request. Skipping optional EGX web source.")
            return []

        # Lightweight extraction: anchor tags with non-trivial visible text.
        link_re = re.compile(
            r'<a[^>]+href=[\'"](?P<href>[^\'"]+)[\'"][^>]*>(?P<title>[^<]{8,300})</a>',
            flags=re.IGNORECASE,
        )
        articles: List[Dict] = []
        seen = set()
        for m in link_re.finditer(body):
            title = html.unescape(m.group("title")).strip()
            href = m.group("href").strip()

            if not title or len(title) < 12:
                continue
            title_l = title.lower()
            if title_l in seen:
                continue
            seen.add(title_l)

            # Keep EGX/news-like anchors only; avoid nav/footer noise.
            if not any(k in title_l for k in ["egx", "exchange", "market", "news", "listed", "trading", "index"]):
                continue

            if href.startswith("/"):
                link = f"https://www.egx.com.eg{href}"
            elif href.startswith("http://") or href.startswith("https://"):
                link = href
            else:
                link = f"https://www.egx.com.eg/{href.lstrip('/')}"

            articles.append(
                {
                    "title": title,
                    "link": link,
                    "summary": "",
                    "published": datetime.now(),
                    "source": "EGX Website",
                }
            )

        logger.info("EGX web adapter fetched %s candidate articles", len(articles))
        return articles
    except Exception as e:
        logger.warning("EGX web adapter failed (optional): %s", e)
        return []


def match_article_to_symbols(article: Dict) -> List[str]:
    """
    Match an article to relevant stock symbols based on content.

    Args:
        article: Article dictionary with title and summary

    Returns:
        List of matching stock symbols (Yahoo format)
    """
    text = f"{article.get('title', '')} {article.get('summary', '')}".upper()
    text_lower = text.lower()
    matched_symbols = []

    for stock in KSA_TOP50:
        ticker_code = stock["symbol"].replace(".SR", "")
        # Check for ticker mention (e.g. "2222" or "2222.SR")
        if re.search(rf'\b{ticker_code}\b', text) or stock["symbol"].upper() in text:
            matched_symbols.append(stock["symbol"])
            continue

        # Check for company name (partial match)
        name_words = stock["name_en"].upper().split()
        significant_words = [w for w in name_words if len(w) > 4]
        matches = sum(1 for w in significant_words if w in text)
        if matches >= 1:
            matched_symbols.append(stock["symbol"])
            continue

        # Check Arabic name
        if stock["name_ar"] and stock["name_ar"] in article.get('title', ''):
            matched_symbols.append(stock["symbol"])

    # Also match general market news to top KSA stocks
    market_keywords = ['tadawul', 'saudi exchange', 'tasi', 'saudi stock',
                       'البورصة السعودية', 'تاسي', 'سوق الأسهم السعودي']
    if any(kw in text_lower for kw in market_keywords):
        top_stocks = ['2222.SR', '1180.SR', '2010.SR', '7010.SR', '4061.SR']
        matched_symbols.extend(top_stocks)

    return list(set(matched_symbols))


def analyze_sentiment_simple(text: str) -> Dict[str, any]:
    """
    Simple keyword-based sentiment analysis for financial news.

    This is a fallback when FinBERT is not available. Uses financial keyword matching.

    Args:
        text: Article title or summary

    Returns:
        Dictionary with sentiment_score (-1 to 1) and sentiment_label
    """
    text_lower = text.lower()

    # Financial positive keywords
    positive_words = [
        'rise', 'gain', 'profit', 'growth', 'surge', 'rally', 'bull', 'upturn',
        'increase', 'boost', 'record', 'high', 'expand', 'dividend', 'success',
        'ارتفاع', 'صعود', 'ربح', 'نمو', 'أرباح', 'إيجابي', 'تحسن'
    ]

    # Financial negative keywords
    negative_words = [
        'fall', 'drop', 'loss', 'decline', 'plunge', 'crash', 'bear', 'downturn',
        'decrease', 'slump', 'low', 'cut', 'fail', 'debt', 'risk', 'concern',
        'انخفاض', 'هبوط', 'خسارة', 'تراجع', 'سلبي', 'ديون', 'مخاطر'
    ]

    pos_count = sum(1 for word in positive_words if word in text_lower)
    neg_count = sum(1 for word in negative_words if word in text_lower)

    total = pos_count + neg_count
    if total == 0:
        return {'sentiment_score': 0.0, 'sentiment_label': 'neutral'}

    score = (pos_count - neg_count) / total

    if score > 0.2:
        label = 'positive'
    elif score < -0.2:
        label = 'negative'
    else:
        label = 'neutral'

    return {'sentiment_score': round(score, 3), 'sentiment_label': label}


def collect_rss_news(days_back: int = 3, use_finbert: bool = True) -> Dict[str, int]:
    """
    Collect news from all configured RSS feeds and save to database.

    Args:
        days_back: Only include articles from this many days ago
        use_finbert: Whether to use FinBERT for sentiment (falls back to simple)

    Returns:
        Dictionary with collection statistics
    """
    print("[RSS] Collecting Egyptian financial news from RSS feeds...")

    # Initialize FinBERT if requested
    sentiment_pipeline = None
    if use_finbert:
        try:
            from transformers import pipeline
            sentiment_pipeline = pipeline("sentiment-analysis", model="ProsusAI/finbert")
            print("[AI] Using FinBERT for sentiment analysis")
        except Exception as e:
            print(f"[WARN] FinBERT not available, using simple sentiment: {e}")

    cutoff_date = datetime.now() - timedelta(days=days_back)
    stats = {
        'feeds_processed': 0,
        'articles_fetched': 0,
        'articles_matched': 0,
        'articles_saved': 0,
        'egx_web_processed': 0,
        'egx_web_articles_fetched': 0,
        'egx_web_articles_saved': 0,
        'errors': 0
    }

    for feed_config in EGYPTIAN_NEWS_FEEDS:
        try:
            print(f"  Fetching: {feed_config['name']}...")
            articles = fetch_rss_feed(feed_config['url'])
            stats['feeds_processed'] += 1
            stats['articles_fetched'] += len(articles)

            for article in articles:
                # Skip old articles
                if article['published'] < cutoff_date:
                    continue

                # Match to symbols
                matched_symbols = match_article_to_symbols(article)
                if not matched_symbols:
                    continue

                stats['articles_matched'] += 1

                # Analyze sentiment
                if sentiment_pipeline:
                    try:
                        result = sentiment_pipeline(article['title'][:512])[0]
                        sentiment_label = result['label']
                        score = result['score']
                        if sentiment_label == 'positive':
                            sentiment_score = score
                        elif sentiment_label == 'negative':
                            sentiment_score = -score
                        else:
                            sentiment_score = 0
                    except Exception:
                        sentiment = analyze_sentiment_simple(article['title'])
                        sentiment_score = sentiment['sentiment_score']
                        sentiment_label = sentiment['sentiment_label']
                else:
                    sentiment = analyze_sentiment_simple(article['title'])
                    sentiment_score = sentiment['sentiment_score']
                    sentiment_label = sentiment['sentiment_label']

                # Save to database for each matched symbol
                with get_connection() as conn:
                    cursor = conn.cursor()
                    for symbol in matched_symbols:
                        try:
                            cursor.execute(_adapt_sql("""
                                INSERT OR IGNORE INTO news
                                (symbol, date, headline, source, url, sentiment_score, sentiment_label)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """), (
                                symbol,
                                article['published'].strftime('%Y-%m-%d'),
                                article['title'][:500],
                                f"RSS:{feed_config['name']}",
                                article['link'],
                                sentiment_score,
                                sentiment_label
                            ))
                            stats['articles_saved'] += 1
                        except Exception as e:
                            logger.debug(f"Duplicate or error: {e}")

        except Exception as e:
            logger.error(f"Error processing feed {feed_config['name']}: {e}")
            stats['errors'] += 1

    # Optional EGX website adapter: disabled by default.
    use_egx_web = _parse_bool_env(
        "USE_EGX_WEB_SCRAPER",
        default=bool(config.EGX_CONFIG.get("use_egx_web_scraper", False)),
    )
    if use_egx_web:
        egx_web_url = os.getenv(
            "EGX_WEB_NEWS_URL",
            config.EGX_CONFIG.get("egx_web_news_url", "https://www.egx.com.eg/en/NewsList.aspx?ID=10"),
        )
        try:
            print("  Fetching: EGX Website (optional adapter)...")
            web_articles = fetch_egx_web_news(egx_web_url)
            stats['egx_web_processed'] = 1
            stats['egx_web_articles_fetched'] = len(web_articles)

            for article in web_articles:
                if article['published'] < cutoff_date:
                    continue
                matched_symbols = match_article_to_symbols(article)
                if not matched_symbols:
                    continue
                stats['articles_matched'] += 1

                sentiment = analyze_sentiment_simple(article['title'])
                sentiment_score = sentiment['sentiment_score']
                sentiment_label = sentiment['sentiment_label']

                with get_connection() as conn:
                    cursor = conn.cursor()
                    for symbol in matched_symbols:
                        try:
                            cursor.execute(_adapt_sql("""
                                INSERT OR IGNORE INTO news
                                (symbol, date, headline, source, url, sentiment_score, sentiment_label)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """), (
                                symbol,
                                article['published'].strftime('%Y-%m-%d'),
                                article['title'][:500],
                                "WEB:EGX",
                                article['link'],
                                sentiment_score,
                                sentiment_label
                            ))
                            stats['articles_saved'] += 1
                            stats['egx_web_articles_saved'] += 1
                        except Exception as e:
                            logger.debug(f"Duplicate or error (EGX web): {e}")
        except Exception as e:
            logger.error(f"Error processing optional EGX web source: {e}")
            stats['errors'] += 1

    return stats


def collect_news_for_symbol(symbol: str, days_back: int = 7) -> List[Dict]:
    """
    Collect news specifically for a single symbol from RSS feeds.

    Args:
        symbol: Stock symbol (e.g. 2222.SR)
        days_back: Days of news to fetch

    Returns:
        List of matched articles
    """
    # Build keywords from KSA_TOP50
    stock_info = None
    for s in KSA_TOP50:
        if s["symbol"] == symbol or s["symbol"].replace(".SR", "") == symbol.replace(".SR", ""):
            stock_info = s
            break
    if not stock_info:
        return []

    ticker_code = symbol.replace(".SR", "")
    keywords = [ticker_code, stock_info["name_en"], stock_info["name_ar"]]
    cutoff_date = datetime.now() - timedelta(days=days_back)
    matched_articles = []

    for feed_config in EGYPTIAN_NEWS_FEEDS:
        articles = fetch_rss_feed(feed_config['url'])
        for article in articles:
            if article['published'] < cutoff_date:
                continue

            text = f"{article['title']} {article['summary']}".upper()
            for keyword in keywords:
                if keyword and keyword.upper() in text:
                    article['matched_keyword'] = keyword
                    article['feed_source'] = feed_config['name']
                    matched_articles.append(article)
                    break

    return matched_articles


if __name__ == "__main__":
    print("=" * 60)
    print("Egyptian Financial News RSS Collector")
    print("=" * 60)

    # Test RSS feeds
    print("\nTesting RSS feed connectivity...")
    for feed in EGYPTIAN_NEWS_FEEDS:
        articles = fetch_rss_feed(feed['url'])
        status = "[OK]" if articles else "[FAIL]"
        print(f"  {status} {feed['name']}: {len(articles)} articles")

    # Run collection
    print("\nRunning news collection...")
    stats = collect_rss_news(days_back=3, use_finbert=False)

    print("\nCollection Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
