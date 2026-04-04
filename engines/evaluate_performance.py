"""
Performance Evaluation Engine (v2)
Replaces evaluate_trades.py

Responsibilities:
1. Resolve outcome fields on trade_recommendations (existing)
2. Calculate benchmark returns (TASI) over same periods (NEW)
3. Calculate alpha (NEW)
4. Resolve user_positions with benchmark comparison (NEW)
5. Track per-agent accuracy contribution (NEW)

Runs as Step 8 in the daily pipeline.
"""

import os
import traceback
from database import get_connection

MODEL_VERSION = "v1.0"  # Increment on agent/pipeline changes
DATABASE_URL = os.getenv('DATABASE_URL')

# Benchmark symbols to try (official symbol first, then compatible aliases)
BENCHMARK_SYMBOLS = ['TASI', '^TASI', 'TASI.SR', 'TASI.INDX']


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
                refreshed = refresh_performance_views()
                if refreshed:
                    print("[Evaluate] Performance views refreshed")
                else:
                    print("[Evaluate] Performance views refresh skipped")
            except Exception as e:
                print(f"[Evaluate] Performance views skipped: {e}")

        # 6. IC monitoring — Spearman correlation of signals vs outcomes
        try:
            ic_results = compute_ic()
            if ic_results:
                avg_ic = sum(r['ic'] for r in ic_results) / len(ic_results)
                print(f"[Evaluate] IC computed for {len(ic_results)} symbols, avg IC={avg_ic:.4f}")
            else:
                print("[Evaluate] IC: insufficient resolved outcomes yet")
        except Exception as e:
            print(f"[Evaluate] IC monitoring skipped: {e}")

        # 7. Concept drift detection — flag stale models
        try:
            stale = detect_model_drift()
            if stale:
                print(f"[Evaluate] Drift detected for {len(stale)} symbols: {stale}")
            else:
                print("[Evaluate] No model drift detected")
        except Exception as e:
            print(f"[Evaluate] Drift detection skipped: {e}")

        print("[Evaluate] Evaluation complete.")
    except Exception as e:
        print(f"[Evaluate] Error during evaluation: {e}")
        traceback.print_exc()


# ─── 1-DAY RESOLUTION ─────────────────────────────────────────

def resolve_1day_outcomes() -> int:
    """
    For recommendations where 1 trading day has passed:
    - Fill actual_next_day_return
    - Fill benchmark_1d_return (EGX30 over same day)
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

            # Benchmark: TASI return over same day
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
    For closed positions: calculate what EGX30 returned
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
    Get benchmark index return between two dates.
    Returns percentage return, or None if data unavailable.
    """
    for symbol in BENCHMARK_SYMBOLS:
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
        return False

    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("SAVEPOINT refresh_perf_views")
            cursor.execute("SELECT refresh_performance_views()")
            cursor.execute("RELEASE SAVEPOINT refresh_perf_views")
            return True
        except Exception as e:
            # View may not exist yet if migration hasn't run
            try:
                cursor.execute("ROLLBACK TO SAVEPOINT refresh_perf_views")
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
            print(f"[Evaluate] Warning: Could not refresh materialized view: {e}")
            return False


# ─── IC MONITORING ────────────────────────────────────────────

