"""
Data Manager - Orchestrates provider fallback chain and caching.

Core module that:
- Manages provider hierarchy
- Implements fallback logic
- Handles caching
- Logs source of data
- Provides clean API to rest of Xmore
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict
import pandas as pd

from .config import Config
from .cache import MarketDataCache
from .utils import get_logger, parse_date_range
from .providers.saudi_exchange_provider import SaudiExchangeProvider
from .providers.eodhd_provider import EODHDProvider
from .providers.egxpy_provider import EGXPYProvider
from .providers.yfinance_provider import YFinanceProvider
from .providers.alpha_vantage_provider import AlphaVantageProvider
from .providers import MarketDataProvider

logger = get_logger(__name__)


class DataManager:
    """
    Central data orchestration layer.
    
    Features:
    - Provider fallback chain: EGXPY → yfinance → Alpha Vantage
    - Automatic caching with 24h TTL
    - Logs provider used for each fetch
    - Unified interface for signal engine and backtesting
    
    Usage:
        dm = DataManager()
        df = dm.fetch_data("COMI", interval="1d", start="2024-01-01")
        egx30 = dm.fetch_egx30()
        index = dm.fetch_index()
    """

    def __init__(self, use_cache: bool = True, cache_ttl_hours: int = 24, verbose: bool = True):
        """
        Initialize DataManager with providers and cache.
        
        Args:
            use_cache: Enable caching
            cache_ttl_hours: Cache time-to-live in hours
            verbose: Log provider initialization
        """
        self.use_cache = use_cache
        self.cache = MarketDataCache(ttl_hours=cache_ttl_hours) if use_cache else None
        self.verbose = verbose
        self.last_source: Dict[str, str] = {}
        
        # Initialize providers in priority order
        self.providers = self._initialize_providers()

    def _initialize_providers(self) -> List[MarketDataProvider]:
        """
        Initialize provider chain in order of preference.
        
        Returns:
            List of provider instances (successfully initialized)
        """
        providers = []

        # Priority 1: Official Saudi Exchange benchmark provider
        try:
            saudi_exchange = SaudiExchangeProvider()
            providers.append(saudi_exchange)
            if self.verbose:
                logger.info("✓ Saudi Exchange provider initialized (benchmark primary)")
        except Exception as e:
            logger.warning(f"Saudi Exchange provider not available: {e}")

        # Priority 2: EODHD (primary for Tadawul equities)
        try:
            eodhd = EODHDProvider()
            providers.append(eodhd)
            if self.verbose:
                logger.info("✓ EODHD provider initialized (KSA primary)")
        except Exception as e:
            logger.warning(f"EODHD not available: {e}")

        # Priority 3: EGXPY (legacy EGX primary)
        try:
            egxpy = EGXPYProvider()
            providers.append(egxpy)
            if self.verbose:
                logger.info("✓ EGXPY provider initialized (EGX primary)")
        except Exception as e:
            logger.warning(f"EGXPY not available: {e}")

        # Priority 4: yfinance (fallback)
        try:
            yf = YFinanceProvider()
            providers.append(yf)
            if self.verbose:
                logger.info("✓ yfinance provider initialized (fallback)")
        except Exception as e:
            logger.warning(f"yfinance not available: {e}")

        # Priority 5: Alpha Vantage (tertiary fallback)
        try:
            av = AlphaVantageProvider()
            providers.append(av)
            if self.verbose:
                logger.info("✓ Alpha Vantage provider initialized (fallback 2)")
        except Exception as e:
            logger.warning(f"Alpha Vantage not available: {e}")
        
        if not providers:
            raise RuntimeError(
                "No data providers available!\n"
                "Install at least one:\n"
                "  pip install egxpy\n"
                "  pip install yfinance\n"
                "  pip install alpha-vantage"
            )
        
        return providers

    def _get_provider_chain(self, symbol: str) -> List[MarketDataProvider]:
        chain = [provider for provider in self.providers if provider.supports_symbol(symbol)]
        return chain or self.providers

    def fetch_data(
        self,
        symbol: str,
        interval: str = "1d",
        start: Optional[str] = None,
        end: Optional[str] = None,
        force_refresh: bool = False
    ) -> pd.DataFrame:
        """
        Fetch market data with automatic provider fallback.
        
        Args:
            symbol: Stock symbol (e.g., "COMI", "SWDY")
            interval: Time interval (1m, 5m, 15m, 1h, 1d, 1w, 1mo)
            start: Start date as string (YYYY-MM-DD or relative like "90d", "1y")
            end: End date as string (YYYY-MM-DD or relative like "today")
            force_refresh: Bypass cache
        
        Returns:
            DataFrame with standardized schema (Date | Open | High | Low | Close | Adj Close | Volume)
        
        Raises:
            ValueError: If all providers fail or invalid parameters
        """
        # Parse date range
        start_dt, end_dt = parse_date_range(start, end)
        
        # Try cache first
        if self.use_cache and not force_refresh:
            cached = self.cache.get(symbol, interval, start_dt, end_dt)
            if cached is not None:
                self.last_source[symbol] = "cache"
                return cached
        
        # Try providers in fallback order
        last_error = None
        for provider in self._get_provider_chain(symbol):
            try:
                logger.info(f"Attempting fetch: {symbol} from {provider.name}")
                
                df = provider.fetch(
                    symbol=symbol,
                    interval=interval,
                    start=start_dt,
                    end=end_dt
                )
                
                # Cache successful fetch
                if self.use_cache and df is not None and not df.empty:
                    self.cache.set(symbol, interval, df, start_dt, end_dt)
                self.last_source[symbol] = provider.name
                
                logger.info(f"✓ Successfully fetched {symbol} from {provider.name}")
                return df
            
            except Exception as e:
                last_error = e
                logger.warning(f"{provider.name} failed for {symbol}: {str(e)}")
                continue
        
        # All providers failed
        raise ValueError(
            f"Unable to fetch {symbol} from any provider after {len(self.providers)} attempts. "
            f"Last error: {last_error}"
        )

    def fetch_egx30(
        self,
        interval: str = "1d",
        start: Optional[str] = None,
        end: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch data for all EGX30 companies.
        
        Args:
            interval: Time interval
            start: Start date
            end: End date
            force_refresh: Bypass cache
        
        Returns:
            Dict mapping symbol → DataFrame
        """
        egx30_data = {}
        
        logger.info(f"Fetching market basket ({len(Config.EGX30_SYMBOLS)} symbols)")
        
        for i, symbol in enumerate(Config.EGX30_SYMBOLS, 1):
            try:
                df = self.fetch_data(symbol, interval, start, end, force_refresh)
                egx30_data[symbol] = df
                logger.info(f"  [{i}/{len(Config.EGX30_SYMBOLS)}] ✓ {symbol}")
            except Exception as e:
                logger.error(f"  [{i}/{len(Config.EGX30_SYMBOLS)}] ✗ {symbol}: {e}")
                egx30_data[symbol] = None
        
        success_count = sum(1 for df in egx30_data.values() if df is not None)
        logger.info(f"EGX30 fetch complete: {success_count}/{len(Config.EGX30_SYMBOLS)} succeeded")
        
        return egx30_data

    def fetch_index(
        self,
        start: Optional[str] = None,
        end: Optional[str] = None,
        force_refresh: bool = False
    ) -> pd.DataFrame:
        """
        Fetch EGX index data (^CASE).
        
        Args:
            start: Start date
            end: End date
            force_refresh: Bypass cache
        
        Returns:
            Index DataFrame
        """
        return self.fetch_data(
            Config.EGX_INDEX_SYMBOL,
            interval="1d",
            start=start,
            end=end,
            force_refresh=force_refresh
        )

    def fetch_multiple(
        self,
        symbols: List[str],
        interval: str = "1d",
        start: Optional[str] = None,
        end: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch data for multiple symbols.
        
        Args:
            symbols: List of symbols
            interval: Time interval
            start: Start date
            end: End date
            force_refresh: Bypass cache
        
        Returns:
            Dict mapping symbol → DataFrame (None if fetch failed)
        """
        result = {}
        
        logger.info(f"Fetching {len(symbols)} symbols")
        
        for i, symbol in enumerate(symbols, 1):
            try:
                df = self.fetch_data(symbol, interval, start, end, force_refresh)
                result[symbol] = df
                logger.info(f"  [{i}/{len(symbols)}] ✓ {symbol}")
            except Exception as e:
                logger.error(f"  [{i}/{len(symbols)}] ✗ {symbol}: {e}")
                result[symbol] = None
        
        success_count = sum(1 for df in result.values() if df is not None)
        logger.info(f"Multi-fetch complete: {success_count}/{len(symbols)} succeeded")
        
        return result

    def clear_cache(self, symbol: Optional[str] = None) -> None:
        """
        Clear cache for a symbol or all.
        
        Args:
            symbol: If provided, clear only this symbol
        """
        if self.cache:
            self.cache.clear(symbol)
        else:
            logger.warning("Cache disabled")

    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        if self.cache:
            return self.cache.get_cache_stats()
        return {"status": "Cache disabled"}

    @property
    def provider_info(self) -> List[str]:
        """Get list of available providers."""
        return [p.name for p in self.providers]

    def get_last_source(self, symbol: str) -> Optional[str]:
        """Get the last successful source/provider used for a symbol."""
        return self.last_source.get(symbol)


def fetch_egx_data(
    symbol: str,
    interval: str = "1d",
    start: Optional[str] = None,
    end: Optional[str] = None,
    force_refresh: bool = False
) -> pd.DataFrame:
    """
    Public convenience API: fetch one symbol with provider fallback + cache.
    """
    dm = DataManager()
    return dm.fetch_data(
        symbol=symbol,
        interval=interval,
        start=start,
        end=end,
        force_refresh=force_refresh
    )


def fetch_multiple_symbols(
    symbols: List[str],
    interval: str = "1d",
    start: Optional[str] = None,
    end: Optional[str] = None,
    force_refresh: bool = False
) -> Dict[str, pd.DataFrame]:
    """
    Public convenience API: fetch multiple symbols with provider fallback + cache.
    """
    dm = DataManager()
    return dm.fetch_multiple(
        symbols=symbols,
        interval=interval,
        start=start,
        end=end,
        force_refresh=force_refresh
    )


def get_egx30_index(
    start: Optional[str] = None,
    end: Optional[str] = None,
    force_refresh: bool = False
) -> pd.DataFrame:
    """
    Public convenience API: fetch EGX benchmark index series.
    """
    dm = DataManager()
    return dm.fetch_index(start=start, end=end, force_refresh=force_refresh)
