"""
Performance Evaluation Engine (v2)
Replaces evaluate_trades.py

Responsibilities:
1. Resolve outcome fields on trade_recommendations (existing)
2. Calculate benchmark returns (TASI) over same periods
3. Calculate alpha vs TASI
4. Resolve user_positions with benchmark comparison
5. Track per-agent accuracy contribution

Runs as Step 8 in the daily pipeline.
"""

import os
import traceback
from database import get_connection

MODEL_VERSION = "v1.0"  # Increment on agent/pipeline changes
DATABASE_URL = os.getenv('DATABASE_URL')

# TASI benchmark symbols to try (in order of preference)
# TASI.INDX is written by engines/fetch_tasi_benchmark.py
# 2222.SR (Aramco) is a ~15% weight proxy of last resort
EGX30_SYMBOLS = ['TASI.INDX', '^TASI', '2222.SR']  # alias kept for internal use


# ─── SQL HELPERS ───────────────────────────────────────────────

def _ph(index):
    """Return placeholder for parameterized query: %s (Postgres) or ? (SQLite)."""
    return '%s' if DATABASE_URL else '?'


def _interval(days):
    """Return date interval expression appropriate for the current DB."""
    if DATABASE_URL:
        return f"CURRENT_DATE - INTERVAL '{days} days'"
    else:
        return f"date('now', '-{days} days')"


def _now():
    """Return NOW() expression for the current DB."""
    return "NOW()" if DATABASE_URL else "datetime('now')"


def _query(cursor, sql, params=None):
    """Execute query and return list of dicts."""
    if DATABASE_URL:
        cursor.execute(sql, params or [])
    else:
        cursor.execute(sql, params or [])
    columns = [desc[0] for desc in cursor.description] if cursor.description else []
    rows = cursor.fetchall()
    result = []
    for row in rows:
        if isinstance(row, dict):
            result.append(row)
        else:
            result.append(dict(zip(columns, row)))
    return result


def _execute(cursor, sql, params=None):
    """Execute an update/insert statement."""
    if DATABASE_URL:
        cursor.execute(sql, params or [])
    else:
        cursor.execute(sql, params or [])


# ─── MAIN ENTRY POINT ─────────────────────────────────────────

def run_evaluation(pipeline_run_id: str = None):
    """
    Full evaluation pass. Called daily after briefing generation.
    """
    print("[Evaluate] Starting performance evaluation...")

    try:
        # 1. Resolve 1-day outcomes + benchmarks
        resolved_1d = resolve_1day_outcomes()
        print(f"[Evaluate] Resolved {resolved_1d} 1-day outcomes")

        # 2. Resolve 5-day outcomes + benchmarks
        resolved_5d = resolve_5day_outcomes()
        print(f"[Evaluate] Resolved {resolved_5d} 5-day outcomes")

        # 3. Resolve closed positions with benchmarks
        resolved_pos = resolve_position_benchmarks()
        print(f"[Evaluate] Resolved {resolved_pos} position benchmarks")

        # 4. Update per-agent accuracy snapshots (PostgreSQL only)
        if DATABASE_URL:
            try:
                update_agent_accuracy_snapshot()
                print("[Evaluate] Agent accuracy snapshot updated")
            except Exception as e:
                print(f"[Evaluate] Agent snapshot skipped (concurrent run / deadlock): {e}")

        # 5. Refresh materialized performance views (PostgreSQL only)
        if DATABASE_URL:
            try:
                refresh_performance_views()
                print("[Evaluate] Performance views refreshed")
            except Exception as e:
                print(f"[Evaluate] Performance views skipped: {e}")

        print("[Evaluate] Evaluation complete.")
    except Exception as e:
        print(f"[Evaluate] Error during evaluation: {e}")
        traceback.print_exc()


# ─── 1-DAY RESOLUTION ─────────────────────────────────────────