def compute_ic(days: int = 20) -> list:
    """
    Compute Information Coefficient (Spearman rank correlation) between
    consensus signal direction and actual next-day return.

    IC > 0.05 = informative signal; IC < 0.02 = noise; IC < 0 = anti-predictive.
    Stores result in signal_ic_log table (created in init-db.js).

    Returns list of dicts: {symbol, ic, ic_date, sample_count}
    """
    try:
        from scipy.stats import spearmanr
    except ImportError:
        return []

    results = []
    with get_connection() as conn:
        cursor = conn.cursor()

        # Ensure table exists (graceful if missing)
        try:
            _ensure_ic_log_table(cursor)
        except Exception:
            pass

        # Fetch resolved signals in the window
        sql = f"""
            SELECT symbol,
                   CASE final_signal WHEN 'UP' THEN 1 WHEN 'DOWN' THEN -1 ELSE 0 END AS direction,
                   actual_next_day_return
            FROM trade_recommendations
            WHERE actual_next_day_return IS NOT NULL
              AND recommendation_date >= {_interval(days)}
              AND final_signal IN ('UP', 'DOWN', 'HOLD')
        """
        # trade_recommendations may not have final_signal; fall back to action
        try:
            rows = _query(cursor, sql)
        except Exception:
            sql2 = f"""
                SELECT symbol,
                       CASE action WHEN 'BUY' THEN 1 WHEN 'SELL' THEN -1 ELSE 0 END AS direction,
                       actual_next_day_return
                FROM trade_recommendations
                WHERE actual_next_day_return IS NOT NULL
                  AND recommendation_date >= {_interval(days)}
            """
            rows = _query(cursor, sql2)

        if not rows:
            return results

        # Group by symbol, compute per-symbol IC
        from collections import defaultdict
        by_sym = defaultdict(list)
        for r in rows:
            by_sym[r['symbol']].append((float(r['direction'] or 0),
                                        float(r['actual_next_day_return'] or 0)))

        today_str = _query(cursor, "SELECT CURRENT_DATE AS d")[0]['d'] if DATABASE_URL \
                    else _query(cursor, "SELECT date('now') AS d")[0]['d']

        for symbol, pairs in by_sym.items():
            if len(pairs) < 5:
                continue
            directions = [p[0] for p in pairs]
            returns    = [p[1] for p in pairs]
            if len(set(directions)) < 2:
                continue
            try:
                ic, _ = spearmanr(directions, returns)
                if ic is None or (hasattr(ic, '__class__') and 'nan' in str(ic).lower()):
                    continue
                ic = round(float(ic), 4)
            except Exception:
                continue

            # Store in IC log
            ph = _ph(1)
            try:
                if DATABASE_URL:
                    cursor.execute("""
                        INSERT INTO signal_ic_log (symbol, ic_date, ic, sample_count, window_days)
                        VALUES (%s, CURRENT_DATE, %s, %s, %s)
                        ON CONFLICT (symbol, ic_date) DO UPDATE SET
                            ic = EXCLUDED.ic, sample_count = EXCLUDED.sample_count
                    """, [symbol, ic, len(pairs), days])
                else:
                    cursor.execute("""
                        INSERT OR REPLACE INTO signal_ic_log
                        (symbol, ic_date, ic, sample_count, window_days)
                        VALUES (?, date('now'), ?, ?, ?)
                    """, [symbol, ic, len(pairs), days])
            except Exception:
                pass

            results.append({'symbol': symbol, 'ic': ic,
                            'ic_date': str(today_str), 'sample_count': len(pairs)})

    return results


def _ensure_ic_log_table(cursor):
    """Create signal_ic_log table if missing (runtime safety net)."""
    if DATABASE_URL:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signal_ic_log (
                id SERIAL PRIMARY KEY,
                symbol TEXT NOT NULL,
                ic_date DATE NOT NULL,
                ic REAL,
                sample_count INTEGER DEFAULT 0,
                window_days INTEGER DEFAULT 20,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, ic_date)
            )
        """)
    else:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signal_ic_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                ic_date DATE NOT NULL,
                ic REAL,
                sample_count INTEGER DEFAULT 0,
                window_days INTEGER DEFAULT 20,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, ic_date)
            )
        """)


# ─── CONCEPT DRIFT DETECTION ──────────────────────────────────

