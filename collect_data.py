"""
Data Collection Script

This module is responsible for fetching stock prices and news from external APIs.
Primary EGX source: EGX live feed (http://41.33.162.236/egs4/)
Fallback: Yahoo Finance (yfinance)
News: NewsAPI + RSS feeds

Key components:
- EGX live feed scraper (primary for Egyptian stocks)
- Price collection via yfinance (fallback + US stocks)
- News collection via NewsAPI
- Basic sentiment analysis using TextBlob
- Database persistence for collected data
"""

import yfinance as yf
from newsapi import NewsApiClient
from datetime import datetime, timedelta
import time
import logging
import requests
import re

# Import your existing logic
import config
from database import get_connection, log_system_run, log_data_quality_issue, create_tables

# Check if using PostgreSQL
import os
DATABASE_URL = os.getenv('DATABASE_URL')

logger = logging.getLogger(__name__)

def _adapt_sql(sql):
    """Convert SQLite SQL to PostgreSQL when needed."""
    if DATABASE_URL:
        sql = sql.replace('?', '%s')
        sql = sql.replace('INSERT OR IGNORE', 'INSERT')
        # Add ON CONFLICT DO NOTHING for PostgreSQL
        if 'INSERT' in sql and 'ON CONFLICT' not in sql:
            sql = sql.rstrip().rstrip(')') + ') ON CONFLICT DO NOTHING'
    return sql

def collect_egx_data():
    """
    Collect EGX stock data using live feed as primary source, yfinance as fallback.

    Strategy:
    - Try EGX live feed first (200+ stocks, real-time data)
    - Fall back to yfinance if live feed fails
    - Store all data in prices table with source tracking

    Returns:
        int: Number of stocks successfully collected.
    """
    print("🏛️  Fetching EGX data...")

    try:
        # Primary: EGX live feed
        from data.egx_live_scraper import fetch_egx_live, egx_to_prices_schema
        df = fetch_egx_live()
        prices_df = egx_to_prices_schema(df)
        
        if len(prices_df) > 0:
            stored = _store_prices(prices_df, source='egx_live')
            print(f"  ✅ EGX live feed: {stored} stocks collected")
            return stored
        else:
            raise ValueError("EGX live feed returned 0 stocks")

    except Exception as e:
        print(f"  ⚠️  EGX live feed failed: {e}")
        print(f"  🔄 Falling back to yfinance for EGX stocks...")
        logger.warning(f"EGX live feed failed: {e}, falling back to yfinance")

        # Fallback: use yfinance for EGX stocks
        return collect_prices_yfinance(config.EGX_STOCKS)


def collect_prices_yfinance(symbols=None):
    """
    Fetch stock prices from Yahoo Finance and save to DB.

    Args:
        symbols: List of symbols to fetch. Defaults to ALL_STOCKS.

    Returns:
        int: Number of stocks successfully collected.
    """
    if symbols is None:
        symbols = config.ALL_STOCKS

    print(f"📈 Fetching price data from yfinance for {len(symbols)} stocks...")
    success_count = 0
    
    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="90d")
            
            if DATABASE_URL:
                yf_sql = """
                    INSERT INTO prices (symbol, date, open, high, low, close, volume, data_source)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (symbol, date) DO UPDATE SET
                        open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low,
                        close=EXCLUDED.close, volume=EXCLUDED.volume, data_source=EXCLUDED.data_source
                """
            else:
                yf_sql = """
                    INSERT OR REPLACE INTO prices
                    (symbol, date, open, high, low, close, volume, data_source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """
            with get_connection() as conn:
                cursor = conn.cursor()
                for date, row in df.iterrows():
                    if row.isnull().any():
                        continue
                    cursor.execute(yf_sql, (
                        symbol,
                        date.strftime('%Y-%m-%d'),
                        float(row['Open']), float(row['High']), float(row['Low']), float(row['Close']),
                        int(row['Volume']), 'yahoo_finance'
                    ))
            success_count += 1
        except Exception as e:
            log_data_quality_issue(symbol, 'api_failure', str(e), 'high')
            print(f"  ❌ Error fetching prices for {symbol}: {e}")
            
    return success_count


