"""
Signal Enrichment Layer — feature explanation, driver generation, risk labeling.

Wraps existing OHLCV data into human-readable signal explanations.
All outputs are bounded enum-safe values with graceful fallbacks.

Principles:
  - NEVER modifies final_signal, confidence, or any existing consensus field
  - ALWAYS returns safe defaults if data is missing or computation fails
  - Entire enrichment is a non-fatal optional layer — pipeline continues on failure
"""

import logging
import math
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


# ─── Feature extraction ───────────────────────────────────────────────────────

_DEFAULTS = {
    "momentum_state":   "neutral",
    "trend_state":      "sideways",
    "volume_behavior":  "normal",
    "volatility_level": "medium",
    "relative_strength": "neutral",
}


def extract_features(df: pd.DataFrame, market_data: Optional[dict] = None) -> dict:
    """
    Extract market state features from OHLCV DataFrame + optional pre-computed market_data.

    Returns enum-bucketed states — never raw floats.
    Always returns safe defaults on missing data.

    Args:
        df:          Raw OHLCV price DataFrame (at least 20 rows ideal).
        market_data: Optional dict from _compute_market_data() — provides RSI,
                     volume_20d_avg, volatility_20d without recomputing.
    """
    features = dict(_DEFAULTS)

    try:
        if df is None or len(df) < 5:
            return features

        close = df['close']
        last = df.iloc[-1]

        # ── RSI (use pre-computed from market_data if available) ──────────────
        rsi = None
        if market_data:
            rsi = _safe_float(market_data.get('recent_rsi'))
        if rsi is None and len(df) >= 15:
            delta = close.diff()
            gain = delta.where(delta > 0, 0.0)
            loss = -delta.where(delta < 0, 0.0)
            avg_gain = gain.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
            avg_loss = loss.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
            rs = avg_gain / avg_loss.replace(0, float('nan'))
            rsi_val = 100 - (100 / (1 + rs))
            rsi = _safe_float(rsi_val.iloc[-1])

        # ── MACD histogram ────────────────────────────────────────────────────
        macd_hist = None
        if len(df) >= 26:
            ema12 = close.ewm(span=12, adjust=False).mean()
            ema26 = close.ewm(span=26, adjust=False).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            macd_hist = _safe_float((macd_line - signal_line).iloc[-1])

        # ── Momentum state ────────────────────────────────────────────────────
        if rsi is not None and macd_hist is not None:
            if rsi > 60 and macd_hist > 0:
                features["momentum_state"] = "strong"
            elif rsi < 40 or macd_hist < 0:
                features["momentum_state"] = "weakening"
            else:
                features["momentum_state"] = "neutral"
        elif rsi is not None:
            if rsi > 60:
                features["momentum_state"] = "strong"
            elif rsi < 40:
                features["momentum_state"] = "weakening"

        # ── Trend state (SMA alignment) ───────────────────────────────────────
        close_last = _safe_float(last.get('close'))
        if close_last is not None and len(df) >= 30:
            sma10 = _safe_float(close.rolling(10).mean().iloc[-1])
            sma30 = _safe_float(close.rolling(30).mean().iloc[-1])
            if sma10 is not None and sma30 is not None:
                if close_last > sma10 and sma10 > sma30:
                    features["trend_state"] = "uptrend"
                elif close_last < sma10 and sma10 < sma30:
                    features["trend_state"] = "downtrend"
                else:
                    features["trend_state"] = "sideways"

        # ── Volume behavior ───────────────────────────────────────────────────
        vol_last = _safe_float(last.get('volume'))
        vol_avg = None
        if market_data:
            vol_avg = _safe_float(market_data.get('volume_20d_avg'))
        if vol_avg is None and len(df) >= 20:
            vol_avg = _safe_float(df['volume'].iloc[-20:].mean())

        if vol_last is not None and vol_avg is not None and vol_avg > 0:
            ratio = vol_last / vol_avg
            if ratio > 2.0:
                open_last = _safe_float(last.get('open'))
                if close_last is not None and open_last is not None:
                    features["volume_behavior"] = (
                        "spike_buying" if close_last >= open_last else "spike_selling"
                    )
                else:
                    features["volume_behavior"] = "spike_buying"
            else:
                features["volume_behavior"] = "normal"

        # ── Volatility level ──────────────────────────────────────────────────
        # Use hist vol from market_data if available, else compute inline
        vol_daily = None
        if market_data:
            vol_daily = _safe_float(market_data.get('volatility_20d'))
        if vol_daily is None and len(df) >= 21:
            returns = close.pct_change().dropna().tail(20)
            if len(returns) > 0:
                vol_daily = _safe_float(returns.std())

        if vol_daily is not None:
            # Daily std → annualised rough estimate → bucket
            # 1.5% daily ≈ ~24% annualised; 3% ≈ ~48% annualised
            if vol_daily < 0.015:
                features["volatility_level"] = "low"
            elif vol_daily > 0.030:
                features["volatility_level"] = "high"
            else:
                features["volatility_level"] = "medium"

        # ── Relative strength (RSI as simple proxy) ───────────────────────────
        if rsi is not None:
            if rsi > 55:
                features["relative_strength"] = "outperforming"
            elif rsi < 45:
                features["relative_strength"] = "underperforming"
            else:
                features["relative_strength"] = "neutral"

    except Exception as e:
        logger.warning(f"extract_features failed — returning defaults: {e}")

    return features


