"""
Execution Realism Agent — gates every trade signal through friction-aware checks.

Applies EGX-specific transaction costs, slippage, partial fill simulation,
minimum edge filtering, and gap risk before a signal becomes a recommendation.
"""

import logging
from config.execution_config import (
    SLIPPAGE_TIERS, FILL_THRESHOLDS, MAX_ADV_PARTICIPATION,
    EGX_ROUND_TRIP_RATE, EGX_MIN_TICKET_EGP, EGX_DAILY_LIMIT_PCT,
    MAX_POSITION_PCT, MIN_EDGE_TO_COST_RATIO,
)


class ExecutionAgent:

    def __init__(self, portfolio_value_egp: float):
        self.portfolio_value_egp = portfolio_value_egp
        self.logger = logging.getLogger("ExecutionAgent")

    # ── Liquidity ────────────────────────────────────────────────────────────

    def get_liquidity_tier(self, avg_daily_volume: int, price: float) -> str:
        adv_egp = avg_daily_volume * price
        if adv_egp >= SLIPPAGE_TIERS["high"]["min_adv_egp"]:
            return "high"
        if adv_egp >= SLIPPAGE_TIERS["medium"]["min_adv_egp"]:
            return "medium"
        return "low"

    # ── Slippage ─────────────────────────────────────────────────────────────

    def apply_slippage(self, price: float, direction: str,
                       ticker: str, avg_daily_volume: int) -> float:
        tier = self.get_liquidity_tier(avg_daily_volume, price)
        bps = SLIPPAGE_TIERS[tier]["bps"]
        if direction.upper() == "BUY":
            result = price * (1 + bps / 10_000)
        else:
            result = price * (1 - bps / 10_000)
        self.logger.debug(
            f"[SLIPPAGE] {ticker} {direction} raw={price:.4f} "
            f"adj={result:.4f} tier={tier}"
        )
        return result

    # ── Partial fill ─────────────────────────────────────────────────────────

    def calculate_fill(self, shares_requested: int, avg_daily_volume: int) -> dict:
        if avg_daily_volume <= 0:
            return {"fill_ratio": 0.30, "wait_days": 5, "split_required": True}
        participation = shares_requested / avg_daily_volume
        fill_ratio, wait_days = 0.30, 5
        for tier in FILL_THRESHOLDS:
            if participation <= tier["max_adv_pct"]:
                fill_ratio = tier["fill_ratio"]
                wait_days  = tier["wait_days"]
                break
        return {
            "fill_ratio":     fill_ratio,
            "wait_days":      wait_days,
            "split_required": participation > MAX_ADV_PARTICIPATION,
        }

    # ── Cost ─────────────────────────────────────────────────────────────────

    def calculate_round_trip_cost(self, position_value_egp: float) -> float:
        return max(
            position_value_egp * EGX_ROUND_TRIP_RATE,
            EGX_MIN_TICKET_EGP * 2,
        )

    # ── Edge check ───────────────────────────────────────────────────────────

    def check_minimum_edge(self, expected_return_pct: float,
                           position_value_egp: float) -> dict:
        cost = self.calculate_round_trip_cost(position_value_egp)
        cost_pct = cost / position_value_egp if position_value_egp > 0 else 1.0
        edge_ratio = expected_return_pct / cost_pct if cost_pct > 0 else 0.0
        approved = edge_ratio >= MIN_EDGE_TO_COST_RATIO
        return {
            "approved":   approved,
            "edge_ratio": round(edge_ratio, 2),
            "cost_pct":   round(cost_pct * 100, 3),
            "reason":     "APPROVED" if approved
                          else f"REJECTED: edge {edge_ratio:.1f}x < required {MIN_EDGE_TO_COST_RATIO}x",
        }

    # ── Gap risk ─────────────────────────────────────────────────────────────

    def apply_egx_gap_risk(self, stop_price: float, prev_close: float) -> float:
        floor = prev_close * (1 - EGX_DAILY_LIMIT_PCT)
        if stop_price < floor:
            return floor
        return stop_price

    # ── Order splitting ──────────────────────────────────────────────────────

    def split_order(self, total_shares: int, avg_daily_volume: int) -> list:
        cap = int(MAX_ADV_PARTICIPATION * avg_daily_volume)
        if cap <= 0:
            return [total_shares]
        schedule = []
        remaining = total_shares
        while remaining > 0:
            child = min(remaining, cap)
            schedule.append(child)
            remaining -= child
        return schedule

    # ── Master evaluation ────────────────────────────────────────────────────

    def evaluate_signal(self, signal: dict, market_data: dict) -> dict:
        ticker           = signal["ticker"]
        action           = signal["action"].upper()
        raw_price        = signal["raw_price"]
        expected_return  = signal["expected_return_pct"]   # already a fraction, e.g. 0.13
        stop_loss_pct    = signal["stop_loss_pct"]
        avg_daily_volume = market_data["avg_daily_volume"]
        prev_close       = market_data["prev_close"]
        portfolio_value  = market_data.get("portfolio_value_egp", self.portfolio_value_egp)

        # 1. Max shares based on position sizing
        max_shares = int((portfolio_value * MAX_POSITION_PCT) / raw_price) if raw_price > 0 else 0

        # 2. Fill simulation
        fill_info      = self.calculate_fill(max_shares, avg_daily_volume)
        fill_ratio     = fill_info["fill_ratio"]
        split_required = fill_info["split_required"]

        # 3. Effective shares after fill
        effective_shares = int(max_shares * fill_ratio)

        # 4. Slippage-adjusted entry price
        fill_price = self.apply_slippage(raw_price, action, ticker, avg_daily_volume)

        # 5. Position value
        position_value = fill_price * effective_shares

        # 6. Edge check — expected_return_pct is a fraction (0.13 = 13%)
        edge_check = self.check_minimum_edge(expected_return, position_value)
        final_action = action if edge_check["approved"] else "BLOCKED"

        # 7. Realistic stop (gap risk)
        raw_stop = raw_price * (1 - stop_loss_pct)
        realistic_stop = self.apply_egx_gap_risk(raw_stop, prev_close)

        # 8. Split schedule
        split_schedule = self.split_order(max_shares, avg_daily_volume) if split_required else []

        round_trip_cost = self.calculate_round_trip_cost(position_value)

        return {
            "ticker":                   ticker,
            "action":                   final_action,
            "raw_signal_price":         raw_price,
            "realistic_fill_price":     fill_price,
            "shares_requested":         max_shares,
            "shares_expected":          effective_shares,
            "position_value_egp":       position_value,
            "round_trip_cost_egp":      round_trip_cost,
            "cost_as_pct_of_position":  edge_check["cost_pct"],
            "edge_ratio":               edge_check["edge_ratio"],
            "approved":                 edge_check["approved"],
            "split_required":           split_required,
            "split_schedule":           split_schedule,
            "realistic_stop_price":     realistic_stop,
            "rejection_reason":         "" if edge_check["approved"] else edge_check["reason"],
        }
