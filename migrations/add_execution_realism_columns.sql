-- Execution Realism Schema Migration
-- Safe to run multiple times (IF NOT EXISTS / ADD COLUMN IF NOT EXISTS)

-- ── New columns on trade_recommendations ────────────────────────────────────
ALTER TABLE trade_recommendations ADD COLUMN IF NOT EXISTS realistic_fill_price       REAL;
ALTER TABLE trade_recommendations ADD COLUMN IF NOT EXISTS position_value_egp         REAL;
ALTER TABLE trade_recommendations ADD COLUMN IF NOT EXISTS round_trip_cost_egp        REAL;
ALTER TABLE trade_recommendations ADD COLUMN IF NOT EXISTS edge_ratio                 REAL;
ALTER TABLE trade_recommendations ADD COLUMN IF NOT EXISTS split_required             BOOLEAN DEFAULT FALSE;
ALTER TABLE trade_recommendations ADD COLUMN IF NOT EXISTS realistic_stop_price       REAL;
ALTER TABLE trade_recommendations ADD COLUMN IF NOT EXISTS execution_approved         BOOLEAN DEFAULT TRUE;
ALTER TABLE trade_recommendations ADD COLUMN IF NOT EXISTS volatility_position_pct    REAL;
ALTER TABLE trade_recommendations ADD COLUMN IF NOT EXISTS kelly_position_pct         REAL;
ALTER TABLE trade_recommendations ADD COLUMN IF NOT EXISTS position_size_pct          REAL;
ALTER TABLE trade_recommendations ADD COLUMN IF NOT EXISTS shares_requested           INTEGER;
ALTER TABLE trade_recommendations ADD COLUMN IF NOT EXISTS shares_expected            INTEGER;
ALTER TABLE trade_recommendations ADD COLUMN IF NOT EXISTS position_sizing_mode       TEXT;
ALTER TABLE trade_recommendations ADD COLUMN IF NOT EXISTS days_held                  INTEGER DEFAULT 0;
ALTER TABLE trade_recommendations ADD COLUMN IF NOT EXISTS highest_price_since_entry  REAL;
ALTER TABLE trade_recommendations ADD COLUMN IF NOT EXISTS trailing_stop_active       BOOLEAN DEFAULT FALSE;
ALTER TABLE trade_recommendations ADD COLUMN IF NOT EXISTS trailing_stop_price        REAL;

-- ── Blocked signals audit log ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS blocked_signals (
    id              SERIAL PRIMARY KEY,
    ticker          TEXT NOT NULL,
    action          TEXT NOT NULL,
    signal_date     TEXT NOT NULL,
    consensus_score REAL,
    block_reason    TEXT NOT NULL,
    raw_price       REAL,
    expected_return REAL,
    edge_ratio      REAL,
    regime_at_block TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── Market regime log ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS regime_log (
    id                   SERIAL PRIMARY KEY,
    log_date             TEXT NOT NULL,
    regime               TEXT NOT NULL,
    egx30_price          REAL,
    ma20                 REAL,
    distance_from_ma_pct REAL,
    new_longs_allowed    BOOLEAN,
    created_at           TIMESTAMPTZ DEFAULT NOW()
);

-- ── SQLite-compatible equivalents (for local dev) ────────────────────────────
-- Run these manually if using SQLite:
--
-- CREATE TABLE IF NOT EXISTS blocked_signals (
--     id              INTEGER PRIMARY KEY AUTOINCREMENT,
--     ticker          TEXT NOT NULL,
--     action          TEXT NOT NULL,
--     signal_date     TEXT NOT NULL,
--     consensus_score REAL,
--     block_reason    TEXT NOT NULL,
--     raw_price       REAL,
--     expected_return REAL,
--     edge_ratio      REAL,
--     regime_at_block TEXT,
--     created_at      TEXT DEFAULT (datetime('now'))
-- );
--
-- CREATE TABLE IF NOT EXISTS regime_log (
--     id                   INTEGER PRIMARY KEY AUTOINCREMENT,
--     log_date             TEXT NOT NULL,
--     regime               TEXT NOT NULL,
--     egx30_price          REAL,
--     ma20                 REAL,
--     distance_from_ma_pct REAL,
--     new_longs_allowed    BOOLEAN,
--     created_at           TEXT DEFAULT (datetime('now'))
-- );