# ─── Driver generation ────────────────────────────────────────────────────────

_DRIVER_MAP = {
    ("momentum_state",    "strong"):          "Momentum is accelerating",
    ("momentum_state",    "weakening"):       "Momentum is weakening",
    ("trend_state",       "uptrend"):         "Price is in an upward trend",
    ("trend_state",       "downtrend"):       "Price is in a downward trend",
    ("volume_behavior",   "spike_buying"):    "Buying pressure is increasing",
    ("volume_behavior",   "spike_selling"):   "Selling pressure is increasing",
    ("volatility_level",  "high"):            "Market conditions are elevated in volatility",
    ("volatility_level",  "low"):             "Market conditions are calm and stable",
    ("relative_strength", "outperforming"):   "Stock is outperforming the broader market",
    ("relative_strength", "underperforming"): "Stock is lagging the broader market",
}

# Priority order — trend first, then momentum, then supporting signals
_DRIVER_PRIORITY = [
    "trend_state",
    "momentum_state",
    "volume_behavior",
    "relative_strength",
    "volatility_level",
]

_NEUTRAL_VALUES = {"neutral", "normal", "sideways", "medium"}


def generate_drivers(features: dict) -> list:
    """
    Generate up to 3 human-readable signal drivers from feature states.

    Only non-neutral states generate a driver — neutral/normal is the
    absence of a signal story, not a story in itself.
    """
    if not features:
        return ["Insufficient data for full analysis"]

    drivers = []
    for key in _DRIVER_PRIORITY:
        value = features.get(key)
        if value is None or value in _NEUTRAL_VALUES:
            continue
        msg = _DRIVER_MAP.get((key, value))
        if msg:
            drivers.append(msg)
        if len(drivers) >= 3:
            break

    return drivers if drivers else ["No strong directional signals detected"]


# ─── Safe confidence scoring ──────────────────────────────────────────────────

def safe_confidence_score(features: dict, base_confidence: float = 0.5) -> float:
    """
    Adjust base confidence (0–1) by feature alignment.

    Aligned confirming signals → small boost.
    Conflicting signals (trend vs momentum) → reduction.
    High volatility → reduction.
    Always clamped to [0.0, 1.0].
    """
    if not features:
        return max(0.0, min(1.0, base_confidence))

    score = base_confidence
    trend    = features.get("trend_state")
    momentum = features.get("momentum_state")
    volume   = features.get("volume_behavior")
    vol_lvl  = features.get("volatility_level")

    # Confirming signals
    if trend == "uptrend" and momentum == "strong":
        score += 0.05
    elif trend == "downtrend" and momentum == "weakening":
        score += 0.05

    if volume == "spike_buying" and trend == "uptrend":
        score += 0.03
    elif volume == "spike_selling" and trend == "downtrend":
        score += 0.03

    # Conflicting signals
    if trend == "uptrend" and momentum == "weakening":
        score -= 0.07
    elif trend == "downtrend" and momentum == "strong":
        score -= 0.07

    # High volatility reduces reliability
    if vol_lvl == "high":
        score -= 0.05

    return round(max(0.0, min(1.0, score)), 3)


# ─── Safe risk label ──────────────────────────────────────────────────────────

