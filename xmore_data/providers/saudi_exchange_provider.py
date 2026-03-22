"""
Saudi Exchange Provider - official Tadawul source for TASI benchmark data.

Best-effort parser for the public historical reports page. If the public page
does not expose the requested back-dated range, the caller should fall back to
EODHD for historical coverage.
"""

from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import requests

from ..config import Config
from ..utils import exponential_backoff, validate_dataframe, get_logger
from . import MarketDataProvider

logger = get_logger(__name__)


class SaudiExchangeProvider(MarketDataProvider):
    """Official Saudi Exchange provider for TASI benchmark data."""

    def __init__(self):
        super().__init__("SaudiExchange")
        self.session = requests.Session()

    def supports_symbol(self, symbol: str) -> bool:
        return (symbol or "").upper() in Config.KSA_BENCHMARK_ALIASES

    def _extract_table(self, html: str) -> pd.DataFrame:
        tables = pd.read_html(html)
        for table in tables:
            lowered = [str(col).strip().lower() for col in table.columns]
            if any("open" in col for col in lowered) and any("close" in col for col in lowered):
                return table
        raise ValueError("No OHLC-like table found in Saudi Exchange response")

    @exponential_backoff(max_attempts=Config.RETRY_ATTEMPTS)
    def fetch(
        self,
        symbol: str,
        interval: str = "1d",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> pd.DataFrame:
        if interval != "1d":
            raise ValueError("Saudi Exchange provider only supports daily benchmark data")

        if end is None:
            end = datetime.utcnow()
        if start is None:
            start = end - timedelta(days=30)

        response = self.session.get(
            Config.SAUDI_EXCHANGE_HISTORICAL_REPORTS_URL,
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()

        table = self._extract_table(response.text)
        rename_map = {}
        for column in table.columns:
            normalized = str(column).strip().lower()
            if "date" in normalized:
                rename_map[column] = "Date"
            elif "open" in normalized:
                rename_map[column] = "Open"
            elif "high" in normalized:
                rename_map[column] = "High"
            elif "low" in normalized:
                rename_map[column] = "Low"
            elif "close" in normalized:
                rename_map[column] = "Close"
            elif "volume" in normalized or "turnover" in normalized:
                rename_map[column] = "Volume"
        table.rename(columns=rename_map, inplace=True)
        if "Adj Close" not in table.columns and "Close" in table.columns:
            table["Adj Close"] = table["Close"]
        if "Volume" not in table.columns:
            table["Volume"] = 0

        validated = validate_dataframe(table, f"SaudiExchange[{symbol}]")
        filtered = validated[
            (validated["Date"] >= pd.Timestamp(start.date()))
            & (validated["Date"] <= pd.Timestamp(end.date()))
        ].reset_index(drop=True)
        if filtered.empty:
            raise ValueError(
                "Saudi Exchange public reports did not expose the requested range; "
                "fall back to EODHD for historical coverage"
            )
        return filtered