def _fetch_usdegp_rate():
    """
    Fetch current USD/EGP exchange rate from multiple sources in priority order:
      1. Central Bank of Egypt (cbe.org.eg) — official source
      2. open.er-api.com — free tier, no key needed
      3. frankfurter.app — ECB-based, free
      4. exchangerate.host — free API
    Returns float rate or None if all sources fail.
    """
    today = datetime.utcnow().strftime('%Y-%m-%d')

    # --- Source 1: CBE official page ---
    try:
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/122.0.0.0 Safari/537.36'
            ),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        }
        resp = requests.get(
            'http://cbe.org.eg/en/economic-research/statistics/exchange-rates',
            headers=headers, timeout=10
        )
        if resp.status_code == 200:
            # CBE renders a table: Currency | Buying | Selling
            # Look for USD row — typically "US Dollar" or "USD"
            text = resp.text
            # Match patterns like USD row in table
            patterns = [
                r'US\s*Dollar.*?(\d+\.\d+).*?(\d+\.\d+)',
                r'USD.*?(\d+\.\d+).*?(\d+\.\d+)',
            ]
            for pat in patterns:
                m = re.search(pat, text, re.IGNORECASE | re.DOTALL)
                if m:
                    buying  = float(m.group(1))
                    selling = float(m.group(2))
                    mid = (buying + selling) / 2
                    if 10 < mid < 200:   # sanity: EGP has been 30–50 range in recent years
                        print(f"  CBE rate: USD/EGP = {mid:.4f} (buying={buying}, selling={selling})")
                        return mid
    except Exception as e:
        print(f"  CBE fetch failed: {e}")

    # --- Source 2: open.er-api.com (free, no key) ---
    try:
        r = requests.get('https://open.er-api.com/v6/latest/USD', timeout=8)
        if r.status_code == 200:
            data = r.json()
            rate = data.get('rates', {}).get('EGP')
            if rate and 10 < rate < 200:
                print(f"  open.er-api rate: USD/EGP = {rate:.4f}")
                return float(rate)
    except Exception as e:
        print(f"  open.er-api failed: {e}")

    # --- Source 3: frankfurter.app (ECB-based) ---
    try:
        r = requests.get('https://api.frankfurter.app/latest?from=USD&to=EGP', timeout=8)
        if r.status_code == 200:
            data = r.json()
            rate = data.get('rates', {}).get('EGP')
            if rate and 10 < rate < 200:
                print(f"  frankfurter rate: USD/EGP = {rate:.4f}")
                return float(rate)
    except Exception as e:
        print(f"  frankfurter failed: {e}")

    # --- Source 4: exchangerate.host ---
    try:
        r = requests.get(
            'https://api.exchangerate.host/latest?base=USD&symbols=EGP',
            timeout=8
        )
        if r.status_code == 200:
            data = r.json()
            rate = data.get('rates', {}).get('EGP')
            if rate and 10 < rate < 200:
                print(f"  exchangerate.host rate: USD/EGP = {rate:.4f}")
                return float(rate)
    except Exception as e:
        print(f"  exchangerate.host failed: {e}")

    return None


def collect_macro_data():
    """
    Fetch macro context data via yfinance and store in the prices table.

    Three instruments captured as special symbols:
      MACRO_BRENT   ← BZ=F  (Brent crude front-month future)
      MACRO_USDEGP  ← USDEGP=X  (USD / Egyptian Pound spot rate, CBE primary)
      MACRO_EEM     ← EEM   (iShares MSCI Emerging Markets ETF)

    Stored in the same prices table as stock prices (with data_source='yfinance_macro').
    The ML agent reads these rows at training/inference time to build macro features.
    """
    MACRO_SYMBOLS = {
        'MACRO_BRENT':  'BZ=F',
        'MACRO_USDEGP': 'USDEGP=X',
        'MACRO_EEM':    'EEM',
    }

    if DATABASE_URL:
        sql = """
            INSERT INTO prices (symbol, date, open, high, low, close, volume, data_source)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (symbol, date) DO UPDATE SET
                open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low,
                close=EXCLUDED.close, volume=EXCLUDED.volume
        """
    else:
        sql = """
            INSERT OR REPLACE INTO prices
            (symbol, date, open, high, low, close, volume, data_source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """

    print("Fetching macro context data (Brent, USD/EGP, EM)...")
    stored = 0
    today = datetime.utcnow().strftime('%Y-%m-%d')

    # --- Special handling for USD/EGP: try CBE official source first ---
    cbe_rate = _fetch_usdegp_rate()
    if cbe_rate is not None:
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (
                    'MACRO_USDEGP',
                    today,
                    cbe_rate, cbe_rate, cbe_rate, cbe_rate,
                    0,
                    'cbe_official',
                ))
            stored += 1
            print(f"  OK MACRO_USDEGP (CBE): {cbe_rate:.4f} EGP/USD")
            MACRO_SYMBOLS.pop('MACRO_USDEGP', None)   # skip yfinance fallback
        except Exception as e:
            print(f"  MACRO_USDEGP CBE store error: {e} — will try yfinance")

    for internal_sym, yf_sym in MACRO_SYMBOLS.items():
        try:
            ticker = yf.Ticker(yf_sym)
            df = ticker.history(period="90d")
            if len(df) == 0:
                print(f"  WARNING: No data for {yf_sym} ({internal_sym})")
                continue
            with get_connection() as conn:
                cursor = conn.cursor()
                for date, row in df.iterrows():
                    cursor.execute(sql, (
                        internal_sym,
                        date.strftime('%Y-%m-%d'),
                        float(row.get('Open',   row['Close'])),
                        float(row.get('High',   row['Close'])),
                        float(row.get('Low',    row['Close'])),
                        float(row['Close']),
                        int(row.get('Volume', 0)),
                        'yfinance_macro',
                    ))
            stored += 1
            print(f"  OK {internal_sym} ({yf_sym}): collected")
        except Exception as e:
            print(f"  WARNING: {internal_sym} ({yf_sym}): {e}")

    return stored


