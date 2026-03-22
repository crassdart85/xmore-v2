"""
yfinance Provider - Primary fallback for market data.

Provides OHLCV data from Yahoo Finance. Covers EGX listed companies
that may have data on Yahoo Finance (limiting compared to EGXPY).
"""

from datetime import datetime, timedelta
from typing import Optional
import pandas as pd

from ..config import Config
from ..utils import exponential_backoff, validate_dataframe, get_logger
from . import MarketDataProvider

logger = get_logger(__name__)


class YFinanceProvider(MarketDataProvider):
    """
    Provider for yfinance (Yahoo Finance API).
    
    Requires: pip install yfinance
    
    Note: Some EGX stocks may not be available on Yahoo Finance.
    Use as fallback when EGXPY unavailable.
    """

    def __init__(self):
        super().__init__("yfinance")
        self.client = self._initialize_client()

    def _initialize_client(self):
        """
        Initialize yfinance client.
        
        Returns:
            yfinance module
        
        Raises:
            ImportError: If yfinance not installed
        """
        try:
            import yfinance as yf
            logger.info("✓ yfinance imported successfully")
            return yf
        except ImportError:
            logger.error("yfinance not installed. Install: pip install yfinance")
            raise

    def supports_symbol(self, symbol: str) -> bool:
        return True

    @exponential_backoff(max_attempts=Config.RETRY_ATTEMPTS)
    def fetch(
        self,
        symbol: str,
        interval: str = "1d",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Fetch historical market data from yfinance.
        
        Args:
            symbol: Trading symbol (may need .CA, .L, .IS suffix for foreign markets)
            interval: OHLCV interval (1m, 5m, 15m, 1h, 1d, 1w, 1mo)
            start: Start date (defaults to 90 days ago)
            end: End date (defaults to today)
        
        Returns:
            Standardized DataFrame
        
        Raises:
            ValueError: If symbol not found or no data
            ConnectionError: If API fails
            TimeoutError: If request exceeds timeout
        """
        try:
            logger.info(f"Fetching {symbol} from yfinance (interval={interval})")
            
            # Set defaults
            if end is None:
                end = datetime.now()
            if start is None:
                start = end - timedelta(days=90)
            
            # Map interval to yfinance format
            yf_interval = self._map_interval(interval)
            
            # Fetch data
            ticker = self.client.Ticker(symbol)
            df = ticker.history(
                start=start,
                end=end,
                interval=yf_interval,
                timeout=Config.EGXPY_TIMEOUT
            )
            
            if df is None or df.empty:
                raise ValueError(f"{symbol} not found on yfinance or no data in range")
            
            # Reset index to make Date a column
            df.reset_index(inplace=True)
            
            # yfinance returns 'Adj Close' already, but add it if missing
            if 'Adj Close' not in df.columns and 'Close' in df.columns:
                df['Adj Close'] = df['Close']
            
            # Validate and standardize
            df = validate_dataframe(df, f"yfinance[{symbol}]")
            logger.info(f"✓ yfinance: {symbol} - {len(df)} rows")
            
            return df
        
        except Exception as e:
            logger.error(f"yfinance failed for {symbol}: {e}")
            raise

    def _map_interval(self, interval: str) -> str:
        """
        Map standard interval names to yfinance conventions.
        
        Args:
            interval: Standard interval (1m, 5m, 15m, 1h, 1d, 1w, 1mo)
        
        Returns:
            yfinance-compatible interval string
        """
        # yfinance uses: 1m, 5m, 15m, 30m, 60m, 1d, 1wk, 1mo
        mapping = {
            "1m": "1m",
            "5m": "5m",
            "15m": "15m",
            "1h": "60m",
            "1d": "1d",
            "1w": "1wk",
            "1mo": "1mo",
        }
        return mapping.get(interval, interval)

    def support_intraday(self) -> bool:
        """yfinance supports intraday data (1m, 5m, 15m, 1h)."""
        return True

    def fetch_index(self, start: Optional[datetime] = None, end: Optional[datetime] = None) -> pd.DataFrame:
        """
        Fetch EGX index data from yfinance (^CASE).
        
        Args:
            start: Start date
            end: End date
        
        Returns:
            Index DataFrame
        """
        return self.fetch("^CASE", interval="1d", start=start, end=end)
