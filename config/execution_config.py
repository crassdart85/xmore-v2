"""
Execution Realism Configuration — market friction parameters.
EGX values in Egyptian Pounds (EGP). Tadawul values in SAR.
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
MAX_POSITION_PCT       = 0.10       # Hard cap: max 10% of portfolio per single stock
MAX_SECTOR_PCT         = 0.35       # Max 35% of portfolio in one sector
BASE_DAILY_VOLATILITY  = 0.020      # 2.0% reference daily std (EGX mid-cap baseline)


def calculate_position_size(
    conviction_score: float,
    daily_volatility: float,
    max_loss_per_trade: float = 0.015,
) -> float:
    """
    Volatility-adjusted position size as a fraction of portfolio.

    Positions scale INVERSELY with daily_volatility and LINEARLY with
    conviction_score (0–100 xmore_score or agent confidence).
    Result is capped at MAX_POSITION_PCT (10%).

    Args:
        conviction_score:  0–100. Scores below 40 receive minimal allocation.
        daily_volatility:  Daily standard deviation as a fraction (e.g. 0.03 = 3%).
        max_loss_per_trade: Maximum tolerated portfolio loss per position (default 1.5%).

    Returns:
        Position size as fraction of portfolio (e.g. 0.07 = 7%).
    """
    daily_volatility = max(float(daily_volatility), 0.005)  # floor at 0.5%

    # Scale inversely with volatility relative to baseline
    vol_adj = min(BASE_DAILY_VOLATILITY / daily_volatility, 2.0)

    # Conviction multiplier: 0.1 for low conviction, 1.0 at max
    if conviction_score >= 100:
        conviction_mult = 1.0
    elif conviction_score >= 40:
        conviction_mult = (float(conviction_score) - 40.0) / 60.0
    else:
        conviction_mult = 0.1

    # Volatility-implied stop: 2× daily vol, minimum 2%
    expected_stop_pct = max(daily_volatility * 2.0, 0.02)
    base_size = max_loss_per_trade / expected_stop_pct

    raw_size = base_size * vol_adj * (0.5 + 0.5 * conviction_mult)
    return min(round(raw_size, 4), MAX_POSITION_PCT)

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

# ============================================================
# TADAWUL (Saudi Exchange) — KSA Configuration
# ============================================================

TADAWUL_CONFIG = {
    # Identity
    "market_id":              "KSA",
    "market_name":            "Saudi Exchange (Tadawul)",
    "market_name_ar":         "تداول",
    "market_name_display":    "Tadawul",
    "mic_code":               "XSAU",
    "currency":               "SAR",
    "currency_symbol":        "ر.س",

    # Yahoo Finance / yfinance
    "ticker_suffix":          ".SR",
    "index_ticker":           "^TASI.SR",
    "regime_index":           "^TASI.SR",
    "bluechip_index":         "^MT30.SR",

    # Schedule (Sun-Thu, UTC+3, NO daylight saving EVER)
    "timezone":               "Asia/Riyadh",
    "trading_days":           [6, 0, 1, 2, 3],  # Sun=6, Mon=0, Thu=3
    "pre_open_utc":           "06:30",
    "market_open_utc":        "07:00",
    "market_close_utc":       "12:00",
    "closing_auction_end_utc":"12:10",
    "github_cron":            "15 12 * * 0,1,2,3,4",  # 12:15 UTC after close

    # Transaction costs (per side, decimal, all-in including 15% VAT)
    "broker_commission":      0.00120,   # 12.0 bps typical
    "cma_fee":                0.00030,   # 3.0 bps VAT EXEMPT
    "exchange_fee":           0.00009,   # 0.9 bps
    "settlement_fee":         0.00005,   # 0.5 bps (Edaa)
    "safekeeping_fee":        0.00001,   # 0.1 bps (Edaa)
    "clearing_fee":           0.00005,   # 0.5 bps (Muqassa)
    "vat_rate":               0.15,      # 15% on all except CMA fee
    "total_cost_per_side":    0.00191,   # ~19.1 bps all-in
    "round_trip_cost":        0.00382,   # ~38.2 bps round-trip

    # Price limits
    "daily_price_limit":      0.10,      # +/-10% standard
    "ipo_price_limit":        0.30,      # +/-30% first 3 sessions
    "nomu_price_limit":       0.30,      # Nomu parallel market

    # Risk metrics
    "risk_free_rate":         0.0425,    # SAMA repo rate — update quarterly
    "saibor_3m":              0.0489,    # 3-month SAIBOR for Sharpe
    "trading_days_per_year":  250,

    # Execution gate thresholds
    "min_edge_multiple":      3.0,
    "min_edge_threshold":     0.01146,   # 3x 38.2bps round-trip
    "slippage_high_adv_sar":  0.00100,   # 10bps ADV > SAR 5M
    "slippage_mid_adv_sar":   0.00250,   # 25bps ADV SAR 1-5M
    "slippage_low_adv_sar":   0.00600,   # 60bps ADV < SAR 1M
    "adv_high_threshold_sar": 5_000_000,
    "adv_mid_threshold_sar":  1_000_000,

    # Holding manager
    "trailing_stop_day":      20,
    "trailing_stop_pct":      0.06,
    "hard_exit_day":          45,

    # Settlement
    "settlement_cycle":       "T+2",
    "stop_loss_native":       False,     # Broker-level only, NOT exchange-native
    "short_selling":          True,      # Covered only via SBL framework

    # Tick sizes (updated June 29, 2025)
    "tick_sizes": [
        (0.01,   24.99,  0.01),
        (25.00,  49.98,  0.02),
        (50.00,  99.95,  0.05),
        (100.00, 249.90, 0.10),
        (250.00, 499.80, 0.20),
        (500.00, float('inf'), 0.50),
    ],

    # Regulatory (for dashboard display)
    "regulator":              "CMA Saudi Arabia",
    "disclaimer_ar":          "هذه الإشارات للأغراض المعلوماتية فقط وليست نصيحة استثمارية",
    "disclaimer_en":          "Signals are for informational purposes only and do not constitute investment advice",
    "shariah_screening":      True,
}
