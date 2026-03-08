"""
xmore.egx_etp.db
~~~~~~~~~~~~~~~~
Database layer for the EGX ETP ingestion pipeline.

Supports:
- PostgreSQL (psycopg v3) when DATABASE_URL is set
- SQLite fallback for local development

Public API
----------
get_connection()                                -> connection object (pg or sqlite)
ensure_schema(conn)                             -> None
upsert_product(conn, card, classification)      -> int  (etp_id)
insert_market_snapshot(conn, etp_id, card, vol_record=None) -> None
insert_holdings(conn, etp_id, rows, snapshot_date) -> None
log_run(conn, run_type)                         -> int  (run_id)
finish_run(conn, run_id, status, stats, error=None) -> None
"""

from __future__ import annotations

import logging
import os
import sqlite3
from datetime import date, datetime, timezone
from typing import Any, List, Optional

from xmore.egx_etp.models import ClassificationResult, HoldingRow, ProductCard, VolumeRecord

logger = logging.getLogger(__name__)

_DATABASE_URL = os.environ.get("DATABASE_URL", "")

# ---------------------------------------------------------------------------
# Mode detection
# ---------------------------------------------------------------------------

def _is_postgres() -> bool:
    return bool(_DATABASE_URL)


# ---------------------------------------------------------------------------
# PostgreSQL connection
# ---------------------------------------------------------------------------

def _pg_connection():
    """Return a live psycopg (v3) connection."""
    try:
        import psycopg  # type: ignore
        from psycopg.rows import dict_row  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "psycopg (v3) is not installed. Run: pip install 'psycopg[binary]'"
        ) from exc

    conn = psycopg.connect(_DATABASE_URL, row_factory=dict_row)
    conn.autocommit = False
    return conn


# ---------------------------------------------------------------------------
# SQLite connection (local dev fallback)
# ---------------------------------------------------------------------------

_SQLITE_PATH = os.environ.get("SQLITE_PATH", "./egx_etp.db")


