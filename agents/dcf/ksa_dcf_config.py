"""
KSA DCF Configuration
=====================
Market-specific DCF parameters for Saudi Arabia (Tadawul / Saudi Exchange).

All rates are expressed as decimals (e.g., 0.05 = 5 %).
Sources:
  - Risk-free rate: SAMA (Saudi Central Bank) policy rate / SAIBOR 1-year
  - ERP: Damodaran Jan 2026 estimate for Saudi Arabia
  - Tax rate: Saudi corporate income tax 20 % (zakat 2.5 % for Saudi-owned entities,
    but listed co. financials typically reflect 20 % CIT)
  - Currency: Saudi Riyal (SAR), pegged to USD at 3.75
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Macro / Market Parameters
# ---------------------------------------------------------------------------

# Risk-free rate — SAMA policy rate (as of Q1 2026, tracking Fed at ~5.25 %)
KSA_RISK_FREE_RATE: float = 0.0525

# Equity Risk Premium for Saudi Arabia (Damodaran, Jan 2026)
KSA_EQUITY_RISK_PREMIUM: float = 0.0620

# Default corporate income tax rate (Saudi CIT)
KSA_TAX_RATE: float = 0.20

# SAR / USD peg (fixed)
KSA_FX_SAR_USD: float = 3.75

# Terminal growth rate — long-run nominal GDP growth (Vision 2030 trajectory)
KSA_TERMINAL_GROWTH_RATE: float = 0.03

# Default forecast horizon (years) for DCF projections
KSA_FORECAST_YEARS: int = 5

# ---------------------------------------------------------------------------
# Sector-Specific WACC Overrides
# ---------------------------------------------------------------------------
# Sector name (matches sector_en in KSA_TOP50) -> WACC decimal
# Leave blank to use computed WACC from beta + ERP

KSA_SECTOR_WACC_OVERRIDES: dict[str, float] = {
    "Banking":            0.10,   # Banks regulated separately; use COE only
    "Insurance":          0.095,
    "Energy":             0.085,
    "Petrochemicals":     0.090,
    "Telecom":            0.088,
    "Retail":             0.092,
    "Food & Beverages":   0.091,
    "Real Estate":        0.096,
    "Building Materials": 0.093,
    "Industrials":        0.094,
    "Materials":          0.093,
    "Healthcare":         0.089,
    "Transportation":     0.091,
}

# ---------------------------------------------------------------------------
# Sector-Specific Terminal Growth Rate Overrides
# ---------------------------------------------------------------------------
# Sectors with higher/lower structural growth expectations

KSA_SECTOR_TERMINAL_GROWTH: dict[str, float] = {
    "Energy":             0.020,  # Mature; oil demand uncertainty
    "Petrochemicals":     0.025,
    "Banking":            0.035,  # Vision 2030 financial deepening
    "Telecom":            0.025,
    "Retail":             0.040,  # Consumer spending boom
    "Food & Beverages":   0.038,
    "Real Estate":        0.045,  # Mega-projects (NEOM, Diriyah, etc.)
    "Healthcare":         0.045,  # Vision 2030 healthcare expansion
    "Industrials":        0.032,
    "Building Materials": 0.042,  # Construction pipeline
    "Insurance":          0.038,
    "Transportation":     0.035,
    "Materials":          0.030,
}

# ---------------------------------------------------------------------------
# Beta Defaults by Sector (when no Bloomberg/Refinitiv beta is available)
# ---------------------------------------------------------------------------

KSA_SECTOR_DEFAULT_BETA: dict[str, float] = {
    "Banking":            0.90,
    "Insurance":          0.85,
    "Energy":             1.05,
    "Petrochemicals":     1.10,
    "Telecom":            0.80,
    "Retail":             1.00,
    "Food & Beverages":   0.75,
    "Real Estate":        1.15,
    "Building Materials": 1.10,
    "Industrials":        1.05,
    "Materials":          1.08,
    "Healthcare":         0.85,
    "Transportation":     0.95,
}

# Fallback beta if sector is unknown
KSA_DEFAULT_BETA: float = 1.00

# ---------------------------------------------------------------------------
# Debt Cost Assumptions
# ---------------------------------------------------------------------------

# Default pre-tax cost of debt (SAIBOR 3M + spread)
KSA_DEFAULT_COST_OF_DEBT: float = 0.065

# Sector-specific cost of debt overrides
KSA_SECTOR_COST_OF_DEBT: dict[str, float] = {
    "Banking":            0.000,  # Not applicable — use COE only for banks
    "Real Estate":        0.075,  # Higher leverage risk
    "Building Materials": 0.072,
    "Industrials":        0.070,
}

# ---------------------------------------------------------------------------
# Sensitivity Analysis Defaults
# ---------------------------------------------------------------------------

# WACC sensitivity range (±bps around base WACC)
KSA_WACC_SENSITIVITY_BPS: list[int] = [-100, -50, 0, 50, 100]

# Terminal growth sensitivity range (±pp around base TGR)
KSA_TGR_SENSITIVITY_PP: list[float] = [-0.01, -0.005, 0.0, 0.005, 0.01]

# ---------------------------------------------------------------------------
# DCF Scenario Multipliers on FCF Growth
# ---------------------------------------------------------------------------

KSA_DCF_SCENARIOS: dict[str, float] = {
    "bull":   1.20,   # Vision 2030 tailwinds fully materialise
    "base":   1.00,
    "bear":   0.75,   # Oil price weakness + execution risk
}

# ---------------------------------------------------------------------------
# Data Source Preferences
# ---------------------------------------------------------------------------

# Preferred financial data sources in priority order
KSA_DATA_SOURCES: list[str] = [
    "tadawul_official",   # Tadawul (Saudi Exchange) XBRL filings
    "argaam",             # Argaam financial portal (Arabic/English)
    "mubasher",           # Mubasher financials
    "yahoo_finance",      # yfinance fallback (.SR suffix)
]

# yfinance symbol suffix for KSA
KSA_YFINANCE_SUFFIX: str = ".SR"

# Tadawul trading hours (Asia/Riyadh, UTC+3)
KSA_MARKET_OPEN:  str = "10:00"
KSA_MARKET_CLOSE: str = "15:00"
KSA_MARKET_TZ:    str = "Asia/Riyadh"
KSA_TRADING_DAYS: list[str] = ["Monday", "Tuesday", "Wednesday", "Thursday", "Sunday"]
# Note: Tadawul trades Sun–Thu, closed Fri–Sat

# Number of trading days per year (Tadawul)
KSA_TRADING_DAYS_PER_YEAR: int = 248

# ---------------------------------------------------------------------------
# Consolidated KSA_DCF_CONFIG dict — consumed by ksa_dcf_engine.py
# ---------------------------------------------------------------------------
KSA_DCF_CONFIG: dict = {
    # Macro
    "LONG_TERM_RATE":         KSA_RISK_FREE_RATE,
    "EQUITY_RISK_PREMIUM":    KSA_EQUITY_RISK_PREMIUM,
    "CORPORATE_TAX_RATE":     KSA_TAX_RATE,
    "TERMINAL_GROWTH_RATE":   KSA_TERMINAL_GROWTH_RATE,
    "FORECAST_YEARS":         KSA_FORECAST_YEARS,

    # WACC bounds
    "WACC_MIN":               0.07,
    "WACC_MAX":               0.18,

    # Sector terminal growth overrides (keyed by sector_en)
    "SECTOR_GROWTH_OVERRIDES": KSA_SECTOR_TERMINAL_GROWTH,

    # Scenario weights (must sum to 1.0)
    "BULL_WEIGHT":            0.25,
    "BASE_WEIGHT":            0.50,
    "BEAR_WEIGHT":            0.25,

    # Valuation label thresholds (margin of safety)
    "DEEP_VALUE_MOS":         0.30,   # >= 30% upside  → DEEP_VALUE
    "UNDERVALUED_MOS":        0.10,   # >= 10% upside  → UNDERVALUED
    "FAIR_VALUE_BAND":        0.05,   # within ±5%     → FAIR_VALUE
    "SPECULATIVE_PREMIUM":    0.20,   # >= 20% premium → SPECULATIVE

    # Data
    "TRADING_DAYS_PER_YEAR":  KSA_TRADING_DAYS_PER_YEAR,
    "SECTOR_DEFAULT_BETA":    KSA_SECTOR_DEFAULT_BETA,
    "DEFAULT_BETA":           KSA_DEFAULT_BETA,
}
