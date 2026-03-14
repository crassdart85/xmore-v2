"""
Execution Realism Configuration — EGX-specific friction parameters.
All monetary values in Egyptian Pounds (EGP).
"""

# ─── EGX TRANSACTION COST STRUCTURE ────────────────────────────────────────
EGX_BROKERAGE_RATE     = 0.00150   # 0.15% per leg
EGX_STAMP_DUTY         = 0.00150   # 0.15% per leg
EGX_FRA_FEE            = 0.000125  # Financial Regulatory Authority
EGX_EXCHANGE_FEE       = 0.000125  # EGX infrastructure fee
EGX_MISR_CLEARING      = 0.00010   # Misr for Central Clearing
EGX_MIN_TICKET_EGP     = 15.0      # Minimum commission per order in EGP
EGX_ROUND_TRIP_RATE    = (EGX_BROKERAGE_RATE + EGX_STAMP_DUTY + EGX_FRA_FEE +
                           EGX_EXCHANGE_FEE + EGX_MISR_CLEARING) * 2

# ─── MINIMUM EDGE RULE ──────────────────────────────────────────────────────
MIN_EDGE_TO_COST_RATIO = 3.0       # Signal expected return must be ≥ 3× round-trip cost
                                    # Round-trip ≈ 0.70–1.0%, so min signal target ≈ +3%

# ─── SLIPPAGE TIERS (basis points) by EGX Liquidity ───────────────────────
# Tier assigned based on Average Daily Turnover (price × volume)
SLIPPAGE_TIERS = {
    "high":   {"min_adv_egp": 5_000_000, "bps": 10},   # COMI, ETEL, TMGH
    "medium": {"min_adv_egp": 1_000_000, "bps": 25},   # SKPC, AMOC, HELI, ISPH
    "low":    {"min_adv_egp": 0,         "bps": 60},   # GBCO, EFIH, ABUK, MFPC
}

# ─── PARTIAL FILL MODEL ─────────────────────────────────────────────────────
# Max order size as % of ADV before partial fill risk kicks in
FILL_THRESHOLDS = [
    {"max_adv_pct": 0.01, "fill_ratio": 0.95, "wait_days": 1},
    {"max_adv_pct": 0.05, "fill_ratio": 0.75, "wait_days": 2},
    {"max_adv_pct": 0.10, "fill_ratio": 0.50, "wait_days": 3},
    {"max_adv_pct": 1.00, "fill_ratio": 0.30, "wait_days": 5},  # >10% ADV — dangerous
]
MAX_ADV_PARTICIPATION = 0.03        # Split orders if position > 3% of ADV

# ─── EGX DAILY PRICE LIMIT ──────────────────────────────────────────────────
EGX_DAILY_LIMIT_PCT    = 0.10       # ±10% max daily move — stops can gap through

# ─── POSITION SIZING ────────────────────────────────────────────────────────
MAX_POSITION_PCT       = 0.10       # Max 10% of portfolio per single stock
MAX_SECTOR_PCT         = 0.35       # Max 35% of portfolio in one sector

# ─── HOLDING PERIOD RULES (replaces hard 30-day limit) ─────────────────────
TRAILING_STOP_ACTIVATION_DAY = 20   # Trailing stop kicks in after day 20
TRAILING_STOP_PCT             = 0.06 # 6% trailing stop once activated
HARD_MAX_HOLDING_DAYS         = 45  # Absolute maximum — failsafe only

# ─── EGX PERFORMANCE BENCHMARKS ────────────────────────────────────────────
EGX_RISK_FREE_RATE_ANNUAL = 0.2725   # Egypt CBE overnight deposit rate — update quarterly
EGX_TRADING_DAYS_PER_YEAR = 247      # Sun–Thu, ~52 weeks minus public holidays

# ─── MARKET REGIME FILTER ───────────────────────────────────────────────────
REGIME_MA_PERIOD       = 20         # EGX30 20-day moving average
REGIME_TICKER          = "^CASE30"  # Yahoo Finance ticker for EGX30
REGIME_BEARISH_BUFFER  = 0.02       # Index must be ≥ 2% above MA to allow new longs
                                    # Prevents buying into corrections/peaks
