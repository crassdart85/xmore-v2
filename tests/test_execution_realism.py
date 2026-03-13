"""
Unit tests for the execution realism layer.
Run with: pytest tests/test_execution_realism.py -v
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch, MagicMock
import pandas as pd
import pytest

from engines.execution_agent import ExecutionAgent
from engines.holding_manager import HoldingManager, _trading_days_held
from config.execution_config import EGX_MIN_TICKET_EGP, MIN_EDGE_TO_COST_RATIO


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def agent():
    return ExecutionAgent(portfolio_value_egp=500_000)


# ─── Test 1: Minimum ticket rule on small position ───────────────────────────

def test_round_trip_cost_minimum_ticket(agent):
    """Position of 500 EGP → cost = 2 × min ticket (30 EGP), not ~3.5 EGP."""
    cost = agent.calculate_round_trip_cost(500.0)
    assert cost == EGX_MIN_TICKET_EGP * 2, (
        f"Expected {EGX_MIN_TICKET_EGP * 2} EGP but got {cost}"
    )


# ─── Test 2: Low-return signal rejected ──────────────────────────────────────

def test_minimum_edge_rejects_low_return(agent):
    """1.5% return, ~0.7% round-trip → edge ratio ≈ 2.1 → REJECTED."""
    # Use a large position so minimum ticket doesn't dominate
    result = agent.check_minimum_edge(
        expected_return_pct=0.015,
        position_value_egp=100_000,
    )
    assert result["approved"] is False
    assert result["edge_ratio"] < MIN_EDGE_TO_COST_RATIO


# ─── Test 3: High-return signal approved ─────────────────────────────────────

def test_minimum_edge_approves_high_return(agent):
    """13% return, ~0.7% round-trip → edge ratio ≈ 18.6 → APPROVED."""
    result = agent.check_minimum_edge(
        expected_return_pct=0.13,
        position_value_egp=100_000,
    )
    assert result["approved"] is True
    assert result["edge_ratio"] >= MIN_EDGE_TO_COST_RATIO


# ─── Test 4: Slippage direction ──────────────────────────────────────────────

def test_slippage_raises_buy_lowers_sell(agent):
    """Medium-tier stock: BUY fill > raw; SELL fill < raw."""
    # Force medium tier: ADV = 2M EGP (volume=200k shares, price=10)
    buy_price  = agent.apply_slippage(10.0, "BUY",  "TEST.CA", avg_daily_volume=200_000)
    sell_price = agent.apply_slippage(10.0, "SELL", "TEST.CA", avg_daily_volume=200_000)
    assert buy_price  > 10.0, "BUY fill should be above raw price"
    assert sell_price < 10.0, "SELL fill should be below raw price"
    # Medium tier = 25 bps
    assert abs(buy_price  - 10.025) < 0.001
    assert abs(sell_price - 9.975)  < 0.001


# ─── Test 5: EGX gap risk floors stop at daily limit ─────────────────────────

def test_egx_gap_risk_floors_stop(agent):
    """prev_close=100, stop=88 (< 90 limit floor) → realistic_stop=90."""
    result = agent.apply_egx_gap_risk(stop_price=88.0, prev_close=100.0)
    assert result == pytest.approx(90.0, rel=1e-4)


def test_egx_gap_risk_leaves_valid_stop(agent):
    """prev_close=100, stop=92 (above 90 floor) → unchanged."""
    result = agent.apply_egx_gap_risk(stop_price=92.0, prev_close=100.0)
    assert result == pytest.approx(92.0, rel=1e-4)


# ─── Test 6: Regime filter blocks new longs in BEAR market ───────────────────

def test_regime_filter_blocks_longs_in_bear():
    """When EGX30 is below MA20, is_long_allowed() must return False."""
    from engines.regime_filter import RegimeFilter

    bear_data = pd.DataFrame({
        "Date":  pd.date_range("2026-01-01", periods=25, freq="D"),
        "Close": [100] * 5 + [95] * 20,   # price drops below initial MA
    })

    rf = RegimeFilter()
    with patch.object(rf, "fetch_egx30_data", return_value=bear_data):
        allowed, reason = rf.is_long_allowed()

    assert allowed is False
    assert "BLOCKED" in reason or "BEAR" in reason or "NEUTRAL" in reason


# ─── Test 7 & 8: Trailing stop activation and ratchet ────────────────────────

def test_trailing_stop_not_active_before_day20():
    """Day 19: update_trailing_stop should NOT set a higher stop."""
    conn = MagicMock()
    hm = HoldingManager(conn)
    pos = {
        "days_held":      19,
        "stop_loss_price": 9.0,
        "trailing_stop_active": False,
    }
    updated = hm.update_trailing_stop(pos, current_price=10.0)
    assert updated["stop_updated"] is False
    assert updated["stop_loss_price"] == 9.0


def test_trailing_stop_activates_at_day20():
    """Day 20: trailing stop = current × 0.94 — should raise the stop."""
    conn = MagicMock()
    hm = HoldingManager(conn)
    pos = {
        "days_held":       20,
        "stop_loss_price": 8.0,   # lower than 9.4
        "trailing_stop_active": False,
    }
    updated = hm.update_trailing_stop(pos, current_price=10.0)
    assert updated["stop_updated"] is True
    assert abs(updated["stop_loss_price"] - 9.4) < 0.001


def test_trailing_stop_never_moves_down():
    """Day 21: price drops to 9.8 — trailing stop must stay at 9.4, not fall to 9.21."""
    conn = MagicMock()
    hm = HoldingManager(conn)
    # Simulate: stop already at 9.4 from previous day
    pos = {
        "days_held":       21,
        "stop_loss_price": 9.4,
        "trailing_stop_active": True,
    }
    updated = hm.update_trailing_stop(pos, current_price=9.8)
    assert updated["stop_loss_price"] >= 9.4, (
        "Trailing stop must never decrease"
    )


# ─── Test 9: Order splitting ──────────────────────────────────────────────────

def test_order_splitting(agent):
    """15,000 shares, ADV=100,000 → cap=3,000 → [3000,3000,3000,3000,3000]."""
    schedule = agent.split_order(total_shares=15_000, avg_daily_volume=100_000)
    assert sum(schedule) == 15_000
    assert all(s <= 3_000 for s in schedule)
    assert len(schedule) == 5


# ─── Test 10: Max holding days triggers SELL_MARKET ──────────────────────────

def test_max_holding_days_triggers_sell_market():
    """days_held=45 → should_exit returns should_exit=True, SELL_MARKET."""
    conn = MagicMock()
    hm = HoldingManager(conn)
    pos = {
        "days_held":        45,
        "target_price":     15.0,
        "stop_loss_price":  7.0,
        "original_stop_loss": 7.0,
        "trailing_stop_active": True,
    }
    result = hm.should_exit(pos, current_price=10.0)
    assert result["should_exit"] is True
    assert result["reason"] == "MAX_HOLDING_DAYS_REACHED"
    assert result["recommended_action"] == "SELL_MARKET"
    assert result["urgency"] == "HIGH"
