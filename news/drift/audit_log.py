"""
news/drift/audit_log.py — Immutable audit log for drift adjustments.

All records are written to the drift_adjustment_log table using the
existing get_connection() abstraction (PG / SQLite).

Immutability is enforced via SHA-256 audit_hash: a tamper-detection
hash over the core numeric fields of each record. Calling verify_integrity()
recomputes the hash and returns False if any mismatch is detected.

This satisfies institutional auditability requirements: every drift
parameter change has a full provenance trail back to the originating
news chunk and article headline.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import List, Optional

from news.models import DriftAdjustmentRecord, EventType

logger = logging.getLogger(__name__)


def _compute_hash(record: DriftAdjustmentRecord) -> str:
    payload = json.dumps({
        "adjustment_id": record.adjustment_id,
        "chunk_id":      record.chunk_id,
        "asset_ticker":  record.asset_ticker,
        "adjustment_bps": record.adjustment_bps,
        "applied_at":    record.applied_at.isoformat(),
    }, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


class AuditLog:
    """Thread-safe (per-connection) audit log writer and reader."""

    def log(self, record: DriftAdjustmentRecord) -> None:
        """Persist a DriftAdjustmentRecord to the DB."""
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
        from database import get_connection, _adapt_sql, DATABASE_URL

        if not record.audit_hash:
            record.audit_hash = _compute_hash(record)

        event_val = record.event_type.value if hasattr(record.event_type, "value") else str(record.event_type)

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                if DATABASE_URL:
                    sql = """
                        INSERT INTO drift_adjustment_log
                            (adjustment_id, chunk_id, asset_ticker, original_drift,
                             adjustment_bps, adjusted_drift, decay_halflife_days,
                             applied_at, expires_at, event_type, source_headline,
                             confidence, applied_by, audit_hash)
                        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
                        ON CONFLICT (adjustment_id) DO NOTHING
                    """
                else:
                    sql = """
                        INSERT OR IGNORE INTO drift_adjustment_log
                            (adjustment_id, chunk_id, asset_ticker, original_drift,
                             adjustment_bps, adjusted_drift, decay_halflife_days,
                             applied_at, expires_at, event_type, source_headline,
                             confidence, applied_by, audit_hash)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """

                cursor.execute(sql, (
                    record.adjustment_id,
                    record.chunk_id,
                    record.asset_ticker,
                    record.original_drift,
                    record.adjustment_bps,
                    record.adjusted_drift,
                    record.decay_halflife_days,
                    record.applied_at.isoformat(),
                    record.expires_at.isoformat(),
                    event_val,
                    record.source_headline[:500],
                    record.confidence,
                    record.applied_by,
                    record.audit_hash,
                ))
        except Exception as exc:
            logger.error("Audit log write failed for %s: %s", record.adjustment_id, exc)

    def get_active_adjustments(self, ticker: str) -> List[DriftAdjustmentRecord]:
        """Return all non-expired adjustments for a given ticker."""
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
        from database import get_connection, _adapt_sql, DATABASE_URL

        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                sql = _adapt_sql("""
                    SELECT adjustment_id, chunk_id, asset_ticker, original_drift,
                           adjustment_bps, adjusted_drift, decay_halflife_days,
                           applied_at, expires_at, event_type, source_headline,
                           confidence, applied_by, audit_hash
                    FROM drift_adjustment_log
                    WHERE asset_ticker = ? AND expires_at > ?
                    ORDER BY applied_at DESC
                """)
                cursor.execute(sql, (ticker, now_iso))
                rows = cursor.fetchall()
        except Exception as exc:
            logger.error("get_active_adjustments failed: %s", exc)
            return []

        records = []
        for row in rows:
            r = dict(row) if hasattr(row, "keys") else {
                "adjustment_id": row[0], "chunk_id": row[1], "asset_ticker": row[2],
                "original_drift": row[3], "adjustment_bps": row[4],
                "adjusted_drift": row[5], "decay_halflife_days": row[6],
                "applied_at": row[7], "expires_at": row[8], "event_type": row[9],
                "source_headline": row[10], "confidence": row[11],
                "applied_by": row[12], "audit_hash": row[13],
            }
            try:
                applied_at = r["applied_at"]
                expires_at = r["expires_at"]
                if isinstance(applied_at, str):
                    applied_at = datetime.fromisoformat(applied_at.replace("Z", "+00:00"))
                if isinstance(expires_at, str):
                    expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))

                records.append(DriftAdjustmentRecord(
                    adjustment_id=r["adjustment_id"],
                    chunk_id=r["chunk_id"],
                    asset_ticker=r["asset_ticker"],
                    original_drift=float(r["original_drift"]),
                    adjustment_bps=float(r["adjustment_bps"]),
                    adjusted_drift=float(r["adjusted_drift"]),
                    decay_halflife_days=int(r["decay_halflife_days"]),
                    applied_at=applied_at,
                    expires_at=expires_at,
                    event_type=EventType(r["event_type"]),
                    source_headline=r["source_headline"],
                    confidence=float(r["confidence"]),
                    applied_by=r["applied_by"],
                    audit_hash=r["audit_hash"],
                ))
            except Exception as exc:
                logger.warning("Could not parse audit row: %s", exc)
        return records

    def verify_integrity(self, adjustment_id: str) -> bool:
        """Recompute audit hash and compare to stored value. Returns False if tampered."""
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
        from database import get_connection, _adapt_sql

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    _adapt_sql("SELECT * FROM drift_adjustment_log WHERE adjustment_id = ?"),
                    (adjustment_id,)
                )
                row = cursor.fetchone()
        except Exception:
            return False

        if not row:
            return False

        r = dict(row) if hasattr(row, "keys") else {}
        try:
            applied_at = r.get("applied_at", "")
            if hasattr(applied_at, "isoformat"):
                applied_at = applied_at.isoformat()

            payload = json.dumps({
                "adjustment_id": r["adjustment_id"],
                "chunk_id":      r["chunk_id"],
                "asset_ticker":  r["asset_ticker"],
                "adjustment_bps": r["adjustment_bps"],
                "applied_at":    applied_at,
            }, sort_keys=True)
            expected = hashlib.sha256(payload.encode()).hexdigest()
            return expected == r.get("audit_hash", "")
        except Exception:
            return False

    def get_recent_adjustments(self, limit: int = 50) -> List[dict]:
        """Return the most recent drift adjustments (all tickers) as plain dicts."""
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
        from database import get_connection, _adapt_sql, DATABASE_URL

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                sql = _adapt_sql("""
                    SELECT adjustment_id, asset_ticker, adjustment_bps,
                           event_type, source_headline, applied_at, expires_at, confidence
                    FROM drift_adjustment_log
                    ORDER BY applied_at DESC
                    LIMIT ?
                """)
                cursor.execute(sql, (limit,))
                rows = cursor.fetchall()
            return [dict(r) if hasattr(r, "keys") else {
                "adjustment_id": r[0], "asset_ticker": r[1], "adjustment_bps": r[2],
                "event_type": r[3], "source_headline": r[4], "applied_at": str(r[5]),
                "expires_at": str(r[6]), "confidence": r[7],
            } for r in rows]
        except Exception as exc:
            logger.error("get_recent_adjustments failed: %s", exc)
            return []
