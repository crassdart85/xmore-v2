"""
Kelly Criterion Capital Allocator — P4

Sizes each signal's position using a conservative fractional Kelly formula
derived from recent per-agent win-rate and average win/loss statistics.

Usage:
    from engines.kelly_allocator import KellyAllocator
    allocator = KellyAllocator(db_connection)
    signals = allocator.allocate(signals)   # adds 'kelly_position_pct' to each

Design:
  - Uses 25% of full Kelly (conservative; standard practice)
  - Win rate and avg win/loss pulled from last 30 days of trade_recommendations
  - Normalises across signals so total allocation ≤ 80% of portfolio
  - Falls back to equal weighting (8%) per signal when history is unavailable
  - Respects MAX_POSITION_PCT hard cap from execution_config

Reference:
  f = (W * b - (1-W)) / b
  where W = win rate, b = avg_win / avg_loss (odds ratio)
  Conservative Kelly = f * 0.25
"""

import logging
import math
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

try:
    from config.execution_config import MAX_POSITION_PCT
except ImportError:
    MAX_POSITION_PCT = 0.10

try:
    from database import get_connection
    import os
    _DATABASE_URL = os.getenv("DATABASE_URL")
except ImportError:
    get_connection = None
    _DATABASE_URL = None

# Allocation parameters
KELLY_FRACTION         = 0.25   # Use 25% of full Kelly (conservative)
MAX_TOTAL_EXPOSURE     = 0.80   # No more than 80% of portfolio deployed at once
DEFAULT_POSITION_PCT   = 0.08   # Fallback when no history available
MIN_KELLY_F            = 0.01   # Floor: never allocate less than 1%
HISTORY_DAYS           = 30     # Rolling window for win-rate stats


class KellyAllocator:
    """Allocates positions to signals using fractional Kelly Criterion."""

    def __init__(self, db_connection=None):
        self._conn = db_connection

    # ── Agent statistics ─────────────────────────────────────────────────────

    def get_agent_stats(self, agent_name: str,
                        symbol: Optional[str] = None) -> Dict[str, float]:
        """
        Fetch rolling 30-day win rate and average win/loss for an agent.
        Returns dict with: win_rate, avg_win_pct, avg_loss_pct, trade_count.
        Falls back to neutral defaults if data unavailable.
        """
        neutral = {
            "win_rate": 0.50,
            "avg_win_pct": 2.0,
            "avg_loss_pct": 1.5,
            "trade_count": 0,
        }

        conn = self._conn
        if conn is None:
            try:
                conn = get_connection().__enter__() if get_connection else None
            except Exception:
                return neutral
        if conn is None:
            return neutral

        ph = "%s" if _DATABASE_URL else "?"
        try:
            cursor = conn.cursor()
            sym_clause = f" AND symbol = {ph}" if symbol else ""
            params = [HISTORY_DAYS]
            if symbol:
                params.append(symbol)

            if _DATABASE_URL:
                date_filter = f"recommendation_date >= CURRENT_DATE - {ph}::integer"
            else:
                date_filter = f"recommendation_date >= date('now', '-' || {ph} || ' days')"

            cursor.execute(f"""
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN was_correct = {'TRUE' if _DATABASE_URL else '1'} THEN 1 ELSE 0 END) AS wins,
                    AVG(CASE WHEN was_correct = {'TRUE' if _DATABASE_URL else '1'}
                             THEN actual_next_day_return END) AS avg_win,
                    AVG(CASE WHEN was_correct = {'FALSE' if _DATABASE_URL else '0'}
                             THEN actual_next_day_return END) AS avg_loss
                FROM trade_recommendations
                WHERE agent_name = {ph}
                AND {date_filter}
                AND was_correct IS NOT NULL
                {sym_clause}
            """, [agent_name] + params)
            row = cursor.fetchone()
            if not row:
                return neutral

            total = int(row[0] or 0)
            wins  = int(row[1] or 0)
            if total < 5:
                return neutral  # Too little data

            win_rate   = wins / total
            avg_win    = abs(float(row[2] or 2.0))   # percentage
            avg_loss   = abs(float(row[3] or 1.5))   # percentage
            return {
                "win_rate":    win_rate,
                "avg_win_pct": max(avg_win, 0.01),
                "avg_loss_pct": max(avg_loss, 0.01),
                "trade_count": total,
            }
        except Exception as e:
            logger.debug("KellyAllocator: stats query failed for %s: %s", agent_name, e)
            return neutral

    # ── Kelly formula ────────────────────────────────────────────────────────

    @staticmethod
    def kelly_f(win_rate: float, avg_win_pct: float, avg_loss_pct: float) -> float:
        """
        Full Kelly fraction (as portfolio fraction).
        f = (W * b - (1-W)) / b   where b = avg_win / avg_loss.
        """
        if avg_win_pct <= 0 or avg_loss_pct <= 0:
            return 0.0
        b = avg_win_pct / avg_loss_pct
        f = (win_rate * b - (1 - win_rate)) / b if b > 0 else 0.0
        return max(f, 0.0)

    @staticmethod
    def conservative_kelly(win_rate: float,
                           avg_win_pct: float,
                           avg_loss_pct: float) -> float:
        """25% fractional Kelly, capped at MAX_POSITION_PCT."""
        full_f = KellyAllocator.kelly_f(win_rate, avg_win_pct, avg_loss_pct)
        frac   = full_f * KELLY_FRACTION
        return min(max(frac, MIN_KELLY_F), MAX_POSITION_PCT)

    # ── Main allocation ───────────────────────────────────────────────────────

    def allocate(self, signals: List[Dict]) -> List[Dict]:
        """
        Add 'kelly_position_pct' to each signal dict.

        Normalises allocations so the total across all signals never exceeds
        MAX_TOTAL_EXPOSURE. Signals without an 'agent_name' key use the
        DEFAULT_POSITION_PCT fallback.

        Args:
            signals: List of signal dicts (must contain at minimum 'agent_name').

        Returns:
            Same list with 'kelly_position_pct' added in-place.
        """
        if not signals:
            return signals

        raw_f: List[float] = []
        for sig in signals:
            agent  = sig.get("agent_name", "")
            symbol = sig.get("symbol", sig.get("ticker"))
            if agent:
                stats = self.get_agent_stats(agent, symbol)
                f = self.conservative_kelly(
                    stats["win_rate"],
                    stats["avg_win_pct"],
                    stats["avg_loss_pct"],
                )
            else:
                f = DEFAULT_POSITION_PCT
            raw_f.append(f)

        total_f = sum(raw_f)
        if total_f <= 0:
            for sig in signals:
                sig["kelly_position_pct"] = DEFAULT_POSITION_PCT
            return signals

        # Normalise so total ≤ MAX_TOTAL_EXPOSURE
        scale = min(MAX_TOTAL_EXPOSURE / total_f, 1.0)
        for sig, f in zip(signals, raw_f):
            normalised = round(f * scale, 4)
            sig["kelly_position_pct"] = max(normalised, MIN_KELLY_F)

        logger.debug(
            "KellyAllocator: allocated %d signals, total_f=%.3f, scale=%.3f",
            len(signals), total_f, scale,
        )
        return signals
