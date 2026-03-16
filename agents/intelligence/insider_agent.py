"""
Insider Agent — Ownership changes and major shareholder moves (Sunday only).
Sources: yfinance institutional/major holders + insider transactions.
"""
import json
import logging
import time
from datetime import datetime

logger = logging.getLogger(__name__)

CREATE_INSIDER_SQL = """
CREATE TABLE IF NOT EXISTS insider_transactions (
    id                   SERIAL PRIMARY KEY,
    ticker               VARCHAR(10) NOT NULL,
    transaction_date     DATE,
    insider_name         VARCHAR(200),
    insider_role         VARCHAR(100),
    transaction_type     VARCHAR(20),
    shares_transacted    BIGINT,
    price_per_share      NUMERIC(10,2),
    value_egp            BIGINT,
    ownership_pct_after  NUMERIC(6,3),
    threshold_crossed    NUMERIC(5,1),
    source               VARCHAR(50),
    raw_json             TEXT,
    created_at           TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (ticker, transaction_date, insider_name, transaction_type)
)
"""

CREATE_INSIDER_SQL_SQLITE = """
CREATE TABLE IF NOT EXISTS insider_transactions (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker               TEXT NOT NULL,
    transaction_date     TEXT,
    insider_name         TEXT,
    insider_role         TEXT,
    transaction_type     TEXT,
    shares_transacted    INTEGER,
    price_per_share      REAL,
    value_egp            INTEGER,
    ownership_pct_after  REAL,
    threshold_crossed    REAL,
    source               TEXT,
    raw_json             TEXT,
    created_at           TEXT DEFAULT (datetime('now')),
    UNIQUE (ticker, transaction_date, insider_name, transaction_type)
)
"""


def ensure_insider_table(conn):
    from database import DATABASE_URL
    cursor = conn.cursor()
    sql = CREATE_INSIDER_SQL if DATABASE_URL else CREATE_INSIDER_SQL_SQLITE
    try:
        cursor.execute(sql)
    except Exception as e:
        logger.warning(f"[INTEL:INSIDER] Table create: {e}")


def fetch_insider_data(conn) -> int:
    if datetime.today().weekday() != 6:
        logger.info("[INTEL:INSIDER] Skipping — runs Sundays only")
        return 0

    try:
        import yfinance as yf
    except ImportError:
        logger.warning("[INTEL:INSIDER] yfinance not installed — skipping")
        return 0

    from database import DATABASE_URL
    from agents.intelligence.egx_universe import EGX_TOP50

    ensure_insider_table(conn)
    cursor = conn.cursor()
    ph = "%s" if DATABASE_URL else "?"
    count = 0

    for ca, yahoo, *_ in EGX_TOP50:
        try:
            stock = yf.Ticker(yahoo)
            time.sleep(1.5)

            # Insider transactions
            try:
                txns = stock.insider_transactions
                if txns is not None and not txns.empty:
                    for _, row in txns.iterrows():
                        shares   = int(row.get("Shares", 0) or 0)
                        value    = float(row.get("Value", 0) or 0)
                        txn_type = "BUY" if shares > 0 else "SELL"
                        txn_date = row.get("Start Date")
                        try:
                            txn_date = str(txn_date.date()) if hasattr(txn_date, "date") else str(txn_date)
                        except Exception:
                            txn_date = None
                        try:
                            cursor.execute(
                                f"INSERT INTO insider_transactions "
                                f"(ticker, transaction_date, insider_name, insider_role, "
                                f"transaction_type, shares_transacted, value_egp, source) "
                                f"VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})"
                                + (" ON CONFLICT DO NOTHING" if DATABASE_URL else " ON CONFLICT (ticker, transaction_date, insider_name, transaction_type) DO NOTHING"),
                                (
                                    ca, txn_date,
                                    str(row.get("Insider", ""))[:200],
                                    str(row.get("Position", ""))[:100],
                                    txn_type, abs(shares), abs(int(value)),
                                    "yfinance",
                                )
                            )
                            count += 1
                        except Exception as ex:
                            logger.debug(f"[INTEL:INSIDER] {ca} insert: {ex}")
            except Exception:
                pass

        except Exception as e:
            logger.error(f"[INTEL:INSIDER] {ca}: {e}")

    logger.info(f"[INTEL:INSIDER] {count} insider transactions stored")
    return count
