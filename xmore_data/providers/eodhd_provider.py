"""
EODHD (EOD Historical Data) Provider — primary source for KSA/Tadawul data.

EODHD has reliable coverage of Saudi Exchange (.SR) symbols, including
stocks that yfinance cannot serve (e.g. 1160.SR, 1170.SR, 3001.SR).

API key: set EODHD_API_KEY environment variable.
Docs: https://eodhd.com/financial-apis/

Endpoints used:
  EOD prices  : GET /api/eod/{TICKER}?api_token=KEY&from=YYYY-MM-DD&to=YYYY-MM-DD&period=d&fmt=json
  Fundamentals: GET /api/fundamentals/{TICKER}?api_token=KEY&fmt=json
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import requests

from . import MarketDataProvider

logger = logging.getLogger(__name__)

_BASE_URL = "https://eodhd.com/api"
_TIMEOUT  = 15   # seconds per request


class EODHDProvider(MarketDataProvider):
    """
    Market data provider backed by EODHD (EOD Historical Data).

    Priority: primary for .SR (Tadawul) symbols; falls back transparently
    to the next provider in the chain when the key is absent or a request
    fails.
    """

    def __init__(self):
        super().__init__("eodhd")
        self.api_key = os.getenv("EODHD_API_KEY", "")
        if self.api_key:
            logger.info("[EODHD] Provider initialised (key present)")
        else:
            logger.info("[EODHD] Provider initialised — EODHD_API_KEY not set, will skip")

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    # ------------------------------------------------------------------
    # MarketDataProvider interface
    # ------------------------------------------------------------------

    def fetch(
        self,
        symbol: str,
        interval: str = "1d",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data from EODHD.

        Returns a DataFrame with columns:
            Date | Open | High | Low | Close | Adj Close | Volume

        Raises ValueError / ConnectionError on failure so the caller's
        fallback chain can catch and continue to the next provider.
        """
        if not self.enabled:
            raise ValueError("EODHD_API_KEY not set — provider disabled")

        if end is None:
            end = datetime.utcnow()
        if start is None:
            start = end - timedelta(days=180)

        # EODHD only supports daily for most markets
        if interval not in ("1d", "1w", "1mo"):
            raise ValueError(f"EODHD does not support intraday interval '{interval}'")

        period_map = {"1d": "d", "1w": "w", "1mo": "m"}
        period = period_map.get(interval, "d")

        url = f"{_BASE_URL}/eod/{symbol}"
        params = {
            "api_token": self.api_key,
            "from":      start.strftime("%Y-%m-%d"),
            "to":        end.strftime("%Y-%m-%d"),
            "period":    period,
            "fmt":       "json",
        }

        try:
            resp = requests.get(url, params=params, timeout=_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            raise ConnectionError(f"EODHD request failed for {symbol}: {e}") from e

        if not data:
            raise ValueError(f"EODHD returned empty data for {symbol}")

        df = pd.DataFrame(data)
        if df.empty or "date" not in df.columns:
            raise ValueError(f"EODHD returned no rows for {symbol}")

        # Normalise column names to standard schema
        df.rename(columns={
            "date":            "Date",
            "open":            "Open",
            "high":            "High",
            "low":             "Low",
            "close":           "Close",
            "adjusted_close":  "Adj Close",
            "volume":          "Volume",
        }, inplace=True)

        df["Date"] = pd.to_datetime(df["Date"])
        df.sort_values("Date", inplace=True)
        df.reset_index(drop=True, inplace=True)

        # Keep only standard columns (EODHD also returns 'exchange_short_name' etc.)
        keep = [c for c in ("Date", "Open", "High", "Low", "Close", "Adj Close", "Volume") if c in df.columns]
        df = df[keep].copy()

        # If adjusted_close missing, alias Close
        if "Adj Close" not in df.columns:
            df["Adj Close"] = df["Close"]

        for col in ("Open", "High", "Low", "Close", "Adj Close", "Volume"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        logger.info("[EODHD] %s — %d rows (%s → %s)", symbol, len(df),
                    df["Date"].iloc[0].date() if len(df) else "?",
                    df["Date"].iloc[-1].date() if len(df) else "?")
        return df

    def support_intraday(self) -> bool:
        return False


# ------------------------------------------------------------------
# Fundamentals helper (used by ksa_fundamentals_agent.py)
# ------------------------------------------------------------------

def fetch_eodhd_fundamentals(symbol: str) -> dict:
    """
    Fetch company fundamentals from EODHD for a single symbol.

    Returns a flat dict matching the keys used by ksa_fundamentals_agent
    (same field names as yfinance's ticker.info where possible).

    Returns {} if the key is absent or the request fails.
    """
    api_key = os.getenv("EODHD_API_KEY", "")
    if not api_key:
        return {}

    url = f"{_BASE_URL}/fundamentals/{symbol}"
    params = {"api_token": api_key, "fmt": "json"}

    try:
        resp = requests.get(url, params=params, timeout=_TIMEOUT)
        resp.raise_for_status()
        raw = resp.json()
    except Exception as e:
        logger.warning("[EODHD] Fundamentals fetch failed for %s: %s", symbol, e)
        return {}

    if not raw or not isinstance(raw, dict):
        return {}

    # Map EODHD's nested structure to a flat dict compatible with yfinance .info keys
    try:
        hi = raw.get("Highlights", {}) or {}
        val = raw.get("Valuation", {}) or {}
        tech = raw.get("Technicals", {}) or {}
        shares = raw.get("SharesStats", {}) or {}
        gen = raw.get("General", {}) or {}

        def _f(v):
            """Return float or None."""
            try:
                return float(v) if v not in (None, "", "None", "N/A") else None
            except (TypeError, ValueError):
                return None

        info = {
            # Price
            "currentPrice":        _f(tech.get("50DayMA")),   # best proxy; real-time not in fundamentals
            "regularMarketPrice":  _f(tech.get("50DayMA")),
            # Market cap
            "marketCap":           _f(hi.get("MarketCapitalization")),
            # Valuation
            "trailingPE":          _f(hi.get("PERatio")),
            "priceToBook":         _f(val.get("PriceBookMRQ")),
            "dividendYield":       _f(hi.get("DividendYield")),
            # Financials
            "totalRevenue":        _f(hi.get("RevenueTTM")),
            "netIncomeToCommon":   _f(hi.get("NetIncomeTTM")),
            "totalAssets":         None,   # not in Highlights; available in Financials sub-key
            "totalDebt":           None,
            "freeCashflow":        _f(hi.get("FreeCashFlowTTM")),
            # Risk / momentum
            "beta":                _f(tech.get("Beta")),
            "fiftyTwoWeekHigh":    _f(tech.get("52WeekHigh")),
            "fiftyTwoWeekLow":     _f(tech.get("52WeekLow")),
        }

        # Pull balance sheet totals if available
        bs = (raw.get("Financials", {}) or {}).get("Balance_Sheet", {}) or {}
        quarterly = bs.get("quarterly", {}) or {}
        if quarterly:
            latest_key = sorted(quarterly.keys())[-1]
            latest_bs = quarterly[latest_key] or {}
            info["totalAssets"] = _f(latest_bs.get("totalAssets"))
            info["totalDebt"]   = _f(latest_bs.get("totalDebt") or latest_bs.get("longTermDebt"))

        return info

    except Exception as e:
        logger.warning("[EODHD] Fundamentals parse error for %s: %s", symbol, e)
        return {}
