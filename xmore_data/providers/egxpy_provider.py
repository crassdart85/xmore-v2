"""
EGXPY (EGXLytics) Provider - Primary data source for EGX market data.

Wraps EGXPY in an abstraction layer with error handling and retry logic.
"""

from datetime import datetime, timedelta
from typing import Optional
import pandas as pd
import sys
from pathlib import Path

from ..config import Config
from ..utils import exponential_backoff, validate_dataframe, get_logger
from . import MarketDataProvider

logger = get_logger(__name__)


class EGXPYProvider(MarketDataProvider):
    """
    Provider for EGXPY (EGXLytics) - Egyptian Exchange data.
    
    Attempts to import EGXPY:
    1. Via pip (installed module)
    2. Via local source in workspace
    
    If both fail, raises ImportError and triggers fallback chain.
    """

    def __init__(self):
        super().__init__("EGXPY")
        self.client = self._initialize_client()

    def _initialize_client(self):
        """
        Initialize EGXPY client with fallback import strategy.
        
        Returns:
            EGXPY client instance
        
        Raises:
            ImportError: If EGXPY cannot be imported from any source
        """
        try:
            # Try standard import (pip installed)
            try:
                import egxpy
                logger.info("✓ EGXPY imported from site-packages")
                return egxpy
            except ImportError:
                logger.warning("EGXPY not in site-packages, trying local import...")
                
                # Try local source import
                workspace_root = Path(__file__).parent.parent.parent
                egxpy_path = workspace_root / "egxpy"
                
                if egxpy_path.exists():
                    sys.path.insert(0, str(workspace_root))
                    import egxpy
                    logger.info(f"✓ EGXPY imported from local: {egxpy_path}")
                    return egxpy
                else:
                    raise ImportError(
                        f"EGXPY not found in site-packages or at {egxpy_path}\n"
                        f"Install: pip install egxpy\n"
                        f"Or provide local source at: {egxpy_path}"
                    )
        
        except Exception as e:
            logger.error(f"Failed to initialize EGXPY: {e}")
            raise

    def supports_symbol(self, symbol: str) -> bool:
        normalized = (symbol or "").upper()
        return not normalized.endswith(".SR") and normalized not in Config.KSA_BENCHMARK_ALIASES

    @exponential_backoff(max_attempts=Config.EGXPY_RETRIES)
    def fetch(
        self,
        symbol: str,
        interval: str = "1d",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Fetch historical market data from EGXPY.
        
        Args:
            symbol: EGX stock symbol (e.g., "COMI", "SWDY", "HRHO")
            interval: OHLCV interval (1d, 1w, 1mo, or 1m if supported)
            start: Start date (defaults to 90 days ago)
            end: End date (defaults to today)
        
        Returns:
            Standardized DataFrame
        
        Raises:
            ValueError: If symbol not found
            ConnectionError: If API fails
            TimeoutError: If request exceeds timeout
        """
        try:
            logger.info(f"Fetching {symbol} from EGXPY (interval={interval})")
            
            # Set defaults
            if end is None:
                end = datetime.now()
            if start is None:
                start = end - timedelta(days=90)
            
            # Convert interval: EGXPY may use different naming
            egxpy_interval = self._map_interval(interval)
            
            # Fetch from EGXPY
            df = self.client.get_stocks_data(
                symbols=[symbol],
                start_date=start.strftime('%Y-%m-%d'),
                end_date=end.strftime('%Y-%m-%d'),
                frequency=egxpy_interval
            )
            
            if df is None or df.empty:
                raise ValueError(f"{symbol} not found in EGXPY or no data in range")
            
            # Handle multi-level columns if present (EGXPY may return multi-index)
            if isinstance(df.columns, pd.MultiIndex):
                # Flatten multi-index columns
                df.columns = [col[0] if col[1] == symbol else col for col in df.columns]
            
            # Validate and standardize
            df = validate_dataframe(df, f"EGXPY[{symbol}]")
            logger.info(f"✓ EGXPY: {symbol} - {len(df)} rows")
            
            return df
        
        except Exception as e:
            logger.error(f"EGXPY failed for {symbol}: {e}")
            raise

    def _map_interval(self, interval: str) -> str:
        """
        Map standard interval names to EGXPY conventions.
        
        Args:
            interval: Standard interval (1d, 1w, 1mo, etc)
        
        Returns:
            EGXPY-compatible interval string
        """
        mapping = {
            "1m": "1T",
            "5m": "5T",
            "15m": "15T",
            "1h": "1H",
            "1d": "1D",
            "1w": "1W",
            "1mo": "1MS",
        }
        return mapping.get(interval, interval)

    def support_intraday(self) -> bool:
        """EGXPY supports intraday data if available."""
        return True

    def fetch_index(self, start: Optional[datetime] = None, end: Optional[datetime] = None) -> pd.DataFrame:
        """
        Fetch EGX index data (^CASE).
        
        Args:
            start: Start date
            end: End date
        
        Returns:
            Index DataFrame
        """
        return self.fetch("^CASE", interval="1d", start=start, end=end)
