"""
Base class for all market data providers.

Defines the contract that all providers must follow.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
import pandas as pd


class MarketDataProvider(ABC):
    """
    Abstract base class for market data providers.
    
    All providers must implement fetch() and optionally support_intraday().
    Output must always conform to standard schema:
    Date | Open | High | Low | Close | Adj Close | Volume
    """

    def __init__(self, name: str):
        """
        Initialize provider.
        
        Args:
            name: Provider name (e.g., "EGXPY", "yfinance", "Alpha Vantage")
        """
        self.name = name

    @abstractmethod
    def fetch(
        self,
        symbol: str,
        interval: str = "1d",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Fetch market data for a symbol.
        
        Args:
            symbol: Trading symbol (e.g., "COMI", "SWDY")
            interval: Time interval (1m, 5m, 15m, 1h, 1d, 1w, 1mo)
            start: Start datetime (inclusive)
            end: End datetime (inclusive)
        
        Returns:
            pd.DataFrame with columns:
            Date | Open | High | Low | Close | Adj Close | Volume
            
        Raises:
            ValueError: If symbol not found or parameters invalid
            ConnectionError: If unable to reach API
            TimeoutError: If request times out
        """
        pass

    def support_intraday(self) -> bool:
        """Check if provider supports intraday (sub-daily) intervals."""
        return False

    def supports_symbol(self, symbol: str) -> bool:
        """Return whether the provider can reasonably serve the requested symbol."""
        return True

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}('{self.name}')>"
