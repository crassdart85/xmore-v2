"""
Pivot Point Engine
Calculates classic floor-trader pivot levels (P, R1, R2, S1, S2),
ATR-based buy guide, trend label, and recommendation type.

Used by run_agents.py to enrich each trade recommendation with
the same columns shown in a standard EGX session sheet.
"""

from __future__ import annotations
import pandas as pd
import numpy as np
from typing import Optional


# ─── Trend labels ────────────────────────────────────────────────────────────
TREND_BULLISH   = "صاعد"        # Rising
TREND_SIDEWAYS  = "عرضى"       # Sideways
TREND_BEARISH   = "هابط"        # Falling

TREND_BULLISH_EN  = "Bullish"
TREND_SIDEWAYS_EN = "Sideways"
TREND_BEARISH_EN  = "Bearish"

# ─── Recommendation type ─────────────────────────────────────────────────────
REC_TRADE = "متاجرة"    # Active trade — HIGH/VERY_HIGH conviction UP
REC_HOLD  = "احتفاظ"    # Hold / conservative — MODERATE/LOW or HOLD signal


def calculate_pivots(df: pd.DataFrame) -> Optional[dict]:
    """
    Classic floor-trader pivot points from the previous session OHLC.

    Args:
        df: DataFrame with columns [open, high, low, close], sorted ascending by date.
            At least 2 rows required.

    Returns:
        dict with keys: pivot, r1, r2, s1, s2, prev_high, prev_low, prev_close
        or None if insufficient data.
    """
    if df is None or len(df) < 2:
        return None

    # Use the last complete session (second-to-last row)
    prev = df.iloc[-2]
    H = float(prev["high"])
    L = float(prev["low"])
    C = float(prev["close"])

    if H <= 0 or L <= 0 or C <= 0:
        return None

    P  = (H + L + C) / 3
    R1 = 2 * P - L
    R2 = P + (H - L)
    S1 = 2 * P - H
    S2 = P - (H - L)

    return {
        "pivot":      round(P,  3),
        "r1":         round(R1, 3),
        "r2":         round(R2, 3),
        "s1":         round(S1, 3),
        "s2":         round(S2, 3),
        "prev_high":  round(H,  3),
        "prev_low":   round(L,  3),
        "prev_close": round(C,  3),
    }


def calculate_atr(df: pd.DataFrame, period: int = 14) -> Optional[float]:
    """True-Range ATR over `period` sessions."""
    if df is None or len(df) < period + 1:
        return None

    sub = df.tail(period + 1).copy()
    sub["prev_close"] = sub["close"].shift(1)
    sub["tr"] = sub.apply(
        lambda r: max(
            r["high"] - r["low"],
            abs(r["high"] - r["prev_close"]),
            abs(r["low"]  - r["prev_close"]),
        ) if pd.notna(r["prev_close"]) else r["high"] - r["low"],
        axis=1,
    )
    atr = sub["tr"].tail(period).mean()
    return round(float(atr), 4) if pd.notna(atr) else None


def get_trend(df: pd.DataFrame) -> tuple[str, str]:
    """
    Determine trend using EMA(10) vs EMA(30) crossover + slope.

    Returns:
        (trend_ar, trend_en) — Arabic and English trend labels.
    """
    if df is None or len(df) < 30:
        return TREND_SIDEWAYS, TREND_SIDEWAYS_EN

    close = df["close"].astype(float)
    ema10 = close.ewm(span=10, adjust=False).mean()
    ema30 = close.ewm(span=30, adjust=False).mean()

    e10 = float(ema10.iloc[-1])
    e30 = float(ema30.iloc[-1])
    slope = float(ema10.iloc[-1]) - float(ema10.iloc[-5])   # 5-bar EMA10 slope

    if e10 > e30 and slope > 0:
        return TREND_BULLISH, TREND_BULLISH_EN
    elif e10 < e30 and slope < 0:
        return TREND_BEARISH, TREND_BEARISH_EN
    else:
        return TREND_SIDEWAYS, TREND_SIDEWAYS_EN


def get_recommendation_type(signal: str, conviction: str) -> tuple[str, str]:
    """
    Map signal + conviction to recommendation type.

    احتفاظ = conservative hold / watch
    متاجرة = active trade (strong buy signal)
    """
    if signal == "UP" and conviction in ("VERY_HIGH", "HIGH"):
        return REC_TRADE, "Trade"
    else:
        return REC_HOLD, "Hold"


def get_buy_guide(close: float, pivots: Optional[dict], atr: Optional[float]) -> float:
    """
    Suggest an entry (buy guide) price.

    Logic:
      - If price is above S1 and S1 > 0: guide = S1 (buy on pullback to support)
      - Otherwise: guide = close - 0.3 * ATR (slight discount to current price)
    """
    if close <= 0:
        return 0.0

    if pivots:
        s1 = pivots.get("s1", 0)
        if 0 < s1 < close:
            return round(s1, 3)

    fallback_discount = (atr or close * 0.03) * 0.3
    return round(close - fallback_discount, 3)


def enrich_recommendation(
    rec: dict,
    df: pd.DataFrame,
    close: float,
) -> dict:
    """
    Add pivot levels, trend, buy guide, and recommendation type to a
    trade recommendation dict in-place. Returns the same dict.

    Args:
        rec:   Recommendation dict from trade_recommender / run_agents.
        df:    Full OHLC price DataFrame for this symbol (sorted ascending).
        close: Latest close price.
    """
    signal     = rec.get("signal", "FLAT")
    conviction = rec.get("conviction", "LOW")

    # --- Pivots ---
    pivots = calculate_pivots(df)

    # --- ATR ---
    atr = calculate_atr(df, period=14)
    if atr is None:
        atr = close * 0.03  # 3% fallback

    # --- Trend ---
    trend_ar, trend_en = get_trend(df)

    # --- Buy guide ---
    buy_guide = get_buy_guide(close, pivots, atr)

    # --- Recommendation type ---
    rec_type_ar, rec_type_en = get_recommendation_type(signal, conviction)

    rec["trend_ar"]       = trend_ar
    rec["trend_en"]       = trend_en
    rec["rec_type_ar"]    = rec_type_ar
    rec["rec_type_en"]    = rec_type_en
    rec["buy_guide"]      = buy_guide

    if pivots:
        rec["pivot"]  = pivots["pivot"]
        rec["r1"]     = pivots["r1"]
        rec["r2"]     = pivots["r2"]
        rec["s1"]     = pivots["s1"]
        rec["s2"]     = pivots["s2"]
    else:
        rec["pivot"] = rec["r1"] = rec["r2"] = rec["s1"] = rec["s2"] = None

    return rec
