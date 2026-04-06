"""
Xmore Data Layer - Quick Reference / Cheat Sheet

Use this as a quick lookup for common tasks.
"""

# ═════════════════════════════════════════════════════════════════════════════
# QUICK START (Copy-Paste)
# ═════════════════════════════════════════════════════════════════════════════

# 1. Install
pip install -r requirements_data.txt

# 2. Setup .env (optional, but recommended for Alpha Vantage)
cp .env.example .env
# Edit .env and add your ALPHA_VANTAGE_API_KEY if desired

# 3. Test installation
python xmore_data/main.py --cache-stats

# ═════════════════════════════════════════════════════════════════════════════
# CLI CHEAT SHEET
# ═════════════════════════════════════════════════════════════════════════════

# FETCH SINGLE SYMBOL
python xmore_data/main.py --symbol 2222.SR
python xmore_data/main.py --symbol 2222.SR --interval 1d --start 2024-01-01

# FETCH MULTIPLE SYMBOLS
python xmore_data/main.py --symbols 2222.SR 1180.SR 2010.SR
python xmore_data/main.py --symbols 2222.SR 1180.SR 2010.SR --start 90d

# FETCH ALL TASI
python xmore_data/main.py --TASI

# FETCH Tadawul INDEX (BENCHMARK)
python xmore_data/main.py --benchmark

# EXPORT DATA
python xmore_data/main.py --symbol 2222.SR --export csv           # Save CSV
python xmore_data/main.py --symbols 2222.SR 1180.SR --export excel   # Multi-sheet Excel
python xmore_data/main.py --TASI --export json                # JSON files

# FORCE REFRESH (SKIP CACHE)
python xmore_data/main.py --symbol 2222.SR --refresh

# CACHE MANAGEMENT
python xmore_data/main.py --cache-stats                        # View cache info
python xmore_data/main.py --clear-cache                        # Delete all cache

# ═════════════════════════════════════════════════════════════════════════════
# PYTHON API CHEAT SHEET
# ═════════════════════════════════════════════════════════════════════════════

from xmore_data import DataManager

# Initialize
dm = DataManager()

# FETCH SINGLE
df = dm.fetch_data("2222.SR")
df = dm.fetch_data("2222.SR", interval="1d", start="2024-01-01", end="2024-12-31")
df = dm.fetch_data("2222.SR", start="90d")  # Last 90 days
df = dm.fetch_data("2222.SR", start="1y")   # Last 1 year

# FETCH MULTIPLE
data = dm.fetch_multiple(["2222.SR", "1180.SR", "2010.SR"])
for symbol, df in data.items():
    print(f"{symbol}: {len(df)} rows")

# FETCH TASI
TASI = dm.fetch_TASI()
for symbol, df in TASI.items():
    if df is not None:
        print(f"{symbol}: SAR {df['Close'].iloc[-1]:.2f}")

# FETCH INDEX
index = dm.fetch_index()

# WORK WITH DATA
df['Daily_Return'] = df['Close'].pct_change()
df['SMA_20'] = df['Close'].rolling(20).mean()
df['Volatility'] = df['Close'].pct_change().rolling(20).std()

# CACHE OPS
dm.clear_cache()                    # Clear all
dm.clear_cache("2222.SR")              # Clear specific symbol
stats = dm.get_cache_stats()
print(dm.provider_info)             # Available providers

# ═════════════════════════════════════════════════════════════════════════════
# COMMON PATTERNS
# ═════════════════════════════════════════════════════════════════════════════

# 1. PORTFOLIO ANALYSIS
symbols = ["2222.SR", "1180.SR", "2010.SR"]
data = dm.fetch_multiple(symbols, start="1y")

for sym, df in data.items():
    if df is not None:
        ret = (df['Close'].iloc[-1] / df['Close'].iloc[0] - 1) * 100
        print(f"{sym}: {ret:+.2f}%")

# 2. SIGNAL GENERATION
df = dm.fetch_data("2222.SR", start="90d")
df['SMA_20'] = df['Close'].rolling(20).mean()
df['SMA_50'] = df['Close'].rolling(50).mean()
df['Signal'] = (df['SMA_20'] > df['SMA_50']).astype(int)  # 1=Bullish, 0=Bearish

# 3. VOLATILITY CALCULATION
df = dm.fetch_data("2222.SR", start="1y")
daily_returns = df['Close'].pct_change()
annual_volatility = daily_returns.std() * (252 ** 0.5)
print(f"Annual Volatility: {annual_volatility:.2%}")

