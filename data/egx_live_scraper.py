"""
EGX Live Data Scraper

Fetches real-time stock data from the Egyptian Exchange live feed at
http://41.33.162.236/egs4/ which provides 200+ stocks with bid/ask/volume.

Primary EGX data source with yfinance fallback.

Column Mapping (Arabic → English):
    الإسم_المختصر → name_ar
    أخر_سعر → last_price
    إغلاق → close
    إقفال_سابق → prev_close
    التغير → change
    %التغيير → change_pct
    أعلى → high (intraday)
    الأدنى → low (intraday)
    الاعلى → high_52w (52-week high)
    الادنى → low_52w (52-week low)
    العرض → bid
    الطلب → ask
    حجم_التداول → volume
"""

import requests
import pandas as pd
import numpy as np
import logging
import re
from datetime import datetime
from io import StringIO

logger = logging.getLogger(__name__)

# EGX Live Feed URL
EGX_LIVE_URL = "http://41.33.162.236/egs4/"

# Arabic column header → English field name mapping
COLUMN_MAP = {
    'الإسم المختصر': 'name_ar',
    'الاسم المختصر': 'name_ar',
    'الإسم': 'name_ar',
    'الاسم': 'name_ar',
    'أخر سعر': 'last_price',
    'اخر سعر': 'last_price',
    'آخر سعر': 'last_price',
    'السعر': 'last_price',
    'إغلاق': 'close',
    'اغلاق': 'close',
    'سعر الإغلاق': 'close',
    'سعر الاغلاق': 'close',
    'إقفال سابق': 'prev_close',
    'اقفال سابق': 'prev_close',
    'التغير': 'change',
    'التغيير': 'change_pct',
    '%التغيير': 'change_pct',
    'التغيير%': 'change_pct',
    'نسبة التغيير': 'change_pct',
    'أعلى': 'high',
    'اعلى': 'high',
    'أعلى سعر': 'high',
    'الأدنى': 'low',
    'الادنى': 'low',
    'أدنى سعر': 'low',
    'الاعلى': 'high_52w',
    'الادني': 'low_52w',
    'العرض': 'bid',
    'الطلب': 'ask',
    'حجم التداول': 'volume',
    'حجم': 'volume',
    'الكمية': 'volume',
    'الرمز': 'ticker',
    'رمز': 'ticker',
    'الكود': 'ticker',
    'كود': 'ticker',
    'رمز الورقة': 'ticker',
    'كود الورقة': 'ticker',
    'رمز السهم': 'ticker',
}


def _normalize_arabic(text):
    """Normalize Arabic text for matching — strip diacritics & normalize alef/ya."""
    if not isinstance(text, str):
        return str(text)
    text = text.strip()
    # Remove Arabic diacritics (tashkeel)
    text = re.sub(r'[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06DC\u06DF-\u06E4\u06E7\u06E8\u06EA-\u06ED]', '', text)
    return text


def _safe_float(val, default=0.0):
    """Safely convert a value to float, handling Arabic numerals and commas."""
    if val is None or val == '' or val == '-' or val == '--':
        return default
    try:
        # Remove commas and whitespace
        cleaned = str(val).replace(',', '').replace('٫', '.').strip()
        # Remove % sign
        cleaned = cleaned.replace('%', '')
        return float(cleaned)
    except (ValueError, TypeError):
        return default


def fetch_egx_live(timeout=30):
    """
    Fetch and parse the EGX live feed HTML table.

    Returns:
        pd.DataFrame: DataFrame with columns mapped to English names,
                      filtered for active stocks, with derived fields calculated.

    Raises:
        requests.RequestException: If the HTTP request fails.
        ValueError: If no valid data is found in the response.
    """
    logger.info(f"Fetching EGX live data from {EGX_LIVE_URL}")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'ar,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate',
    }

    response = requests.get(EGX_LIVE_URL, headers=headers, timeout=timeout)
    response.raise_for_status()

    # Force proper encoding for Arabic content
    response.encoding = response.apparent_encoding or 'utf-8'
    html_content = response.text

    # Parse HTML tables
    try:
        tables = pd.read_html(StringIO(html_content), encoding='utf-8')
    except Exception as e:
        logger.error(f"Failed to parse HTML tables: {e}")
        raise ValueError(f"No tables found in EGX live feed response: {e}")

    if not tables:
        raise ValueError("No tables found in EGX live feed response")

    # Use the largest table (the main stock table)
    df = max(tables, key=len)
    logger.info(f"Found table with {len(df)} rows and {len(df.columns)} columns")

    # Map columns from Arabic to English
    df = _map_columns(df)

    # Filter inactive stocks (close == 0 AND volume == 0)
    df = _filter_inactive(df)

    # Calculate derived fields
    df = _calculate_derived_fields(df)

    # Add metadata
    df['date'] = datetime.now().strftime('%Y-%m-%d')
    df['source'] = 'egx_live'

    logger.info(f"EGX live feed: {len(df)} active stocks processed")
    logger.info(f"EGX columns mapped: {list(df.columns)}")
    return df