def resolve_1day_outcomes() -> int:
    """
    For recommendations where 1 trading day has passed:
    - Fill actual_next_day_return
    - Fill benchmark_1d_return (TASI over same day)
    - Calculate alpha_1d
    - Set was_correct
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        # Find unresolved 1-day recommendations
        sql = f"""
            SELECT tr.id, tr.symbol, tr.action, tr.signal, tr.close_price,
                   tr.recommendation_date
            FROM trade_recommendations tr
            WHERE tr.actual_next_day_return IS NULL
            AND tr.recommendation_date <= {_interval(1)}
            AND tr.recommendation_date >= {_interval(90)}
            AND tr.close_price IS NOT NULL
            AND tr.close_price > 0
        """
        unresolved = _query(cursor, sql)

        count = 0
        for rec in unresolved:
            rec_date = rec["recommendation_date"]

            # Stock return: next trading day's close
            next_sql = f"""
                SELECT close, date FROM prices
                WHERE symbol = {_ph(1)} AND date > {_ph(2)}
                ORDER BY date ASC LIMIT 1
            """
            next_price = _query(cursor, next_sql, [rec["symbol"], rec_date])

            if not next_price:
                continue

            next_close = next_price[0]["close"]
            next_date = next_price[0]["date"]

            if rec["close_price"] is None or rec["close_price"] <= 0:
                continue

            actual_return = round(
                ((next_close - rec["close_price"]) / rec["close_price"]) * 100, 4
            )

            # Benchmark: TASI index return over same day
            benchmark_return = get_benchmark_return(cursor, rec_date, next_date)

            # Buy-and-hold: same stock, same period (identical to actual for 1-day)
            buyhold_return = actual_return

            # Alpha
            alpha = round(actual_return - benchmark_return, 4) if benchmark_return is not None else None

            # Was correct?
            was_correct = evaluate_correctness(rec["action"], actual_return)

            # Check if benchmark columns exist (they may not on older SQLite dbs)
            try:
                if DATABASE_URL:
                    cursor.execute("SAVEPOINT ev_1d")
                update_sql = f"""
                    UPDATE trade_recommendations SET
                        actual_next_day_return = {_ph(1)},
                        benchmark_1d_return = {_ph(2)},
                        buyhold_1d_return = {_ph(3)},
                        alpha_1d = {_ph(4)},
                        was_correct = {_ph(5)},
                        resolved_at = {_now()},
                        model_version = {_ph(6)}
                    WHERE id = {_ph(7)}
                """
                _execute(cursor, update_sql, [
                    actual_return, benchmark_return, buyhold_return, alpha,
                    was_correct, MODEL_VERSION, rec["id"]
                ])
                if DATABASE_URL:
                    cursor.execute("RELEASE SAVEPOINT ev_1d")
            except Exception:
                # Fallback: update only existing columns (SQLite without migration)
                if DATABASE_URL:
                    cursor.execute("ROLLBACK TO SAVEPOINT ev_1d")
                update_sql = f"""
                    UPDATE trade_recommendations SET
                        actual_next_day_return = {_ph(1)},
                        was_correct = {_ph(2)}
                    WHERE id = {_ph(3)}
                """
                _execute(cursor, update_sql, [actual_return, was_correct, rec["id"]])

            count += 1

        return count


# ─── 5-DAY RESOLUTION ─────────────────────────────────────────

def resolve_5day_outcomes() -> int:
    """
    For recommendations where 5+ trading days have passed:
    - Fill actual_5day_return
    - Fill benchmark_5d_return
    - Calculate alpha_5d
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        sql = f"""
            SELECT tr.id, tr.symbol, tr.close_price, tr.recommendation_date
            FROM trade_recommendations tr
            WHERE tr.actual_5day_return IS NULL
            AND tr.recommendation_date <= {_interval(7)}
            AND tr.recommendation_date >= {_interval(90)}
            AND tr.close_price IS NOT NULL
            AND tr.close_price > 0
        """
        unresolved = _query(cursor, sql)

        count = 0
        for rec in unresolved:
            rec_date = rec["recommendation_date"]

            # Stock price 5 trading days later
            if DATABASE_URL:
                price_sql = f"""
                    SELECT close, date FROM prices
                    WHERE symbol = {_ph(1)} AND date > {_ph(2)}
                    ORDER BY date ASC
                    OFFSET 4 LIMIT 1
                """
            else:
                price_sql = f"""
                    SELECT close, date FROM prices
                    WHERE symbol = {_ph(1)} AND date > {_ph(2)}
                    ORDER BY date ASC
                    LIMIT 1 OFFSET 4
                """
            price_5d = _query(cursor, price_sql, [rec["symbol"], rec_date])

            if not price_5d:
                continue

            close_5d = price_5d[0]["close"]
            date_5d = price_5d[0]["date"]

            if rec["close_price"] is None or rec["close_price"] <= 0:
                continue

            actual_5d = round(
                ((close_5d - rec["close_price"]) / rec["close_price"]) * 100, 4
            )

            # Benchmark: EGX30 over same 5-day period
            benchmark_5d = get_benchmark_return(cursor, rec_date, date_5d)

            # Buy-and-hold: same stock 5-day
            buyhold_5d = actual_5d

            alpha_5d = round(actual_5d - benchmark_5d, 4) if benchmark_5d is not None else None

            try:
                if DATABASE_URL:
                    cursor.execute("SAVEPOINT ev_5d")
                update_sql = f"""
                    UPDATE trade_recommendations SET
                        actual_5day_return = {_ph(1)},
                        benchmark_5d_return = {_ph(2)},
                        buyhold_5d_return = {_ph(3)},
                        alpha_5d = {_ph(4)}
                    WHERE id = {_ph(5)}
                """
                _execute(cursor, update_sql, [actual_5d, benchmark_5d, buyhold_5d, alpha_5d, rec["id"]])
                if DATABASE_URL:
                    cursor.execute("RELEASE SAVEPOINT ev_5d")
            except Exception:
                # Fallback for SQLite without benchmark columns
                if DATABASE_URL:
                    cursor.execute("ROLLBACK TO SAVEPOINT ev_5d")
                update_sql = f"""
                    UPDATE trade_recommendations SET actual_5day_return = {_ph(1)} WHERE id = {_ph(2)}
                """
                _execute(cursor, update_sql, [actual_5d, rec["id"]])

            count += 1

        return count


