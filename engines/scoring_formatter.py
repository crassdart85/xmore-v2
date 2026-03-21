"""
Universal Investor Scoring Formatter — Xmore2

Translates internal composite scores (0–1) into 6 external presentation formats.
The composite score weighs 4 components:
  consensus × 0.40 + execution × 0.25 + regime × 0.20 + momentum × 0.15

Scoring modes:
  xmore_native  — 0.00–1.00 float (internal default)
  standard_100  — 0–100 int
  letter_grade  — A+ / A / B+ / B / C / D / F
  stars         — 1.0–5.0 float (half-star resolution)
  signal_tier   — S / A / B / C / D
  conviction    — HIGH / MEDIUM / LOW
"""

# SCORE DISAMBIGUATION
# There are two distinct scores in this system:
#
# 1. Xmore Score (0–100): bull×0.30 + (100−bear)×0.25 + agreement×0.25 + confidence×0.20
#    Source: consensus_results.xmore_score
#    Meaning: How bullish are the agents on this stock?
#
# 2. Composite Investor Score (0–1): consensus×0.40 + execution×0.25 + regime×0.20 + momentum×0.15
#    Source: scored_signals.composite_score
#    Meaning: How high-quality is this as a tradeable signal?
#
# These are NOT interchangeable. The Composite Score uses consensus_score (raw agent BUY vote
# fraction, 0.0–1.0) as its consensus component — NOT the Xmore Score.
# The Xmore Score is a bullishness index; the Composite Score is a trade-quality index.

from __future__ import annotations
import math
from datetime import datetime, timezone
from typing import Optional


# ─── Mode Registry ──────────────────────────────────────────────

SCORING_MODES = {
    "xmore_native": {
        "scale": (0.0, 1.0),
        "type": "float",
        "threshold": 0.62,
        "description": "Internal 0–1 composite score",
    },
    "standard_100": {
        "scale": (0, 100),
        "type": "int",
        "threshold": 62,
        "description": "0–100 integer score (common in quant reports)",
    },
    "letter_grade": {
        "scale": ["A+", "A", "B+", "B", "C", "D", "F"],
        "type": "str",
        "threshold": "B",
        "description": "Academic-style grade",
    },
    "stars": {
        "scale": (1.0, 5.0),
        "type": "float",
        "threshold": 3.5,
        "description": "1–5 stars (0.5 resolution)",
    },
    "signal_tier": {
        "scale": ["S", "A", "B", "C", "D"],
        "type": "str",
        "threshold": "B",
        "description": "S/A/B/C/D tier (common in retail trading apps)",
    },
    "conviction": {
        "scale": ["HIGH", "MEDIUM", "LOW"],
        "type": "str",
        "threshold": "MEDIUM",
        "description": "Conviction level for portfolio managers",
    },
}

# ─── Component Weights ───────────────────────────────────────────

COMPOSITE_WEIGHTS = {
    "consensus":  0.40,
    "execution":  0.25,
    "regime":     0.20,
    "momentum":   0.15,
}

# ─── Regime score mapping ─────────────────────────────────────────

REGIME_SCORES = {
    "BULL":    1.0,
    "NEUTRAL": 0.50,
    "BEAR":    0.0,
}


# ─── ScoringFormatter ────────────────────────────────────────────

