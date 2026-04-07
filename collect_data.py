"""
Data Collection Script

This module is responsible for fetching stock prices and news from external APIs.
Primary source: Yahoo Finance (yfinance) for KSA .SR Tadawul stocks.
News: NewsAPI + RSS feeds

Key components:
- Price collection via yfinance (primary for KSA/Tadawul stocks)
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

def collect_ksa_data():
    """
    Collect KSA/Tadawul stock data via yfinance.

    Strategy:
    - Use yfinance for all .SR (Saudi Exchange) symbols
    - Store all data in prices table with source tracking

    Returns:
        int: Number of stocks successfully collected.
    """
    print("🏛️  Fetching KSA/Tadawul data via yfinance...")
    return collect_prices_yfinance(config.KSA_STOCKS)


def validate_price_continuity(symbol: str, df) -> None:
    """
    Check a price DataFrame for data-quality issues and log warnings.

    Checks:
      - Date gaps > 7 calendar days (missing data / exchange closure anomaly)
      - Single-day price jumps > 15% (potential unadjusted corporate action)

    Args:
        symbol: Ticker string for logging.
        df:     DataFrame returned by yf.Ticker.history(), indexed by DatetimeIndex.
    """
    if df is None or len(df) < 2:
        return

    import pandas as pd
    dates = pd.to_datetime(df.index)

    # --- Gap check ---
    for i in range(1, len(dates)):
        gap_days = (dates[i] - dates[i - 1]).days
        if gap_days > 7:
            msg = f"Date gap of {gap_days} calendar days between {dates[i-1].date()} and {dates[i].date()}"
            logger.warning("[DataQuality] %s: %s", symbol, msg)
            try:
                log_data_quality_issue(symbol, "date_gap", msg, "medium")
            except Exception:
                pass

    # --- Price-jump check (> 15 %) ---
    closes = df["Close"].dropna()
    pct_changes = closes.pct_change().dropna()
    for ts, chg in pct_changes.items():
        if abs(chg) > 0.15:
            msg = (
                f"Price jump of {chg*100:.1f}% on {getattr(ts, 'date', lambda: ts)()}"
                f" — possible split or unadjusted corporate action"
            )
            logger.warning("[DataQuality] %s: %s", symbol, msg)
            try:
                log_data_quality_issue(symbol, "price_jump", msg, "high")
            except Exception:
                pass


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
            validate_price_continuity(symbol, df)
            
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


def _fetch_usdsar_rate():
    """
    Fetch current USD/SAR exchange rate from multiple sources in priority order:
      1. open.er-api.com — free tier, no key needed
      2. frankfurter.app — ECB-based, free
      3. exchangerate.host — free API
    SAR is pegged to USD at ~3.75, so the rate should be very stable.
    Returns float rate or None if all sources fail.
    """
    # --- Source 1: open.er-api.com (free, no key) ---
    try:
        r = requests.get('https://open.er-api.com/v6/latest/USD', timeout=8)
        if r.status_code == 200:
            data = r.json()
            rate = data.get('rates', {}).get('SAR')
            if rate and 2.5 < rate < 5.0:  # SAR is pegged ~3.75
                print(f"  open.er-api rate: USD/SAR = {rate:.4f}")
                return float(rate)
    except Exception as e:
        print(f"  open.er-api failed: {e}")

    # --- Source 2: frankfurter.app (ECB-based) ---
    try:
        r = requests.get('https://api.frankfurter.app/latest?from=USD&to=SAR', timeout=8)
        if r.status_code == 200:
            data = r.json()
            rate = data.get('rates', {}).get('SAR')
            if rate and 2.5 < rate < 5.0:
                print(f"  frankfurter rate: USD/SAR = {rate:.4f}")
                return float(rate)
    except Exception as e:
        print(f"  frankfurter failed: {e}")

    # --- Source 3: exchangerate.host ---
    try:
        r = requests.get(
            'https://api.exchangerate.host/latest?base=USD&symbols=SAR',
            timeout=8
        )
        if r.status_code == 200:
            data = r.json()
            rate = data.get('rates', {}).get('SAR')
            if rate and 2.5 < rate < 5.0:
                print(f"  exchangerate.host rate: USD/SAR = {rate:.4f}")
                return float(rate)
    except Exception as e:
        print(f"  exchangerate.host failed: {e}")

    # Fallback: SAR is pegged at 3.75
    print("  Using fallback pegged rate: USD/SAR = 3.7500")
    return 3.75


def collect_macro_data():
    """
    Fetch macro context data via yfinance and store in the prices table.

    Three instruments captured as special symbols:
      MACRO_BRENT   ← BZ=F  (Brent crude front-month future)
      MACRO_USDSAR  ← SAR=X  (USD / Saudi Riyal spot rate)
      MACRO_EEM     ← EEM   (iShares MSCI Emerging Markets ETF)

    Stored in the same prices table as stock prices (with data_source='yfinance_macro').
    The ML agent reads these rows at training/inference time to build macro features.
    """
    MACRO_SYMBOLS = {
        'MACRO_BRENT':  'BZ=F',
        'MACRO_USDSAR': 'SAR=X',
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

    print("Fetching macro context data (Brent, USD/SAR, EM)...")
    stored = 0
    today = datetime.utcnow().strftime('%Y-%m-%d')

    # --- Special handling for USD/SAR: try API sources first ---
    sar_rate = _fetch_usdsar_rate()
    if sar_rate is not None:
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (
                    'MACRO_USDSAR',
                    today,
                    sar_rate, sar_rate, sar_rate, sar_rate,
                    0,
                    'fx_api',
                ))
            stored += 1
            print(f"  OK MACRO_USDSAR: {sar_rate:.4f} SAR/USD")
            MACRO_SYMBOLS.pop('MACRO_USDSAR', None)   # skip yfinance fallback
        except Exception as e:
            print(f"  MACRO_USDSAR store error: {e} — will try yfinance")

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

    # KSA stocks: use yfinance for Tadawul .SR symbols
    if config.KSA_STOCKS:
        total += collect_ksa_data()

    # US stocks: always use yfinance
    if config.US_STOCKS:
        print("📈 Fetching US stock data from yfinance...")
        total += collect_prices_yfinance(config.US_STOCKS)

    # Macro context (Brent, USD/SAR, EM) — used as ML features
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
            # For KSA, adding 'Saudi' or 'Tadawul' helps filter irrelevant global noise.
            ticker_code = symbol.split('.')[0]
            query = f"{ticker_code} Saudi Stock OR {ticker_code} Tadawul"
            
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
    Collect KSA/Tadawul financial news from RSS feeds.

    This supplements NewsAPI with local Saudi/GCC sources for better KSA coverage.
    RSS feeds are particularly useful for Arabic-language financial news.

    Returns:
        dict: Collection statistics from RSS collector
    """
    print("📰 Fetching KSA RSS news feeds...")
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
            # Acquire advisory lock so evaluate.py knows not to read incomplete prices
            from engines.job_locks import acquire_lock, release_lock
            _lock_conn = None
            try:
                from database import get_connection as _gc
                _lock_conn = _gc().__enter__()
                acquire_lock(_lock_conn, 'intraday-price-update', ttl_minutes=10)
            except Exception:
                pass  # Fail-open: don't block collection on lock issues

            p_count = collect_prices()

            # Release lock after prices are written
            if _lock_conn:
                try:
                    release_lock(_lock_conn, 'intraday-price-update')
                    _lock_conn.commit()
                    _lock_conn.close()
                except Exception:
                    pass

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