def safe_risk_label(features: dict) -> str:
    """Derive Low / Medium / High risk label from features."""
    if not features:
        return "Medium"

    vol_lvl = features.get("volatility_level", "medium")
    volume  = features.get("volume_behavior", "normal")

    if vol_lvl == "high" or volume in ("spike_buying", "spike_selling"):
        return "High"
    if vol_lvl == "low" and volume == "normal":
        return "Low"
    return "Medium"


# ─── Expected move ────────────────────────────────────────────────────────────

def safe_expected_move(df: pd.DataFrame, signal: str) -> Optional[str]:
    """
    Compute a bounded expected move range using ATR (14-period).

    Returns a human-readable range string (e.g. "+2.1% to +4.3%") or None.
    Hard limits: any bound exceeding ±20% returns None (unreliable data).

    ATR-based 5-day estimate:
      Low bound  = 1× ATR%  (typical daily move × 1)
      High bound = 2× ATR%  (typical daily move × 2)
    """
    try:
        if df is None or len(df) < 15:
            return None

        close_val = _safe_float(df.iloc[-1].get('close'))
        if close_val is None or close_val <= 0:
            return None

        # True Range → 14-period ATR
        high = df['high']
        low  = df['low']
        prev_close = df['close'].shift(1)

        tr = pd.concat([
            (high - low).abs(),
            (high - prev_close).abs(),
            (low  - prev_close).abs(),
        ], axis=1).max(axis=1)

        atr_val = _safe_float(tr.rolling(14).mean().iloc[-1])
        if atr_val is None or atr_val <= 0:
            return None

        atr_pct = (atr_val / close_val) * 100
        low_bound  = round(atr_pct * 1.0, 1)
        high_bound = round(atr_pct * 2.0, 1)

        if high_bound > 20.0:
            return None  # data too noisy / stock too volatile to give a range

        if signal in ('BUY', 'UP', 'STRONG_BUY'):
            return f"+{low_bound}% to +{high_bound}%"
        elif signal in ('SELL', 'DOWN', 'STRONG_SELL'):
            return f"-{low_bound}% to -{high_bound}%"
        else:
            return f"-{low_bound}% to +{low_bound}%"

    except Exception as e:
        logger.warning(f"safe_expected_move failed: {e}")
        return None


# ─── Signal label ─────────────────────────────────────────────────────────────

def generate_signal_label(signal: str, confidence, features: dict) -> str:
    """
    Map signal + feature state → a single human-readable label shown in the UI.

    Labels are intentionally few (8) and mutually exclusive; the highest-priority
    matching condition wins.

    Returns one of:
      BUY  → "Breakout Candidate" | "Accumulation Zone" | "Strong Momentum" | "Bullish Setup"
      SELL → "Liquidity Trap"     | "High Risk Volatility" | "Distribution Zone" | "Bearish Setup"
      HOLD → "Consolidation"      | "High Uncertainty"     | "Wait & Watch"
    """
    sig = (signal or "").upper().strip()
    conf = float(confidence) if confidence is not None else 0.0
    trend = features.get("trend_state", "sideways")
    vol_beh = features.get("volume_behavior", "normal")
    vol_lvl = features.get("volatility_level", "medium")
    momentum = features.get("momentum_state", "neutral")

    if sig == "BUY":
        if vol_beh == "spike_buying" and trend == "uptrend":
            return "Breakout Candidate"
        if trend == "uptrend" and momentum in ("strong", "neutral") and vol_beh == "normal":
            return "Accumulation Zone"
        if momentum == "strong" and conf >= 0.75:
            return "Strong Momentum"
        return "Bullish Setup"

    if sig == "SELL":
        if trend == "downtrend" and vol_beh in ("spike_selling", "normal") and momentum == "weakening":
            return "Liquidity Trap"
        if vol_lvl == "high":
            return "High Risk Volatility"
        if vol_beh == "spike_selling":
            return "Distribution Zone"
        return "Bearish Setup"

    # HOLD
    if vol_lvl == "high":
        return "High Uncertainty"
    if vol_lvl == "low" and trend == "sideways":
        return "Consolidation"
    return "Wait & Watch"


