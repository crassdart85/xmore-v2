"""
Backfill Historical Predictions
================================
Generates what Xmore's agents WOULD HAVE predicted for each EGX30 stock
over the last N trading days, saves to the database with is_simulated=TRUE,
then immediately evaluates actual returns (prices already exist for past dates).

Usage:
    python backfill_predictions.py --days 60
    python backfill_predictions.py --days 60 --dry-run

This populates the track-record page with historical simulation data so
investors can see performance over a meaningful period — clearly labeled
as simulated, not live predictions.
"""

import argparse
import json
import os
import sys
import logging
from datetime import datetime, timedelta

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# ── Imports ────────────────────────────────────────────────────────────────────

from database import get_connection
from engines.timemachine_data import fetch_historical_prices, EGX30_SYMBOLS
from engines.timemachine_signals import _run_agents_on_history, _get_trading_days

DATABASE_URL = os.getenv('DATABASE_URL')


# ── Helpers ────────────────────────────────────────────────────────────────────

def _ph():
    return '%s' if DATABASE_URL else '?'


def _safe_add_column(cursor, table, column, definition):
    try:
        if DATABASE_URL:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {definition}")
        else:
            try:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            except Exception:
                pass  # Column already exists in SQLite
    except Exception as e:
        logger.debug(f"  add_column {table}.{column}: {e}")


def ensure_simulated_columns(conn):
    """Add is_simulated column to both tables if missing."""
    cur = conn.cursor()
    _safe_add_column(cur, 'consensus_results', 'is_simulated', 'BOOLEAN DEFAULT FALSE')
    _safe_add_column(cur, 'trade_recommendations', 'is_simulated', 'BOOLEAN DEFAULT FALSE')
    conn.commit()
    logger.info("✅ is_simulated columns ensured on both tables")


def get_existing_dates(conn, symbol):
    """Return set of dates already in consensus_results for this symbol."""
    cur = conn.cursor()
    ph = _ph()
    cur.execute(
        f"SELECT prediction_date FROM consensus_results WHERE symbol = {ph}",
        (symbol,)
    )
    rows = cur.fetchall()
    return {str(r[0]) if not isinstance(r, dict) else str(r['prediction_date']) for r in rows}


def map_signal(consensus_score, action):
    """Map time-machine agent output to consensus_results schema fields."""
    final_signal = 'UP' if consensus_score >= 0.50 else 'HOLD'
    if consensus_score >= 0.75:
        conviction = 'HIGH'
    elif consensus_score >= 0.60:
        conviction = 'MEDIUM'
    else:
        conviction = 'LOW'
    confidence = round(consensus_score * 100, 1)
    bull_score = confidence
    bear_score = round((1 - consensus_score) * 100, 1)
    return final_signal, conviction, confidence, bull_score, bear_score


def insert_consensus(conn, symbol, date, sig, conviction, confidence, bull_score, bear_score,
                     agents_agree, dry_run):
    if dry_run:
        return
    ph = _ph()
    cur = conn.cursor()
    agents_total = 4
    agent_agreement = round(agents_agree / agents_total, 2)

    if DATABASE_URL:
        cur.execute(f"""
            INSERT INTO consensus_results
                (symbol, prediction_date, final_signal, conviction, confidence,
                 bull_score, bear_score, agent_agreement, agents_agreeing, agents_total,
                 majority_direction, risk_action, is_simulated)
            VALUES ({','.join([ph]*13)})
            ON CONFLICT (symbol, prediction_date) DO NOTHING
        """, (
            symbol, date, sig, conviction, confidence,
            bull_score, bear_score, agent_agreement, agents_agree, agents_total,
            sig, 'PROCEED', True
        ))
    else:
        cur.execute(f"""
            INSERT OR IGNORE INTO consensus_results
                (symbol, prediction_date, final_signal, conviction, confidence,
                 bull_score, bear_score, agent_agreement, agents_agreeing, agents_total,
                 majority_direction, risk_action, is_simulated)
            VALUES ({','.join([ph]*13)})
        """, (
            symbol, date, sig, conviction, confidence,
            bull_score, bear_score, agent_agreement, agents_agree, agents_total,
            sig, 'PROCEED', 1
        ))


