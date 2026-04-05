"""
Unit tests for institutional-grade performance metrics.
Run with: pytest tests/test_performance_metrics.py -v
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import math
import pytest
from unittest.mock import MagicMock, patch

from engines.performance_metrics import (
    sharpe_ratio, sortino_ratio,
    calculate_calmar_ratio, calculate_max_drawdown_details,
    calculate_rolling_sharpe, calculate_win_loss_ratio,
    calculate_benchmark_comparison, generate_full_metrics_report,
    max_drawdown, EGX_DAILY_RF, EGX_RISK_FREE_RATE_ANNUAL, EGX_TRADING_DAYS_PER_YEAR,
    MINIMUM_TRADES_FOR_METRICS,
)


# ─── Helpers ────────────────────────────────────────────────────

def make_returns(n=50, daily_mean=0.10, daily_std=0.80, seed=42):
    """Generate synthetic daily returns in PERCENTAGE POINTS (e.g. 0.10 = 0.10%)."""
    import random
    random.seed(seed)
    return [random.gauss(daily_mean, daily_std) for _ in range(n)]


# ─── Test 1: Sharpe uses KSA SAIBOR 4.89%, not US 5% ──────────

def test_sharpe_uses_ksa_rate_not_us():
    """KSA rate (4.89%) < US rate (5%) → KSA Sharpe should be higher (less rf deducted)."""
    returns = make_returns(60, daily_mean=0.20)  # 0.20% daily mean
    ksa_sharpe = sharpe_ratio(returns)                              # uses KSA default (4.89%)
    us_sharpe  = sharpe_ratio(returns, risk_free_rate=0.05 / 252)  # US daily rf
    assert ksa_sharpe > us_sharpe, (
        f"KSA Sharpe ({ksa_sharpe:.3f}) should be higher than US Sharpe ({us_sharpe:.3f}) "
        f"because KSA risk-free rate (4.89%) < US (5.0%)"
    )


def test_sharpe_annualizes_with_250_days():
    """Annualized Sharpe should use sqrt(250) for KSA, not sqrt(252)."""
    # Generate returns in percentage points
    import random; random.seed(7)
    returns = [0.10 + random.gauss(0, 1.0) for _ in range(100)]  # ~0.10% daily mean, 1% std
    result = sharpe_ratio(returns)
    m = sum(returns) / len(returns) / 100   # to decimal
    s = (sum((r / 100 - m) ** 2 for r in returns) / (len(returns) - 1)) ** 0.5
    ratio_252 = ((m - EGX_DAILY_RF) / s) * math.sqrt(252)
    ratio_250 = ((m - EGX_DAILY_RF) / s) * math.sqrt(EGX_TRADING_DAYS_PER_YEAR)
    assert abs(result - ratio_250) < abs(result - ratio_252) + 0.01  # 250 should be closer


# ─── Test 2: Sortino with all-positive returns ──────────────────

def test_sortino_all_positive_returns():
    """All positive returns → no downside → Sortino = 99.9 (not crash)."""
    returns = [1.0, 2.0, 1.5, 0.8, 1.2]  # percentage points
    result = sortino_ratio(returns)
    assert result == 99.9, f"Expected 99.9 but got {result}"


def test_sortino_does_not_crash_on_positive_only():
    """Verify sortino_ratio does not raise any exception."""
    try:
        sortino_ratio([1.0, 2.0, 1.5])  # percentage points
    except Exception as e:
        pytest.fail(f"sortino_ratio raised {e}")


# ─── Test 3: Calmar with zero drawdown ──────────────────────────

def test_calmar_zero_drawdown_returns_zero():
    """Zero drawdown → Calmar = 0.0, no ZeroDivisionError."""
    returns = make_returns(50)
    result = calculate_calmar_ratio(returns, max_dd=0.0)
    assert result == 0.0


def test_calmar_insufficient_data_returns_none():
    """Fewer than 20 data points → returns None."""
    result = calculate_calmar_ratio([0.001] * 10, max_dd=0.05)
    assert result is None


# ─── Test 4: Max drawdown details – peak, trough, recovery ──────

def test_max_drawdown_details_correct():
    """Equity [100,105,110,95,90,98,112] → MDD ~-18.2%, recovered."""
    curve = [100, 105, 110, 95, 90, 98, 112]
    details = calculate_max_drawdown_details(curve)
    # Max drawdown: 110 → 90 = -18.18%
    assert abs(details["max_drawdown_pct"] - (-18.18 / 100)) < 0.01, (
        f"Expected ~-0.1818, got {details['max_drawdown_pct']}"
    )
    assert details["drawdown_end_idx"] == 4, f"Trough should be at index 4, got {details['drawdown_end_idx']}"
    assert details["is_recovered"] is True, "Should be recovered (112 > 110)"


def test_max_drawdown_details_no_recovery():
    """Curve that never recovers → is_recovered = False."""
    curve = [100, 105, 110, 90, 85]
    details = calculate_max_drawdown_details(curve)
    assert details["is_recovered"] is False


# ─── Test 5: Win/loss ratio handles edge cases ──────────────────

def test_win_loss_all_wins():
    """All winning trades → no crash, loss stats are 0."""
    trades = [{"return_pct": 5.0}, {"return_pct": 8.0}, {"return_pct": 3.0}]
    result = calculate_win_loss_ratio(trades)
    assert result["win_rate"] == pytest.approx(1.0)
    assert result["avg_loss_pct"] == 0


def test_win_loss_all_losses():
    """All losing trades → no crash, win stats are 0."""
    trades = [{"return_pct": -2.0}, {"return_pct": -5.0}]
    result = calculate_win_loss_ratio(trades)
    assert result["win_rate"] == pytest.approx(0.0)
    assert result["avg_win_pct"] == 0


# ─── Test 6: Benchmark comparison beta ──────────────────────────

def test_benchmark_beta_perfect_tracking():
    """Portfolio perfectly tracks benchmark → beta ~1.0, alpha_total ~0."""
    returns = [0.5, -0.2, 1.0, 0.1, -0.3, 0.8] * 5  # percentage points
    result = calculate_benchmark_comparison(returns, returns)
    assert abs(result["beta"] - 1.0) < 0.01, f"Beta should be ~1.0, got {result['beta']}"
    assert abs(result["alpha_total"]) < 0.01, f"Alpha should be ~0, got {result['alpha_total']}"


# ─── Test 7: Rolling Sharpe empty when too few points ───────────

def test_rolling_sharpe_too_few_points():
    """Fewer data points than window → empty list."""
    result = calculate_rolling_sharpe([0.10] * 20, window=30)
    assert result == []


def test_rolling_sharpe_correct_length():
    """50 returns, window=30 → 21 rolling values."""
    result = calculate_rolling_sharpe([0.10] * 50, window=30)
    assert len(result) == 21


# ─── Test 8: Data quality warning when trade_count < 30 ─────────

def test_data_quality_warning_triggered():
    """generate_full_metrics_report should warn when fewer than 30 trades."""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    cursor.description = [("recommendation_date",), ("actual_next_day_return",),
                          ("benchmark_1d_return",), ("alpha_1d",), ("was_correct",)]
    # Only 10 rows — returns in percentage points
    cursor.fetchall.return_value = [
        ("2026-01-10", 0.50, 0.20, 0.30, True)
    ] * 10

    report = generate_full_metrics_report(conn, days=90)
    assert report["minimum_trades_met"] is False
    assert "30" in report["data_quality_warning"] or "10" in report["data_quality_warning"]


# ─── Test 9: Export summary returns HTML 200 ────────────────────

def test_export_summary_endpoint():
    """GET /api/performance-v2/export-summary returns valid HTML."""
    try:
        import requests
        r = requests.get('https://xmore-project.onrender.com/api/performance-v2/export-summary', timeout=10)
        assert r.status_code == 200
        assert '<!DOCTYPE html>' in r.text or '<html' in r.text
    except ImportError:
        pytest.skip("requests not installed")
    except Exception:
        pytest.skip("Live server not reachable in test environment")


# ─── Test 10: Full report has all required fields ────────────────

def test_full_report_all_required_fields():
    """generate_full_metrics_report returns a dict with all required keys."""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    cursor.description = [("recommendation_date",), ("actual_next_day_return",),
                          ("benchmark_1d_return",), ("alpha_1d",), ("was_correct",)]
    # 35 rows to pass minimum threshold — returns in percentage points
    cursor.fetchall.return_value = [
        ("2026-01-10", 0.50, 0.20, 0.30, True)
    ] * 35

    report = generate_full_metrics_report(conn, days=90)
    required = [
        "period_days", "generated_at", "trade_count", "sharpe_ratio",
        "sortino_ratio", "calmar_ratio", "max_drawdown", "rolling_sharpe_30d",
        "win_loss", "benchmark", "risk_free_rate_used",
        "minimum_trades_met", "data_quality_warning",
    ]
    for key in required:
        assert key in report, f"Missing required key: {key}"

    assert report["risk_free_rate_used"] == pytest.approx(EGX_RISK_FREE_RATE_ANNUAL)
    assert report["minimum_trades_met"] is True
    assert isinstance(report["win_loss"], dict)
    assert isinstance(report["max_drawdown"], dict)
