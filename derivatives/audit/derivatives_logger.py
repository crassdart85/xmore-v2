"""Derivatives-specific audit event logger with SHA-256 hash chain.

Maintains a separate SQLite table ``derivatives_events`` that is linked to
the main audit chain via ``linked_run_id``.  Every record stores a
``prev_hash`` pointing to the previous derivatives event, forming its own
immutable chain.  The first record's ``prev_hash`` is seeded from
``AuditLogger.get_latest_hash()`` to tie both chains together.

Schema
------
::

    derivatives_events (
        event_id        TEXT PRIMARY KEY,   -- UUID
        event_type      TEXT NOT NULL,       -- pricing|greeks|vol_surface|var
        linked_run_id   TEXT NOT NULL,       -- run UUID passed by caller
        inputs_json     TEXT NOT NULL,
        result_json     TEXT NOT NULL,
        record_hash     TEXT NOT NULL,       -- SHA-256 of all fields + prev_hash
        prev_hash       TEXT NOT NULL,
        recorded_at     TEXT NOT NULL        -- ISO-8601 UTC
    )

Custom exceptions
-----------------
``AuditFailureError`` — raised by ``verify_chain()`` when any hash mismatch
is detected.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent.parent.parent / "derivatives_audit.db"


class AuditFailureError(Exception):
    """Raised when the derivatives audit hash chain is broken.

    Attributes:
        event_id: The ``event_id`` of the first offending record.
    """

    def __init__(self, message: str, event_id: Optional[str] = None):
        super().__init__(message)
        self.event_id = event_id


class DerivativesLogger:
    """Append-only, hash-chained audit logger for derivatives events.

    Each call to a ``log_*`` method appends one record to
    ``derivatives_events``.  The SHA-256 hash of each record covers its own
    content plus ``prev_hash``, creating a tamper-evident chain.

    Args:
        db_path: SQLite file path.  Defaults to
            ``<repo_root>/derivatives_audit.db``.
        audit_logger: Optional ``AuditLogger`` instance.  When provided, the
            first record's ``prev_hash`` is seeded from the main audit chain.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        audit_logger=None,
    ):
        self.db_path = str(db_path or DB_PATH)
        self.audit_logger = audit_logger
        self._init_db()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        """Create ``derivatives_events`` table if it does not exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS derivatives_events (
                    event_id      TEXT PRIMARY KEY,
                    event_type    TEXT NOT NULL,
                    linked_run_id TEXT NOT NULL,
                    inputs_json   TEXT NOT NULL,
                    result_json   TEXT NOT NULL,
                    record_hash   TEXT NOT NULL,
                    prev_hash     TEXT NOT NULL,
                    recorded_at   TEXT NOT NULL
                )
                """
            )

    # ------------------------------------------------------------------
    # Internal: write one record
    # ------------------------------------------------------------------

    def _write(
        self,
        event_type: str,
        linked_run_id: str,
        inputs: dict,
        result: dict,
    ) -> str:
        """Append one event to the chain.

        Args:
            event_type: One of ``pricing``, ``greeks``, ``vol_surface``,
                ``var``.
            linked_run_id: The caller-supplied run UUID.
            inputs: Serialisable input dict.
            result: Serialisable result dict.

        Returns:
            New ``event_id`` UUID string.
        """
        event_id = str(uuid.uuid4())
        prev_hash = self._get_latest_hash()
        now = datetime.now(timezone.utc).isoformat()
        inputs_json = json.dumps(inputs, default=str)
        result_json = json.dumps(result, default=str)

        record_hash = hashlib.sha256(
            f"{event_id}{event_type}{linked_run_id}"
            f"{inputs_json}{result_json}{prev_hash}{now}".encode()
        ).hexdigest()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO derivatives_events
                    (event_id, event_type, linked_run_id,
                     inputs_json, result_json,
                     record_hash, prev_hash, recorded_at)
                VALUES (?,?,?,?,?,?,?,?)
                """,
                (
                    event_id,
                    event_type,
                    linked_run_id,
                    inputs_json,
                    result_json,
                    record_hash,
                    prev_hash,
                    now,
                ),
            )
        return event_id

    def _get_latest_hash(self) -> str:
        """Return the hash of the most-recent derivatives event.

        If the derivatives table is empty, falls back to the main audit
        chain hash (or ``"0" * 64`` if neither exists).

        Returns:
            64-character hex SHA-256 digest.
        """
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT record_hash FROM derivatives_events "
                "ORDER BY recorded_at DESC LIMIT 1"
            ).fetchone()
        if row:
            return row[0]
        # Seed from main audit chain
        if self.audit_logger is not None:
            try:
                return self.audit_logger.get_latest_hash()
            except Exception:
                pass
        return "0" * 64

    # ------------------------------------------------------------------
    # Public log_* methods
    # ------------------------------------------------------------------

    def log_pricing(self, pricer, result: float, run_id: str) -> str:
        """Log a BSM or binomial pricing call.

        Args:
            pricer: The ``BSMPricer`` (or compatible) instance used.
            result: The computed option price.
            run_id: Caller-supplied run UUID (from outer audit log).

        Returns:
            ``event_id`` of the new derivatives_events record.

        Audit:
            This method itself appends to the hash chain.  No further
            logging is needed by the caller.
        """
        inputs = {
            "S": getattr(pricer, "S", None),
            "K": getattr(pricer, "K", None),
            "T": getattr(pricer, "T", None),
            "r": getattr(pricer, "r", None),
            "sigma": getattr(pricer, "sigma", None),
            "option_type": getattr(pricer, "option_type", None),
            "q": getattr(pricer, "q", None),
        }
        result_dict = {"price": float(result)}
        return self._write("pricing", run_id, inputs, result_dict)

    def log_greeks(
        self,
        greeks,
        second_order,
        run_id: str,
    ) -> str:
        """Log a Greeks computation.

        Args:
            greeks: ``Greeks`` dataclass (first-order).
            second_order: ``SecondOrderGreeks`` dataclass or ``None``.
            run_id: Caller-supplied run UUID.

        Returns:
            ``event_id`` of the new record.
        """
        inputs = {}
        result_dict: dict = {}
        if hasattr(greeks, "as_dict"):
            result_dict["first_order"] = greeks.as_dict()
        else:
            result_dict["first_order"] = str(greeks)
        if second_order is not None and hasattr(second_order, "as_dict"):
            result_dict["second_order"] = second_order.as_dict()
        else:
            result_dict["second_order"] = None
        return self._write("greeks", run_id, inputs, result_dict)

    def log_vol_surface(self, surface, run_id: str) -> str:
        """Log a VolSurface calibration event.

        Args:
            surface: A ``VolSurface`` instance with ``to_dict()`` method.
            run_id: Caller-supplied run UUID.

        Returns:
            ``event_id`` of the new record.
        """
        inputs = {
            "n_expiries": int(len(surface.expiries)),
            "n_strikes": int(len(surface.strikes)),
            "S": float(surface.S),
            "r": float(surface.r),
            "q": float(surface.q),
        }
        result_dict = surface.to_dict()
        return self._write("vol_surface", run_id, inputs, result_dict)

    def log_var(self, var_result, run_id: str) -> str:
        """Log a VaR/CVaR computation.

        Args:
            var_result: An ``OptionsVaRResult`` or ``VaRResult`` instance.
            run_id: Caller-supplied run UUID.

        Returns:
            ``event_id`` of the new record.
        """
        inputs = {}
        result_dict = {
            "var": getattr(var_result, "var", None),
            "cvar": getattr(var_result, "cvar", None),
            "confidence": getattr(var_result, "confidence", None),
            "horizon_days": getattr(var_result, "horizon_days", None),
            "method": getattr(var_result, "method", None),
            "n_scenarios": getattr(var_result, "n_scenarios", None),
            "stressed_scenario": getattr(var_result, "stressed_scenario", None),
        }
        return self._write("var", run_id, inputs, result_dict)

    # ------------------------------------------------------------------
    # Public: verify_chain
    # ------------------------------------------------------------------

    def verify_chain(self, from_event_id: Optional[str] = None) -> bool:
        """Walk the derivatives_events hash chain and verify integrity.

        Args:
            from_event_id: Optional starting event ID.  If provided, only
                records with ``recorded_at`` >= that event's timestamp are
                verified.  Defaults to verifying the entire chain.

        Returns:
            ``True`` if the chain is intact.

        Raises:
            AuditFailureError: Immediately on the first hash mismatch
                detected, with ``event_id`` pointing to the offending record.

        Notes:
            * Records are walked in ``recorded_at`` ascending order.
            * For each record, the stored ``record_hash`` is recomputed and
              compared to the stored value.
            * The ``prev_hash`` of each record must equal the ``record_hash``
              of its predecessor.
        """
        with sqlite3.connect(self.db_path) as conn:
            if from_event_id is not None:
                start_ts = conn.execute(
                    "SELECT recorded_at FROM derivatives_events WHERE event_id = ?",
                    (from_event_id,),
                ).fetchone()
                if start_ts is None:
                    raise AuditFailureError(
                        f"Event ID '{from_event_id}' not found.",
                        event_id=from_event_id,
                    )
                rows = conn.execute(
                    """
                    SELECT event_id, event_type, linked_run_id,
                           inputs_json, result_json, record_hash, prev_hash, recorded_at
                    FROM derivatives_events
                    WHERE recorded_at >= ?
                    ORDER BY recorded_at ASC
                    """,
                    (start_ts[0],),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT event_id, event_type, linked_run_id,
                           inputs_json, result_json, record_hash, prev_hash, recorded_at
                    FROM derivatives_events
                    ORDER BY recorded_at ASC
                    """
                ).fetchall()

        if not rows:
            return True

        prev_hash_expected: Optional[str] = None

        for row in rows:
            (event_id, event_type, linked_run_id,
             inputs_json, result_json, record_hash,
             prev_hash, recorded_at) = row

            # Recompute hash
            recomputed = hashlib.sha256(
                f"{event_id}{event_type}{linked_run_id}"
                f"{inputs_json}{result_json}{prev_hash}{recorded_at}".encode()
            ).hexdigest()

            if recomputed != record_hash:
                raise AuditFailureError(
                    f"Hash mismatch for event_id='{event_id}': "
                    f"stored={record_hash}, recomputed={recomputed}",
                    event_id=event_id,
                )

            # Check prev_hash linkage (skip for the very first record in query)
            if prev_hash_expected is not None and prev_hash != prev_hash_expected:
                raise AuditFailureError(
                    f"Chain break at event_id='{event_id}': "
                    f"prev_hash={prev_hash} != expected={prev_hash_expected}",
                    event_id=event_id,
                )

            prev_hash_expected = record_hash

        return True