class ScoringFormatter:
    """
    Converts internal signals into investor-facing scores in 6 modes.

    Usage:
        sf = ScoringFormatter(mode="standard_100")
        score = sf.format(composite_score=0.74)   # → 74
        entry = sf.build_scored_entry(symbol, rec, components)
    """

    def __init__(self, mode: str = "xmore_native"):
        if mode not in SCORING_MODES:
            raise ValueError(
                f"Unknown scoring mode '{mode}'. Valid: {list(SCORING_MODES.keys())}"
            )
        self.mode = mode
        self._cfg = SCORING_MODES[mode]

    # ── Public: format a 0–1 composite to this mode's representation ──

    def format(self, composite_score: float) -> object:
        """Convert a 0–1 composite score to the mode's output type."""
        s = max(0.0, min(1.0, float(composite_score)))
        m = self.mode

        if m == "xmore_native":
            return round(s, 4)

        if m == "standard_100":
            return int(round(s * 100))

        if m == "letter_grade":
            return _to_letter_grade(s)

        if m == "stars":
            # Map 0–1 → 1–5, then round to nearest 0.5
            raw = 1.0 + s * 4.0
            return round(raw * 2) / 2  # half-star resolution

        if m == "signal_tier":
            return _to_signal_tier(s)

        if m == "conviction":
            return _to_conviction(s)

        return s  # fallback

    # ── Public: all 6 representations at once ──

    def format_all(self, composite_score: float) -> dict:
        """Return score in all 6 modes simultaneously."""
        s = max(0.0, min(1.0, float(composite_score)))
        return {
            "xmore_native":  round(s, 4),
            "standard_100":  int(round(s * 100)),
            "letter_grade":  _to_letter_grade(s),
            "stars":         round((1.0 + s * 4.0) * 2) / 2,
            "signal_tier":   _to_signal_tier(s),
            "conviction":    _to_conviction(s),
        }

    # ── Public: check if score meets the mode's actionable threshold ──

    def meets_threshold(self, composite_score: float) -> bool:
        """True if the score clears the actionable threshold for this mode."""
        formatted = self.format(composite_score)
        threshold = self._cfg["threshold"]

        if self._cfg["type"] in ("float", "int"):
            return formatted >= threshold

        if self.mode == "letter_grade":
            _order = ["F", "D", "C", "B", "B+", "A", "A+"]
            fi = _order.index(formatted) if formatted in _order else 0
            ti = _order.index(threshold) if threshold in _order else 0
            return fi >= ti

        if self.mode == "signal_tier":
            _order = ["D", "C", "B", "A", "S"]
            fi = _order.index(formatted) if formatted in _order else 0
            ti = _order.index(threshold) if threshold in _order else 0
            return fi >= ti

        if self.mode == "conviction":
            _order = ["LOW", "MEDIUM", "HIGH"]
            fi = _order.index(formatted) if formatted in _order else 0
            ti = _order.index(threshold) if threshold in _order else 0
            return fi >= ti

        return False

    # ── Public: build a complete scored_signals row ──

    def build_scored_entry(
        self,
        symbol: str,
        rec: dict,
        components: dict,
        mode: Optional[str] = None,
    ) -> dict:
        """
        Build a dict ready for insertion into scored_signals table.

        components keys expected:
          consensus_score (0–1), execution_score (0–1),
          regime_score (0–1), momentum_score (0–1)
        """
        composite = calculate_composite_score(components)
        all_scores = self.format_all(composite)

        target_mode = mode or self.mode
        formatted   = ScoringFormatter(target_mode).format(composite)

        return {
            "symbol":            symbol,
            "signal_date":       rec.get("recommendation_date") or datetime.now(timezone.utc).date().isoformat(),
            "action":            rec.get("action", "HOLD"),
            "composite_score":   round(composite, 4),
            "scoring_mode":      target_mode,
            "score_value":       str(formatted),
            "consensus_score":   round(components.get("consensus_score", 0), 4),
            "execution_score":   round(components.get("execution_score", 0), 4),
            "regime_score":      round(components.get("regime_score", 0), 4),
            "momentum_score":    round(components.get("momentum_score", 0), 4),
            "meets_threshold":   self.meets_threshold(composite),
            "all_formats":       all_scores,
            "created_at":        datetime.now(timezone.utc).isoformat(),
        }


# ─── Composite Score Calculator ──────────────────────────────────

