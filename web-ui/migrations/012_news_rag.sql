-- Migration 012: News RAG + Drift Adjustment tables
-- Adds live news feed integration layer:
--   1. news_rag_chunks  — embedded news chunks (extends rag_chunks concept with full metadata)
--   2. drift_adjustment_log — immutable audit log of every drift parameter change

-- ── Table 1: news_rag_chunks ──────────────────────────────────────────────────
-- Stores chunked, embedded news articles with classification metadata.
-- Kept separate from rag_chunks to avoid schema collision with market_report chunks.
CREATE TABLE IF NOT EXISTS news_rag_chunks (
    id               TEXT PRIMARY KEY,               -- UUID chunk_id
    article_url      TEXT NOT NULL,
    source_name      TEXT NOT NULL,
    title            TEXT NOT NULL,
    content          TEXT NOT NULL,
    chunk_index      INTEGER NOT NULL DEFAULT 0,
    published_at     TIMESTAMPTZ NOT NULL,
    ingested_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    language         TEXT NOT NULL DEFAULT 'en',
    market_tag       TEXT NOT NULL DEFAULT 'UNKNOWN', -- EGX | TASI | MACRO | MENA | UNKNOWN
    event_type       TEXT NOT NULL DEFAULT 'GENERAL', -- RATE_DECISION | FX_MOVE | EARNINGS_RELEASE ...
    affected_assets  TEXT NOT NULL DEFAULT '[]',      -- JSON array of ticker strings
    affected_sectors TEXT NOT NULL DEFAULT '[]',      -- JSON array of sector strings
    drift_direction  TEXT NOT NULL DEFAULT 'UNCERTAIN', -- POSITIVE | NEGATIVE | NEUTRAL | UNCERTAIN
    drift_magnitude_estimate REAL,                    -- Annualized bps, nullable
    embedding        TEXT                             -- JSON-encoded 768-dim float list
);

CREATE INDEX IF NOT EXISTS idx_news_rag_chunks_published ON news_rag_chunks(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_news_rag_chunks_market    ON news_rag_chunks(market_tag);
CREATE INDEX IF NOT EXISTS idx_news_rag_chunks_event     ON news_rag_chunks(event_type);
CREATE INDEX IF NOT EXISTS idx_news_rag_chunks_url       ON news_rag_chunks(article_url);

-- ── Table 2: drift_adjustment_log ────────────────────────────────────────────
-- Immutable audit log of every drift parameter adjustment triggered by news events.
-- Each record includes an audit_hash (SHA-256) for tamper detection.
CREATE TABLE IF NOT EXISTS drift_adjustment_log (
    adjustment_id       TEXT PRIMARY KEY,
    chunk_id            TEXT NOT NULL,               -- References news_rag_chunks.id
    asset_ticker        TEXT NOT NULL,
    original_drift      REAL NOT NULL,
    adjustment_bps      REAL NOT NULL,               -- Annualized basis points, signed
    adjusted_drift      REAL NOT NULL,
    decay_halflife_days INTEGER NOT NULL,
    applied_at          TIMESTAMPTZ NOT NULL,
    expires_at          TIMESTAMPTZ NOT NULL,
    event_type          TEXT NOT NULL,
    source_headline     TEXT NOT NULL,
    confidence          REAL NOT NULL,
    applied_by          TEXT NOT NULL DEFAULT 'news_drift_engine',
    audit_hash          TEXT NOT NULL                -- SHA-256 for immutability check
);

CREATE INDEX IF NOT EXISTS idx_drift_log_ticker     ON drift_adjustment_log(asset_ticker);
CREATE INDEX IF NOT EXISTS idx_drift_log_applied_at ON drift_adjustment_log(applied_at DESC);
CREATE INDEX IF NOT EXISTS idx_drift_log_expires_at ON drift_adjustment_log(expires_at);
