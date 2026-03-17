"""
Configuration file for Xmore2 Trading System.

Store all settings, API keys, and constants here.
Sections:
- Stock Selection: Which stocks to track
- API Credentials: Keys for external services
- Data Collection: Settings for fetching data
- Database: Path and connection settings
- Notifications: Email alerts
- Prediction: Agent parameters
- Evaluation: success metrics
"""

import os
from datetime import time

# ============================================
# STOCK SELECTION
# ============================================

# Import EGX symbols from dedicated module
from egx_symbols import get_egx30_symbols

# EGX Stocks - Use EGX 30 index constituents by default
# This provides the most liquid and actively traded Egyptian stocks
# Note: EGX data may have liquidity gaps or delays compared to US markets.
EGX_STOCKS = get_egx30_symbols()

# US Stocks (Optional / Legacy)
US_STOCKS = [
    # "AAPL",
    # "MSFT",
]

# Combined list - defaulting to EGX for Xmore2
ALL_STOCKS = EGX_STOCKS + US_STOCKS

# ============================================
# EGYPTIAN MARKET SETTINGS
# ============================================

# EGX Market Configuration
EGX_CONFIG = {
    "market_name": "Egyptian Exchange",
    "currency": "EGP",
    "timezone": "Africa/Cairo",
    "trading_days": ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"],
    "trading_hours": {
        "open": "09:00",   # EGX opens at 09:00 Cairo (07:00 UTC)
        "close": "14:00",  # EGX closes at 14:00 Cairo (12:00 UTC)
    },
    # EGX has higher volatility than US markets
    "volatility_adjustment": 1.2,
    # Use RSS feeds for better Egyptian news coverage
    "use_rss_news": True,
    # Optional best-effort EGX website scraper adapter (disabled by default)
    # Enable only if EGX pages are reachable from your runtime environment.
    "use_egx_web_scraper": False,
    "egx_web_news_url": "https://www.egx.com.eg/en/NewsList.aspx?ID=10",
}

# ============================================
# API CREDENTIALS
# ============================================

# News API (Get free key from: https://newsapi.org/)
NEWS_API_KEY = os.getenv('NEWS_API_KEY', '')

# Add other API keys as needed
# ALPHA_VANTAGE_KEY = os.getenv('ALPHA_VANTAGE_KEY', '')

# ============================================
# DATA COLLECTION SETTINGS
# ============================================

# How many days of historical data to fetch initially
# 90 days is a balance between having enough history for indicators (like 50-day MA) and speed.
INITIAL_LOOKBACK_DAYS = 90

# How many days to fetch on daily updates
DAILY_LOOKBACK_DAYS = 5  # Fetch last 5 days to catch any gaps from weekends/holidays

# Retry settings (your B→D pattern)
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5  # Wait between retries

# Data collection time (after market close)
# EGX closes at 14:00 Cairo (12:00 UTC). Hourly intraday updates run 09:00-14:00 Cairo.
COLLECTION_TIME = time(14, 30)  # 2:30 PM Cairo (30 min post-close fallback)

# ============================================
# DATABASE SETTINGS
# ============================================

DATABASE_PATH = 'stocks.db'

# ============================================
# NOTIFICATION SETTINGS
# ============================================

# Email settings - loaded from environment variables
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.mail.yahoo.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
EMAIL_FROM = os.getenv('EMAIL_FROM', '')
EMAIL_TO = os.getenv('EMAIL_TO', '')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD', '')

# Alert thresholds
ALERT_ON_MISSING_DATA = True
ALERT_ON_COLLECTION_FAILURE = True
ALERT_ON_PREDICTION_ERROR = True

# ============================================
# PREDICTION SETTINGS
# ============================================

# Technical indicator parameters
RSI_PERIOD = 14     # Standard industry default for RSI
RSI_OVERSOLD = 30   # Below this = Buy signal (undervalued)
RSI_OVERBOUGHT = 70 # Above this = Sell signal (overvalued)

MA_SHORT_PERIOD = 10 # 2 weeks (approx) - fast moving trend
MA_LONG_PERIOD = 30  # 1.5 months (approx) - slow moving trend