def detect_model_drift(window: int = 20, baseline_window: int = 60,
                       drop_threshold: float = 0.10,
                       max_model_age_days: int = 60) -> list:
    """
    Page-Hinkley test for concept drift in model accuracy.

    Flags a symbol as drifted if:
      1. Rolling accuracy dropped > drop_threshold vs the 60-day baseline, OR
      2. Model file is older than max_model_age_days

    Returns list of drifted symbols. Callers can delete model files to force retrain.
    """
    import os
    import glob

    stale = []

    with get_connection() as conn:
        cursor = conn.cursor()

        # Per-symbol rolling accuracy vs baseline
        sql = f"""
            SELECT symbol,
                   AVG(CASE WHEN was_correct THEN 1.0 ELSE 0.0 END) AS recent_acc,
                   COUNT(*) AS cnt
            FROM trade_recommendations
            WHERE was_correct IS NOT NULL
              AND recommendation_date >= {_interval(window)}
            GROUP BY symbol
            HAVING COUNT(*) >= 5
        """
        recent_rows = _query(cursor, sql)

        sql_base = f"""
            SELECT symbol,
                   AVG(CASE WHEN was_correct THEN 1.0 ELSE 0.0 END) AS base_acc
            FROM trade_recommendations
            WHERE was_correct IS NOT NULL
              AND recommendation_date >= {_interval(baseline_window)}
            GROUP BY symbol
            HAVING COUNT(*) >= 15
        """
        baseline_rows = {r['symbol']: float(r['base_acc'] or 0)
                        for r in _query(cursor, sql_base)}

    for row in recent_rows:
        sym = row['symbol']
        recent_acc = float(row['recent_acc'] or 0)
        base_acc = baseline_rows.get(sym)
        if base_acc is not None and (base_acc - recent_acc) > drop_threshold:
            stale.append(sym)

    # Also flag models older than max_model_age_days
    model_dir = os.path.join(os.path.dirname(__file__), '..', 'models')
    if os.path.isdir(model_dir):
        import time
        now = time.time()
        max_age_sec = max_model_age_days * 86400
        for pkl in glob.glob(os.path.join(model_dir, '*_predictor.pkl')):
            age = now - os.path.getmtime(pkl)
            if age > max_age_sec:
                sym = os.path.basename(pkl).replace('_predictor.pkl', '').replace('_', '.')
                if sym not in stale:
                    stale.append(sym)
                # Remove stale model to force retrain on next pipeline run
                try:
                    os.remove(pkl)
                except Exception:
                    pass

    return stale


def compute_information_coefficient(lookback_days: int = 60) -> dict:
    """
    IC = Spearman rank correlation between signal_strength and actual_return
    across all evaluated predictions with calibrated metrics.

    IC > 0.05 = weak positive edge
    IC > 0.10 = meaningful edge (institutional threshold)
    IC > 0.15 = strong edge

    Returns {'ic': float, 'p_value': float, 'sample_size': int}
    """
    try:
        from scipy.stats import spearmanr
    except ImportError:
        return {'ic': None, 'p_value': None, 'sample_size': 0, 'error': 'scipy not installed'}

    with get_connection() as conn:
        cursor = conn.cursor()

        sql = f"""
            SELECT signal_strength, actual_return
            FROM evaluations
            WHERE signal_strength IS NOT NULL
              AND actual_return IS NOT NULL
              AND evaluated_at >= {_interval(lookback_days)}
        """
        rows = _query(cursor, sql)
        if not rows or len(rows) < 10:
            return {'ic': None, 'p_value': None, 'sample_size': len(rows or []),
                    'error': 'insufficient data'}

        strengths = [float(r['signal_strength']) for r in rows]
        returns = [float(r['actual_return']) for r in rows]

        ic, p_val = spearmanr(strengths, returns)
        return {
            'ic': round(float(ic), 4),
            'p_value': round(float(p_val), 4),
            'sample_size': len(rows),
        }


# ─── STANDALONE EXECUTION ─────────────────────────────────────

if __name__ == "__main__":
    run_evaluation(pipeline_run_id=f"manual_run")

    ic_result = compute_information_coefficient()
    if ic_result.get('ic') is not None:
        print(f"IC = {ic_result['ic']:.4f} (p={ic_result['p_value']:.4f}, n={ic_result['sample_size']})")
    else:
        print(f"IC: {ic_result.get('error', 'N/A')}")

    print("Performance evaluation complete.")
