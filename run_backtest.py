#!/usr/bin/env python3
"""Weekly walk-forward backtest runner. Called by GitHub Actions every Sunday."""
import os, sys, time, logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


def get_db_connection():
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        import psycopg2
        return psycopg2.connect(db_url)
    else:
        import sqlite3
        return sqlite3.connect("stocks.db")


def ensure_tables(conn):
    """Create backtest tables if they don't exist."""
    is_pg = 'psycopg2' in type(conn).__module__
    serial  = 'SERIAL' if is_pg else 'INTEGER'
    tstz    = 'TIMESTAMPTZ' if is_pg else 'TIMESTAMP'
    bool_t  = 'BOOLEAN' if is_pg else 'INTEGER'
    now_fn  = 'NOW()' if is_pg else "datetime('now')"
    conflict = "ON CONFLICT (symbol, agent_name, run_date) DO NOTHING" if is_pg else "OR IGNORE"

    sqls = [
        f"""CREATE TABLE IF NOT EXISTS backtest_results (
            id                      {serial} PRIMARY KEY,
            symbol                  TEXT NOT NULL,
            agent_name              TEXT NOT NULL,
            run_date                DATE NOT NULL,
            methodology             TEXT NOT NULL DEFAULT 'walk_forward',
            train_window_days       INTEGER NOT NULL DEFAULT 90,
            test_window_days        INTEGER NOT NULL DEFAULT 20,
            step_size_days          INTEGER NOT NULL DEFAULT 10,
            windows_tested          INTEGER NOT NULL DEFAULT 0,
            directional_accuracy    REAL,
            directional_accuracy_std REAL,
            signal_count_total      INTEGER,
            win_count               INTEGER,
            loss_count              INTEGER,
            avg_return_pct          REAL,
            avg_win_pct             REAL,
            avg_loss_pct            REAL,
            profit_factor           REAL,
            is_simulated            {bool_t} DEFAULT 0,
            data_quality_warning    TEXT DEFAULT '',
            created_at              {tstz} DEFAULT {now_fn},
            updated_at              {tstz} DEFAULT {now_fn},
            UNIQUE (symbol, agent_name, run_date)
        )""",
        f"""CREATE TABLE IF NOT EXISTS backtest_run_log (
            id                       {serial} PRIMARY KEY,
            run_date                 DATE NOT NULL UNIQUE,
            symbols_attempted        INTEGER,
            symbols_completed        INTEGER,
            symbols_skipped          INTEGER,
            symbols_failed           INTEGER,
            total_results            INTEGER,
            avg_directional_accuracy REAL,
            best_symbol              TEXT,
            best_agent               TEXT,
            run_duration_seconds     REAL,
            errors_json              TEXT,
            created_at               {tstz} DEFAULT {now_fn}
        )""",
        "CREATE INDEX IF NOT EXISTS idx_backtest_run_date ON backtest_results(run_date DESC)",
        "CREATE INDEX IF NOT EXISTS idx_backtest_symbol   ON backtest_results(symbol, agent_name)",
    ]
    for sql in sqls:
        try:
            if is_pg:
                cur = conn.cursor()
                cur.execute(sql)
                conn.commit()
            else:
                conn.execute(sql)
                conn.commit()
        except Exception as e:
            logger.warning(f"Table creation warning: {e}")


def main():
    start = time.time()
    logger.info("=" * 52)
    logger.info("[BACKTEST] Weekly walk-forward backtest starting")
    logger.info(f"[BACKTEST] Run time: {datetime.utcnow().isoformat()}")
    logger.info("=" * 52)

    conn = get_db_connection()
    try:
        ensure_tables(conn)
        from engines.walk_forward_backtest import WalkForwardBacktest
        engine  = WalkForwardBacktest(db_connection=conn)
        summary = engine.run_full_backtest()
        elapsed = round(time.time() - start, 1)
        logger.info("=" * 52)
        logger.info(f"[BACKTEST] Done in {elapsed}s")
        logger.info(f"[BACKTEST] Symbols tested:  {summary['symbols_tested']}")
        logger.info(f"[BACKTEST] Symbols skipped: {summary['symbols_skipped']}")
        logger.info(f"[BACKTEST] Avg accuracy:    {summary['avg_directional_accuracy']:.1%}")
        if summary.get('best_symbol'):
            logger.info(f"[BACKTEST] Best symbol:     {summary['best_symbol']} ({summary['best_symbol_accuracy']:.1%})")
        if summary.get('best_agent'):
            logger.info(f"[BACKTEST] Best agent:      {summary['best_agent']} ({summary['best_agent_accuracy']:.1%})")
        logger.info("=" * 52)
        sys.exit(0)
    except Exception as e:
        logger.error(f"[BACKTEST] Fatal: {e}", exc_info=True)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
