-- =============================================================================
-- KSA Schema Migration
-- Saudi Arabia (Tadawul) market support for Xmore platform
-- Run once against the target database (PostgreSQL in production, SQLite in dev)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Extend egx30_stocks (shared stock reference table) to support KSA symbols
--    The table already exists from the EGX migration; we add a market column.
-- -----------------------------------------------------------------------------

ALTER TABLE egx30_stocks
    ADD COLUMN IF NOT EXISTS market        VARCHAR(10)  DEFAULT 'EGX',
    ADD COLUMN IF NOT EXISTS exchange_code VARCHAR(20)  DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS currency      VARCHAR(5)   DEFAULT 'EGP',
    ADD COLUMN IF NOT EXISTS country_code  VARCHAR(3)   DEFAULT 'EG';

-- Update existing EGX rows to be explicit
UPDATE egx30_stocks
SET    market        = 'EGX',
       exchange_code = 'CASE',
       currency      = 'EGP',
       country_code  = 'EG'
WHERE  market IS NULL
    OR market = 'EGX';

-- -----------------------------------------------------------------------------
-- 2. KSA stock reference table (mirrors egx30_stocks structure + KSA columns)
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ksa_stocks (
    id             SERIAL PRIMARY KEY,
    symbol         VARCHAR(20)  NOT NULL UNIQUE,          -- e.g. 2222.SR
    name_en        VARCHAR(200) NOT NULL,
    name_ar        VARCHAR(200) NOT NULL,
    sector_en      VARCHAR(100) NOT NULL,
    sector_ar      VARCHAR(100) NOT NULL,
    market         VARCHAR(10)  NOT NULL DEFAULT 'TADAWUL',
    exchange_code  VARCHAR(20)  NOT NULL DEFAULT 'XSAU',
    currency       VARCHAR(5)   NOT NULL DEFAULT 'SAR',
    country_code   VARCHAR(3)   NOT NULL DEFAULT 'SA',
    is_mt30        BOOLEAN      NOT NULL DEFAULT FALSE,   -- MSCI Tadawul 30 constituent
    is_banking     BOOLEAN      NOT NULL DEFAULT FALSE,
    is_active      BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ksa_stocks_symbol
    ON ksa_stocks (symbol);

CREATE INDEX IF NOT EXISTS idx_ksa_stocks_sector
    ON ksa_stocks (sector_en);

CREATE INDEX IF NOT EXISTS idx_ksa_stocks_mt30
    ON ksa_stocks (is_mt30)
    WHERE is_mt30 = TRUE;

-- -----------------------------------------------------------------------------
-- 3. KSA daily price table
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ksa_prices (
    id            BIGSERIAL    PRIMARY KEY,
    symbol        VARCHAR(20)  NOT NULL,
    trading_date  DATE         NOT NULL,
    open          NUMERIC(12,4),
    high          NUMERIC(12,4),
    low           NUMERIC(12,4),
    close         NUMERIC(12,4) NOT NULL,
    volume        BIGINT,
    adjusted_close NUMERIC(12,4),
    pct_change    NUMERIC(8,4),
    turnover_sar  NUMERIC(18,2),                         -- value traded in SAR
    data_source   VARCHAR(50)  DEFAULT 'tadawul',
    created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (symbol, trading_date)
);

CREATE INDEX IF NOT EXISTS idx_ksa_prices_symbol_date
    ON ksa_prices (symbol, trading_date DESC);

CREATE INDEX IF NOT EXISTS idx_ksa_prices_date
    ON ksa_prices (trading_date DESC);

-- -----------------------------------------------------------------------------
-- 4. KSA trade recommendations (mirrors trade_recommendations structure)
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ksa_trade_recommendations (
    id                BIGSERIAL    PRIMARY KEY,
    symbol            VARCHAR(20)  NOT NULL,
    recommendation    VARCHAR(10)  NOT NULL CHECK (recommendation IN ('BUY','SELL','HOLD')),
    confidence        VARCHAR(20)  NOT NULL DEFAULT 'MODERATE',
    consensus_score   NUMERIC(5,4),
    price_at_signal   NUMERIC(12,4),
    target_price      NUMERIC(12,4),
    stop_loss         NUMERIC(12,4),
    reasoning         TEXT,
    agent_votes       JSONB,                              -- {agent_name: vote}
    regime            VARCHAR(30)  DEFAULT 'UNKNOWN',
    market            VARCHAR(10)  NOT NULL DEFAULT 'TADAWUL',
    created_at        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at        TIMESTAMP,
    is_active         BOOLEAN      NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_ksa_trade_recs_symbol
    ON ksa_trade_recommendations (symbol, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ksa_trade_recs_active
    ON ksa_trade_recommendations (is_active, created_at DESC)
    WHERE is_active = TRUE;

-- -----------------------------------------------------------------------------
-- 5. KSA signal evaluation (mirrors prediction_evaluations structure)
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ksa_signal_evaluations (
    id                  BIGSERIAL    PRIMARY KEY,
    recommendation_id   BIGINT       REFERENCES ksa_trade_recommendations(id) ON DELETE SET NULL,
    symbol              VARCHAR(20)  NOT NULL,
    agent_name          VARCHAR(50)  NOT NULL,
    predicted_direction VARCHAR(10)  NOT NULL,
    actual_direction    VARCHAR(10),
    predicted_at        TIMESTAMP    NOT NULL,
    evaluated_at        TIMESTAMP,
    price_at_signal     NUMERIC(12,4),
    price_at_evaluation NUMERIC(12,4),
    pct_change          NUMERIC(8,4),
    is_correct          BOOLEAN,
    horizon_days        INTEGER      NOT NULL DEFAULT 5,
    market              VARCHAR(10)  NOT NULL DEFAULT 'TADAWUL'
);

CREATE INDEX IF NOT EXISTS idx_ksa_signal_eval_symbol
    ON ksa_signal_evaluations (symbol, predicted_at DESC);

CREATE INDEX IF NOT EXISTS idx_ksa_signal_eval_agent
    ON ksa_signal_evaluations (agent_name, predicted_at DESC);

-- -----------------------------------------------------------------------------
-- 6. KSA DCF valuation results cache
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ksa_dcf_results (
    id               BIGSERIAL    PRIMARY KEY,
    symbol           VARCHAR(20)  NOT NULL,
    run_date         DATE         NOT NULL,
    scenario         VARCHAR(10)  NOT NULL DEFAULT 'base',  -- bull/base/bear
    intrinsic_value  NUMERIC(14,4),
    current_price    NUMERIC(12,4),
    upside_pct       NUMERIC(8,4),
    wacc             NUMERIC(6,4),
    terminal_growth  NUMERIC(6,4),
    forecast_years   INTEGER      NOT NULL DEFAULT 5,
    inputs_json      JSONB,
    outputs_json     JSONB,
    model_version    VARCHAR(20)  DEFAULT '1.0',
    created_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (symbol, run_date, scenario)
);

CREATE INDEX IF NOT EXISTS idx_ksa_dcf_symbol_date
    ON ksa_dcf_results (symbol, run_date DESC);

-- -----------------------------------------------------------------------------
-- 7. KSA market regime log
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ksa_regime_log (
    id             BIGSERIAL  PRIMARY KEY,
    log_date       DATE       NOT NULL UNIQUE,
    regime         VARCHAR(30) NOT NULL,                   -- Calm/Turbulent/Crisis
    regime_index   INTEGER,
    probability    NUMERIC(5,4),
    mt30_return_1d NUMERIC(8,4),
    mt30_vol_20d   NUMERIC(8,4),
    notes          TEXT,
    created_at     TIMESTAMP  NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- 8. KSA news / sentiment snapshot (lightweight; full text in main news tables)
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ksa_news_sentiment (
    id            BIGSERIAL    PRIMARY KEY,
    symbol        VARCHAR(20),                            -- NULL = market-wide
    news_date     DATE         NOT NULL,
    sentiment     VARCHAR(10)  NOT NULL DEFAULT 'NEUTRAL', -- POSITIVE/NEGATIVE/NEUTRAL
    sentiment_score NUMERIC(5,4),
    headline_en   TEXT,
    headline_ar   TEXT,
    source        VARCHAR(100),
    url           TEXT,
    created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ksa_news_sentiment_symbol_date
    ON ksa_news_sentiment (symbol, news_date DESC);

-- -----------------------------------------------------------------------------
-- 9. KSA user watchlist extension
--    Existing user_watchlists table uses symbol column; KSA symbols end in .SR
--    so no structural change needed — this view provides a convenience filter.
-- -----------------------------------------------------------------------------

CREATE OR REPLACE VIEW ksa_user_watchlists AS
SELECT *
FROM   user_watchlists
WHERE  symbol LIKE '%.SR';

-- -----------------------------------------------------------------------------
-- Done
-- -----------------------------------------------------------------------------
