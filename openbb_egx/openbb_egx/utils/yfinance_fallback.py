"""
yfinance fallback for EGX historical data.

Uses the .CA suffix convention for EGX tickers on Yahoo Finance.
"""

import logging
from datetime import date, timedelta
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


async def fetch_yfinance_history(
    symbol: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Optional[List[Dict[str, Any]]]:
    """
    Fetch historical OHLCV data from yfinance for an EGX symbol.

    Args:
        symbol: EGX ticker (e.g. 'COMI' or 'COMI.CA')
        start_date: Start date (default: 90 days ago)
        end_date: End date (default: today)

    Returns list of dicts or None on failure.
    """
    try:
        import yfinance as yf
    except ImportError:
        logger.warning('yfinance not installed')
        return None

    # Ensure .CA suffix
    yf_symbol = symbol if symbol.endswith('.CA') else f"{symbol}.CA"

    if start_date is None:
        start_date = date.today() - timedelta(days=90)
    if end_date is None:
        end_date = date.today()

    try:
        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(start=start_date.isoformat(), end=end_date.isoformat())

        if df is None or df.empty:
            logger.warning('[yfinance] No data for %s', yf_symbol)
            return None

        rows = []
        for idx, row in df.iterrows():
            dt = idx.date() if hasattr(idx, 'date') else idx
            close = float(row.get('Close', 0))
            if close == 0:
                continue
            rows.append({
                'symbol': yf_symbol,
                'date': str(dt),
                'open': float(row.get('Open', close)),
                'high': float(row.get('High', close)),
                'low': float(row.get('Low', close)),
                'close': close,
                'volume': int(row.get('Volume', 0)),
                'change_pct': None,
            })

        logger.info('[yfinance] Fetched %d rows for %s', len(rows), yf_symbol)
        return rows if rows else None

    except Exception as exc:
        logger.warning('[yfinance] Failed for %s: %s', yf_symbol, exc)
        return None