# ─── POSITION BENCHMARK RESOLUTION ────────────────────────────

def resolve_position_benchmarks() -> int:
    """
    For closed positions: calculate what TASI returned
    over the same entry_date → exit_date period.
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        try:
            sql = f"""
                SELECT id, symbol, entry_date, exit_date, entry_price,
                       exit_price, return_pct
                FROM user_positions
                WHERE status = 'CLOSED'
                AND benchmark_return_pct IS NULL
                AND entry_date IS NOT NULL
                AND exit_date IS NOT NULL
            """
            unresolved = _query(cursor, sql)
        except Exception:
            # benchmark_return_pct column may not exist yet
            return 0

        count = 0
        for pos in unresolved:
            benchmark = get_benchmark_return(cursor, pos["entry_date"], pos["exit_date"])

            if benchmark is not None:
                alpha = round(pos["return_pct"] - benchmark, 2) if pos["return_pct"] is not None else None

                update_sql = f"""
                    UPDATE user_positions SET
                        benchmark_return_pct = {_ph(1)},
                        alpha_pct = {_ph(2)}
                    WHERE id = {_ph(3)}
                """
                _execute(cursor, update_sql, [benchmark, alpha, pos["id"]])
                count += 1

        return count


# ─── BENCHMARK HELPER ─────────────────────────────────────────

def get_benchmark_return(cursor, start_date, end_date) -> float:
    """
    Get TASI benchmark return between two dates.
    Tries TASI.INDX (stored by fetch_tasi_benchmark.py), then ^TASI, then
    Saudi Aramco (2222.SR) as a liquid proxy of last resort.
    Returns percentage return, or None if data unavailable.
    """
    for symbol in EGX30_SYMBOLS:
        start_sql = f"""
            SELECT close FROM prices
            WHERE symbol = {_ph(1)} AND date <= {_ph(2)}
            ORDER BY date DESC LIMIT 1
        """
        start_price = _query(cursor, start_sql, [symbol, start_date])

        end_sql = f"""
            SELECT close FROM prices
            WHERE symbol = {_ph(1)} AND date <= {_ph(2)}
            ORDER BY date DESC LIMIT 1
        """
        end_price = _query(cursor, end_sql, [symbol, end_date])

        if start_price and end_price and start_price[0]["close"] and start_price[0]["close"] > 0:
            return round(
                ((end_price[0]["close"] - start_price[0]["close"])
                 / start_price[0]["close"]) * 100, 4
            )

    return None


def evaluate_correctness(action: str, actual_return: float):
    """Determine if a recommendation was correct."""
    if action == "BUY":
        return actual_return > 0           # Price went up
    elif action == "SELL":
        return actual_return < 0           # Price went down (good exit)
    elif action == "HOLD":
        return actual_return >= -2.0       # Didn't crash
    return None                            # WATCH: no correctness


# ─── PER-AGENT ACCURACY TRACKING ──────────────────────────────

def update_agent_accuracy_snapshot():
    """
    Compute rolling accuracy for each agent and store a daily snapshot.
    PostgreSQL only (agent_performance_daily table + complex window queries).
    """
    if not DATABASE_URL:
        return

    with get_connection() as conn:
        cursor = conn.cursor()

        # Get distinct agents
        agents = _query(cursor, "SELECT DISTINCT agent_name FROM predictions WHERE agent_name IS NOT NULL")

        for agent_row in agents:
            agent_name = agent_row["agent_name"]

            # 30-day window — join on prediction_date (the day the rec was made), not target_date
            stats_30 = _query(cursor, """
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE tr.was_correct = TRUE) AS correct,
                    ROUND(AVG(p.confidence)::numeric, 1) AS avg_conf
                FROM predictions p
                JOIN trade_recommendations tr
                    ON tr.symbol = p.symbol AND tr.recommendation_date = p.prediction_date
                WHERE p.agent_name = %s
                AND p.prediction_date >= CURRENT_DATE - 30
                AND tr.was_correct IS NOT NULL
                AND (tr.is_live = TRUE OR tr.is_live IS NULL)
            """, [agent_name])

            # 90-day window
            stats_90 = _query(cursor, """
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE tr.was_correct = TRUE) AS correct
                FROM predictions p
                JOIN trade_recommendations tr
                    ON tr.symbol = p.symbol AND tr.recommendation_date = p.prediction_date
                WHERE p.agent_name = %s
                AND p.prediction_date >= CURRENT_DATE - 90
                AND tr.was_correct IS NOT NULL
                AND (tr.is_live = TRUE OR tr.is_live IS NULL)
            """, [agent_name])

            s30 = stats_30[0] if stats_30 else {"total": 0, "correct": 0, "avg_conf": 0}
            s90 = stats_90[0] if stats_90 else {"total": 0, "correct": 0}

            total_30 = int(s30.get("total", 0) or 0)
            correct_30 = int(s30.get("correct", 0) or 0)
            avg_conf_30 = float(s30.get("avg_conf", 0) or 0)
            win_rate_30 = round(correct_30 / total_30 * 100, 1) if total_30 > 0 else None

            total_90 = int(s90.get("total", 0) or 0)
            correct_90 = int(s90.get("correct", 0) or 0)
            win_rate_90 = round(correct_90 / total_90 * 100, 1) if total_90 > 0 else None

            _execute(cursor, """
                INSERT INTO agent_performance_daily (
                    snapshot_date, agent_name,
                    predictions_30d, correct_30d, win_rate_30d, avg_confidence_30d,
                    predictions_90d, correct_90d, win_rate_90d
                ) VALUES (
                    CURRENT_DATE, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s
                )
                ON CONFLICT (snapshot_date, agent_name) DO UPDATE SET
                    predictions_30d = EXCLUDED.predictions_30d,
                    correct_30d = EXCLUDED.correct_30d,
                    win_rate_30d = EXCLUDED.win_rate_30d,
                    avg_confidence_30d = EXCLUDED.avg_confidence_30d,
                    predictions_90d = EXCLUDED.predictions_90d,
                    correct_90d = EXCLUDED.correct_90d,
                    win_rate_90d = EXCLUDED.win_rate_90d
            """, [
                agent_name,
                total_30, correct_30, win_rate_30, avg_conf_30,
                total_90, correct_90, win_rate_90
            ])


# ─── REFRESH MATERIALIZED VIEW ────────────────────────────────

def refresh_performance_views():
    """Refresh the materialized performance views (PostgreSQL only)."""
    if not DATABASE_URL:
        return

    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT refresh_performance_views()")
        except Exception as e:
            # View may not exist yet if migration hasn't run
            print(f"[Evaluate] Warning: Could not refresh materialized view: {e}")


# ─── STANDALONE EXECUTION ─────────────────────────────────────

if __name__ == "__main__":
    run_evaluation(pipeline_run_id=f"manual_run")
    print("✅ Performance evaluation complete.")
