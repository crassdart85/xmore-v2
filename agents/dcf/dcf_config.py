from datetime import date


class EgyptDCFConfig:
    """Egypt-specific DCF configuration and macro assumptions."""

    # ── Risk-free rate (CBE overnight deposit rate) ────────────────────────────
    # Update quarterly when CBE publishes rate changes
    RISK_FREE_RATE = 0.190          # 19.0% (Feb 2026)

    # ── Equity Risk Premium (Egypt) ────────────────────────────────────────────
    # Damodaran EMRP + country risk premium. Conservative for stability.
    EQUITY_RISK_PREMIUM = 0.110     # 11.0%

    # ── Terminal growth assumptions ───────────────────────────────────────────
    # Long-run nominal GDP growth (inflation + real). Conservative estimate.
    TERMINAL_GROWTH_RATE = 0.080    # 8.0%

    # ── Inflation adjustment (nominal projections) ─────────────────────────────
    CURRENT_INFLATION = 0.119       # ~11.9% (Jan 2026)

    # ── Currency conversion (for USD denominated tickers) ──────────────────────
    CURRENCY = "EGP"
    USD_EGP_RATE = 47.39            # update weekly via yfinance, if available

    # ── Sector-specific long-run terminal growth overrides ────────────────────
    SECTOR_TERMINAL_GROWTH = {
        "Technology":     0.100,  # faster digital adoption
        "Real Estate":    0.085,
        "Banking":        0.075,
        "Consumer Goods": 0.090,
        "Telecom":        0.070,
        "Oil & Gas":      0.065,
        "Chemicals":      0.070,
        "Healthcare":     0.095,
        "Industrials":    0.075,
        "default":        0.080,
    }

    # ── Sector revenue growth assumptions (Stage 1) ──────────────────────────
    SECTOR_REVENUE_GROWTH = {
        "Technology":     {"bull": 0.25, "base": 0.18, "bear": 0.10},
        "Real Estate":    {"bull": 0.20, "base": 0.14, "bear": 0.05},
        "Banking":        {"bull": 0.22, "base": 0.16, "bear": 0.08},
        "Consumer Goods": {"bull": 0.18, "base": 0.13, "bear": 0.06},
        "Telecom":        {"bull": 0.15, "base": 0.10, "bear": 0.04},
        "Oil & Gas":      {"bull": 0.20, "base": 0.12, "bear": 0.02},
        "Chemicals":      {"bull": 0.18, "base": 0.12, "bear": 0.03},
        "Healthcare":     {"bull": 0.22, "base": 0.16, "bear": 0.08},
        "Industrials":    {"bull": 0.16, "base": 0.11, "bear": 0.04},
        "default":        {"bull": 0.18, "base": 0.12, "bear": 0.04},
    }

    # ── Free cash flow margin fallbacks (for missing data) ────────────────────
    SECTOR_FCF_MARGIN = {
        "Technology":     0.18,
        "Banking":        None,   # banks use earnings-based model (no FCF)
        "Real Estate":    0.12,
        "Consumer Goods": 0.08,
        "Telecom":        0.15,
        "Oil & Gas":      0.14,
        "Chemicals":      0.12,
        "Healthcare":     0.13,
        "Industrials":    0.09,
        "default":        0.10,
    }

    # ── DCF confidence thresholds (based on years of history available) ──────
    HIGH_CONFIDENCE_MIN_YEARS = 4
    MEDIUM_CONFIDENCE_MIN_YEARS = 2
    # < 2 years → LOW confidence

    # ── Margin-of-safety labels ──────────────────────────────────────────────
    DEEP_VALUE_THRESHOLD  = 0.40   # >40% discount → DEEP_VALUE
    UNDERVALUED_THRESHOLD = 0.15   # 15–40% discount → UNDERVALUED
    FAIR_VALUE_BAND       = 0.10   # ±10% of fair value → FAIR
    OVERVALUED_THRESHOLD  = -0.15  # 15–40% premium → OVERVALUED
    # < -40% → SPECULATIVE

    # ── Run schedule / cadence notes ─────────────────────────────────────────
    # Full DCF pipeline runs weekly (Sunday). The signal is emitted once per
    # week (or once per month for a slower cadence), and is intended to be
    # used as a supplementary validation input for the existing agent consensus.
    RUN_CADENCE = "weekly"
