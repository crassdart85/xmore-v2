"""
Shared friction estimates for offline backtests.

These helpers reuse the live execution realism primitives where historical
backtests have enough data (price + volume) to estimate slippage, ticket cost,
and fill quality without rewriting the execution model.
"""

from __future__ import annotations

from typing import Dict

try:
    from config.execution_config import BASE_DAILY_VOLATILITY, calculate_position_size
except ImportError:
    BASE_DAILY_VOLATILITY = 0.02

    def calculate_position_size(conviction_score, daily_volatility, max_loss_per_trade=0.015):
        daily_volatility = max(float(daily_volatility), 0.005)
        expected_stop_pct = max(daily_volatility * 2.0, 0.02)
        return min(max_loss_per_trade / expected_stop_pct, 0.10)

try:
    from engines.execution_agent import ExecutionAgent
except ImportError:
    ExecutionAgent = None


DEFAULT_PORTFOLIO_VALUE_EGP = 500_000.0
DEFAULT_CONVICTION_SCORE = 70.0


def estimate_directional_trade_return(
    direction: str,
    entry_price: float,
    exit_price: float,
    avg_daily_volume: float,
    portfolio_value_egp: float = DEFAULT_PORTFOLIO_VALUE_EGP,
    conviction_score: float = DEFAULT_CONVICTION_SCORE,
    daily_volatility: float = BASE_DAILY_VOLATILITY,
) -> Dict[str, float]:
    """
    Estimate gross/net directional return for a historical signal.

    Returns are expressed in percentage points on the signal. Net return applies:
    - slippage on entry and exit
    - liquidity-driven fill ratio scaling
    - round-trip transaction costs
    """
    direction = str(direction or "").upper()
    entry_price = float(entry_price or 0)
    exit_price = float(exit_price or 0)
    avg_daily_volume = max(int(avg_daily_volume or 0), 0)
    daily_volatility = max(float(daily_volatility or BASE_DAILY_VOLATILITY), 0.005)

    if direction not in {"UP", "DOWN"} or entry_price <= 0 or exit_price <= 0:
        return {
            "gross_direction_return_pct": 0.0,
            "net_direction_return_pct": 0.0,
            "fill_ratio": 0.0,
            "slippage_drag_pct": 0.0,
            "transaction_cost_pct": 0.0,
        }

    if ExecutionAgent is None:
        raw_return = ((exit_price - entry_price) / entry_price) * 100.0
        directional = raw_return if direction == "UP" else -raw_return
        return {
            "gross_direction_return_pct": directional,
            "net_direction_return_pct": directional,
            "fill_ratio": 1.0,
            "slippage_drag_pct": 0.0,
            "transaction_cost_pct": 0.0,
        }

    exec_agent = ExecutionAgent(portfolio_value_egp=portfolio_value_egp)
    position_pct = calculate_position_size(conviction_score, daily_volatility)
    shares_requested = int((portfolio_value_egp * position_pct) / entry_price) if entry_price > 0 else 0
    fill_info = exec_agent.calculate_fill(shares_requested, avg_daily_volume)
    fill_ratio = float(fill_info.get("fill_ratio", 0) or 0)
    shares_filled = int(shares_requested * fill_ratio)

    raw_return = ((exit_price - entry_price) / entry_price) * 100.0
    gross_direction_return = raw_return if direction == "UP" else -raw_return

    if shares_filled <= 0:
        return {
            "gross_direction_return_pct": gross_direction_return,
            "net_direction_return_pct": 0.0,
            "fill_ratio": 0.0,
            "slippage_drag_pct": 0.0,
            "transaction_cost_pct": 0.0,
        }

    entry_fill = exec_agent.apply_slippage(entry_price, "BUY" if direction == "UP" else "SELL", "BT", avg_daily_volume)
    exit_fill = exec_agent.apply_slippage(exit_price, "SELL" if direction == "UP" else "BUY", "BT", avg_daily_volume)

    if direction == "UP":
        slipped_direction_return = ((exit_fill - entry_fill) / entry_fill) * 100.0
    else:
        slipped_direction_return = ((entry_fill - exit_fill) / entry_fill) * 100.0

    position_value = entry_fill * shares_filled
    if position_value <= 0:
        transaction_cost_pct = 0.0
    else:
        transaction_cost_pct = (exec_agent.calculate_round_trip_cost(position_value) / position_value) * 100.0

    scaled_return = slipped_direction_return * fill_ratio
    net_direction_return = scaled_return - transaction_cost_pct
    slippage_drag = gross_direction_return - slipped_direction_return

    return {
        "gross_direction_return_pct": round(gross_direction_return, 6),
        "net_direction_return_pct": round(net_direction_return, 6),
        "fill_ratio": round(fill_ratio, 6),
        "slippage_drag_pct": round(slippage_drag, 6),
        "transaction_cost_pct": round(transaction_cost_pct, 6),
    }
