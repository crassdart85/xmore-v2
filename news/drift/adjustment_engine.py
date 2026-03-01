"""
news/drift/adjustment_engine.py — News-driven drift parameter adjustment for Monte Carlo.

Design principles:
  1. Conservative by default: uncertain direction → no adjustment.
  2. Immutable audit log: every adjustment recorded with full provenance.
  3. Exponential decay: impact attenuates over time toward zero.
  4. No double-counting: same article_url+event_type pair only fires once.
  5. Bounded adjustments: max ±500 bps to prevent runaway parameter drift.

Integration with SimulationEngine:
  Call get_net_drift_adjustment(ticker) at the start of each simulation run
  to obtain the current net adjustment in annualized basis points, then add
  it to the historical drift estimate before simulating paths.

  Example:
      engine = SimulationEngine(config)
      engine.fit(returns_df)
      drift_adj_bps = get_net_drift_adjustment("COMI.CA")
      # Apply: adjusted_mu = base_mu + drift_adj_bps / 10_000
"""

from __future__ import annotations

import logging
import math
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from news.models import (
    DriftAdjustmentRecord, DriftDirection, EventType, ProcessedChunk
)
from news.drift.audit_log import AuditLog
from news.drift.decay_model import ExponentialDecayModel

logger = logging.getLogger(__name__)

# ── Impact parameter table ────────────────────────────────────────────────────
# magnitude_bps: annualized drift adjustment at t=0 (full impact).
# decay_halflife_days: days until impact halves.
# affected_scope: "asset" | "sector" | "market".
# confidence_base: prior confidence before any LLM refinement.
#
# Calibration note: these are informed starting points.
# Back-test against EGX event study data and refine per market.

DRIFT_IMPACT_TABLE: Dict[EventType, Dict] = {
    EventType.RATE_DECISION: {
        "magnitude_bps": 150,
        "decay_halflife_days": 10,
        "affected_scope": "sector",
        "confidence_base": 0.85,
    },
    EventType.FX_MOVE: {
        "magnitude_bps": 200,
        "decay_halflife_days": 7,
        "affected_scope": "market",
        "confidence_base": 0.80,
    },
    EventType.EARNINGS_RELEASE: {
        "magnitude_bps": 250,
        "decay_halflife_days": 5,
        "affected_scope": "asset",
        "confidence_base": 0.90,
    },
    EventType.IMF_WORLD_BANK: {
        "magnitude_bps": 180,
        "decay_halflife_days": 14,
        "affected_scope": "market",
        "confidence_base": 0.75,
    },
    EventType.MACRO_DATA: {
        "magnitude_bps": 100,
        "decay_halflife_days": 7,
        "affected_scope": "market",
        "confidence_base": 0.70,
    },
}

_MAX_ADJUSTMENT_BPS = 500.0   # Hard cap: ±500 bps annualised


def _direction_sign(direction: DriftDirection) -> int:
    d = direction.value if hasattr(direction, "value") else str(direction)
    return {"POSITIVE": 1, "NEGATIVE": -1, "NEUTRAL": 0, "UNCERTAIN": 0}.get(d, 0)


def _get_baseline_drift(ticker: str) -> float:
    """
    Look up the most recent annualized drift from the prices table.
    Falls back to 0.0 if the ticker is not in the DB or has < 30 data points.
    """
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    try:
        from database import get_connection, _adapt_sql
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                _adapt_sql("SELECT close FROM prices WHERE symbol = ? ORDER BY date DESC LIMIT 252"),
                (ticker,)
            )
            rows = cursor.fetchall()
        closes = [float(r["close"] if hasattr(r, "keys") else r[0]) for r in rows if r]
        if len(closes) < 30:
            return 0.0
        import numpy as np
        log_rets = np.diff(np.log(closes[::-1]))   # Oldest first
        return float(np.mean(log_rets) * 252)      # Annualised
    except Exception:
        return 0.0