def collect_prices():
    """
    Fetch stock prices — EGX live feed for Egyptian stocks, yfinance for US stocks.
    Also collects macro context data (Brent, USD/EGP, EM ETF).

    Returns:
        int: Number of stocks successfully collected.
    """
    total = 0

    # EGX stocks: try live feed first, fallback to yfinance
    if config.EGX_STOCKS:
        total += collect_egx_data()

    # US stocks: always use yfinance
    if config.US_STOCKS:
        print("📈 Fetching US stock data from yfinance...")
        total += collect_prices_yfinance(config.US_STOCKS)

    # Macro context (Brent, USD/EGP, EM) — used as ML features
    collect_macro_data()

    return total


def _store_prices(prices_df, source='egx_live'):
    """
    Store a DataFrame of prices into the database.

    Args:
        prices_df: DataFrame with columns: symbol, date, open, high, low, close, volume
        source: Data source identifier string

    Returns:
        int: Number of records stored.
    """
    stored = 0

    if DATABASE_URL:
        # PostgreSQL: explicit upsert (INSERT OR REPLACE is SQLite-only syntax)
        sql = """
            INSERT INTO prices (symbol, date, open, high, low, close, volume, data_source)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (symbol, date) DO UPDATE SET
                open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low,
                close=EXCLUDED.close, volume=EXCLUDED.volume, data_source=EXCLUDED.data_source
        """
    else:
        sql = """
            INSERT OR REPLACE INTO prices
            (symbol, date, open, high, low, close, volume, data_source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """

    with get_connection() as conn:
        cursor = conn.cursor()
        for _, row in prices_df.iterrows():
            try:
                cursor.execute(sql, (
                    str(row['symbol']),
                    str(row['date']),
                    float(row['open']),
                    float(row['high']),
                    float(row['low']),
                    float(row['close']),
                    int(row['volume']),
                    source
                ))
                stored += 1
            except Exception as e:
                logger.error(f"Error storing price for {row['symbol']}: {e}")
    return stored

