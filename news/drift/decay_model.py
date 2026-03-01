"""
news/drift/decay_model.py — Exponential decay of news impact on drift parameters.

Formula:
    effective_adjustment(t) = adjustment_bps * exp(-t * ln(2) / halflife_days)

At t=0 (event time): full adjustment applied.
At t=halflife_days:  half the adjustment remains.
At t=4*halflife:     ~6% remains (effectively decayed out).

The decay halflife is event-type specific (see DRIFT_IMPACT_TABLE in
adjustment_engine.py) — macro events decay slowly (14 days), earnings
announcements decay quickly (5 days).
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from news.models import DriftAdjustmentRecord


class ExponentialDecayModel:
    """Stateless: just computes current_value() from a record at any point in time."""

    def current_value(self, record: DriftAdjustmentRecord) -> float:
        """Returns the current effective drift adjustment in annualized bps."""
        now = datetime.now(timezone.utc)
        if now >= record.expires_at:
            return 0.0
        elapsed_days = (now - record.applied_at).total_seconds() / 86_400
        decay_factor = math.exp(
            -elapsed_days * math.log(2) / record.decay_halflife_days
        )
        return record.adjustment_bps * decay_factor

    def time_to_expiry_days(self, record: DriftAdjustmentRecord) -> float:
        now = datetime.now(timezone.utc)
        return max(0.0, (record.expires_at - now).total_seconds() / 86_400)

    def is_expired(self, record: DriftAdjustmentRecord) -> bool:
        return datetime.now(timezone.utc) >= record.expires_at
