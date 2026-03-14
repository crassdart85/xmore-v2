"""
Unit tests for Universal Investor Scoring Formatter.
Run with: pytest tests/test_scoring_formatter.py -v
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from engines.scoring_formatter import (
    ScoringFormatter,
    calculate_composite_score,
    derive_components_from_rec,
    SCORING_MODES,
    COMPOSITE_WEIGHTS,
)


# ─── Test 1: All 6 modes are registered ──────────────────────────

def test_all_modes_registered():
    """SCORING_MODES must contain exactly the 6 required keys."""
    required = {"xmore_native", "standard_100", "letter_grade", "stars", "signal_tier", "conviction"}
    assert required == set(SCORING_MODES.keys())


# ─── Test 2: Composite weights sum to 1.0 ────────────────────────

def test_composite_weights_sum_to_one():
    total = sum(COMPOSITE_WEIGHTS.values())
    assert abs(total - 1.0) < 1e-9, f"Weights sum to {total}, expected 1.0"


# ─── Test 3: standard_100 range [0, 100] ────────────────────────

def test_standard_100_bounds():
    sf = ScoringFormatter("standard_100")
    assert sf.format(0.0) == 0
    assert sf.format(1.0) == 100
    assert sf.format(0.5) == 50
    assert isinstance(sf.format(0.74), int)


# ─── Test 4: letter_grade ordering ──────────────────────────────

def test_letter_grade_ordering():
    sf = ScoringFormatter("letter_grade")
    assert sf.format(0.95) == "A+"
    assert sf.format(0.87) == "A"
    assert sf.format(0.79) == "B+"
    assert sf.format(0.70) == "B"
    assert sf.format(0.55) == "C"
    assert sf.format(0.40) == "D"
    assert sf.format(0.20) == "F"


# ─── Test 5: stars half-resolution ──────────────────────────────

def test_stars_half_resolution():
    sf = ScoringFormatter("stars")
    score = sf.format(0.75)   # raw = 1 + 0.75*4 = 4.0
    assert score == 4.0
    score2 = sf.format(0.625)  # raw = 3.5
    assert score2 == 3.5
    # Verify result is always a multiple of 0.5
    for raw in [0.1, 0.3, 0.55, 0.72, 0.88]:
        s = sf.format(raw)
        assert (s * 2) % 1 == 0, f"stars={s} is not a half-step multiple"


# ─── Test 6: signal_tier thresholds ─────────────────────────────

def test_signal_tier_thresholds():
    sf = ScoringFormatter("signal_tier")
    assert sf.format(0.95) == "S"
    assert sf.format(0.80) == "A"
    assert sf.format(0.65) == "B"
    assert sf.format(0.50) == "C"
    assert sf.format(0.20) == "D"


# ─── Test 7: conviction thresholds ──────────────────────────────

def test_conviction_thresholds():
    sf = ScoringFormatter("conviction")
    assert sf.format(0.70) == "HIGH"
    assert sf.format(0.50) == "MEDIUM"
    assert sf.format(0.20) == "LOW"


# ─── Test 8: calculate_composite_score weights ───────────────────

def test_composite_score_full_components():
    """All 4 components = 1.0 → composite = 1.0."""
    score = calculate_composite_score({
        "consensus_score": 1.0,
        "execution_score": 1.0,
        "regime_score":    1.0,
        "momentum_score":  1.0,
    })
    assert abs(score - 1.0) < 1e-6


def test_composite_score_zero_components():
    """All 4 components = 0 → composite = 0."""
    score = calculate_composite_score({
        "consensus_score": 0.0,
        "execution_score": 0.0,
        "regime_score":    0.0,
        "momentum_score":  0.0,
    })
    assert abs(score) < 1e-6


def test_composite_score_missing_defaults_to_neutral():
    """Missing components default to 0.5 (not 0)."""
    score_empty = calculate_composite_score({})
    assert abs(score_empty - 0.5) < 1e-6


# ─── Test 9: meets_threshold ─────────────────────────────────────

def test_meets_threshold_standard_100():
    sf = ScoringFormatter("standard_100")
    assert sf.meets_threshold(0.80) is True   # 80 >= 62
    assert sf.meets_threshold(0.50) is False  # 50 < 62


def test_meets_threshold_conviction():
    sf = ScoringFormatter("conviction")
    assert sf.meets_threshold(0.70) is True   # HIGH >= MEDIUM
    assert sf.meets_threshold(0.30) is False  # LOW < MEDIUM


def test_meets_threshold_letter_grade():
    sf = ScoringFormatter("letter_grade")
    assert sf.meets_threshold(0.70) is True   # B >= B threshold
    assert sf.meets_threshold(0.30) is False  # F < B


# ─── Test 10: format_all returns all 6 keys ──────────────────────

def test_format_all_keys():
    sf = ScoringFormatter("xmore_native")
    all_scores = sf.format_all(0.75)
    required_keys = {"xmore_native", "standard_100", "letter_grade", "stars", "signal_tier", "conviction"}
    assert required_keys == set(all_scores.keys())


# ─── Test 11: invalid mode raises ValueError ──────────────────────

def test_invalid_mode_raises():
    with pytest.raises(ValueError):
        ScoringFormatter("nonexistent_mode")


# ─── Test 12: build_scored_entry returns required keys ───────────

def test_build_scored_entry_required_keys():
    sf = ScoringFormatter("standard_100")
    rec = {
        "action": "BUY",
        "confidence": 75,
        "recommendation_date": "2026-03-14",
    }
    components = {
        "consensus_score": 0.75,
        "execution_score": 0.80,
        "regime_score":    1.0,
        "momentum_score":  0.65,
    }
    entry = sf.build_scored_entry("COMI.CA", rec, components)
    required = {
        "symbol", "signal_date", "action", "composite_score", "scoring_mode",
        "score_value", "consensus_score", "execution_score", "regime_score",
        "momentum_score", "meets_threshold", "all_formats", "created_at",
    }
    for key in required:
        assert key in entry, f"Missing key: {key}"
    assert entry["symbol"] == "COMI.CA"
    assert entry["scoring_mode"] == "standard_100"
    assert isinstance(entry["score_value"], str)
    assert isinstance(entry["composite_score"], float)


# ─── Test 13: clamp out-of-range inputs ──────────────────────────

def test_format_clamps_out_of_range():
    sf = ScoringFormatter("standard_100")
    assert sf.format(-0.5) == 0
    assert sf.format(1.5) == 100


# ─── Test 14: derive_components_from_rec with edge_ratio ─────────

def test_derive_components_edge_ratio():
    rec = {
        "confidence": 80,
        "edge_ratio": 9.0,
        "execution_approved": True,
    }
    comps = derive_components_from_rec(rec, regime="BULL")
    assert comps["consensus_score"] == pytest.approx(0.80, abs=0.01)
    assert comps["execution_score"] == pytest.approx(9.0 / 15.0, abs=0.01)
    assert comps["regime_score"] == 1.0


def test_derive_components_bear_regime():
    rec = {"confidence": 60}
    comps = derive_components_from_rec(rec, regime="BEAR")
    assert comps["regime_score"] == 0.0