# Prediction timeframe
PREDICTION_HORIZON_DAYS = 5  # Predict next 5 trading days (shortened for EGX volatility)

# Confidence thresholds
# Confidence thresholds
MIN_CONFIDENCE_TO_PREDICT = 0.3  # Don't predict if confidence < 30% (agents return 0-1)

# ============================================
# EVALUATION SETTINGS
# ============================================

# What counts as "correct" prediction
# If we predict UP, and price goes up by at least this %, it's correct
MIN_MOVE_THRESHOLD = 0.5  # 0.5% minimum move to count

# ============================================
# RISK AGENT CONFIGURATION (Layer 3)
# ============================================
# These thresholds control how aggressively the Risk Agent gates signals.
# Adjust for market conditions — tighter for volatile periods, looser for calm.

RISK_CONFIG = {
    # Stock-level risk
    "min_avg_volume_20d": 50000,       # Minimum 20-day avg volume for liquidity
    "max_bid_ask_spread_pct": 3.0,     # Max bid-ask spread as % of price
    "max_volatility_20d": 0.06,        # Max 20-day daily volatility (std of returns)
    "min_price": 1.0,                  # Minimum stock price (EGP)

    # Portfolio-level risk
    "max_sector_concentration": 0.40,  # Max 40% of signals in one sector
    "max_correlated_signals": 3,       # Max same-direction signals in correlated group

    # Signal quality risk
    "min_bull_bear_gap": 10,           # Min gap between bull and bear scores
    "min_agent_agreement": 0.5,        # At least 50% of agents must agree
    "max_bear_score": 75,              # If bear score exceeds this, block

    # Drawdown risk
    "max_5d_drawdown_pct": -0.15,      # Block if stock dropped >15% in 5 days
    "max_20d_drawdown_pct": -0.25,     # Block if stock dropped >25% in 20 days
}

# Consensus engine agent weights (sum should be ~1.0)
# Gemini_LLM_Agent included when GOOGLE_API_KEY is set; consensus engine
# normalises weights at runtime so it's safe to always list it here.
AGENT_WEIGHTS = {
    "ML_RandomForest":     0.25,
    "MA_Crossover_Agent":  0.20,
    "RSI_Agent":          0.17,
    "Volume_Spike_Agent": 0.13,
    "Gemini_LLM_Agent":   0.15,
    "DCF_Valuation_Agent": 0.10,
}

# ============================================
# LOGGING
# ============================================

LOG_LEVEL = 'INFO'  # DEBUG, INFO, WARNING, ERROR
LOG_FILE = 'logs/trading_system.log'

# ============================================
# FEATURE FLAGS (turn features on/off easily)
# ============================================

FEATURES = {
    'collect_news': True,
    'sentiment_analysis': True,
    'volume_analysis': True,
    'send_email_reports': True,
}

# ============================================
# VALIDATION
# ============================================

def validate_config():
    """
    Check that critical settings are configured correctly.
    
    Returns:
        List[str]: A list of configuration issues/warnings. Empty if config is valid.
        
    Example:
        >>> issues = validate_config()
        >>> if issues: print(f"Found {len(issues)} problems")
    """
    issues = []
    
    if NEWS_API_KEY == 'YOUR_API_KEY_HERE':
        issues.append("⚠️  NEWS_API_KEY not set")
    
    if not ALL_STOCKS:
        issues.append("❌ No stocks configured to track")
    
    if EMAIL_PASSWORD == '' and FEATURES['send_email_reports']:
        issues.append("⚠️  EMAIL_PASSWORD not set (reports won't send)")
    
    return issues

if __name__ == "__main__":
    print("🔍 Validating configuration...")
    print(f"📊 Tracking {len(ALL_STOCKS)} stocks: {', '.join(ALL_STOCKS)}")
    print(f"📧 Reports will be sent to: {EMAIL_TO}")
    
    issues = validate_config()
    if issues:
        print("\n⚠️  Configuration issues found:")
        for issue in issues:
            print(f"  {issue}")
    else:
        print("\n✅ Configuration looks good!")