def _sqlite_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(_SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ---------------------------------------------------------------------------
# Public connection factory
# ---------------------------------------------------------------------------

def get_connection():
    """Return a database connection (psycopg or sqlite3)."""
    if _is_postgres():
        logger.debug("Using PostgreSQL: %s", _DATABASE_URL[:40] + "...")
        return _pg_connection()
    logger.debug("DATABASE_URL not set — using SQLite at %s", _SQLITE_PATH)
    return _sqlite_connection()


# ---------------------------------------------------------------------------
# DDL helpers
# ---------------------------------------------------------------------------

def _pg_ddl() -> str:
    return """
CREATE TABLE IF NOT EXISTS etp_product (
    etp_id BIGSERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    arabic_name TEXT,
    english_name TEXT,
    issuer TEXT,
    instrument_type TEXT NOT NULL CHECK (instrument_type IN ('ETF','GOLD_ETP','INDEX_TRACKER','STRUCTURED_NOTE','ETN','UNKNOWN_ETP')),
    underlying_exposure TEXT,
    currency TEXT DEFAULT 'EGP',
    nav_available BOOLEAN DEFAULT FALSE,
    holdings_available BOOLEAN DEFAULT FALSE,
    prem_disc_available BOOLEAN DEFAULT FALSE,
    classification_confidence NUMERIC(5,2),
    classification_reason TEXT,
    source_url TEXT NOT NULL,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS etp_market_snapshot (
    etp_id BIGINT NOT NULL REFERENCES etp_product(etp_id) ON DELETE CASCADE,
    asof_date DATE NOT NULL,
    close_price NUMERIC(18,6),
    change_pct NUMERIC(18,6),
    nav_value NUMERIC(18,6),
    prem_disc NUMERIC(18,6),
    volume BIGINT,
    value NUMERIC(18,2),
    source_url TEXT NOT NULL,
    scraped_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (etp_id, asof_date)
);

CREATE TABLE IF NOT EXISTS etp_holdings_snapshot (
    snapshot_id BIGSERIAL PRIMARY KEY,
    etp_id BIGINT NOT NULL REFERENCES etp_product(etp_id) ON DELETE CASCADE,
    snapshot_date DATE NOT NULL,
    source_url TEXT NOT NULL,
    scraped_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (etp_id, snapshot_date, source_url)
);

CREATE TABLE IF NOT EXISTS etp_holding_line (
    snapshot_id BIGINT NOT NULL REFERENCES etp_holdings_snapshot(snapshot_id) ON DELETE CASCADE,
    line_no INTEGER NOT NULL,
    holding_name TEXT NOT NULL,
    holding_symbol TEXT,
    weight_pct NUMERIC(18,10),
    PRIMARY KEY (snapshot_id, line_no)
);

CREATE TABLE IF NOT EXISTS raw_page_archive (
    archive_id BIGSERIAL PRIMARY KEY,
    url TEXT NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    fetch_method TEXT NOT NULL,
    content_type TEXT DEFAULT 'text/html',
    body_path TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scrape_run_log (
    run_id BIGSERIAL PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running','success','failed')),
    cards_found INTEGER,
    holdings_rows INTEGER,
    nav_rows INTEGER,
    volume_rows INTEGER,
    error_message TEXT,
    run_type TEXT NOT NULL DEFAULT 'incremental' CHECK (run_type IN ('incremental','backfill'))
);
"""


def _sqlite_ddl() -> str:
    """SQLite-compatible DDL (no BIGSERIAL, no TIMESTAMPTZ, no BOOLEAN)."""
    return """
CREATE TABLE IF NOT EXISTS etp_product (
    etp_id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    arabic_name TEXT,
    english_name TEXT,
    issuer TEXT,
    instrument_type TEXT NOT NULL,
    underlying_exposure TEXT,
    currency TEXT DEFAULT 'EGP',
    nav_available INTEGER DEFAULT 0,
    holdings_available INTEGER DEFAULT 0,
    prem_disc_available INTEGER DEFAULT 0,
    classification_confidence REAL,
    classification_reason TEXT,
    source_url TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS etp_market_snapshot (
    etp_id INTEGER NOT NULL REFERENCES etp_product(etp_id) ON DELETE CASCADE,
    asof_date TEXT NOT NULL,
    close_price REAL,
    change_pct REAL,
    nav_value REAL,
    prem_disc REAL,
    volume INTEGER,
    value REAL,
    source_url TEXT NOT NULL,
    scraped_at TEXT NOT NULL,
    PRIMARY KEY (etp_id, asof_date)
);

CREATE TABLE IF NOT EXISTS etp_holdings_snapshot (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    etp_id INTEGER NOT NULL REFERENCES etp_product(etp_id) ON DELETE CASCADE,
    snapshot_date TEXT NOT NULL,
    source_url TEXT NOT NULL,
    scraped_at TEXT NOT NULL,
    UNIQUE (etp_id, snapshot_date, source_url)
);

CREATE TABLE IF NOT EXISTS etp_holding_line (
    snapshot_id INTEGER NOT NULL REFERENCES etp_holdings_snapshot(snapshot_id) ON DELETE CASCADE,
    line_no INTEGER NOT NULL,
    holding_name TEXT NOT NULL,
    holding_symbol TEXT,
    weight_pct REAL,
    PRIMARY KEY (snapshot_id, line_no)
);

CREATE TABLE IF NOT EXISTS raw_page_archive (
    archive_id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    fetch_method TEXT NOT NULL,
    content_type TEXT DEFAULT 'text/html',
    body_path TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scrape_run_log (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    cards_found INTEGER,
    holdings_rows INTEGER,
    nav_rows INTEGER,
    volume_rows INTEGER,
    error_message TEXT,
    run_type TEXT NOT NULL DEFAULT 'incremental'
);
"""


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> str:
    return date.today().isoformat()


def _bool_val(v: bool, pg: bool) -> Any:
    """SQLite stores booleans as 0/1; psycopg accepts Python bool."""
    return v if pg else int(v)


def _execute(conn, sql: str, params: tuple = ()) -> Any:
    """Unified execute for both psycopg and sqlite3."""
    if _is_postgres():
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur
    else:
        return conn.execute(sql, params)


def _executemany(conn, sql: str, param_list: list[tuple]) -> None:
    if _is_postgres():
        with conn.cursor() as cur:
            cur.executemany(sql, param_list)
    else:
        conn.executemany(sql, param_list)


def _fetchone(conn, sql: str, params: tuple = ()) -> Optional[Any]:
    if _is_postgres():
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()
    else:
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None


# ---------------------------------------------------------------------------
# Public schema function
# ---------------------------------------------------------------------------

def ensure_schema(conn) -> None:
    """Create all ETP tables if they do not exist."""
    pg = _is_postgres()
    ddl = _pg_ddl() if pg else _sqlite_ddl()

    if pg:
        with conn.cursor() as cur:
            cur.execute(ddl)
        conn.commit()
    else:
        conn.executescript(ddl)
        conn.commit()

    logger.info("Schema ensured (mode=%s)", "postgres" if pg else "sqlite")


# ---------------------------------------------------------------------------
# upsert_product
# ---------------------------------------------------------------------------

def upsert_product(conn, card: ProductCard, classification: ClassificationResult) -> int:
    """
    Insert or update etp_product for *card*.

    Returns the etp_id (integer).
    """
    pg = _is_postgres()
    now = _now_iso()

    nav_flag = _bool_val(card.nav_value is not None, pg)
    prem_flag = _bool_val(card.prem_disc is not None, pg)
    # holdings_available is set later via update after holdings insert

    if pg:
        sql = """
            INSERT INTO etp_product
                (code, arabic_name, english_name, issuer, instrument_type,
                 underlying_exposure, currency,
                 nav_available, holdings_available, prem_disc_available,
                 classification_confidence, classification_reason,
                 source_url, first_seen_at, last_seen_at)
            VALUES
                (%s, %s, %s, %s, %s, %s, 'EGP', %s, FALSE, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (code) DO UPDATE SET
                arabic_name = COALESCE(EXCLUDED.arabic_name, etp_product.arabic_name),
                english_name = COALESCE(EXCLUDED.english_name, etp_product.english_name),
                issuer = COALESCE(EXCLUDED.issuer, etp_product.issuer),
                instrument_type = EXCLUDED.instrument_type,
                underlying_exposure = COALESCE(EXCLUDED.underlying_exposure, etp_product.underlying_exposure),
                nav_available = EXCLUDED.nav_available OR etp_product.nav_available,
                prem_disc_available = EXCLUDED.prem_disc_available OR etp_product.prem_disc_available,
                classification_confidence = EXCLUDED.classification_confidence,
                classification_reason = EXCLUDED.classification_reason,
                source_url = EXCLUDED.source_url,
                last_seen_at = EXCLUDED.last_seen_at
            RETURNING etp_id
        """
        params = (
            card.code,
            card.arabic_name,
            card.english_name,
            classification.issuer,
            classification.instrument_type,
            classification.underlying_exposure,
            nav_flag,
            prem_flag,
            classification.confidence,
            classification.reason,
            card.source_url,
            now,
            now,
        )
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            etp_id: int = row["etp_id"]
        conn.commit()
        return etp_id

    else:
        # SQLite — no RETURNING; use INSERT OR REPLACE + lastrowid
        # First try insert
        insert_sql = """
            INSERT OR IGNORE INTO etp_product
                (code, arabic_name, english_name, issuer, instrument_type,
                 underlying_exposure, currency,
                 nav_available, holdings_available, prem_disc_available,
                 classification_confidence, classification_reason,
                 source_url, first_seen_at, last_seen_at)
            VALUES (?,?,?,?,?,?,'EGP',?,0,?,?,?,?,?,?)
        """
        conn.execute(
            insert_sql,
            (
                card.code,
                card.arabic_name,
                card.english_name,
                classification.issuer,
                classification.instrument_type,
                classification.underlying_exposure,
                nav_flag,
                prem_flag,
                classification.confidence,
                classification.reason,
                card.source_url,
                now,
                now,
            ),
        )
        # Then update (handles both insert and update case)
        update_sql = """
            UPDATE etp_product SET
                arabic_name = COALESCE(?, arabic_name),
                english_name = COALESCE(?, english_name),
                issuer = COALESCE(?, issuer),
                instrument_type = ?,
                underlying_exposure = COALESCE(?, underlying_exposure),
                nav_available = ? OR nav_available,
                prem_disc_available = ? OR prem_disc_available,
                classification_confidence = ?,
                classification_reason = ?,
                source_url = ?,
                last_seen_at = ?
            WHERE code = ?
        """
        conn.execute(
            update_sql,
            (
                card.arabic_name,
                card.english_name,
                classification.issuer,
                classification.instrument_type,
                classification.underlying_exposure,
                nav_flag,
                prem_flag,
                classification.confidence,
                classification.reason,
                card.source_url,
                now,
                card.code,
            ),
        )
        row = conn.execute("SELECT etp_id FROM etp_product WHERE code = ?", (card.code,)).fetchone()
        etp_id = dict(row)["etp_id"]
        conn.commit()
        return etp_id


# ---------------------------------------------------------------------------
# insert_market_snapshot
# ---------------------------------------------------------------------------

def insert_market_snapshot(
    conn,
    etp_id: int,
    card: ProductCard,
    vol_record: Optional[VolumeRecord] = None,
) -> None:
    """
    Upsert one row into etp_market_snapshot for today's date.

    On conflict (etp_id, asof_date) the row is updated with the latest values.
    """
    pg = _is_postgres()
    today = _today()
    now = _now_iso()

    volume = vol_record.volume if vol_record else None
    value = vol_record.value if vol_record else None

    if pg:
        sql = """
            INSERT INTO etp_market_snapshot
                (etp_id, asof_date, close_price, change_pct, nav_value, prem_disc,
                 volume, value, source_url, scraped_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (etp_id, asof_date) DO UPDATE SET
                close_price = EXCLUDED.close_price,
                change_pct  = EXCLUDED.change_pct,
                nav_value   = EXCLUDED.nav_value,
                prem_disc   = EXCLUDED.prem_disc,
                volume      = COALESCE(EXCLUDED.volume, etp_market_snapshot.volume),
                value       = COALESCE(EXCLUDED.value, etp_market_snapshot.value),
                scraped_at  = EXCLUDED.scraped_at
        """
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (etp_id, today, card.close_price, card.change_pct,
                 card.nav_value, card.prem_disc, volume, value,
                 card.source_url, now),
            )
        conn.commit()
    else:
        sql = """
            INSERT INTO etp_market_snapshot
                (etp_id, asof_date, close_price, change_pct, nav_value, prem_disc,
                 volume, value, source_url, scraped_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT (etp_id, asof_date) DO UPDATE SET
                close_price = excluded.close_price,
                change_pct  = excluded.change_pct,
                nav_value   = excluded.nav_value,
                prem_disc   = excluded.prem_disc,
                volume      = COALESCE(excluded.volume, etp_market_snapshot.volume),
                value       = COALESCE(excluded.value, etp_market_snapshot.value),
                scraped_at  = excluded.scraped_at
        """
        conn.execute(
            sql,
            (etp_id, today, card.close_price, card.change_pct,
             card.nav_value, card.prem_disc, volume, value,
             card.source_url, now),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# insert_holdings
# ---------------------------------------------------------------------------

def insert_holdings(
    conn,
    etp_id: int,
    rows: List[HoldingRow],
    snapshot_date: str,
) -> None:
    """
    Insert a holdings snapshot + holding lines for *etp_id*.

    The snapshot row is upserted (unique on etp_id + snapshot_date + source_url).
    Existing holding lines for this snapshot are replaced.
    """
    if not rows:
        return

    pg = _is_postgres()
    now = _now_iso()
    source_url = "https://www.egx.com.eg/en/FundConstituents.aspx"

    # --- upsert snapshot header ---
    if pg:
        snap_sql = """
            INSERT INTO etp_holdings_snapshot (etp_id, snapshot_date, source_url, scraped_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (etp_id, snapshot_date, source_url) DO UPDATE SET scraped_at = EXCLUDED.scraped_at
            RETURNING snapshot_id
        """
        with conn.cursor() as cur:
            cur.execute(snap_sql, (etp_id, snapshot_date, source_url, now))
            row = cur.fetchone()
            snapshot_id: int = row["snapshot_id"]
    else:
        snap_sql = """
            INSERT OR IGNORE INTO etp_holdings_snapshot (etp_id, snapshot_date, source_url, scraped_at)
            VALUES (?,?,?,?)
        """
        conn.execute(snap_sql, (etp_id, snapshot_date, source_url, now))
        snap_row = conn.execute(
            "SELECT snapshot_id FROM etp_holdings_snapshot WHERE etp_id=? AND snapshot_date=? AND source_url=?",
            (etp_id, snapshot_date, source_url),
        ).fetchone()
        snapshot_id = dict(snap_row)["snapshot_id"]

    # --- delete old lines for this snapshot (idempotent replacement) ---
    if pg:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM etp_holding_line WHERE snapshot_id = %s", (snapshot_id,))
    else:
        conn.execute("DELETE FROM etp_holding_line WHERE snapshot_id = ?", (snapshot_id,))

    # --- insert holding lines ---
    if pg:
        line_sql = """
            INSERT INTO etp_holding_line (snapshot_id, line_no, holding_name, holding_symbol, weight_pct)
            VALUES (%s, %s, %s, %s, %s)
        """
        with conn.cursor() as cur:
            for i, hr in enumerate(rows, start=1):
                cur.execute(
                    line_sql,
                    (snapshot_id, i, hr.holding_name or "?", hr.holding_symbol, hr.weight_pct),
                )
    else:
        line_sql = """
            INSERT INTO etp_holding_line (snapshot_id, line_no, holding_name, holding_symbol, weight_pct)
            VALUES (?,?,?,?,?)
        """
        for i, hr in enumerate(rows, start=1):
            conn.execute(
                line_sql,
                (snapshot_id, i, hr.holding_name or "?", hr.holding_symbol, hr.weight_pct),
            )

    # --- mark holdings_available on parent product ---
    if pg:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE etp_product SET holdings_available = TRUE WHERE etp_id = %s",
                (etp_id,),
            )
    else:
        conn.execute(
            "UPDATE etp_product SET holdings_available = 1 WHERE etp_id = ?",
            (etp_id,),
        )

    conn.commit()
    logger.debug("Holdings inserted: etp_id=%d, snapshot_id=%d, lines=%d", etp_id, snapshot_id, len(rows))


