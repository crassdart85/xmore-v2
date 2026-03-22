"""
EODHD Provider - Primary source for Tadawul equities and benchmark fallback.
"""

from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import requests

from ..config import Config
from ..utils import exponential_backoff, validate_dataframe, get_logger
from . import MarketDataProvider

logger = get_logger(__name__)


class EODHDProvider(MarketDataProvider):
    """Provider for EOD Historical Data API."""

    def __init__(self):
        super().__init__("EODHD")
        if not Config.EODHD_API_KEY:
            raise RuntimeError("EODHD_API_KEY not configured")
        self.api_key = Config.EODHD_API_KEY
        self.base_url = Config.EODHD_BASE_URL.rstrip("/")
        self.session = requests.Session()

    def supports_symbol(self, symbol: str) -> bool:
        normalized = (symbol or "").upper()
        return normalized.endswith(".SR") or normalized in Config.KSA_BENCHMARK_ALIASES

    def _normalize_symbol(self, symbol: str) -> str:
        normalized = (symbol or "").upper()
        if normalized in Config.KSA_BENCHMARK_ALIASES:
            return Config.EODHD_BENCHMARK_SYMBOL
        if normalized.endswith(".SR"):
            return symbol.upper()
        return symbol

    def _map_interval(self, interval: str) -> str:
        mapping = {
            "1d": "d",
            "1w": "w",
            "1mo": "m",
        }
        if interval not in mapping:
            raise ValueError(f"EODHD does not support interval '{interval}' in this integration")
        return mapping[interval]

    @exponential_backoff(max_attempts=Config.RETRY_ATTEMPTS)
    def fetch(
        self,
        symbol: str,
        interval: str = "1d",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> pd.DataFrame:
        if end is None:
            end = datetime.utcnow()
        if start is None:
            start = end - timedelta(days=90)

        endpoint_symbol = self._normalize_symbol(symbol)
        url = f"{self.base_url}/eod/{endpoint_symbol}"
        params = {
            "api_token": self.api_key,
            "fmt": "json",
            "period": self._map_interval(interval),
            "from": start.strftime("%Y-%m-%d"),
            "to": end.strftime("%Y-%m-%d"),
        }

        logger.info("Fetching %s from EODHD", endpoint_symbol)
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()

        if not isinstance(payload, list) or not payload:
            raise ValueError(f"EODHD returned no rows for {symbol}")

        df = pd.DataFrame(payload)
        rename_map = {
            "date": "Date",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "adjusted_close": "Adj Close",
            "adjustedClose": "Adj Close",
            "volume": "Volume",
        }
        df.rename(columns=rename_map, inplace=True)
        if "Adj Close" not in df.columns and "Close" in df.columns:
            df["Adj Close"] = df["Close"]

        validated = validate_dataframe(df, f"EODHD[{symbol}]")
        if validated["Date"].min() > pd.Timestamp(start.date()):
            raise ValueError(
                f"EODHD did not return the requested start range for {symbol}: "
                f"{validated['Date'].min().date()} > {start.date()}"
            )
        return validated