def compute_liquidity_score(df: pd.DataFrame, market_data: Optional[dict] = None) -> str:
    """
    Classify stock liquidity as "High" | "Medium" | "Low" based on
    20-day average daily value traded (ADV = avg_volume × close_price).

    Thresholds are calibrated for Tadawul (SAR-denominated):
      High   : ADV > 50M SAR
      Medium : 10M – 50M SAR
      Low    : < 10M SAR
    """
    try:
        adv_value = None
        if market_data:
            vol_avg = _safe_float(market_data.get("volume_20d_avg"))
            close = _safe_float(market_data.get("close") or market_data.get("last_close"))
            if vol_avg and close:
                adv_value = vol_avg * close

        if adv_value is None and df is not None and len(df) >= 5:
            window = min(20, len(df))
            avg_vol = _safe_float(df["volume"].iloc[-window:].mean())
            last_close = _safe_float(df["close"].iloc[-1])
            if avg_vol and last_close:
                adv_value = avg_vol * last_close

        if adv_value is None:
            return "Unknown"
        if adv_value > 50_000_000:
            return "High"
        if adv_value > 10_000_000:
            return "Medium"
        return "Low"
    except Exception:
        return "Unknown"


# ─── Regime detection ─────────────────────────────────────────────────────────

def detect_regime(features: dict) -> str:
    """
    Classify market regime as metadata — attached to signal but never used
    to change the signal itself.

    Returns: "normal" | "high_volatility" | "low_liquidity"
    """
    if not features:
        return "normal"

    vol_lvl = features.get("volatility_level", "medium")
    volume  = features.get("volume_behavior", "normal")

    if vol_lvl == "high":
        return "high_volatility"
    if vol_lvl == "low" and volume == "normal":
        return "low_liquidity"
    return "normal"


# ─── Main enrichment entry point ──────────────────────────────────────────────

def enrich_signal(consensus_result: dict, df: pd.DataFrame,
                  signal: str, market_data: Optional[dict] = None) -> dict:
    """
    Non-destructive enrichment of an existing consensus result dict.

    Adds:
      drivers            — list[str]   human-readable signal drivers (max 3)
      risk_level         — str         "Low" | "Medium" | "High"
      expected_move      — str | None  e.g. "+2.1% to +4.3%", None if unavailable
      enrichment_regime  — str         "normal" | "high_volatility" | "low_liquidity"
      enrichment_features — dict       raw feature states (for debugging/API)
      signal_label       — str         e.g. "Breakout Candidate", "Accumulation Zone"
      liquidity_score    — str         "High" | "Medium" | "Low" | "Unknown"

    Never modifies: final_signal, confidence, conviction, or any pre-existing field.
    Falls back silently — pipeline always continues on failure.
    """
    try:
        features = extract_features(df, market_data)
        consensus_result["drivers"]             = generate_drivers(features)
        consensus_result["risk_level"]          = safe_risk_label(features)
        consensus_result["expected_move"]       = safe_expected_move(df, signal)
        consensus_result["expected_move_pct"]   = _compute_atr_pct(df)
        consensus_result["enrichment_regime"]   = detect_regime(features)
        consensus_result["enrichment_features"] = features
        consensus_result["signal_label"]        = generate_signal_label(
            signal, consensus_result.get("confidence"), features
        )
        consensus_result["liquidity_score"]     = compute_liquidity_score(df, market_data)
    except Exception as e:
        logger.warning(f"enrich_signal failed (non-fatal): {e}")
        consensus_result.setdefault("drivers",             ["Insufficient data for full analysis"])
        consensus_result.setdefault("risk_level",          "Medium")
        consensus_result.setdefault("expected_move",       None)
        consensus_result.setdefault("expected_move_pct",   None)
        consensus_result.setdefault("enrichment_regime",   "normal")
        consensus_result.setdefault("enrichment_features", {})
        consensus_result.setdefault("signal_label",        "—")
        consensus_result.setdefault("liquidity_score",     "Unknown")

    return consensus_result


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _compute_atr_pct(df: pd.DataFrame) -> Optional[float]:
    """Return ATR(14) as a percentage of close price, for the cost gate."""
    try:
        if df is None or len(df) < 15:
            return None
        close_val = _safe_float(df.iloc[-1].get('close'))
        if close_val is None or close_val <= 0:
            return None
        high, low, prev_close = df['high'], df['low'], df['close'].shift(1)
        tr = pd.concat([(high - low).abs(), (high - prev_close).abs(),
                         (low - prev_close).abs()], axis=1).max(axis=1)
        atr = _safe_float(tr.rolling(14).mean().iloc[-1])
        if atr is None or atr <= 0:
            return None
        return round((atr / close_val) * 100, 3)
    except Exception:
        return None


def _safe_float(val) -> Optional[float]:
    """Convert value to float, returning None on failure or non-finite result."""
    try:
        if val is None:
            return None
        f = float(val)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return None
