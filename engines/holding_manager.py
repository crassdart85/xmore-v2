"""
Holding Manager — replaces the hard 30-day exit with an intelligent trailing stop.

Activates a 6% trailing stop on day 20, lets winners run, and only uses the
45-day hard limit as an absolute failsafe.
"""

import logging
from datetime import date, timedelta

from config.execution_config import (
    TRAILING_STOP_ACTIVATION_DAY,
    TRAILING_STOP_PCT,
    HARD_MAX_HOLDING_DAYS,
)

logger = logging.getLogger("HoldingManager")

# EGX trades Sun–Thu; exclude Fri(4) and Sat(5)
_EGX_WEEKEND = {4, 5}


def _trading_days_held(entry_date, as_of_date=None) -> int:
    """Count EGX trading days (Sun–Thu) between entry and as_of_date (exclusive)."""
    if as_of_date is None:
        as_of_date = date.today()
    if isinstance(entry_date, str):
        entry_date = date.fromisoformat(entry_date)
    if isinstance(as_of_date, str):
        as_of_date = date.fromisoformat(as_of_date)
    count = 0
    current = entry_date + timedelta(days=1)
    while current <= as_of_date:
        if current.weekday() not in _EGX_WEEKEND:
            count += 1
        current += timedelta(days=1)
    return count


class HoldingManager:

    def __init__(self, db_connection):
        self.conn = db_connection

    # ── Position fetch ───────────────────────────────────────────────────────

    def get_open_positions(self) -> list:
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT id, symbol, entry_price, entry_date,
                       close_price          AS current_price,
                       highest_price_since_entry,
                       trailing_stop_price  AS stop_loss_price,
                       stop_loss_price      AS original_stop_loss,
                       target_price,
                       trailing_stop_active
                FROM trade_recommendations
                WHERE action = 'BUY'
                AND (execution_approved = 1 OR execution_approved IS NULL)
                AND actual_next_day_return IS NULL
            """)
        except Exception as e:
            logger.warning(f"[HoldingManager] get_open_positions query error: {e}")
            return []

        rows = cursor.fetchall()
        positions = []
        for row in rows:
            pos = dict(row) if hasattr(row, "keys") else dict(zip(
                ["id", "symbol", "entry_price", "entry_date", "current_price",
                 "highest_price_since_entry", "stop_loss_price",
                 "original_stop_loss", "target_price", "trailing_stop_active"],
                row,
            ))
            pos["days_held"] = _trading_days_held(pos.get("entry_date", date.today()))
            positions.append(pos)
        return positions

    # ── Trailing stop update ─────────────────────────────────────────────────

    def update_trailing_stop(self, position: dict, current_price: float) -> dict:
        pos = dict(position)
        pos["stop_updated"] = False

        if pos.get("days_held", 0) < TRAILING_STOP_ACTIVATION_DAY:
            return pos

        trailing_stop = current_price * (1 - TRAILING_STOP_PCT)
        existing_stop = pos.get("stop_loss_price") or 0.0
        new_stop      = max(existing_stop, trailing_stop)

        if new_stop != existing_stop:
            pos["stop_loss_price"]    = new_stop
            pos["trailing_stop_active"] = True
            pos["stop_updated"]       = True

        return pos

    # ── Exit decision ────────────────────────────────────────────────────────

    def should_exit(self, position: dict, current_price: float) -> dict:
        days_held      = position.get("days_held", 0)
        target_price   = position.get("target_price") or float("inf")
        stop_price     = position.get("stop_loss_price") or 0.0
        original_stop  = position.get("original_stop_loss") or 0.0

        # 1. Target hit
        if current_price >= target_price:
            return {
                "should_exit":         True,
                "reason":              "TARGET_REACHED",
                "recommended_action":  "SELL_LIMIT",
                "urgency":             "MEDIUM",
            }

        # 2. Trailing stop (day ≥ 20)
        if days_held >= TRAILING_STOP_ACTIVATION_DAY and stop_price > 0 and current_price <= stop_price:
            return {
                "should_exit":         True,
                "reason":              "TRAILING_STOP_TRIGGERED",
                "recommended_action":  "SELL_MARKET",
                "urgency":             "HIGH",
            }

        # 3. Hard stop
        if original_stop > 0 and current_price <= original_stop:
            return {
                "should_exit":         True,
                "reason":              "HARD_STOP_TRIGGERED",
                "recommended_action":  "SELL_MARKET",
                "urgency":             "HIGH",
            }

        # 4. Max holding days
        if days_held >= HARD_MAX_HOLDING_DAYS:
            return {
                "should_exit":         True,
                "reason":              "MAX_HOLDING_DAYS_REACHED",
                "recommended_action":  "SELL_MARKET",
                "urgency":             "HIGH",
            }

        return {
            "should_exit":         False,
            "reason":              "HOLD",
            "recommended_action":  "HOLD",
            "urgency":             "LOW",
        }

    # ── Daily check ──────────────────────────────────────────────────────────

    def run_daily_check(self, price_data: dict) -> list:
        """
        Iterate all open positions; return those requiring action today.
        price_data: {symbol: current_price}
        """
        positions      = self.get_open_positions()
        action_required = []

        for pos in positions:
            symbol        = pos["symbol"]
            current_price = price_data.get(symbol)

            if current_price is None:
                logger.debug(f"[HoldingManager] No price for {symbol} — skipping")
                continue

            # Update trailing stop if applicable
            updated_pos = self.update_trailing_stop(pos, current_price)

            # Check exit
            exit_info = self.should_exit(updated_pos, current_price)

            if exit_info["should_exit"]:
                action_required.append({
                    **updated_pos,
                    "current_price": current_price,
                    **exit_info,
                })
            elif updated_pos["stop_updated"]:
                # Stop raised but no exit yet — log for audit
                logger.info(
                    f"[HoldingManager] {symbol} trailing stop raised to "
                    f"{updated_pos['stop_loss_price']:.4f}"
                )

        return action_required
