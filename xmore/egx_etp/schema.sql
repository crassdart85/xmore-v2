-- ==========================================================================
-- EGX ETP Ingestion Schema
-- PostgreSQL DDL — run via ensure_schema() or directly via psql
-- ==========================================================================

-- --------------------------------------------------------------------------
-- etp_product
-- Master registry of every ETP instrument discovered on EGX.
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS etp_product (
    etp_id                  BIGSERIAL PRIMARY KEY,
    code                    TEXT        NOT NULL UNIQUE,
    arabic_name             TEXT,
    english_name            TEXT,
    issuer                  TEXT,
    instrument_type         TEXT        NOT NULL
                                CHECK (instrument_type IN (
                                    'ETF',
                                    'GOLD_ETP',
                                    'INDEX_TRACKER',
                                    'STRUCTURED_NOTE',
                                    'ETN',
                                    'UNKNOWN_ETP'
                                )),
    underlying_exposure     TEXT,
    currency                TEXT        DEFAULT 'EGP',
    nav_available           BOOLEAN     DEFAULT FALSE,
    holdings_available      BOOLEAN     DEFAULT FALSE,
    prem_disc_available     BOOLEAN     DEFAULT FALSE,
    classification_confidence NUMERIC(5,2),
    classification_reason   TEXT,
    source_url              TEXT        NOT NULL,
    first_seen_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE  etp_product IS 'Master registry of every ETP instrument discovered on EGX.';
COMMENT ON COLUMN etp_product.instrument_type IS 'Conservative classification: ETF | GOLD_ETP | INDEX_TRACKER | STRUCTURED_NOTE | ETN | UNKNOWN_ETP';
COMMENT ON COLUMN etp_product.underlying_exposure IS 'NULL when unknown — never invented. E.g. ''gold'', ''EGX30'', ''index''.';
COMMENT ON COLUMN etp_product.classification_confidence IS '0.00–1.00 confidence score from classifier.';

-- --------------------------------------------------------------------------
-- etp_market_snapshot
-- One row per (instrument, trading date) with OHLCV-equivalent fields.
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS etp_market_snapshot (
    etp_id          BIGINT      NOT NULL REFERENCES etp_product(etp_id) ON DELETE CASCADE,
    asof_date       DATE        NOT NULL,
    close_price     NUMERIC(18,6),
    change_pct      NUMERIC(18,6),
    nav_value       NUMERIC(18,6),
    prem_disc       NUMERIC(18,6),
    volume          BIGINT,
    value           NUMERIC(18,2),
    source_url      TEXT        NOT NULL,
    scraped_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (etp_id, asof_date)
);

COMMENT ON TABLE  etp_market_snapshot IS 'Daily market snapshot per ETP instrument.';
COMMENT ON COLUMN etp_market_snapshot.prem_disc IS 'Premium/discount vs NAV in percent.';

-- --------------------------------------------------------------------------
-- etp_holdings_snapshot
-- Header row for one fund-constituents extraction event.
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS etp_holdings_snapshot (
    snapshot_id     BIGSERIAL   PRIMARY KEY,
    etp_id          BIGINT      NOT NULL REFERENCES etp_product(etp_id) ON DELETE CASCADE,
    snapshot_date   DATE        NOT NULL,
    source_url      TEXT        NOT NULL,
    scraped_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (etp_id, snapshot_date, source_url)
);

-- --------------------------------------------------------------------------
-- etp_holding_line
-- One constituent per line within a holdings snapshot.
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS etp_holding_line (
    snapshot_id     BIGINT      NOT NULL REFERENCES etp_holdings_snapshot(snapshot_id) ON DELETE CASCADE,
    line_no         INTEGER     NOT NULL,
    holding_name    TEXT        NOT NULL,
    holding_symbol  TEXT,
    weight_pct      NUMERIC(18,10),
    PRIMARY KEY (snapshot_id, line_no)
);

COMMENT ON COLUMN etp_holding_line.weight_pct IS 'Portfolio weight as a decimal percent (e.g. 5.25 = 5.25%).';

-- --------------------------------------------------------------------------
-- raw_page_archive
-- Tracks every raw HTML file saved to disk for auditability.
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS raw_page_archive (
    archive_id      BIGSERIAL   PRIMARY KEY,
    url             TEXT        NOT NULL,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    fetch_method    TEXT        NOT NULL,    -- 'requests' or 'playwright'
    content_type    TEXT        DEFAULT 'text/html',
    body_path       TEXT        NOT NULL     -- absolute path on disk
);

COMMENT ON TABLE raw_page_archive IS 'Audit trail of every raw HTML page fetched.';

-- --------------------------------------------------------------------------
-- scrape_run_log
-- One row per pipeline execution for monitoring and debugging.
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS scrape_run_log (
    run_id          BIGSERIAL   PRIMARY KEY,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ,
    status          TEXT        NOT NULL DEFAULT 'running'
                                CHECK (status IN ('running', 'success', 'failed')),
    cards_found     INTEGER,
    holdings_rows   INTEGER,
    nav_rows        INTEGER,
    volume_rows     INTEGER,
    error_message   TEXT,
    run_type        TEXT        NOT NULL DEFAULT 'incremental'
                                CHECK (run_type IN ('incremental', 'backfill'))
);

COMMENT ON TABLE scrape_run_log IS 'One row per pipeline execution for monitoring and debugging.';

-- --------------------------------------------------------------------------
-- Optional indexes (improve query speed on large datasets)
-- --------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_etp_snapshot_date   ON etp_market_snapshot (asof_date DESC);
CREATE INDEX IF NOT EXISTS idx_etp_snapshot_etp_id ON etp_market_snapshot (etp_id);
CREATE INDEX IF NOT EXISTS idx_etp_holdings_etp_id ON etp_holdings_snapshot (etp_id);
CREATE INDEX IF NOT EXISTS idx_run_log_started_at  ON scrape_run_log (started_at DESC);
