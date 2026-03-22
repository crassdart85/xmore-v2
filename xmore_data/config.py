"""
Configuration management for xmore_data module.

Loads settings from environment variables (.env file) and provides
centralized configuration for API endpoints, rate limits, cache settings.
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load .env file from project root
ENV_PATH = Path(__file__).parent.parent / ".env"
load_dotenv(ENV_PATH)


class Config:
    """Centralized configuration for data layer."""

    # API Keys (loaded from .env, graceful fallback)
    ALPHA_VANTAGE_API_KEY: Optional[str] = os.getenv("ALPHA_VANTAGE_API_KEY")
    EODHD_API_KEY: Optional[str] = (
        os.getenv("EODHD_API_KEY")
        or os.getenv("EODHD_API_TOKEN")
        or os.getenv("EOD_API_KEY")
    )
    
    # EGXPY Configuration
    EGXPY_TIMEOUT: int = int(os.getenv("EGXPY_TIMEOUT", "30"))
    EGXPY_RETRIES: int = int(os.getenv("EGXPY_RETRIES", "3"))
    
    # Cache Configuration
    CACHE_DIR: Path = Path(os.getenv(
        "CACHE_DIR", 
        str(Path(__file__).parent.parent / ".cache" / "market_data")
    ))
    CACHE_EXPIRATION_HOURS: int = int(os.getenv("CACHE_EXPIRATION_HOURS", "24"))
    
    # Rate Limiting
    ALPHA_VANTAGE_RATE_LIMIT: int = 5  # Free tier: 5 calls/min
    ALPHA_VANTAGE_RATE_WINDOW_SEC: int = 60
    EODHD_RATE_LIMIT: int = 20
    EODHD_RATE_WINDOW_SEC: int = 60
    YFINANCE_RATE_LIMIT: int = 100  # Conservative estimate
    YFINANCE_RATE_WINDOW_SEC: int = 60
    
    # Retry Configuration (Exponential Backoff)
    RETRY_ATTEMPTS: int = int(os.getenv("RETRY_ATTEMPTS", "3"))
    RETRY_BASE_DELAY: float = float(os.getenv("RETRY_BASE_DELAY", "1.0"))
    RETRY_MAX_DELAY: float = float(os.getenv("RETRY_MAX_DELAY", "32.0"))
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: Path = Path(os.getenv(
        "LOG_FILE",
        str(Path(__file__).parent.parent / "logs" / "xmore_data.log")
    ))
    
    # Markets
    EGX_INDEX_SYMBOL: str = "^CASE"  # Egyptian Exchange Index
    KSA_INDEX_SYMBOL: str = os.getenv("KSA_INDEX_SYMBOL", "TASI")
    KSA_BENCHMARK_ALIASES: list[str] = [
        "TASI",
        "^TASI",
        "TASI.SR",
        "TASI_INDEX",
        "SAUDI_TASI",
    ]
    EODHD_BENCHMARK_SYMBOL: str = os.getenv("EODHD_BENCHMARK_SYMBOL", "TASI.INDX")
    EODHD_KSA_EXCHANGE: str = os.getenv("EODHD_KSA_EXCHANGE", "SR")
    EODHD_BASE_URL: str = os.getenv("EODHD_BASE_URL", "https://eodhd.com/api")
    SAUDI_EXCHANGE_HISTORICAL_REPORTS_URL: str = os.getenv(
        "SAUDI_EXCHANGE_HISTORICAL_REPORTS_URL",
        "https://www.saudiexchange.sa/wps/portal/saudiexchange/newsandreports/reports-publications/historical-reports?locale=en",
    )
    EGX30_SYMBOLS: list[str] = [
        "COMI",    # Commercial International Bank
        "SWDY",    # Swvl Holding Company
        "HRHO",    # Hercules Steel
        "ETEL",    # Etelecom
        "ECAP",    # Egyptian Capital Bank
        "NAPLF",   # Napco Group
        "ORWA",    # Orwa Ceramics
        "ELKA",    # Elkabel
        "TMGH",    # Telecom Egypt
        "ADIB",    # Abu Dhabi Islamic Bank
        "NBAFI",   # NBK Abu Dhabi
        "AMLK",    # Almalakawy
        "CLMD",    # Climate Lands
        "DMSTY",   # Domatia
        "ESTHE",   # Egypt Structural Code
        "GOOD",    # Goodman
        "HACC",    # Hana Capital
        "IFLU",    # Influcity
        "OCCI",    # Occidental Petroleum
        "PBK",     # Paribas
        "RPHC",    # Rephco Pharma
        "SIFI",    # Sifi Capital
        "SWVL",    # Swvl
        "TALC",    # Taleco
        "VANL",    # Vanilo
        "WBHC",    # WBHC
        "XSOV",    # Sovereign Fund
        "YEXT",    # Yext
        "ZEND",    # Zendig
    ]
    
    # Data Standards
    STANDARD_COLUMNS: list[str] = [
        "Date",
        "Open",
        "High",
        "Low",
        "Close",
        "Adj Close",
        "Volume"
    ]
    
    # Intervals
    SUPPORTED_INTERVALS: list[str] = ["1m", "5m", "15m", "1h", "1d", "1w", "1mo"]
    
    @classmethod
    def validate(cls) -> None:
        """Validate critical configuration."""
        if not cls.ALPHA_VANTAGE_API_KEY:
            print("⚠️  ALPHA_VANTAGE_API_KEY not set in .env (Alpha Vantage fallback disabled)")
        if not cls.EODHD_API_KEY:
            print("⚠️  EODHD_API_KEY not set in .env (EODHD provider disabled)")
        
        cls.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cls.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        print(f"✓ Configuration validated. Cache dir: {cls.CACHE_DIR}")


# Ensure runtime directories exist on import so components/tests can rely on them
Config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
Config.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

if __name__ == "__main__":
    Config.validate()
    print(f"Cache TTL: {Config.CACHE_EXPIRATION_HOURS}h")
    print(f"EGX30 symbols configured: {len(Config.EGX30_SYMBOLS)}")

