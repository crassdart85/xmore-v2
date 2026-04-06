"""
Xmore Data Layer - Complete Guide

========================================================================
                    PRODUCTION-READY DATA INGESTION
              FOR KSA/TADAWUL MARKET DATA (EODHD PRIMARY)
========================================================================

> **KSA Branch Note**: This branch targets Saudi Exchange (Tadawul) with
> EODHD as the primary data source and yfinance as fallback.
> Legacy Tadawul provider code (EGXPY, Alpha Vantage) is retained for
> compatibility but is not used in the active KSA pipeline.

📋 TABLE OF CONTENTS
1. Overview
2. Architecture
3. Quick Start
4. CLI Usage
5. Programmatic API
6. Configuration
7. Caching Strategy
8. Troubleshooting
9. Development Notes

========================================================================
1. OVERVIEW
========================================================================

The Xmore Data Layer is a modular, fault-tolerant system for ingesting
KSA/Tadawul market data with:

✓ Multi-provider fallback chain (EODHD → yfinance → Alpha Vantage)
✓ Intelligent caching (24h TTL, force refresh)
✓ Rate limiting for free APIs
✓ Structured logging
✓ Type hints & production-ready code
✓ CLI interface for ad-hoc queries
✓ Signal integration-ready

Design Goals:
- Power Xmore's signal generation engine
- Benchmark against TASI
- Support backtesting and live trading
- Zero hardcoded secrets
- Graceful degradation under API failures

========================================================================
2. ARCHITECTURE
========================================================================

Folder Structure:
───────────────────────────────────────────────────────────────────────
xmore_data/
├── __init__.py                      # Package exports
├── config.py                        # Configuration & secrets management
├── utils.py                         # Logging, retry logic, validators
├── cache.py                         # Joblib-based caching layer
├── data_manager.py                  # Core orchestration & fallback logic
├── main.py                          # CLI interface (argparse)
│
└── providers/
    ├── __init__.py                  # Base provider class
    ├── egxpy_provider.py            # Legacy: EGXLytics integration (Tadawul only)
    ├── eodhd_provider.py            # Primary: EODHD API (KSA/Tadawul)
    ├── yfinance_provider.py         # Fallback 1: Yahoo Finance
    └── alpha_vantage_provider.py    # Fallback 2: Alpha Vantage

───────────────────────────────────────────────────────────────────────

Data Flow:
┌──────────────────┐
│   User Request   │
│  (symbol, date)  │
└────────┬─────────┘
         │
         ▼
┌──────────────────────────────┐
│   DataManager.fetch_data()   │
└────────┬─────────────────────┘
         │
         ▼
┌──────────────────────────────┐
│  Check Cache (24h TTL)       │◄─── ✓ Return (HIT)
└────────┬─────────────────────┘
         │ ✗ MISS
         ▼
┌──────────────────────────────┐
│  Try Provider #1: EODHD      │───► ✓ Success? Cache & Return
└────────┬─────────────────────┘
         │ ✗ Fail
         ▼
┌──────────────────────────────┐
│  Try Provider #2: yfinance   │───► ✓ Success? Cache & Return
└────────┬─────────────────────┘
         │ ✗ Fail
         ▼
┌──────────────────────────────┐
│  Try Provider #3: Alpha Van. │───► ✓ Success? Cache & Return
└────────┬─────────────────────┘
         │ ✗ Fail
         ▼
    Raise Error

Provider Features:
┌─────────────────────────────────────────────────────────────────────┐
│ PROVIDER      │ PRIMARY | INTRADAY | RATE LIMIT | SYMBOLS          │
┝─────────────────────────────────────────────────────────────────────┤
│ EODHD         │   ✓    │    ✓    │   Fair    │ KSA + Global     │
│ yfinance      │   ✗    │    ✓    │   Fair    │ KSA (.SR)        │
│ Alpha Vantage │   ✗    │    ✗    │ 5/min    │ Global stocks    │
│ EGXPY         │   ✗    │    ✓    │   None    │ Tadawul only (legacy)│
└─────────────────────────────────────────────────────────────────────┘

========================================================================
3. QUICK START
========================================================================

A. INSTALLATION
───────────────────────────────────────────────────────────────────────

1. Install dependencies:

   pip install -r requirements_data.txt

   This installs:
   - pandas, numpy
   - yfinance (required)
   - joblib (caching)
   - python-dotenv (secrets)
   - Optional: egxpy (legacy Tadawul only), alpha-vantage
   - EODHD_API_KEY recommended for KSA primary provider


2. Create .env file in project root:

   # .env
   EODHD_API_KEY=your_key_here         # Primary KSA data source
   ALPHA_VANTAGE_API_KEY=your_key_here  # Optional fallback, get from https://www.alphavantage.co
   CACHE_EXPIRATION_HOURS=24
   LOG_LEVEL=INFO


3. Verify installation:

   python xmore_data/main.py --cache-stats


B. FIRST DATA FETCH
───────────────────────────────────────────────────────────────────────

Fetch 2222.SR (Saudi Aramco) last 90 days:

   python xmore_data/main.py --symbol 2222.SR --summary

Expected output:
   ╔════════════════════════════════════════════════════════╗
   ║ 2222.SR [from EODHD]
   ╠════════════════════════════════════════════════════════╣
   ║ Latest Close     : SAR XX.XX
   ║ Change           : +X.XX (+X.XX%)
   ║ High / Low       : XXX.XX / XXX.XX
   ║ Avg Volume       : X,XXX,XXX
   ║ Data Points      : XX rows
   ║ Date Range       : 2025-XX-XX to 2026-XX-XX
   ╚══════════════════════════════════════════════════════════╝

C. IMPORT IN YOUR CODE
───────────────────────────────────────────────────────────────────────

from xmore_data import DataManager

dm = DataManager()
df = dm.fetch_data("2222.SR", interval="1d", start="2024-01-01")

print(df.head())
print(df.columns)  # Date, Open, High, Low, Close, Adj Close, Volume

========================================================================
4. CLI USAGE
========================================================================

A. BASIC COMMANDS
───────────────────────────────────────────────────────────────────────

Fetch single symbol:
   python xmore_data/main.py --symbol 2222.SR

Fetch multiple symbols:
   python xmore_data/main.py --symbols 2222.SR 1180.SR 2010.SR

Fetch entire KSA universe:
   python xmore_data/main.py --egx30

Fetch TASI index (benchmark):
   python xmore_data/main.py --benchmark

B. DATE RANGES
───────────────────────────────────────────────────────────────────────

Explicit dates:
   python xmore_data/main.py --symbol 2222.SR --start 2024-01-01 --end 2024-12-31

Relative dates:
   python xmore_data/main.py --symbol 2222.SR --start 90d      # Last 90 days
   python xmore_data/main.py --symbol 2222.SR --start 1y       # Last 1 year
   python xmore_data/main.py --symbol 2222.SR --start 6mo      # Last 6 months
   python xmore_data/main.py --symbol 2222.SR --start 4w       # Last 4 weeks

C. INTERVALS
───────────────────────────────────────────────────────────────────────

   --interval 1m    # 1-minute (intraday, limited provider support)
   --interval 5m    # 5-minute
   --interval 15m   # 15-minute
   --interval 1h    # Hourly
   --interval 1d    # Daily (default)
   --interval 1w    # Weekly
   --interval 1mo   # Monthly

D. EXPORT OPTIONS
───────────────────────────────────────────────────────────────────────

Export to CSV:
   python xmore_data/main.py --symbol 2222.SR --export csv

Export to Excel (multiple symbols in one file):
   python xmore_data/main.py --symbols 2222.SR 1180.SR 2010.SR --export excel

Export to JSON:
   python xmore_data/main.py --benchmark --export json

Custom output directory:
   python xmore_data/main.py --symbol 2222.SR --export csv --output-dir /path/to/exports

E. CACHE MANAGEMENT
───────────────────────────────────────────────────────────────────────

Show cache stats:
   python xmore_data/main.py --cache-stats

Force refresh (bypass cache):
   python xmore_data/main.py --symbol 2222.SR --refresh

Clear all cache:
   python xmore_data/main.py --clear-cache

F. SUMMARY & DISPLAY
───────────────────────────────────────────────────────────────────────

Show data summary (default if no export):
   python xmore_data/main.py --symbol 2222.SR --summary

Fetch + export without summary:
   python xmore_data/main.py --symbol 2222.SR --export csv

========================================================================
5. PROGRAMMATIC API
========================================================================

A. BASIC USAGE
───────────────────────────────────────────────────────────────────────

from xmore_data import DataManager

# Initialize (loads config, validates providers)
dm = DataManager(
    use_cache=True,           # Enable caching
    cache_ttl_hours=24,       # Cache time-to-live
    verbose=True              # Print initialization logs
)

# Fetch single symbol
df = dm.fetch_data(
    symbol="2222.SR",
    interval="1d",
    start="2024-01-01",       # Optional: YYYY-MM-DD or relative (90d, 1y)
    end="2024-12-31",         # Optional: defaults to today
    force_refresh=False       # Optional: bypass cache
)

print(df.columns)
# Output: Index(['Date', 'Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume'], ...)

print(df.head())
# Output:
#         Date       Open       High        Low      Close  Adj Close    Volume
# 0 2024-01-01   125.48   126.15   124.20   125.65      125.65  1234567
# 1 2024-01-02   125.80   127.00   125.00   126.50      126.50  1567890
# ...

B. FETCH MULTIPLE SYMBOLS
───────────────────────────────────────────────────────────────────────

# Fetch multiple symbols at once
data = dm.fetch_multiple(
    symbols=["2222.SR", "1180.SR", "2010.SR"],
    interval="1d",
    start="2024-01-01"
)

# Returns: Dict[symbol] -> DataFrame
for symbol, df in data.items():
    if df is not None:
        print(f"{symbol}: {len(df)} rows, latest close = {df['Close'].iloc[-1]}")

C. FETCH TASI INDEX
───────────────────────────────────────────────────────────────────────

# Fetch TASI index (Tadawul benchmark)
index_df = dm.fetch_index(start="2024-01-01")

# Calculate TASI index returns
index_df['Daily_Return'] = index_df['Close'].pct_change()

D. FETCH ALL KSA UNIVERSE
───────────────────────────────────────────────────────────────────────

# Fetch all KSA universe stocks
ksa_data = dm.fetch_egx30(interval="1d", start="2024-01-01")

# Returns: Dict[symbol] -> DataFrame (None if failed)
success_count = sum(1 for df in ksa_data.values() if df is not None)
print(f"Successfully fetched {success_count} symbols")

for symbol, df in ksa_data.items():
    if df is not None and not df.empty:
        latest_price = df['Close'].iloc[-1]
        print(f"{symbol}: SAR {latest_price:.2f}")

E. CACHE OPERATIONS
───────────────────────────────────────────────────────────────────────

# Clear cache for specific symbol
dm.clear_cache(symbol="2222.SR")

# Clear all cache
dm.clear_cache()

# Get cache statistics
stats = dm.get_cache_stats()
print(stats)
# Output: {
#     'cache_dir': '/path/to/.cache/market_data',
#     'file_count': 12,
#     'size_mb': 4.56,
#     'ttl_hours': 24
# }

F. PROVIDER INFORMATION
───────────────────────────────────────────────────────────────────────

# Check which providers are available
print(dm.provider_info)
# Output: ['EODHD', 'yfinance', 'Alpha Vantage']

========================================================================
6. CONFIGURATION
========================================================================

All configuration via .env or environment variables:

ALPHA_VANTAGE_API_KEY
    API key for Alpha Vantage (optional, fallback disabled if not set)
    Get free key: https://www.alphavantage.co/api/

CACHE_EXPIRATION_HOURS
    Cache TTL in hours (default: 24)
    Set to 0 to disable caching

CACHE_DIR
    Directory for cache files (default: .cache/market_data)
    Can be absolute path or relative

LOG_LEVEL
    Logging verbosity: DEBUG, INFO (default), WARNING, ERROR

LOG_FILE
    Log file path (default: logs/xmore_data.log)

EGXPY_TIMEOUT
    EGXPY request timeout in seconds (default: 30)

EGXPY_RETRIES
    Number of EGXPY retry attempts (default: 3)

RETRY_ATTEMPTS
    For all providers, max retries (default: 3)

RETRY_BASE_DELAY
    Initial retry delay in seconds (default: 1.0)
    Uses exponential backoff: 1s, 2s, 4s, 8s...

RETRY_MAX_DELAY
    Maximum delay between retries (default: 32.0)

Example .env file:
─────────────────────────────────────────────────────────────────────
# .env
ALPHA_VANTAGE_API_KEY=A1B2C3D4E5F6G7H8
CACHE_EXPIRATION_HOURS=24
CACHE_DIR=.cache/market_data
LOG_LEVEL=INFO
LOG_FILE=logs/xmore_data.log
EGXPY_TIMEOUT=30
EGXPY_RETRIES=3
RETRY_ATTEMPTS=3
RETRY_BASE_DELAY=1.0
RETRY_MAX_DELAY=32.0
─────────────────────────────────────────────────────────────────────

========================================================================
7. CACHING STRATEGY
========================================================================

A. HOW CACHING WORKS
───────────────────────────────────────────────────────────────────────

Cache Key:
    Symbol + Interval + Date Range Hash
    Example: 2222_SR_1d_a3f5c1d2.joblib

Cache Location:
    .cache/market_data/

Serialization:
    joblib (compressed, safe for pandas DataFrames)

TTL (Time-To-Live):
    Default 24 hours (configurable)
    Stale files automatically cleaned on cache miss

B. CACHE BEHAVIOR
───────────────────────────────────────────────────────────────────────

Cache Hit (age < TTL):
    ✓ Return cached data immediately
    ✓ Avoid API calls
    ✓ Performance: instant

Cache Miss (file doesn't exist):
    ✗ Fetch from provider
    ✓ Store in cache
    ✓ Return fresh data

Cache Expired (age >= TTL):
    ✗ Delete stale file
    ✗ Fetch from provider
    ✓ Store new data

Force Refresh:
    ✗ Ignore cache
    ✗ Always fetch from provider
    ✓ Update cache with new data

C. CACHE MANAGEMENT
───────────────────────────────────────────────────────────────────────

View cache size:
    dm.get_cache_stats()

Clear symbol cache:
    dm.clear_cache("2222.SR")

Clear all cache:
    dm.clear_cache()

Disable caching:
    dm = DataManager(use_cache=False)

Fetch with refresh:
    dm.fetch_data("2222.SR", force_refresh=True)

========================================================================
8. TROUBLESHOOTING
========================================================================

Problem: "No data providers available!"
───────────────────────────────────────────────────────────────────────
Solution:
    Install at least one provider:
    pip install yfinance          # Minimum required
    pip install egxpy             # Recommended primary
    pip install alpha-vantage     # Tertiary fallback

Problem: "ALPHA_VANTAGE_API_KEY not set"
───────────────────────────────────────────────────────────────────────
Solution:
    This is a WARNING, not an ERROR. Alpha Vantage is optional.
    To enable:
    1. Get free API key: https://www.alphavantage.co/api/
    2. Add to .env: ALPHA_VANTAGE_API_KEY=your_key
    3. Restart application

Problem: "Symbol not found / no data in range"
───────────────────────────────────────────────────────────────────────
Causes:
    - Valid symbol but not in this provider's database
    - Date range outside available data
    - All providers failed
Solution:
    Check symbol spelling: 2222.SR
    Try wider date range: --start 1y
    Check provider coverage: EODHD has full KSA coverage (requires EODHD_API_KEY)
    Verify .env ALPHA_VANTAGE_API_KEY if tertiary fallback fails

Problem: "Rate limit exceeded (Alpha Vantage)"
───────────────────────────────────────────────────────────────────────
Cause:
    Free tier: 5 API calls/minute
Solution:
    Module automatically waits and retries
    Use cache to avoid repeated calls
    Upgrade to paid tier if needed

Problem: "EGXPY failed / not found"
───────────────────────────────────────────────────────────────────────
Solution:
    Try installing: pip install egxpy
    Verify import: python -c "import egxpy; print(egxpy.__version__)"
    Check workspace has egxpy source
    Fallback to yfinance (already works)

Problem: "Cache not working / always refetching"
───────────────────────────────────────────────────────────────────────
Solution:
    Check cache enabled: dm.use_cache == True
    View cache: python main.py --cache-stats
    Clear cache: python main.py --clear-cache
    Set correct TTL in .env: CACHE_EXPIRATION_HOURS=24

Problem: Slow performance
───────────────────────────────────────────────────────────────────────
Solution:
    Enable caching (default: on)
    Use dm.fetch_multiple() instead of loop
    Use relative date ranges (90d faster than full 10-year history)
    Increase CACHE_EXPIRATION_HOURS if data doesn't change often

========================================================================
9. DEVELOPMENT NOTES
========================================================================

A. ADDING NEW PROVIDERS
───────────────────────────────────────────────────────────────────────

1. Create new_provider.py in xmore_data/providers/

2. Inherit from MarketDataProvider (in __init__.py):

   from . import MarketDataProvider
   
   class NewProvider(MarketDataProvider):
       def __init__(self):
           super().__init__("NewProvider")
           self.client = self._init_client()
       
       @exponential_backoff()
       def fetch(self, symbol, interval="1d", start=None, end=None):
           # Your fetch logic
           df = ...  # fetch from API
           return validate_dataframe(df, "NewProvider")

3. Register in data_manager.py _initialize_providers():

   try:
       new = NewProvider()
       providers.append(new)
   except Exception as e:
       logger.warning(f"NewProvider not available: {e}")

4. Add to requirements_data.txt

B. TESTING
───────────────────────────────────────────────────────────────────────

Test single provider:
   from xmore_data.providers.egxpy_provider import EGXPYProvider
   provider = EGXPYProvider()
   df = provider.fetch("2222.SR", start="2024-01-01")
   print(df)

Test fallback chain (intentionally break EGXPY):
   dm = DataManager()
   dm.providers = dm.providers[1:]  # Remove EGXPY
   df = dm.fetch_data("2222.SR")  # Should use yfinance

C. LOGGING CONFIGURATION
───────────────────────────────────────────────────────────────────────

Logs written to:
   - Console (STDOUT)
   - File: logs/xmore_data.log

Log levels:
   DEBUG: Detailed debug info
   INFO: Success, milestones
   WARNING: Fallbacks, degradation
   ERROR: Failures, exceptions

Control verbosity:
   In .env: LOG_LEVEL=DEBUG
   In code: Config.LOG_LEVEL = "DEBUG"

D. INTEGRATION WITH XMORE SIGNAL ENGINE
───────────────────────────────────────────────────────────────────────

Example: Using data layer in signal generation:

   from xmore_data import DataManager
   from signal_engine import SignalGenerator
   
   dm = DataManager()
   sg = SignalGenerator()
   
   # Fetch data
   df = dm.fetch_data("2222.SR", start="2024-01-01")
   
   # Generate signals
   signals = sg.generate_signals(df)
   
   # Log predictions
   for signal in signals:
       print(f"{signal.date} {signal.symbol}: {signal.forecast}")

========================================================================
END OF GUIDE
========================================================================

Questions? Check:
1. README.md
2. xmore_data/__init__.py (module exports)
3. xmore_data/config.py (configuration)
4. xmore_data/data_manager.py (core logic)
5. Log files in logs/xmore_data.log

Version: 1.0.0
Last Updated: 2026-02-15
"""
