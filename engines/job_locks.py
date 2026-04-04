"""
Job Locks — lightweight advisory locking to prevent concurrent pipeline steps.

Prevents evaluate.py from reading prices while collect_data.py is still writing them.
Uses a `job_locks` table with TTL-based expiry (default 10 min).

Usage:
    from engines.job_locks import acquire_lock, release_lock, is_lock_held

    acquire_lock(conn, 'intraday-price-update')
    try:
        ... do work ...
    finally:
        release_lock(conn, 'intraday-price-update')

    if is_lock_held(conn, 'intraday-price-update'):
        print("Price update in progress, skipping evaluation")
        sys.exit(0)
"""

import os
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv('DATABASE_URL')


def _ph(n: int) -> str:
    return f'${n}' if DATABASE_URL else '?'


def _now_expr() -> str:
    return 'NOW()' if DATABASE_URL else "datetime('now')"


def ensure_job_locks_table(conn):
    """Create the job_locks table if it doesn't exist."""
    if DATABASE_URL:
        auto_id = 'TEXT PRIMARY KEY'
    else:
        auto_id = 'TEXT PRIMARY KEY'

    cursor = conn.cursor()
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS job_locks (
            job_name TEXT PRIMARY KEY,
            locked_at TIMESTAMP NOT NULL DEFAULT {_now_expr()},
            expires_at TIMESTAMP NOT NULL
        )
    """)
    conn.commit()


def acquire_lock(conn, job_name: str, ttl_minutes: int = 10) -> bool:
    """
    Acquire an advisory lock for the given job.
    Returns True if lock was acquired, False if already held by another run.
    Expired locks are automatically overwritten.
    """
    try:
        ensure_job_locks_table(conn)
        cursor = conn.cursor()

        if DATABASE_URL:
            # PostgreSQL: upsert, but only if expired or not present
            cursor.execute("""
                INSERT INTO job_locks (job_name, locked_at, expires_at)
                VALUES ($1, NOW(), NOW() + INTERVAL '%s minutes')
                ON CONFLICT (job_name) DO UPDATE
                SET locked_at = NOW(),
                    expires_at = NOW() + INTERVAL '%s minutes'
                WHERE job_locks.expires_at < NOW()
            """ % (ttl_minutes, ttl_minutes), (job_name,))
        else:
            now = datetime.utcnow()
            expires = now + timedelta(minutes=ttl_minutes)
            now_str = now.strftime('%Y-%m-%d %H:%M:%S')
            expires_str = expires.strftime('%Y-%m-%d %H:%M:%S')
            # Delete expired, then insert
            cursor.execute(
                "DELETE FROM job_locks WHERE job_name = ? AND expires_at < ?",
                (job_name, now_str)
            )
            cursor.execute(
                "INSERT OR IGNORE INTO job_locks (job_name, locked_at, expires_at) VALUES (?, ?, ?)",
                (job_name, now_str, expires_str)
            )

        conn.commit()

        # Verify we hold the lock
        cursor.execute(
            f"SELECT job_name FROM job_locks WHERE job_name = {_ph(1)}",
            (job_name,)
        )
        row = cursor.fetchone()
        acquired = row is not None
        if acquired:
            logger.info(f"Lock acquired: {job_name} (TTL={ttl_minutes}m)")
        else:
            logger.warning(f"Lock NOT acquired: {job_name} (held by another run)")
        return acquired

    except Exception as e:
        logger.warning(f"Lock acquire failed for {job_name}: {e}")
        return True  # Fail-open: don't block pipeline on lock failures


def release_lock(conn, job_name: str):
    """Release the advisory lock for the given job."""
    try:
        ensure_job_locks_table(conn)
        cursor = conn.cursor()
        cursor.execute(
            f"DELETE FROM job_locks WHERE job_name = {_ph(1)}",
            (job_name,)
        )
        conn.commit()
        logger.info(f"Lock released: {job_name}")
    except Exception as e:
        logger.warning(f"Lock release failed for {job_name}: {e}")


def is_lock_held(conn, job_name: str) -> bool:
    """
    Check if a lock is currently held (not expired).
    Returns True if the lock exists and has not expired.
    """
    try:
        ensure_job_locks_table(conn)
        cursor = conn.cursor()

        if DATABASE_URL:
            cursor.execute(
                "SELECT 1 FROM job_locks WHERE job_name = $1 AND expires_at > NOW()",
                (job_name,)
            )
        else:
            now_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute(
                "SELECT 1 FROM job_locks WHERE job_name = ? AND expires_at > ?",
                (job_name, now_str)
            )

        held = cursor.fetchone() is not None
        if held:
            logger.info(f"Lock check: {job_name} is HELD")
        return held

    except Exception as e:
        logger.warning(f"Lock check failed for {job_name}: {e}")
        return False  # Fail-open