def _evaluate_correctness(action_db, actual_return):
    if action_db == 'BUY':
        return actual_return > 0
    elif action_db == 'SELL':
        return actual_return < 0
    elif action_db == 'HOLD':
        return actual_return >= -2.0
    return None


def insert_trade_rec(conn, symbol, date, action_raw, confidence, conviction,
                     entry_price, stop_loss_price, target_price,
                     stop_loss_pct, target_pct, dry_run,
                     actual_next_day_return=None):
    if dry_run:
        return
    ph = _ph()
    cur = conn.cursor()
    action_db = 'BUY' if action_raw in ('buy', 'strong_buy') else 'HOLD'
    signal_db = 'UP'
    risk_reward = round(target_pct / stop_loss_pct, 2) if stop_loss_pct else 0
    user_id = 1  # default user
    was_correct = _evaluate_correctness(action_db, actual_next_day_return) \
        if actual_next_day_return is not None else None

    if DATABASE_URL:
        cur.execute(f"""
            INSERT INTO trade_recommendations
                (user_id, symbol, recommendation_date, action, signal,
                 confidence, conviction, risk_action,
                 close_price, stop_loss_pct, target_pct,
                 stop_loss_price, target_price, risk_reward_ratio,
                 is_simulated, actual_next_day_return, was_correct)
            VALUES ({','.join([ph]*17)})
            ON CONFLICT (user_id, symbol, recommendation_date) DO NOTHING
        """, (
            user_id, symbol, date, action_db, signal_db,
            confidence, conviction, 'PROCEED',
            entry_price, stop_loss_pct * 100, target_pct * 100,
            stop_loss_price, target_price, risk_reward,
            True, actual_next_day_return, was_correct
        ))
    else:
        cur.execute(f"""
            INSERT OR IGNORE INTO trade_recommendations
                (user_id, symbol, recommendation_date, action, signal,
                 confidence, conviction, risk_action,
                 close_price, stop_loss_pct, target_pct,
                 stop_loss_price, target_price, risk_reward_ratio,
                 is_simulated, actual_next_day_return, was_correct)
            VALUES ({','.join([ph]*17)})
        """, (
            user_id, symbol, date, action_db, signal_db,
            confidence, conviction, 'PROCEED',
            entry_price, stop_loss_pct * 100, target_pct * 100,
            stop_loss_price, target_price, risk_reward,
            1, actual_next_day_return, was_correct
        ))


def get_next_day_return(price_data, symbol, day, entry_price):
    """Compute actual_next_day_return using already-fetched price_data."""
    prices = price_data.get(symbol, [])
    future = sorted([p for p in prices if p['date'] > day], key=lambda p: p['date'])
    if not future or not entry_price or entry_price <= 0:
        return None
    next_close = future[0]['close']
    return round((next_close - entry_price) / entry_price * 100, 4)


# ── Main ───────────────────────────────────────────────────────────────────────