# ---------------------------------------------------------------------------
# log_run / finish_run
# ---------------------------------------------------------------------------

def log_run(conn, run_type: str = "incremental") -> int:
    """
    Insert a new scrape_run_log row with status='running'.

    Returns the run_id.
    """
    pg = _is_postgres()
    now = _now_iso()

    if pg:
        sql = """
            INSERT INTO scrape_run_log (started_at, status, run_type)
            VALUES (%s, 'running', %s)
            RETURNING run_id
        """
        with conn.cursor() as cur:
            cur.execute(sql, (now, run_type))
            row = cur.fetchone()
            run_id: int = row["run_id"]
        conn.commit()
        return run_id
    else:
        sql = "INSERT INTO scrape_run_log (started_at, status, run_type) VALUES (?,?,?)"
        cur = conn.execute(sql, (now, "running", run_type))
        conn.commit()
        return cur.lastrowid


def finish_run(
    conn,
    run_id: int,
    status: str,
    stats: dict,
    error: Optional[str] = None,
) -> None:
    """
    Update the scrape_run_log row with final status and statistics.

    Parameters
    ----------
    status
        ``'success'`` or ``'failed'``
    stats
        Dict with optional keys: cards_found, holdings_rows, nav_rows, volume_rows
    error
        Error message if status=='failed'
    """
    pg = _is_postgres()
    now = _now_iso()

    fields = {
        "finished_at": now,
        "status": status,
        "cards_found": stats.get("cards_found"),
        "holdings_rows": stats.get("holdings_rows"),
        "nav_rows": stats.get("nav_rows"),
        "volume_rows": stats.get("volume_rows"),
        "error_message": error,
    }

    if pg:
        sql = """
            UPDATE scrape_run_log SET
                finished_at = %s, status = %s,
                cards_found = %s, holdings_rows = %s,
                nav_rows = %s, volume_rows = %s,
                error_message = %s
            WHERE run_id = %s
        """
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    fields["finished_at"], fields["status"],
                    fields["cards_found"], fields["holdings_rows"],
                    fields["nav_rows"], fields["volume_rows"],
                    fields["error_message"], run_id,
                ),
            )
        conn.commit()
    else:
        sql = """
            UPDATE scrape_run_log SET
                finished_at = ?, status = ?,
                cards_found = ?, holdings_rows = ?,
                nav_rows = ?, volume_rows = ?,
                error_message = ?
            WHERE run_id = ?
        """
        conn.execute(
            sql,
            (
                fields["finished_at"], fields["status"],
                fields["cards_found"], fields["holdings_rows"],
                fields["nav_rows"], fields["volume_rows"],
                fields["error_message"], run_id,
            ),
        )
        conn.commit()

    logger.info("Run %d finished: status=%s stats=%s", run_id, status, stats)


# ---------------------------------------------------------------------------
# raw_page_archive helper
# ---------------------------------------------------------------------------

def record_archive(conn, url: str, method: str, body_path: str) -> None:
    """Insert one row into raw_page_archive."""
    pg = _is_postgres()
    now = _now_iso()

    if pg:
        sql = """
            INSERT INTO raw_page_archive (url, fetched_at, fetch_method, body_path)
            VALUES (%s, %s, %s, %s)
        """
        with conn.cursor() as cur:
            cur.execute(sql, (url, now, method, body_path))
        conn.commit()
    else:
        sql = "INSERT INTO raw_page_archive (url, fetched_at, fetch_method, body_path) VALUES (?,?,?,?)"
        conn.execute(sql, (url, now, method, body_path))
        conn.commit()