def calculate_composite_score(components: dict) -> float:
    """
    Weighted composite of 4 normalized 0–1 component scores.

    Expected keys: consensus_score, execution_score, regime_score, momentum_score
    Missing components default to 0.5 (neutral) to avoid penalizing data gaps.
    """
    consensus = float(components.get("consensus_score", 0.5))
    execution = float(components.get("execution_score", 0.5))
    regime    = float(components.get("regime_score",    0.5))
    momentum  = float(components.get("momentum_score",  0.5))

    # Clamp each to [0, 1]
    consensus = max(0.0, min(1.0, consensus))
    execution = max(0.0, min(1.0, execution))
    regime    = max(0.0, min(1.0, regime))
    momentum  = max(0.0, min(1.0, momentum))

    composite = (
        consensus * COMPOSITE_WEIGHTS["consensus"] +
        execution * COMPOSITE_WEIGHTS["execution"] +
        regime    * COMPOSITE_WEIGHTS["regime"]    +
        momentum  * COMPOSITE_WEIGHTS["momentum"]
    )
    return round(composite, 6)


def derive_components_from_rec(rec: dict, regime: str = "NEUTRAL") -> dict:
    """
    Derive scoring components from a trade_recommendation dict.

    Used when components are not individually tracked — infers from
    the existing fields available in rec.
    """
    # consensus_score: prefer empirically calibrated confidence, then raw BUY vote
    # fraction, then raw confidence. Do NOT use xmore_score — that is a separate
    # bullishness index, not the consensus component of the composite score.
    calibrated_conf = rec.get("calibrated_confidence")
    raw_bull = rec.get("bull")  # 0–100: % of agents that voted BUY
    raw_conf = rec.get("confidence")  # 0–100: consensus confidence
    if calibrated_conf is not None:
        consensus_score = max(0.0, min(1.0, float(calibrated_conf) / 100.0))
    elif raw_bull is not None:
        consensus_score = max(0.0, min(1.0, float(raw_bull) / 100.0))
    elif raw_conf is not None:
        consensus_score = max(0.0, min(1.0, float(raw_conf) / 100.0))
    else:
        consensus_score = 0.5  # neutral default when no agent data available

    # execution_score: prefer expected edge after costs, then edge_ratio.
    expected_edge_pct = rec.get("expected_edge_pct")
    edge = rec.get("edge_ratio")
    if expected_edge_pct is not None:
        execution_score = max(0.0, min(1.0, 0.5 + (float(expected_edge_pct) / 5.0)))
    elif edge is not None:
        execution_score = min(1.0, float(edge) / 15.0)
    elif rec.get("execution_approved") is True:
        execution_score = 0.7
    elif rec.get("execution_approved") is False:
        execution_score = 0.1
    else:
        execution_score = 0.5

    # regime_score: from regime string
    regime_score = REGIME_SCORES.get(regime.upper(), 0.5)

    # momentum_score: prefer explicit momentum alignment from consensus, then alpha,
    # then priority/action.
    momentum_alignment = rec.get("momentum_alignment")
    alpha = rec.get("alpha_1d")
    if momentum_alignment is not None:
        momentum_score = max(0.0, min(1.0, float(momentum_alignment) / 100.0))
    elif alpha is not None:
        # alpha of +3% → 0.8, ±0 → 0.5, -3% → 0.2
        momentum_score = max(0.0, min(1.0, 0.5 + float(alpha) * (0.3 / 0.03)))
    else:
        priority = rec.get("priority") or 0.5
        momentum_score = max(0.0, min(1.0, float(priority)))

    return {
        "consensus_score": round(consensus_score, 4),
        "execution_score": round(execution_score, 4),
        "regime_score":    round(regime_score, 4),
        "momentum_score":  round(momentum_score, 4),
    }


# ─── Private helpers ─────────────────────────────────────────────

def _to_letter_grade(s: float) -> str:
    if s >= 0.93: return "A+"
    if s >= 0.85: return "A"
    if s >= 0.77: return "B+"
    if s >= 0.65: return "B"
    if s >= 0.50: return "C"
    if s >= 0.35: return "D"
    return "F"


def _to_signal_tier(s: float) -> str:
    if s >= 0.90: return "S"
    if s >= 0.75: return "A"
    if s >= 0.60: return "B"
    if s >= 0.40: return "C"
    return "D"


def _to_conviction(s: float) -> str:
    if s >= 0.65: return "HIGH"
    if s >= 0.40: return "MEDIUM"
    return "LOW"
