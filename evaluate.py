"""
Prediction Evaluation Module

This script checks past predictions against actual market outcomes to determine agent performance.
It populates the 'evaluations' table in the database.
"""
import os
import pandas as pd
from datetime import datetime, timedelta
import config
from database import get_connection
import argparse
import logging

logger = logging.getLogger(__name__)

# Check if using PostgreSQL
DATABASE_URL = os.getenv('DATABASE_URL')

def _adapt_sql(sql):
    """Convert SQLite SQL to PostgreSQL when needed."""
    if DATABASE_URL:
        sql = sql.replace('?', '%s')
    return sql


def _update_rag_context_outcome(symbol: str, prediction_date: str, actual_outcome: str, actual_change_pct: float):
    """Update prediction_contexts row with actual outcome (for Feature 5 pattern matching)."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(_adapt_sql("""
                UPDATE prediction_contexts
                SET actual_outcome = ?, actual_change_pct = ?
                WHERE symbol = ? AND prediction_date = ?
            """), (actual_outcome, actual_change_pct, symbol, prediction_date))
    except Exception as e:
        pass  # Table may not exist on older installs — safe to ignore

def evaluate_prediction(predicted_direction: str, predicted_confidence: float,
                        actual_return: float) -> dict:
    """
    Multi-metric evaluation of a single prediction.

    Returns dict with:
      ok              — binary directional accuracy (backward compat)
      magnitude_score — [-1, +1] reward correct+large, penalize wrong+large
      calibration_score — 1 - Brier penalty (higher = better)
      signal_strength — signed confidence for IC computation
      actual_return   — realized % return
    """
    # 1. Binary directional accuracy
    if predicted_direction == 'HOLD':
        ok = abs(actual_return) < 2.0
    else:
        actual_outcome = 'UP' if actual_return >= config.MIN_MOVE_THRESHOLD else (
            'DOWN' if actual_return <= -config.MIN_MOVE_THRESHOLD else 'FLAT')
        ok = (predicted_direction == actual_outcome)

    # 2. Magnitude-weighted score: correct + large move → high reward
    direction_sign = 1 if ok else -1
    magnitude_score = direction_sign * min(abs(actual_return) / 5.0, 1.0)

    # 3. Brier-style confidence penalty
    conf_norm = max(0.0, min(1.0, predicted_confidence / 100.0))
    outcome = 1.0 if ok else 0.0
    brier_score = (conf_norm - outcome) ** 2
    calibration_score = 1.0 - brier_score

    # 4. Signal strength for IC computation
    if predicted_direction == 'UP':
        signal_strength = conf_norm
    elif predicted_direction == 'DOWN':
        signal_strength = -conf_norm
    else:
        signal_strength = 0.0

    return {
        'ok': ok,
        'magnitude_score': round(magnitude_score, 4),
        'calibration_score': round(calibration_score, 4),
        'signal_strength': round(signal_strength, 4),
        'actual_return': round(actual_return, 4),
    }


def evaluate_predictions():
    """
    Compare resolved predictions against actual stock price movements.

    Process:
    1. Identify predictions where the target_date has passed but no evaluation exists.
    2. Retrieve actual close prices for prediction_date and target_date.
    3. Calculate percentage change.
    4. Determine actual outcome (UP/DOWN/FLAT) based on MIN_MOVE_THRESHOLD.
    5. Compare prediction vs actual outcome.
    6. Store result in 'evaluations' table with calibrated metrics.
    """
    today = datetime.now().strftime('%Y-%m-%d')
    print(f"🧐 Evaluating predictions due by {today}...")

    with get_connection() as conn:
        # 1. Get predictions that haven't been evaluated yet
        # We join with evaluations to ensure we don't re-evaluate (e.id IS NULL)
        query = _adapt_sql("""
            SELECT p.* FROM predictions p
            LEFT JOIN evaluations e ON p.id = e.prediction_id
            WHERE p.target_date <= ? AND e.id IS NULL
        """)

        # Use cursor for PostgreSQL compatibility
        cursor = conn.cursor()
        cursor.execute(query, (today,))
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        predictions = pd.DataFrame(rows, columns=columns) if rows else pd.DataFrame()

        for _, pred in predictions.iterrows():
            symbol = pred['symbol']
            
            # 2. Get the actual prices for the start and end dates
            price_query = _adapt_sql("SELECT close FROM prices WHERE symbol = ? AND date = ?")
            cursor.execute(price_query, (symbol, pred['prediction_date']))
            start_price_row = cursor.fetchone()
            cursor.execute(price_query, (symbol, pred['target_date']))
            end_price_row = cursor.fetchone()
            
            if not start_price_row:
                # prediction_date may be a weekend/holiday (e.g. Friday when daily-pipeline runs)
                # Fall back to the nearest PRIOR trading day's close
                prior_query = _adapt_sql(
                    "SELECT close FROM prices WHERE symbol = ? AND date <= ? ORDER BY date DESC LIMIT 1"
                )
                cursor.execute(prior_query, (symbol, pred['prediction_date']))
                start_price_row = cursor.fetchone()
            if not start_price_row:
                print(f"⚠️ Missing price data to evaluate {symbol} for {pred['prediction_date']}")
                continue
            if not end_price_row:
                # Target date may be a weekend/holiday — use nearest next trading day
                near_query = _adapt_sql(
                    "SELECT close FROM prices WHERE symbol = ? AND date >= ? ORDER BY date ASC LIMIT 1"
                )
                cursor.execute(near_query, (symbol, pred['target_date']))
                end_price_row = cursor.fetchone()
            if not end_price_row:
                print(f"⚠️ Missing price data to evaluate {symbol} for {pred['target_date']}")
                continue

            start_price = start_price_row['close']
            end_price = end_price_row['close']
            
            # 3. Calculate actual change
            if start_price == 0: continue # Prevent division by zero
            pct_change = ((end_price - start_price) / start_price) * 100
            
            # 4. Determine outcome
            actual_outcome = "FLAT"
            if pct_change >= config.MIN_MOVE_THRESHOLD:
                actual_outcome = "UP"
            elif pct_change <= -config.MIN_MOVE_THRESHOLD:
                actual_outcome = "DOWN"
            
            # 5. Multi-metric evaluation
            predicted = pred['prediction']
            predicted_confidence = float(pred.get('confidence', 50) or 50)
            metrics = evaluate_prediction(predicted, predicted_confidence, pct_change)
            was_correct = metrics['ok']

            # 6. Store evaluation with calibrated metrics
            cursor.execute(_adapt_sql("""
                INSERT INTO evaluations
                (prediction_id, symbol, agent_name, prediction, actual_outcome, was_correct,
                 actual_change_pct, magnitude_score, calibration_score, signal_strength, actual_return)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """), (int(pred['id']), symbol, pred['agent_name'], predicted, actual_outcome,
                   bool(was_correct), float(pct_change),
                   metrics['magnitude_score'], metrics['calibration_score'],
                   metrics['signal_strength'], metrics['actual_return']))

            # Update RAG pattern-matching context with actual outcome
            _update_rag_context_outcome(symbol, str(pred['prediction_date']), actual_outcome, float(pct_change))

            status_icon = "+" if was_correct else "-"
            print(f"  {status_icon} {symbol} ({pred['agent_name']}): Pred {predicted} vs Actual {actual_outcome} ({pct_change:+.2f}%) mag={metrics['magnitude_score']:+.2f} cal={metrics['calibration_score']:.2f}")

def evaluate_lookback(days_ago=7):
    """
    Evaluate performance specifically for predictions that targeted a specific past date.
    Useful for "Weekly Review" style reporting.
    
    Args:
        days_ago (int): Number of days to look back for the TARGET date.
    """
    target_date = (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%d')
    print(f"\n📅 Look-back Analysis for Target Date: {target_date}")
    
    with get_connection() as conn:
        # Fetch evaluations that were aiming for this specific target date
        query = _adapt_sql("""
            SELECT e.*, p.prediction_date
            FROM evaluations e
            JOIN predictions p ON e.prediction_id = p.id
            WHERE p.target_date = ?
        """)

        cursor = conn.cursor()
        cursor.execute(query, (target_date,))
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        evals = pd.DataFrame(rows, columns=columns) if rows else pd.DataFrame()
        
        if len(evals) == 0:
            print(f"  No evaluations found targeting {target_date}")
            return

        total = len(evals)
        correct = evals['was_correct'].sum()
        accuracy = (correct / total) * 100
        
        print(f"  📊 Total Predictions: {total}")
        print(f"  🎯 Correct: {correct}")
        print(f"  📈 Accuracy: {accuracy:.1f}%")
        
        print("\n  Detailed Breakdown:")
        print(evals[['symbol', 'agent_name', 'prediction', 'actual_outcome', 'was_correct']].to_string(index=False))

def record_portfolio_daily_actuals():
    """
    Record today's actual close price for every stock in an active portfolio forecast.

    An "active" forecast is one where:
      - run_date <= today (forecast has started)
      - target_date > today (hasn't matured yet)
      - ok = 1 (forecast succeeded)

    Stores one row per (portfolio_id, symbol, date) in portfolio_daily_actuals.
    Skips gracefully if price data is missing for today.
    """
    today = datetime.now().strftime('%Y-%m-%d')
    print(f"📅 Recording daily actuals for active portfolio forecasts ({today})...")

    with get_connection() as conn:
        cursor = conn.cursor()

        # Find distinct active forecast rows (one entry per portfolio+symbol)
        active_q = _adapt_sql("""
            SELECT DISTINCT r.portfolio_id, r.symbol, r.run_date
            FROM portfolio_forecast_results r
            WHERE r.run_date <= ? AND r.target_date > ? AND r.ok = TRUE
        """)
        cursor.execute(active_q, (today, today))
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        active = [dict(zip(columns, row)) if not hasattr(row, 'keys') else dict(row) for row in rows]

        if not active:
            print("  No active portfolio forecasts to track.")
            return

        price_exact_q = _adapt_sql("SELECT close FROM prices WHERE symbol = ? AND date = ?")
        price_near_q  = _adapt_sql(
            "SELECT close FROM prices WHERE symbol = ? AND date <= ? ORDER BY date DESC LIMIT 1"
        )

        if DATABASE_URL:
            upsert_q = """
                INSERT INTO portfolio_daily_actuals (portfolio_id, symbol, date, actual_close, return_pct_from_start)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (portfolio_id, symbol, date) DO UPDATE
                  SET actual_close = EXCLUDED.actual_close,
                      return_pct_from_start = EXCLUDED.return_pct_from_start
            """
        else:
            upsert_q = """
                INSERT OR REPLACE INTO portfolio_daily_actuals
                (portfolio_id, symbol, date, actual_close, return_pct_from_start)
                VALUES (?, ?, ?, ?, ?)
            """

        recorded = 0
        for row in active:
            symbol   = row['symbol']
            run_date = row['run_date']
            pid      = row['portfolio_id']

            # Get base price (price on run_date)
            cursor.execute(price_exact_q, (symbol, run_date))
            base_row = cursor.fetchone()
            if not base_row:
                continue
            base_price = base_row[0] if isinstance(base_row, (list, tuple)) else base_row['close']
            if not base_price or base_price == 0:
                continue

            # Get today's price (exact or nearest past trading day)
            cursor.execute(price_exact_q, (symbol, today))
            today_row = cursor.fetchone()
            if not today_row:
                cursor.execute(price_near_q, (symbol, today))
                today_row = cursor.fetchone()
            if not today_row:
                continue

            today_price = today_row[0] if isinstance(today_row, (list, tuple)) else today_row['close']
            if not today_price:
                continue

            return_pct = ((today_price - base_price) / base_price) * 100

            cursor.execute(upsert_q, (
                int(pid), symbol, today, float(today_price), float(return_pct)
            ))
            recorded += 1

        print(f"  Recorded {recorded} daily actual(s).")


def evaluate_portfolio_forecasts():
    """
    Auto-evaluate portfolio forecast results whose target_date has passed.

    For each portfolio_forecast_results row where:
      - target_date <= today
      - no evaluation row exists yet

    Fetches the actual close price from the prices table (or nearest available
    date within 5 days), computes actual_return_pct, and stores the result in
    portfolio_forecast_evaluations.
    """
    # Record today's prices for all in-progress forecasts first
    record_portfolio_daily_actuals()

    today = datetime.now().strftime('%Y-%m-%d')
    print(f"📊 Evaluating portfolio forecasts due by {today}...")

    with get_connection() as conn:
        cursor = conn.cursor()

        # Find due results with no evaluation yet
        due_query = _adapt_sql("""
            SELECT r.id, r.portfolio_id, r.symbol, r.run_date, r.target_date,
                   r.expected_return_pct, r.investment_amount, r.ok
            FROM portfolio_forecast_results r
            LEFT JOIN portfolio_forecast_evaluations e ON r.id = e.forecast_result_id
            WHERE r.target_date <= ? AND e.id IS NULL AND r.ok = TRUE
        """)
        cursor.execute(due_query, (today,))
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        due = [dict(zip(columns, row)) if not hasattr(row, 'keys') else dict(row) for row in rows]

        if not due:
            print("  No portfolio forecasts due for evaluation.")
            return

        print(f"  Found {len(due)} portfolio forecast(s) to evaluate.")
        price_q = _adapt_sql("SELECT close FROM prices WHERE symbol = ? AND date = ?")
        near_q  = _adapt_sql(
            "SELECT close, date FROM prices WHERE symbol = ? AND date >= ? "
            "ORDER BY date ASC LIMIT 1"
        )

        evaluated = 0
        for row in due:
            symbol      = row['symbol']
            run_date    = row['run_date']
            target_date = row['target_date']
            expected    = row['expected_return_pct'] or 0.0

            # Fetch actual close on run_date (base price)
            cursor.execute(price_q, (symbol, run_date))
            base_row = cursor.fetchone()
            if not base_row:
                print(f"  ⚠️  No base price for {symbol} on {run_date}, skipping")
                continue
            base_price = base_row[0] if not hasattr(base_row, '__getitem__') or isinstance(base_row, (list, tuple)) else base_row['close']

            # Fetch actual close on target_date (or nearest available within 5 days)
            cursor.execute(price_q, (symbol, target_date))
            end_row = cursor.fetchone()
            if not end_row:
                cursor.execute(near_q, (symbol, target_date))
                end_row = cursor.fetchone()
            if not end_row:
                print(f"  ⚠️  No actual price for {symbol} near {target_date}, skipping")
                continue

            actual_close = end_row[0] if not hasattr(end_row, '__getitem__') or isinstance(end_row, (list, tuple)) else end_row['close']
            if base_price == 0:
                continue

            actual_return = ((actual_close - base_price) / base_price) * 100
            error_pct     = actual_return - expected
            within_5  = abs(error_pct) <= 5.0
            within_10 = abs(error_pct) <= 10.0

            insert_q = _adapt_sql("""
                INSERT INTO portfolio_forecast_evaluations
                (forecast_result_id, portfolio_id, symbol, run_date, target_date,
                 expected_return_pct, actual_return_pct, actual_close,
                 error_pct, within_5pct, within_10pct)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """)
            cursor.execute(insert_q, (
                int(row['id']), int(row['portfolio_id']),
                symbol, run_date, target_date,
                float(expected), float(actual_return), float(actual_close),
                float(error_pct),
                1 if within_5  else 0,
                1 if within_10 else 0,
            ))
            icon = "✅" if within_10 else "⚠️"
            print(f"  {icon} {symbol}: expected {expected:+.1f}% → actual {actual_return:+.1f}% (err {error_pct:+.1f}%)")
            evaluated += 1

        print(f"  ✅ Evaluated {evaluated} portfolio forecast(s).")


def evaluate_signal_horizons():
    """
    Evaluate consensus signals at D+10 and D+20 horizons (D+5 is covered by evaluate_predictions).
    Reads consensus_results from the past 30 days, checks actual prices at D+10 and D+20,
    and stores results in stock_signal_evals.
    """
    today = datetime.now().strftime('%Y-%m-%d')
    cutoff = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')
    print(f"📐 Evaluating signal horizons (D+10, D+20) up to {today}...")

    with get_connection() as conn:
        cursor = conn.cursor()

        # Fetch consensus signals from past 60 days
        q = _adapt_sql("""
            SELECT symbol, prediction_date, final_signal
            FROM consensus_results
            WHERE prediction_date >= ? AND prediction_date <= ?
            AND final_signal IN ('UP', 'DOWN')
        """)
        cursor.execute(q, (cutoff, today))
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        signals = pd.DataFrame(rows, columns=columns) if rows else pd.DataFrame()

        if signals.empty:
            print("  No consensus signals to evaluate.")
            return

        price_q = _adapt_sql("SELECT close FROM prices WHERE symbol = ? AND date = ?")
        near_q  = _adapt_sql(
            "SELECT close FROM prices WHERE symbol = ? AND date >= ? ORDER BY date ASC LIMIT 1"
        )
        prior_q = _adapt_sql(
            "SELECT close FROM prices WHERE symbol = ? AND date <= ? ORDER BY date DESC LIMIT 1"
        )

        if DATABASE_URL:
            upsert_q = """
                INSERT INTO stock_signal_evals
                (symbol, prediction_date, horizon_days, predicted_signal, actual_change_pct, was_correct)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (symbol, prediction_date, horizon_days) DO NOTHING
            """
        else:
            upsert_q = """
                INSERT OR IGNORE INTO stock_signal_evals
                (symbol, prediction_date, horizon_days, predicted_signal, actual_change_pct, was_correct)
                VALUES (?, ?, ?, ?, ?, ?)
            """

        done = 0
        for _, row in signals.iterrows():
            symbol = row['symbol']
            pred_date = str(row['prediction_date'])
            signal = row['final_signal']

            # Get base price
            cursor.execute(prior_q, (symbol, pred_date))
            base_row = cursor.fetchone()
            if not base_row:
                continue
            base_price = float(base_row[0] if isinstance(base_row, (list, tuple)) else base_row['close'])
            if base_price == 0:
                continue

            for horizon in [10, 20]:
                target_dt = (datetime.strptime(pred_date, '%Y-%m-%d') + timedelta(days=horizon)).strftime('%Y-%m-%d')
                if target_dt > today:
                    continue  # Not yet evaluable
                cursor.execute(price_q, (symbol, target_dt))
                end_row = cursor.fetchone()
                if not end_row:
                    cursor.execute(near_q, (symbol, target_dt))
                    end_row = cursor.fetchone()
                if not end_row:
                    continue
                end_price = float(end_row[0] if isinstance(end_row, (list, tuple)) else end_row['close'])
                change_pct = ((end_price - base_price) / base_price) * 100
                actual_dir = 'UP' if change_pct >= 0.5 else ('DOWN' if change_pct <= -0.5 else 'FLAT')
                was_correct = (signal == actual_dir)
                cursor.execute(upsert_q, (symbol, pred_date, horizon, signal, float(change_pct), bool(was_correct)))
                done += 1

        print(f"  ✅ Evaluated {done} signal-horizon pair(s).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Evaluate Xmore2 Predictions')
    parser.add_argument('--lookback', action='store_true', help='Run look-back analysis for previous week')
    parser.add_argument('--days', type=int, default=7, help='Days ago for look-back (default: 7)')
    parser.add_argument('--force', action='store_true', help='Ignore job locks and run anyway')
    args = parser.parse_args()

    # Check if intraday-price-update is running — avoid evaluating against incomplete data
    if not args.force:
        try:
            from engines.job_locks import is_lock_held
            with get_connection() as _lc:
                if is_lock_held(_lc, 'intraday-price-update'):
                    print("⏳ Intraday price update in progress — skipping evaluation to avoid reading incomplete data.")
                    print("   Re-run with --force to override.")
                    import sys
                    sys.exit(0)
        except Exception:
            pass  # Fail-open: if lock check fails, proceed with evaluation

    # Always run standard evaluation first to ensure latest data is processed
    evaluate_predictions()

    # Evaluate portfolio forecasts whose target date has passed
    evaluate_portfolio_forecasts()

    # Evaluate signals at D+10 and D+20 horizons
    evaluate_signal_horizons()

    if args.lookback:
        evaluate_lookback(days_ago=args.days)