def _map_columns(df):
    """Map Arabic column headers to English field names."""
    # Try to match columns using our mapping
    new_columns = {}
    for col in df.columns:
        col_str = _normalize_arabic(str(col))
        matched = False

        for arabic, english in COLUMN_MAP.items():
            if arabic in col_str or col_str in arabic:
                new_columns[col] = english
                matched = True
                break

        if not matched:
            # Keep original column name, cleaned
            new_columns[col] = col_str.replace(' ', '_')

    df = df.rename(columns=new_columns)

    # Drop duplicate columns that arose from multiple Arabic variants mapping
    # to the same English name — keeps the first occurrence of each column.
    df = df.loc[:, ~df.columns.duplicated()]

    # Convert numeric columns
    numeric_cols = ['last_price', 'close', 'prev_close', 'change', 'change_pct',
                    'high', 'low', 'high_52w', 'low_52w', 'bid', 'ask', 'volume']

    for col in numeric_cols:
        if col in df.columns:
            df[col] = df[col].apply(_safe_float)

    return df


def _filter_inactive(df):
    """Filter out rows where close == 0 AND volume == 0 (suspended/inactive stocks)."""
    close_col = 'close' if 'close' in df.columns else 'last_price'
    vol_col = 'volume'

    if close_col in df.columns and vol_col in df.columns:
        before = len(df)
        df = df[~((df[close_col] == 0) & (df[vol_col] == 0))].copy()
        filtered = before - len(df)
        if filtered > 0:
            logger.info(f"Filtered out {filtered} inactive/suspended stocks")

    return df


def _calculate_derived_fields(df):
    """Calculate derived fields from raw data."""
    # Bid-Ask Spread (liquidity indicator)
    if 'ask' in df.columns and 'bid' in df.columns and 'last_price' in df.columns:
        df['bid_ask_spread'] = np.where(
            df['last_price'] > 0,
            (df['ask'] - df['bid']) / df['last_price'],
            0.0
        )
    else:
        df['bid_ask_spread'] = 0.0

    # 52-week range position (where in the annual range is the stock now)
    if 'close' in df.columns and 'low_52w' in df.columns and 'high_52w' in df.columns:
        range_diff = df['high_52w'] - df['low_52w']
        df['range_52w_position'] = np.where(
            range_diff > 0,
            (df['close'] - df['low_52w']) / range_diff,
            0.5  # Default to midpoint if range is 0
        )
    else:
        df['range_52w_position'] = 0.5

    # Intraday range (daily volatility)
    if 'high' in df.columns and 'low' in df.columns and 'prev_close' in df.columns:
        df['intraday_range'] = np.where(
            df['prev_close'] > 0,
            (df['high'] - df['low']) / df['prev_close'],
            0.0
        )
    else:
        df['intraday_range'] = 0.0

    return df


def egx_to_prices_schema(df):
    """
    Convert EGX live feed DataFrame to match the prices table schema.
    Schema: symbol, date, open, high, low, close, volume

    Since the live feed doesn't provide 'open', we use prev_close as proxy.
    """
    records = []

    for _, row in df.iterrows():
        # Build symbol — use ticker if available, else derive from name
        symbol = None
        if 'ticker' in df.columns and pd.notna(row.get('ticker')):
            ticker = str(row['ticker']).strip()
            if ticker:
                symbol = f"{ticker}.CA" if not ticker.endswith('.CA') else ticker

        if not symbol and 'name_ar' in df.columns:
            # Fallback: use name_ar as symbol if it looks like a short EGX ticker
            # (EGX tickers are typically 2-6 char Arabic abbreviations)
            raw = str(row.get('name_ar', '')).strip()
            if raw and len(raw) <= 10:
                symbol = f"{raw}.CA" if not raw.endswith('.CA') else raw

        if not symbol:
            continue

        record = {
            'symbol': symbol,
            'date': row.get('date', datetime.now().strftime('%Y-%m-%d')),
            'open': row.get('prev_close', row.get('close', 0)),  # Use prev_close as proxy for open
            'high': row.get('high', row.get('close', 0)),
            'low': row.get('low', row.get('close', 0)),
            'close': row.get('close', row.get('last_price', 0)),
            'volume': int(row.get('volume', 0)),
        }

        # Skip if no meaningful price data
        if record['close'] == 0:
            continue

        records.append(record)

    result = pd.DataFrame(records)
    logger.info(f"Converted {len(result)} stocks to prices schema")
    return result


def get_egx_names(df=None):
    """
    Extract bilingual company name mapping from the live feed.

    Returns:
        dict: {symbol: {'name_ar': str, 'ticker': str}} for all stocks
    """
    if df is None:
        df = fetch_egx_live()

    names = {}
    for _, row in df.iterrows():
        ticker = str(row.get('ticker', '')).strip() if 'ticker' in df.columns else ''
        name_ar = str(row.get('name_ar', '')).strip() if 'name_ar' in df.columns else ''

        if ticker:
            symbol = f"{ticker}.CA" if not ticker.endswith('.CA') else ticker
            names[symbol] = {
                'name_ar': name_ar,
                'ticker': ticker,
            }

    return names


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("🏛️  Fetching EGX live data...")

    try:
        df = fetch_egx_live()
        print(f"\n✅ Fetched {len(df)} active stocks")
        print(f"\nColumns: {list(df.columns)}")
        print(f"\nSample data (first 5 rows):")
        display_cols = [c for c in ['name_ar', 'ticker', 'close', 'volume', 'bid_ask_spread', 'range_52w_position'] if c in df.columns]
        if display_cols:
            print(df[display_cols].head().to_string())

        # Convert to prices schema
        prices_df = egx_to_prices_schema(df)
        print(f"\n📊 Converted {len(prices_df)} stocks to prices schema:")
        print(prices_df.head().to_string())

        # Get names
        names = get_egx_names(df)
        print(f"\n📝 Extracted {len(names)} company names")
        for symbol, info in list(names.items())[:5]:
            print(f"  {symbol}: {info['name_ar']}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