# 4. BENCHMARK COMPARISON
stock = dm.fetch_data("2222.SR", start="90d")
index = dm.fetch_index(start="90d")

stock_ret = (stock['Close'].iloc[-1] / stock['Close'].iloc[0] - 1) * 100
index_ret = (index['Close'].iloc[-1] / index['Close'].iloc[0] - 1) * 100
alpha = stock_ret - index_ret

print(f"Stock Return: {stock_ret:+.2f}%")
print(f"Index Return: {index_ret:+.2f}%")
print(f"Alpha: {alpha:+.2f}%")

# 5. BACKTESTING PREPARATION
backtest_symbols = ["2222.SR", "1180.SR", "2010.SR", "ETEL", "ECAP"]
data = dm.fetch_multiple(backtest_symbols, start="2024-01-01", end="2024-12-31")

# Save to CSV for backtester
for symbol, df in data.items():
    if df is not None:
        df.to_csv(f"backtest_data/{symbol}.csv", index=False)

# ═════════════════════════════════════════════════════════════════════════════
# TROUBLESHOOTING
# ═════════════════════════════════════════════════════════════════════════════

# ERROR: No data providers available
# FIX: pip install yfinance

# ERROR: Symbol not found
# FIX: Check spelling (2222.SR not COMISHR)
#      Use --refresh to bypass cache
#      Try different date range

# ERROR: Rate limit exceeded (Alpha Vantage)
# INFO: Module auto-waits, this is OK
# FIX: Check cache stats, use cache to avoid repeated calls

# ERROR: EODHD not available
# INFO: Falls back to yfinance automatically
# FIX: pip install EODHD (optional but recommended)

# SLOW PERFORMANCE
# FIX: Enable cache (default: on)
#      Use relative date: --start 90d instead of full history
#      Increase CACHE_EXPIRATION_HOURS in .env

# ═════════════════════════════════════════════════════════════════════════════
# ENVIRONMENT VARIABLES (.env)
# ═════════════════════════════════════════════════════════════════════════════

# For full reference, see .env.example
ALPHA_VANTAGE_API_KEY=your_key_here
CACHE_EXPIRATION_HOURS=24
LOG_LEVEL=INFO
EODHD_TIMEOUT=30
EODHD_RETRIES=3

# ═════════════════════════════════════════════════════════════════════════════
# FILE STRUCTURE
# ═════════════════════════════════════════════════════════════════════════════

xmore_data/
├── __init__.py              # Package init
├── config.py                # Configuration
├── utils.py                 # Logging, retry, validation
├── cache.py                 # Caching system
├── data_manager.py          # Core orchestration
├── main.py                  # CLI interface
├── examples.py              # Example usage
├── test_data_manager.py     # Tests
├── setup.py                 # Package setup
└── providers/
    ├── __init__.py          # Base provider class
    ├── EODHD_provider.py     # EODHD provider
    ├── yfinance_provider.py  # yfinance provider
    └── alpha_vantage_provider.py  # Alpha Vantage provider

# ═════════════════════════════════════════════════════════════════════════════
# STANDARD OUTPUT FORMAT
# ═════════════════════════════════════════════════════════════════════════════

DataFrame columns (always):
    Date         - datetime
    Open         - float (SAR)
    High         - float (SAR)
    Low          - float (SAR)
    Close        - float (SAR)
    Adj Close    - float (SAR)
    Volume       - int

Example:
         Date       Open       High        Low      Close  Adj Close    Volume
0 2026-01-01   125.48   126.15   124.20   125.65      125.65  1234567
1 2026-01-02   125.80   127.00   125.00   126.50      126.50  1567890

# ═════════════════════════════════════════════════════════════════════════════
# USEFUL ONE-LINERS
# ═════════════════════════════════════════════════════════════════════════════

# Check module install
python -c "from xmore_data import DataManager; print('✓ OK')"

# Show available providers
python -c "from xmore_data import DataManager; dm = DataManager(); print(dm.provider_info)"

# Get latest price
python -c "from xmore_data import DataManager; dm = DataManager(); df = dm.fetch_data('2222.SR'); print(df['Close'].iloc[-1])"

# Export TASI to Excel
python xmore_data/main.py --TASI --export excel

# Test all features
python xmore_data/examples.py

# ═════════════════════════════════════════════════════════════════════════════

Last Updated: 2026-02-15
Version: 1.0.0
"""