# Static sector → ticker fallback (used when egx30_stocks table not available)
_SECTOR_TICKERS_FALLBACK: Dict[str, List[str]] = {
    "banking": ["COMI.CA", "QNBE.CA", "HDBK.CA", "CIEB.CA", "CANA.CA", "FAIT.CA", "EGBE.CA"],
    "financial_services": ["HRHO.CA", "EFIH.CA", "FWRY.CA", "CCAP.CA", "CICH.CA", "VALU.CA", "CNFN.CA"],
    "real_estate": ["TMGH.CA", "PHDC.CA", "OCDI.CA", "ORHD.CA", "AMER.CA"],
    "energy": ["SKPC.CA", "EPCO.CA", "ABUK.CA"],
    "telecom": ["ETEL.CA", "ORTE.CA"],
    "industrials": ["SUCE.CA", "ARCC.CA", "EAST.CA"],
    "consumer": ["JUFO.CA", "EDIT.CA", "CLHO.CA"],
}

_EGX30_FALLBACK = [
    "COMI.CA", "HRHO.CA", "TMGH.CA", "EFIH.CA", "FWRY.CA", "ORTE.CA",
    "ETEL.CA", "PHDC.CA", "OCDI.CA", "QNBE.CA", "SKPC.CA", "CCAP.CA",
    "HDBK.CA", "CNFN.CA", "EAST.CA", "ORHD.CA", "SUCE.CA", "JUFO.CA",
    "EDIT.CA", "VALU.CA", "CICH.CA", "AMER.CA", "ARCC.CA", "EGBE.CA",
    "BTFH.CA", "BINV.CA", "CLHO.CA", "ESRS.CA", "ALCN.CA", "CIEB.CA",
]


def _resolve_affected_assets(chunk: ProcessedChunk, scope: str) -> List[str]:
    """Return the list of ticker symbols to apply the adjustment to."""
    if scope == "asset" and chunk.affected_assets:
        return list(chunk.affected_assets)

    if scope == "sector" and chunk.affected_sectors:
        # Try DB first; fall back to static map
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
        try:
            from database import get_connection, _adapt_sql, DATABASE_URL
            placeholders = ",".join(
                [f"${i+1}" if DATABASE_URL else "?" for i in range(len(chunk.affected_sectors))]
            )
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    _adapt_sql(f"SELECT symbol FROM egx30_stocks WHERE LOWER(sector_en) IN ({placeholders})"),
                    [s.replace("_", " ") for s in chunk.affected_sectors],
                )
                rows = cursor.fetchall()
            db_tickers = [r["symbol"] if hasattr(r, "keys") else r[0] for r in rows]
            if db_tickers:
                return db_tickers
        except Exception:
            pass
        # Fallback: static sector map
        result: List[str] = []
        for sector in chunk.affected_sectors:
            result.extend(_SECTOR_TICKERS_FALLBACK.get(sector, []))
        return list(dict.fromkeys(result))   # Deduplicate preserving order

    # "market" scope — all EGX30 stocks
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    try:
        from database import get_connection, _adapt_sql
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT symbol FROM egx30_stocks LIMIT 30")
            rows = cursor.fetchall()
        db_tickers = [r["symbol"] if hasattr(r, "keys") else r[0] for r in rows]
        if db_tickers:
            return db_tickers
    except Exception:
        pass
    return _EGX30_FALLBACK


