"""Immutable audit logger with SHA-256 hash chain.

Every record is linked to its predecessor via ``prev_hash``, forming a
tamper-evident chain.  The ``record_hash`` field covers the record's own
content *plus* ``prev_hash``, so any mutation of a past record breaks every
subsequent hash.
"""
# DERIVATIVES MODULE INTEGRATION
import sqlite3
import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "audit.db"


class AuditLogger:
    """Append-only, hash-chained audit event store backed by SQLite.

    Args:
        db_path: Path to the SQLite database file.  Defaults to
            ``<repo_root>/audit.db``.
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(DB_PATH)
        self._init_db()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        """Create the ``audit_log`` table if it does not already exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_log (
                    run_id       TEXT PRIMARY KEY,
                    event_type   TEXT NOT NULL,
                    inputs_json  TEXT NOT NULL,
                    outputs_json TEXT NOT NULL,
                    record_hash  TEXT NOT NULL,
                    prev_hash    TEXT NOT NULL,
                    recorded_at  TEXT NOT NULL
                )
                """
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def log(self, event_type: str, inputs: dict, outputs: dict) -> str:
        """Append a new audit record to the chain.

        Args:
            event_type: Free-text category label (e.g. ``"pricing"``).
            inputs: Arbitrary dict of input parameters.
            outputs: Arbitrary dict of computed outputs.

        Returns:
            The ``run_id`` UUID string for the newly created record.
        """
        run_id = str(uuid.uuid4())
        prev_hash = self.get_latest_hash()
        now = datetime.now(timezone.utc).isoformat()
        inputs_json = json.dumps(inputs, default=str)
        outputs_json = json.dumps(outputs, default=str)
        record_hash = hashlib.sha256(
            f"{run_id}{event_type}{inputs_json}{outputs_json}{prev_hash}{now}".encode()
        ).hexdigest()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO audit_log VALUES (?,?,?,?,?,?,?)",
                (
                    run_id,
                    event_type,
                    inputs_json,
                    outputs_json,
                    record_hash,
                    prev_hash,
                    now,
                ),
            )
        return run_id

    def get_latest_hash(self) -> str:
        """Return the SHA-256 hash of the most-recently written audit record.

        Used by ``DerivativesLogger`` to initialise the ``prev_hash`` of the
        first record in a new derivatives hash chain.

        Returns:
            64-character hex digest, or ``"0" * 64`` when the table is empty.

        # DERIVATIVES MODULE INTEGRATION
        """
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT record_hash FROM audit_log ORDER BY recorded_at DESC LIMIT 1"
            ).fetchone()
        return row[0] if row else "0" * 64