def run(days: int = 60, dry_run: bool = False):
    today = datetime.now().date()
    # Buffer: need 50+ days before backfill start for warmup indicators
    buffer_start = (today - timedelta(days=days + 90)).strftime('%Y-%m-%d')
    backfill_start = (today - timedelta(days=days)).strftime('%Y-%m-%d')
    backfill_end   = (today - timedelta(days=1)).strftime('%Y-%m-%d')

    logger.info(f"📅 Backfill range: {backfill_start} → {backfill_end} ({days} days)")
    logger.info(f"📦 Fetching price data from {buffer_start} …")

    price_data = fetch_historical_prices(buffer_start, backfill_end)
    if not price_data:
        logger.error("❌ No price data returned — aborting")
        sys.exit(1)

    stocks = [s for s in price_data if s != '^EGX30']
    trading_days = _get_trading_days(price_data, backfill_start, backfill_end)
    logger.info(f"📈 {len(stocks)} stocks, {len(trading_days)} trading days")

    inserted = 0
    skipped = 0
    errors = 0

    with get_connection() as conn:
        if not dry_run:
            ensure_simulated_columns(conn)

        # Cache existing dates per symbol to avoid duplicate queries
        existing = {s: get_existing_dates(conn, s) for s in stocks}

        for day in trading_days:
            day_inserted = 0
            for symbol in stocks:
                if day in existing.get(symbol, set()):
                    skipped += 1
                    continue

                prices = price_data.get(symbol, [])
                # Only historical up to this day
                hist = [p for p in prices if p['date'] <= day]
                if len(hist) < 50:
                    continue

                try:
                    sig_data = _run_agents_on_history(symbol, hist, day)
                    if sig_data is None:
                        # No signal (< 0.50 consensus) — still insert as HOLD/neutral
                        # so the log shows the agent ran but had no strong view
                        continue  # Skip low-confidence days to avoid noise

                    final_signal, conviction, confidence, bull_score, bear_score = \
                        map_signal(sig_data['consensus_score'], sig_data['action'])

                    insert_consensus(
                        conn, symbol, day,
                        final_signal, conviction, confidence, bull_score, bear_score,
                        sig_data['agents_agree'], dry_run
                    )
                    actual_return = get_next_day_return(
                        price_data, symbol, day, sig_data['entry_price']
                    )
                    insert_trade_rec(
                        conn, symbol, day,
                        sig_data['action'], confidence, conviction,
                        sig_data['entry_price'],
                        sig_data['stop_loss_price'],
                        sig_data['target_price'],
                        0.05 if sig_data['action'] == 'strong_buy' else 0.07,
                        0.15 if sig_data['action'] == 'strong_buy' else 0.10,
                        dry_run,
                        actual_next_day_return=actual_return
                    )
                    inserted += 1
                    day_inserted += 1

                except Exception as e:
                    logger.warning(f"  ⚠ {symbol} {day}: {e}")
                    errors += 1
                    # Rollback failed row so subsequent rows aren't aborted
                    try:
                        conn.rollback()
                    except Exception:
                        pass

            if not dry_run:
                try:
                    conn.commit()
                except Exception:
                    conn.rollback()

            if day_inserted:
                logger.info(f"  {day}: +{day_inserted} signals inserted")

    logger.info(f"\n✅ Done. Inserted={inserted}, Skipped={skipped}, Errors={errors}")

    # ── Patch already-existing simulated rows that still have NULL returns ──
    if not dry_run:
        ph = _ph()
        updated = 0
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(f"""
                SELECT id, symbol, recommendation_date, close_price, action
                FROM trade_recommendations
                WHERE is_simulated = {'TRUE' if DATABASE_URL else '1'}
                AND actual_next_day_return IS NULL
                AND close_price IS NOT NULL AND close_price > 0
            """)
            rows = cur.fetchall()
            pending = [
                dict(zip([d[0] for d in cur.description], r)) if not isinstance(r, dict) else r
                for r in rows
            ]

        for rec in pending:
            day = str(rec['recommendation_date'])
            sym = rec['symbol']
            entry = rec['close_price']
            actual = get_next_day_return(price_data, sym, day, entry)
            if actual is None:
                continue
            action_db = rec['action']
            wc = _evaluate_correctness(action_db, actual)
            try:
                with get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute(f"""
                        UPDATE trade_recommendations
                        SET actual_next_day_return = {ph}, was_correct = {ph}
                        WHERE id = {ph}
                    """, (actual, wc, rec['id']))
                    conn.commit()
                updated += 1
            except Exception as e:
                logger.debug(f"  patch {sym} {day}: {e}")

        if updated:
            logger.info(f"✅ Patched {updated} existing simulated rows with actual returns")

    if not dry_run and inserted > 0:
        logger.info("\n🔄 Running evaluate_performance to fill actual returns …")
        try:
            from engines.evaluate_performance import run_evaluation
            run_evaluation()
            logger.info("✅ evaluate_performance complete")
        except Exception as e:
            logger.warning(f"⚠ evaluate_performance failed: {e} — run catchup-evaluation manually")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Backfill historical EGX predictions')
    parser.add_argument('--days', type=int, default=60, help='Days to backfill (default: 60)')
    parser.add_argument('--dry-run', action='store_true', help='Count signals without writing')
    args = parser.parse_args()
    run(days=args.days, dry_run=args.dry_run)