class DriftAdjustmentEngine:
    """
    Receives high-impact news chunks from the ingestion pipeline and applies
    calibrated, time-decaying drift adjustments to simulation parameters.
    """

    def __init__(self) -> None:
        self._audit_log = AuditLog()
        self._decay_model = ExponentialDecayModel()
        self._applied_events: set = set()    # Prevent double-application within session

    def process_chunk(self, chunk: ProcessedChunk) -> int:
        """
        Entry point called by the ingestion pipeline for drift-relevant chunks.
        Returns the number of assets adjusted.
        """
        if chunk.event_type not in DRIFT_IMPACT_TABLE:
            return 0

        event_key = f"{chunk.article_url}|{chunk.event_type.value}"
        if event_key in self._applied_events:
            return 0
        self._applied_events.add(event_key)

        impact = DRIFT_IMPACT_TABLE[chunk.event_type]
        sign = _direction_sign(chunk.drift_direction)
        if sign == 0:
            logger.info("Drift skipped (uncertain direction): %.60s", chunk.title)
            return 0

        assets = _resolve_affected_assets(chunk, impact["affected_scope"])
        if not assets:
            logger.info("Drift skipped (no affected assets resolved): %.60s", chunk.title)
            return 0

        count = 0
        for ticker in assets:
            record = self._build_record(chunk, ticker, impact, sign)
            self._audit_log.log(record)
            logger.info(
                "Drift adj: %s %+.0fbps [%s] <- %s",
                ticker, record.adjustment_bps, chunk.event_type.value, chunk.source_name
            )
            count += 1

        return count

    def get_net_drift_adjustment(self, ticker: str) -> float:
        """
        Returns the net current drift adjustment in annualized bps for a ticker.
        Called by SimulationEngine at the start of each simulation run.
        """
        active = self._audit_log.get_active_adjustments(ticker)
        if not active:
            return 0.0
        return sum(self._decay_model.current_value(r) for r in active)

    def get_adjustment_summary(self, ticker: str) -> dict:
        """Returns a summary dict for API exposure (Node.js route)."""
        active = self._audit_log.get_active_adjustments(ticker)
        net_bps = sum(self._decay_model.current_value(r) for r in active)
        return {
            "ticker": ticker,
            "net_adjustment_bps": round(net_bps, 2),
            "net_adjustment_annualized": round(net_bps / 10_000, 6),
            "active_adjustments": len(active),
            "adjustments": [
                {
                    "adjustment_id":  r.adjustment_id,
                    "event_type":     r.event_type.value,
                    "adjustment_bps": round(r.adjustment_bps, 2),
                    "current_effective_bps": round(self._decay_model.current_value(r), 2),
                    "source_headline": r.source_headline[:120],
                    "applied_at":     r.applied_at.isoformat(),
                    "expires_at":     r.expires_at.isoformat(),
                    "confidence":     r.confidence,
                }
                for r in active
            ],
        }

    # ── Private helpers ───────────────────────────────────────────────────────

    def _build_record(
        self,
        chunk: ProcessedChunk,
        ticker: str,
        impact: dict,
        sign: int,
    ) -> DriftAdjustmentRecord:
        baseline = _get_baseline_drift(ticker)
        adj_bps = float(min(max(impact["magnitude_bps"] * sign, -_MAX_ADJUSTMENT_BPS), _MAX_ADJUSTMENT_BPS))
        expires_at = datetime.now(timezone.utc) + timedelta(days=impact["decay_halflife_days"] * 4)

        from news.drift.audit_log import _compute_hash
        record = DriftAdjustmentRecord(
            adjustment_id=str(uuid.uuid4()),
            chunk_id=chunk.chunk_id,
            asset_ticker=ticker,
            original_drift=baseline,
            adjustment_bps=adj_bps,
            adjusted_drift=baseline + adj_bps / 10_000,
            decay_halflife_days=impact["decay_halflife_days"],
            applied_at=datetime.now(timezone.utc),
            expires_at=expires_at,
            event_type=chunk.event_type,
            source_headline=chunk.title,
            confidence=impact["confidence_base"],
        )
        record.audit_hash = _compute_hash(record)
        return record


# ── Module-level singleton for use by SimulationEngine ────────────────────────

_ENGINE_SINGLETON: Optional[DriftAdjustmentEngine] = None


def get_drift_engine() -> DriftAdjustmentEngine:
    global _ENGINE_SINGLETON
    if _ENGINE_SINGLETON is None:
        _ENGINE_SINGLETON = DriftAdjustmentEngine()
    return _ENGINE_SINGLETON


def get_net_drift_adjustment(ticker: str) -> float:
    """
    Convenience function: get net drift adjustment for a ticker.
    Import this in SimulationEngine for integration:

        from news.drift.adjustment_engine import get_net_drift_adjustment
        drift_adj = get_net_drift_adjustment(ticker)   # annualized bps
        mu_adjusted = mu_historical + drift_adj / 10_000
    """
    return get_drift_engine().get_net_drift_adjustment(ticker)
