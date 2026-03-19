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
        self._stats_cache: Dict[str, Dict[str, float]] = {}

    # ── Agent statistics ─────────────────────────────────────────────────────

    def get_signal_stats(self, symbol: Optional[str] = None) -> Dict[str, float]:
        """
        Fetch rolling-window BUY performance stats.

        Priority:
          1) Symbol-specific BUY stats (if symbol provided and enough samples)
          2) Global BUY stats fallback

        Returns dict with: win_rate, avg_win_pct, avg_loss_pct, trade_count.
        Falls back to neutral defaults if data unavailable.
        """
        neutral = {
            "win_rate": 0.50,
            "avg_win_pct": 2.0,
            "avg_loss_pct": 1.5,
            "trade_count": 0,
        }

        cache_key = (symbol or "_GLOBAL_").upper()
        if cache_key in self._stats_cache:
            return self._stats_cache[cache_key]

        conn = self._conn
        if conn is None:
            return neutral
        if conn is None:
            return neutral

        ph = "%s" if _DATABASE_URL else "?"

        def _fetch(sym: Optional[str]) -> Optional[Dict[str, float]]:
            cursor = conn.cursor()
            sym_clause = f" AND symbol = {ph}" if sym else ""
            params = []
            if sym:
                params.append(sym)

            if _DATABASE_URL:
                date_filter = f"recommendation_date >= CURRENT_DATE - INTERVAL '{HISTORY_DAYS} days'"
            else:
                date_filter = f"recommendation_date >= date('now', '-{HISTORY_DAYS} days')"

            cursor.execute(f"""
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN actual_next_day_return > 0 THEN 1 ELSE 0 END) AS wins,
                    AVG(CASE WHEN actual_next_day_return > 0
                             THEN actual_next_day_return END) AS avg_win,
                    AVG(CASE WHEN actual_next_day_return < 0
                             THEN ABS(actual_next_day_return) END) AS avg_loss
                FROM trade_recommendations
                WHERE action = 'BUY'
                  AND actual_next_day_return IS NOT NULL
                  AND (is_live = {'TRUE' if _DATABASE_URL else '1'} OR is_live IS NULL)
                  AND {date_filter}
                  {sym_clause}
            """, params)
            row = cursor.fetchone()
            if not row:
                return None

            total = int(row[0] or 0)
            wins = int(row[1] or 0)
            if total < 5:
                return None

            avg_win = abs(float(row[2] or 2.0))   # percentage
            avg_loss = abs(float(row[3] or 1.5))  # percentage
            return {
                "win_rate": wins / total,
                "avg_win_pct": max(avg_win, 0.01),
                "avg_loss_pct": max(avg_loss, 0.01),
                "trade_count": total,
            }

        try:
            stats = _fetch(symbol) if symbol else None
            if not stats:
                stats = _fetch(None)  # global fallback
            if not stats:
                stats = neutral
            self._stats_cache[cache_key] = stats
            return stats
        except Exception as e:
            logger.debug("KellyAllocator: stats query failed for %s: %s", symbol or "_GLOBAL_", e)
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
        Normalises allocations so combined Kelly exposure never exceeds
        MAX_TOTAL_EXPOSURE.

        Args:
            signals: List of signal dicts (should contain at minimum 'symbol' or 'ticker').

        Returns:
            Same list with 'kelly_position_pct' added in-place.
        """
        if not signals:
            return signals

        raw_f: List[float] = []
        for sig in signals:
            symbol = sig.get("symbol", sig.get("ticker"))
            stats = self.get_signal_stats(symbol)
            f = self.conservative_kelly(
                stats["win_rate"],
                stats["avg_win_pct"],
                stats["avg_loss_pct"],
            )

            # Confidence-aware modulation keeps Kelly responsive to current signal quality.
            try:
                confidence = float(sig.get("confidence", 50) or 50)
            except Exception:
                confidence = 50.0
            conf_mult = min(max(confidence / 70.0, 0.70), 1.20)
            f = min(max(f * conf_mult, MIN_KELLY_F), MAX_POSITION_PCT)
            raw_f.append(f)

        total_f = sum(raw_f)
        if total_f <= 0:
            for sig in signals:
                sig["kelly_position_pct"] = DEFAULT_POSITION_PCT
            return signals

        # Normalise so total ≤ MAX_TOTAL_EXPOSURE
        scale = min(MAX_TOTAL_EXPOSURE / total_f, 1.0)
        effective_floor = min(MIN_KELLY_F, MAX_TOTAL_EXPOSURE / max(len(signals), 1))
        scaled_allocations = [max(round(f * scale, 4), effective_floor) for f in raw_f]
        scaled_total = sum(scaled_allocations)
        if scaled_total > MAX_TOTAL_EXPOSURE and scaled_total > 0:
            cap_scale = MAX_TOTAL_EXPOSURE / scaled_total
            scaled_allocations = [round(v * cap_scale, 4) for v in scaled_allocations]

        for sig, alloc in zip(signals, scaled_allocations):
            sig["kelly_position_pct"] = alloc

        logger.debug(
            "KellyAllocator: allocated %d signals, total_f=%.3f, scale=%.3f",
            len(signals), total_f, scale,
        )
        return signals
