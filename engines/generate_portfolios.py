#!/usr/bin/env python3
"""
Cron orchestrator for model portfolio generation.
"""

import logging
import os
from datetime import datetime

from database import get_connection, is_postgres, sql_bool, sql_today
from engines.circuit_breaker import apply_circuit_breaker
from engines.performance_metrics import get_performance_summary
from engines.portfolio_engine import (
    CONFIGS,
    allocate_weights,
    collect_active_signals,
    filter_signals_for_portfolio,
    score_and_rank,
    validate_and_publish,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
DATABASE_URL = is_postgres()

REBALANCE_DAYS = {"conservative": 30, "balanced": 14, "aggressive": 7}


def _ph(idx: int) -> str:
    return "%s" if DATABASE_URL else "?"


def should_rebalance(portfolio_type: str) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT MAX(generated_at) AS max_generated_at FROM model_portfolios WHERE portfolio_type = {_ph(1)}",
            (portfolio_type,),
        )
        row = cursor.fetchone()
    if not row:
        return True
    last_date = row[0] if not isinstance(row, dict) else row.get("max_generated_at")
    if not last_date:
        return True
    days_since = (datetime.now(last_date.tzinfo) - last_date).days if getattr(last_date, "tzinfo", None) else (datetime.now() - last_date).days
    return days_since >= REBALANCE_DAYS[portfolio_type]


def update_daily_performance():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT id, portfolio_type FROM model_portfolios WHERE is_active = {sql_bool(True)}")
        portfolios = cursor.fetchall()

        for row in portfolios:
            portfolio_id = row[0] if not isinstance(row, dict) else row.get("id")
            cursor.execute(
                f"""
                SELECT pa.stock_symbol, pa.allocation_pct
                FROM portfolio_allocations pa
                WHERE pa.portfolio_id = {_ph(1)}
                """,
                (portfolio_id,),
            )
            allocations = cursor.fetchall()
            if not allocations:
                continue

            weighted_return = 0.0
            weighted_benchmark = 0.0
            wins = 0
            resolved = 0

            for alloc in allocations:
                stock_symbol = alloc[0] if not isinstance(alloc, dict) else alloc.get("stock_symbol")
                weight_pct = float(alloc[1] if not isinstance(alloc, dict) else alloc.get("allocation_pct") or 0)
                cursor.execute(
                    f"""
                    SELECT actual_next_day_return, benchmark_1d_return, was_correct
                    FROM trade_recommendations
                    WHERE symbol = {_ph(1)}
                      AND actual_next_day_return IS NOT NULL
                    ORDER BY recommendation_date DESC
                    LIMIT 1
                    """,
                    (stock_symbol,),
                )
                tr = cursor.fetchone()
                if not tr:
                    continue

                ret = float(tr[0] if not isinstance(tr, dict) else tr.get("actual_next_day_return") or 0)
                bench = float(tr[1] if not isinstance(tr, dict) else tr.get("benchmark_1d_return") or 0)
                was_correct = tr[2] if not isinstance(tr, dict) else tr.get("was_correct")
                weighted_return += (weight_pct / 100.0) * ret
                weighted_benchmark += (weight_pct / 100.0) * bench
                resolved += 1
                if was_correct in (True, 1, "t"):
                    wins += 1

            cursor.execute(
                f"""
                SELECT total_return_pct
                FROM portfolio_performance
                WHERE portfolio_id = {_ph(1)}
                ORDER BY snapshot_date DESC
                LIMIT 1
                """,
                (portfolio_id,),
            )
            last_row = cursor.fetchone()
            prev_total = float(last_row[0] if last_row and not isinstance(last_row, dict) else (last_row.get("total_return_pct") if last_row else 0) or 0)
            total_return = prev_total + weighted_return
            alpha = weighted_return - weighted_benchmark
            win_rate = (wins / resolved * 100.0) if resolved else 0.0

            # Pull rolling risk stats from existing metrics engine as a baseline.
            metrics = get_performance_summary(days=90, live_only=True)
            cursor.execute(
                f"""
                INSERT INTO portfolio_performance
                (portfolio_id, snapshot_date, total_return_pct, daily_return_pct, egx30_return_pct, alpha_pct,
                 sharpe_ratio, max_drawdown_pct, win_rate_pct)
                VALUES ({_ph(1)}, {sql_today()}, {_ph(2)}, {_ph(3)}, {_ph(4)}, {_ph(5)}, {_ph(6)}, {_ph(7)}, {_ph(8)})
                ON CONFLICT (portfolio_id, snapshot_date) DO UPDATE SET
                    total_return_pct = EXCLUDED.total_return_pct,
                    daily_return_pct = EXCLUDED.daily_return_pct,
                    egx30_return_pct = EXCLUDED.egx30_return_pct,
                    alpha_pct = EXCLUDED.alpha_pct,
                    sharpe_ratio = EXCLUDED.sharpe_ratio,
                    max_drawdown_pct = EXCLUDED.max_drawdown_pct,
                    win_rate_pct = EXCLUDED.win_rate_pct
                """,
                (
                    portfolio_id,
                    total_return,
                    weighted_return,
                    weighted_benchmark,
                    alpha,
                    metrics.get("sharpe_ratio", 0),
                    metrics.get("max_drawdown", 0),
                    win_rate,
                ),
            )


def generate_all_portfolios():
    all_signals = collect_active_signals()
    if not all_signals:
        logger.warning("No active signals found; skipping generation")
        return {}

    results = {}
    for portfolio_type, config in CONFIGS.items():
        try:
            if not should_rebalance(portfolio_type):
                results[portfolio_type] = "skipped"
                continue

            filtered = filter_signals_for_portfolio(all_signals, config)
            if not filtered:
                results[portfolio_type] = "no_signals"
                continue

            scored = score_and_rank(filtered)
            allocation = allocate_weights(scored, config)
            allocation = apply_circuit_breaker(portfolio_type, config, allocation)
            portfolio_id = validate_and_publish(portfolio_type, allocation, config)
            results[portfolio_type] = f"success:{portfolio_id}" if portfolio_id > 0 else "failed"
        except Exception as exc:
            logger.exception("Error processing %s", portfolio_type)
            results[portfolio_type] = f"error:{exc}"

    update_daily_performance()
    logger.info("Portfolio generation results: %s", results)
    return results


if __name__ == "__main__":
    generate_all_portfolios()
