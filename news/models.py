"""
news/models.py — Pydantic data models for the news RAG integration layer.

All pipeline components share these schemas. Keep this module free of
heavy imports so it can be imported quickly from any entry point.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
import uuid

from pydantic import BaseModel, Field


# ── Enumerations ──────────────────────────────────────────────────────────────

class MarketTag(str, Enum):
    EGX     = "EGX"
    TASI    = "TASI"
    MACRO   = "MACRO"      # Global macro affecting both
    MENA    = "MENA"       # Regional, non-market-specific
    UNKNOWN = "UNKNOWN"


class EventType(str, Enum):
    RATE_DECISION      = "RATE_DECISION"       # CBE/SAMA rate announcement
    FX_MOVE            = "FX_MOVE"             # EGP/USD or SAR peg events
    EARNINGS_RELEASE   = "EARNINGS_RELEASE"    # Corporate earnings
    REGULATORY_CHANGE  = "REGULATORY_CHANGE"  # CMA, EFSA, EGX rule changes
    MACRO_DATA         = "MACRO_DATA"          # Inflation, GDP, trade balance
    IMF_WORLD_BANK     = "IMF_WORLD_BANK"      # Program updates, disbursements
    GEOPOLITICAL       = "GEOPOLITICAL"        # Regional political events
    CORPORATE_ACTION   = "CORPORATE_ACTION"   # M&A, dividends, rights issues
    IPO                = "IPO"                # New listings
    GENERAL            = "GENERAL"            # Unclassified financial news
    IRRELEVANT         = "IRRELEVANT"         # Non-financial — filter out


class DriftDirection(str, Enum):
    POSITIVE  = "POSITIVE"
    NEGATIVE  = "NEGATIVE"
    NEUTRAL   = "NEUTRAL"
    UNCERTAIN = "UNCERTAIN"


# ── Core article schema ───────────────────────────────────────────────────────

class RawArticle(BaseModel):
    source_name:  str
    source_url:   str
    title:        str
    body:         str
    published_at: datetime
    language:     str = "en"         # "en" | "ar"
    url:          str
    content_hash: str                # SHA-256 of title + body[:500]
    market_tag:   MarketTag = MarketTag.UNKNOWN

    @classmethod
    def build(
        cls,
        source_name: str,
        source_url: str,
        title: str,
        body: str,
        published_at: datetime,
        url: str,
        language: str = "en",
        market_tag: MarketTag = MarketTag.UNKNOWN,
    ) -> "RawArticle":
        content_hash = hashlib.sha256(
            (title + body[:500]).encode("utf-8", errors="replace")
        ).hexdigest()
        return cls(
            source_name=source_name,
            source_url=source_url,
            title=title,
            body=body,
            published_at=published_at,
            language=language,
            url=url,
            content_hash=content_hash,
            market_tag=market_tag,
        )


# ── Processed chunk (stored in DB + vector store) ────────────────────────────

class ProcessedChunk(BaseModel):
    chunk_id:         str = Field(default_factory=lambda: str(uuid.uuid4()))
    article_url:      str
    source_name:      str
    title:            str
    content:          str
    published_at:     datetime
    ingested_at:      datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    language:         str = "en"
    market_tag:       MarketTag = MarketTag.UNKNOWN
    event_type:       EventType = EventType.GENERAL
    affected_assets:  List[str] = Field(default_factory=list)
    affected_sectors: List[str] = Field(default_factory=list)
    drift_direction:  DriftDirection = DriftDirection.UNCERTAIN
    drift_magnitude_estimate: Optional[float] = None  # Annualized bps
    embedding:        Optional[List[float]] = None
    chunk_index:      int = 0


# ── Drift audit record ────────────────────────────────────────────────────────

class DriftAdjustmentRecord(BaseModel):
    adjustment_id:       str = Field(default_factory=lambda: str(uuid.uuid4()))
    chunk_id:            str
    asset_ticker:        str
    original_drift:      float
    adjustment_bps:      float       # Signed annualized basis points
    adjusted_drift:      float
    decay_halflife_days: int
    applied_at:          datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at:          datetime
    event_type:          EventType
    source_headline:     str
    confidence:          float       # 0.0 – 1.0
    applied_by:          str = "news_drift_engine"
    audit_hash:          str = ""    # Filled by DriftAdjustmentEngine._compute_audit_hash()