def collect_news():
    """
    Fetch recent news headlines for all stocks from NewsAPI and analyze sentiment.

    Collection Strategy:
    - Fetches news from the last 2 days
    - Limits to top 10 headlines per stock
    - Uses FinBERT for financial sentiment analysis
    - Saves headline, source, URL, and sentiment

    Returns:
        int: Number of stocks for which news was successfully collected.

    Example Output in DB:
        | symbol | date       | headline             | sentiment_label |
        |--------|------------|----------------------|-----------------|
        | AAPL   | 2023-10-25 | Apple releases iOS 18| positive        |
    """
    print("📰 Fetching news data...")
    newsapi = NewsApiClient(api_key=config.NEWS_API_KEY)
    success_count = 0

    # Initialize FinBERT
    print("🧠 Loading FinBERT model...")
    try:
        from transformers import pipeline
        # Use a financial sentiment analysis model
        sentiment_pipeline = pipeline("sentiment-analysis", model="ProsusAI/finbert")
        use_sentiment = True
    except ImportError:
        print("⚠️ Transformers not installed. Skipping sentiment analysis.")
        use_sentiment = False
    except Exception as e:
        print(f"⚠️ Error loading FinBERT: {e}. Skipping sentiment analysis.")
        use_sentiment = False

    # Calculate start date for news search (last 2 days)
    from_date = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
    
    for symbol in config.ALL_STOCKS:
        try:
            # Build query: symbol + generic terms for context. 
            # For EGX, adding 'Egypt' helps filter irrelevant global noise.
            query = f"{symbol} OR {symbol.split('.')[0]} Egypt Stock"
            
            # Query NewsAPI for everything about the symbol
            articles = newsapi.get_everything(q=query, from_param=from_date, language='en')
            
            with get_connection() as conn:
                cursor = conn.cursor()
                # Only take the top 10 most relevant articles to save space
                for art in articles['articles'][:10]:

                    sentiment_score = 0
                    sentiment_label = 'neutral'

                    if use_sentiment:
                        try:
                            # Analyze title
                            result = sentiment_pipeline(art['title'])[0]
                            sentiment_label = result['label']
                            score = result['score']

                            # Map to -1 to 1
                            if sentiment_label == 'positive':
                                sentiment_score = score
                            elif sentiment_label == 'negative':
                                sentiment_score = -score
                            else: # neutral
                                sentiment_score = 0
                        except Exception as e:
                            print(f"Error analyzing sentiment for {symbol}: {e}")


                    cursor.execute(_adapt_sql("""
                        INSERT OR IGNORE INTO news
                        (symbol, date, headline, source, url, sentiment_score, sentiment_label)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """), (
                        symbol,
                        art['publishedAt'][:10], # Extract YYYY-MM-DD from ISO timestamp
                        art['title'],
                        art['source']['name'],
                        art['url'],
                        sentiment_score,
                        sentiment_label
                    ))
            success_count += 1
        except Exception as e:
            print(f"❌ Error fetching news for {symbol}: {e}")
            
    return success_count

def collect_rss_news_wrapper():
    """
    Collect Egyptian financial news from RSS feeds.

    This supplements NewsAPI with local Egyptian sources for better EGX coverage.
    RSS feeds are particularly useful for Arabic-language financial news.

    Returns:
        dict: Collection statistics from RSS collector
    """
    print("📰 Fetching Egyptian RSS news feeds...")
    try:
        from rss_news_collector import collect_rss_news
        stats = collect_rss_news(days_back=3, use_finbert=False)
        print(f"  ✅ RSS: {stats['articles_saved']} articles from {stats['feeds_processed']} feeds")
        return stats
    except ImportError:
        print("  ⚠️ RSS collector not available, skipping")
        return {'articles_saved': 0}
    except Exception as e:
        print(f"  ❌ RSS collection error: {e}")
        return {'articles_saved': 0, 'error': str(e)}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Xmore data collection")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--prices-only', action='store_true',
                      help='Collect prices only (fast, used for intraday updates)')
    mode.add_argument('--news-only', action='store_true',
                      help='Collect news + RSS only (no price fetching)')
    args = parser.parse_args()

    start_time = time.time()
    print(f"🚀 Starting data collection at {datetime.now()}")
    print(f"📊 Collecting data for {len(config.ALL_STOCKS)} stocks")

    # Initialize database tables first
    print("🔧 Initializing database tables...")
    create_tables()

    try:
        p_count = n_count = rss_count = 0

        if args.prices_only:
            # Lightweight intraday price update — no news
            p_count = collect_prices()
            duration = time.time() - start_time
            msg = f"[prices-only] Collected prices for {p_count} stocks."
            log_system_run("collect_data.py", "success", msg, duration)
            print(f"✅ {msg}")

        elif args.news_only:
            # News + RSS only — respects NewsAPI daily rate limits
            n_count = collect_news()
            rss_stats = collect_rss_news_wrapper()
            rss_count = rss_stats.get('articles_saved', 0)
            duration = time.time() - start_time
            msg = f"[news-only] NewsAPI for {n_count} stocks, RSS articles: {rss_count}."
            log_system_run("collect_data.py", "success", msg, duration)
            print(f"✅ {msg}")

        else:
            # Full collection: prices + news + RSS
            p_count = collect_prices()
            n_count = collect_news()
            rss_stats = collect_rss_news_wrapper()
            rss_count = rss_stats.get('articles_saved', 0)
            duration = time.time() - start_time
            msg = f"Collected prices for {p_count} stocks, NewsAPI for {n_count} stocks, RSS articles: {rss_count}."
            log_system_run("collect_data.py", "success", msg, duration)
            print(f"✅ Collection complete! {msg}")

    except Exception as e:
        duration = time.time() - start_time
        log_system_run("collect_data.py", "failure", str(e), duration)
        print(f"💥 System Failure: {e}")