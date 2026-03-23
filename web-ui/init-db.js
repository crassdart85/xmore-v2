console.log('=== INIT-DB.JS STARTING ===');
const { Pool } = require('pg');

const DATABASE_URL = process.env.DATABASE_URL;
console.log('DATABASE_URL exists:', !!DATABASE_URL);

if (!DATABASE_URL) {
  console.log('⚠️  No DATABASE_URL found. Skipping database initialization.');
  process.exit(0);
}

// Set a global timeout - exit after 900 seconds no matter what
const TIMEOUT_MS = 900000;
const timeoutId = setTimeout(() => {
  console.error('❌ Database initialization timed out after 900 seconds');
  process.exit(1);
}, TIMEOUT_MS);
timeoutId.unref(); // Don't keep process alive just for timeout

// max:1 forces all pool.query() calls to reuse the same connection,
// so a single SET lock_timeout applies to every subsequent statement.
const pool = new Pool({
  connectionString: DATABASE_URL,
  ssl: { rejectUnauthorized: false },
  connectionTimeoutMillis: 10000,
  idleTimeoutMillis: 30000,
  max: 1,
});

/**
 * Execute a CREATE INDEX (or ALTER TABLE) statement safely.
 *
 * Wraps each DDL in its own BEGIN/COMMIT with SET LOCAL so that
 * lock_timeout and statement_timeout take effect even when Render's
 * managed Postgres overrides session-level SET commands via role config
 * or connection-pool resets between queries.
 *
 * SET LOCAL is transaction-scoped and cannot be overridden externally —
 * it applies for the duration of the enclosing transaction only.
 *
 * Errors (lock timeout, statement timeout, concurrent run) are caught
 * and logged as warnings; they never abort the whole init.
 */
async function safeCreateIndex(db, sql) {
  try {
    await db.query('BEGIN');
    await db.query("SET LOCAL lock_timeout = '5s'");
    await db.query("SET LOCAL statement_timeout = '120s'"); // cap index builds at 2 min
    await db.query(sql);
    await db.query('COMMIT');
  } catch (e) {
    try { await db.query('ROLLBACK'); } catch (_) {}
    console.warn(`⚠️  DDL skipped (lock timeout / concurrent run): ${e.message.split('\n')[0]}`);
  }
}

async function initializeDatabase() {
  console.log('🔧 Initializing PostgreSQL database...');
  console.log('📍 Connecting to:', DATABASE_URL.replace(/:[^:@]+@/, ':****@'));

  try {
    // Test connection
    console.log('⏳ Testing database connection...');
    await pool.query('SELECT 1');
    console.log('✅ Connected to PostgreSQL');

    // lock_timeout: fail fast if we can't acquire a DDL lock within 5s
    // (covers concurrent GH Actions jobs holding AccessExclusiveLock).
    // statement_timeout=0: index BUILD time is intentionally unlimited —
    // lock_timeout already protects against lock hangs. Capping build time
    // caused all 47 index creations to timeout at 30s each, consuming the
    // entire 300s global window before the server could start.
    // Both settings are session-level; with max:1 pool they apply to every
    // subsequent pool.query() call on this same connection.
    await pool.query("SET lock_timeout = '5s'");
    await pool.query("SET statement_timeout = '0'");
    console.log('⏱  lock_timeout=5s  statement_timeout=0 (unlimited)');

    // Create tables
    console.log('📋 Creating tables...');

    // Table 1: Stock Prices
    await pool.query(`
      CREATE TABLE IF NOT EXISTS prices (
        id SERIAL PRIMARY KEY,
        symbol TEXT NOT NULL,
        date DATE NOT NULL,
        open REAL,
        high REAL,
        low REAL,
        close REAL NOT NULL,
        volume INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        data_source TEXT DEFAULT 'yahoo_finance',
        UNIQUE(symbol, date)
      )
    `);

    // Table 2: Financial News
    await pool.query(`
      CREATE TABLE IF NOT EXISTS news (
        id SERIAL PRIMARY KEY,
        symbol TEXT NOT NULL,
        date DATE NOT NULL,
        headline TEXT NOT NULL,
        source TEXT,
        url TEXT,
        sentiment_score REAL,
        sentiment_label TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(symbol, headline, date)
      )
    `);

    // Table 11: Sentiment Scores (Aggregated)
    await pool.query(`
      CREATE TABLE IF NOT EXISTS sentiment_scores (
        id SERIAL PRIMARY KEY,
        symbol TEXT NOT NULL,
        date DATE NOT NULL,
        avg_sentiment REAL,
        sentiment_label TEXT,
        article_count INTEGER DEFAULT 0,
        positive_count INTEGER DEFAULT 0,
        negative_count INTEGER DEFAULT 0,
        neutral_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(symbol, date)
      )
    `);
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_sentiment_symbol_date ON sentiment_scores(symbol, date)');

    // Table 3: Predictions
    await pool.query(`
      CREATE TABLE IF NOT EXISTS predictions (
        id SERIAL PRIMARY KEY,
        symbol TEXT NOT NULL,
        prediction_date DATE NOT NULL,
        target_date DATE NOT NULL,
        agent_name TEXT NOT NULL,
        prediction TEXT NOT NULL,
        confidence REAL,
        predicted_change_pct REAL,
        metadata TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(symbol, prediction_date, target_date, agent_name)
      )
    `);

    // Table 4: Evaluations
    await pool.query(`
      CREATE TABLE IF NOT EXISTS evaluations (
        id SERIAL PRIMARY KEY,
        prediction_id INTEGER NOT NULL,
        symbol TEXT NOT NULL,
        agent_name TEXT NOT NULL,
        prediction TEXT NOT NULL,
        actual_outcome TEXT,
        was_correct BOOLEAN,
        actual_change_pct REAL,
        prediction_error REAL,
        evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (prediction_id) REFERENCES predictions(id)
      )
    `);

    // Table 5: Data Quality Log
    await pool.query(`
      CREATE TABLE IF NOT EXISTS data_quality_log (
        id SERIAL PRIMARY KEY,
        date DATE NOT NULL,
        symbol TEXT NOT NULL,
        issue_type TEXT NOT NULL,
        description TEXT,
        severity TEXT,
        resolved BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
    `);

    // Table 6: System Log
    await pool.query(`
      CREATE TABLE IF NOT EXISTS system_log (
        id SERIAL PRIMARY KEY,
        script_name TEXT NOT NULL,
        status TEXT NOT NULL,
        message TEXT,
        execution_time_seconds REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
    `);

    // Table 7: Consensus Results (3-Layer Pipeline Output)
    await pool.query(`
      CREATE TABLE IF NOT EXISTS consensus_results (
        id SERIAL PRIMARY KEY,
        symbol TEXT NOT NULL,
        prediction_date DATE NOT NULL,

        -- Final output
        final_signal TEXT NOT NULL,
        conviction TEXT,
        confidence REAL,
        risk_adjusted BOOLEAN DEFAULT FALSE,

        -- Agreement
        agent_agreement REAL,
        agents_agreeing INTEGER,
        agents_total INTEGER,
        majority_direction TEXT,

        -- Bull / Bear scores
        bull_score INTEGER,
        bear_score INTEGER,

        -- Risk
        risk_action TEXT,
        risk_score INTEGER,

        -- Full data (JSON)
        bull_case_json TEXT,
        bear_case_json TEXT,
        risk_assessment_json TEXT,
        agent_signals_json TEXT,
        reasoning_chain_json TEXT,
        display_json TEXT,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(symbol, prediction_date)
      )
    `);

    // Add reasoning column to predictions if it doesn't exist
    try {
      await pool.query('ALTER TABLE predictions ADD COLUMN IF NOT EXISTS reasoning TEXT');
      console.log('✅ Added reasoning column to predictions');
    } catch (err) {
      // Column may already exist, that's fine
    }

    // Add xmore_score column to consensus_results if not exists
    try {
      await pool.query('ALTER TABLE consensus_results ADD COLUMN IF NOT EXISTS xmore_score REAL');
      console.log('✅ Added xmore_score column to consensus_results');
    } catch (err) { /* already exists */ }
    try { await pool.query('ALTER TABLE consensus_results ADD COLUMN IF NOT EXISTS calibrated_confidence REAL'); } catch (err) { /* already exists */ }
    try { await pool.query('ALTER TABLE consensus_results ADD COLUMN IF NOT EXISTS expected_edge_pct REAL'); } catch (err) { /* already exists */ }
    try { await pool.query('ALTER TABLE consensus_results ADD COLUMN IF NOT EXISTS ranking_score REAL'); } catch (err) { /* already exists */ }
    try { await pool.query('ALTER TABLE consensus_results ADD COLUMN IF NOT EXISTS weight_profile_json TEXT'); } catch (err) { /* already exists */ }
    try { await pool.query('ALTER TABLE consensus_results ADD COLUMN IF NOT EXISTS calibration_meta_json TEXT'); } catch (err) { /* already exists */ }

    // Signal enrichment columns (drivers, risk_level, expected_move, enrichment_regime)
    try { await pool.query('ALTER TABLE consensus_results ADD COLUMN IF NOT EXISTS drivers_json TEXT'); } catch (err) { /* already exists */ }
    try { await pool.query('ALTER TABLE consensus_results ADD COLUMN IF NOT EXISTS risk_level TEXT'); } catch (err) { /* already exists */ }
    try { await pool.query('ALTER TABLE consensus_results ADD COLUMN IF NOT EXISTS expected_move TEXT'); } catch (err) { /* already exists */ }
    try { await pool.query('ALTER TABLE consensus_results ADD COLUMN IF NOT EXISTS enrichment_regime TEXT'); } catch (err) { /* already exists */ }

    // Table: Backtest Results (walk-forward ML performance per symbol)
    await pool.query(`
      CREATE TABLE IF NOT EXISTS backtest_results (
        id SERIAL PRIMARY KEY,
        symbol TEXT NOT NULL,
        run_date DATE NOT NULL,
        n_rows INTEGER,
        n_splits INTEGER,
        accuracy REAL,
        directional_accuracy REAL,
        signal_pnl_pct REAL,
        up_precision REAL,
        down_precision REAL,
        features_used INTEGER,
        fold_scores_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(symbol, run_date)
      )
    `);
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_backtest_symbol ON backtest_results(symbol, run_date DESC)');
    console.log('✅ backtest_results table ready');

    // Table: Agent Performance Daily (populated by evaluate_performance.py)
    await pool.query(`
      CREATE TABLE IF NOT EXISTS agent_performance_daily (
        id SERIAL PRIMARY KEY,
        snapshot_date DATE NOT NULL,
        agent_name TEXT NOT NULL,
        predictions_30d INTEGER,
        correct_30d INTEGER,
        win_rate_30d REAL,
        avg_confidence_30d REAL,
        predictions_90d INTEGER,
        correct_90d INTEGER,
        win_rate_90d REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(snapshot_date, agent_name)
      )
    `);
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_apd_snapshot ON agent_performance_daily(snapshot_date DESC)');
    console.log('✅ agent_performance_daily table ready');

    // Table: Regime Log (populated by regime_filter.py)
    await pool.query(`
      CREATE TABLE IF NOT EXISTS regime_log (
        id SERIAL PRIMARY KEY,
        date DATE NOT NULL UNIQUE,
        regime TEXT NOT NULL,
        hmm_state INTEGER,
        volatility REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
    `);
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_regime_log_date ON regime_log(date DESC)');
    console.log('✅ regime_log table ready');

    // Table: ETF Signals (populated by agent_etf_signal.py)
    await pool.query(`
      CREATE TABLE IF NOT EXISTS etf_signals (
        id BIGSERIAL PRIMARY KEY,
        instrument_id BIGINT NOT NULL,
        symbol TEXT NOT NULL,
        signal_date DATE NOT NULL DEFAULT CURRENT_DATE,
        signal TEXT NOT NULL DEFAULT 'HOLD',
        confidence NUMERIC(5,3) DEFAULT 0,
        ma_signal TEXT,
        rsi_signal TEXT,
        nav_signal TEXT,
        momentum_signal TEXT,
        rsi_value NUMERIC(6,2),
        nav_premium_pct NUMERIC(7,3),
        close_price NUMERIC(14,4),
        notes TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(instrument_id, signal_date)
      )
    `);
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_etf_signals_date ON etf_signals(signal_date DESC)');
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_etf_signals_symbol ON etf_signals(symbol)');
    console.log('✅ etf_signals table ready');

    // ============================================
    // AUTH & WATCHLIST TABLES
    // ============================================

    // Table 8: Users
    console.log('📊 Creating users table...');
    await pool.query(`
      CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        email VARCHAR(255) NOT NULL,
        email_lower VARCHAR(255) NOT NULL UNIQUE,
        password_hash VARCHAR(255) NOT NULL,
        display_name VARCHAR(100),
        preferred_language VARCHAR(5) DEFAULT 'en',
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login_at TIMESTAMP
      )
    `);

    // Table 9: EGX 30 Stocks reference
    console.log('📊 Creating egx30_stocks table...');
    await pool.query(`
      CREATE TABLE IF NOT EXISTS egx30_stocks (
        id SERIAL PRIMARY KEY,
        symbol VARCHAR(20) NOT NULL UNIQUE,
        name_en VARCHAR(200) NOT NULL,
        name_ar VARCHAR(200) NOT NULL,
        sector_en VARCHAR(100),
        sector_ar VARCHAR(100),
        is_active BOOLEAN DEFAULT TRUE,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
    `);

    // Table 10: User Watchlist
    console.log('📊 Creating user_watchlist table...');
    await pool.query(`
      CREATE TABLE IF NOT EXISTS user_watchlist (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        stock_id INTEGER NOT NULL REFERENCES egx30_stocks(id) ON DELETE CASCADE,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, stock_id)
      )
    `);

    // Table 12: User Positions
    console.log('📊 Creating user_positions table...');
    await pool.query(`
      CREATE TABLE IF NOT EXISTS user_positions (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        symbol TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'OPEN',
        entry_date DATE NOT NULL,
        entry_price REAL,
        exit_date DATE,
        exit_price REAL,
        return_pct REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
    `);
    await safeCreateIndex(pool, "CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_open_position ON user_positions(user_id, symbol) WHERE status = 'OPEN'");
    await safeCreateIndex(pool, "CREATE INDEX IF NOT EXISTS idx_positions_user ON user_positions(user_id)");

    // Table 13: Trade Recommendations
    console.log('📊 Creating trade_recommendations table...');
    await pool.query(`
      CREATE TABLE IF NOT EXISTS trade_recommendations (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        symbol TEXT NOT NULL,
        recommendation_date DATE NOT NULL,
        action TEXT NOT NULL,
        signal TEXT NOT NULL,
        confidence INTEGER NOT NULL,
        conviction TEXT,
        risk_action TEXT,
        priority REAL,
        close_price REAL,
        stop_loss_pct REAL,
        target_pct REAL,
        stop_loss_price REAL,
        target_price REAL,
        risk_reward_ratio REAL,
        reasons TEXT,
        reasons_ar TEXT,
        bull_score INTEGER,
        bear_score INTEGER,
        agents_agreeing INTEGER,
        agents_total INTEGER,
        risk_flags TEXT,
        actual_next_day_return REAL,
        actual_5day_return REAL,
        was_correct BOOLEAN,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, symbol, recommendation_date)
      )
    `);
    await safeCreateIndex(pool, "CREATE INDEX IF NOT EXISTS idx_trade_rec_user_date ON trade_recommendations(user_id, recommendation_date DESC)");

    // Session-sheet columns on trade_recommendations (safe)
    for (const col of [
      ['trend_ar','TEXT'], ['trend_en','TEXT'], ['rec_type_ar','TEXT'], ['rec_type_en','TEXT'],
      ['buy_guide','REAL'], ['pivot','REAL'], ['r1','REAL'], ['r2','REAL'], ['s1','REAL'], ['s2','REAL'],
      ['benchmark_1d_return','REAL'], ['alpha_1d','REAL'], ['benchmark_5d_return','REAL'], ['alpha_5d','REAL'],
      ['patterns','TEXT'],
      ['is_live','BOOLEAN DEFAULT FALSE'], ['is_simulated','BOOLEAN DEFAULT FALSE'],
      ['resolved_at','TIMESTAMP'], ['buyhold_1d_return','REAL'], ['model_version','TEXT'],
      ['realistic_fill_price','REAL'], ['position_value_egp','REAL'], ['round_trip_cost_egp','REAL'],
      ['edge_ratio','REAL'], ['split_required','BOOLEAN DEFAULT FALSE'], ['realistic_stop_price','REAL'],
      ['execution_approved','BOOLEAN DEFAULT TRUE'], ['volatility_position_pct','REAL'],
      ['kelly_position_pct','REAL'], ['position_size_pct','REAL'],
      ['shares_requested','INTEGER'], ['shares_expected','INTEGER'], ['position_sizing_mode','TEXT'],
    ]) {
      try { await pool.query(`ALTER TABLE trade_recommendations ADD COLUMN IF NOT EXISTS ${col[0]} ${col[1]}`); } catch(_) {}
    }

    // Table: Daily Briefings (one global row per date)
    await pool.query(`
      CREATE TABLE IF NOT EXISTS daily_briefings (
        id SERIAL PRIMARY KEY,
        briefing_date DATE NOT NULL UNIQUE,
        market_pulse_json TEXT,
        sector_breakdown_json TEXT,
        risk_alerts_json TEXT,
        sentiment_snapshot_json TEXT,
        stocks_processed INTEGER,
        generation_time_seconds REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
    `);
    await safeCreateIndex(pool, "CREATE INDEX IF NOT EXISTS idx_briefings_date ON daily_briefings(briefing_date DESC)");

    // Table: Market Intelligence reports (Admin dashboard)
    await pool.query(`
      CREATE TABLE IF NOT EXISTS market_reports (
        id SERIAL PRIMARY KEY,
        filename TEXT NOT NULL,
        upload_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        extracted_text TEXT,
        language VARCHAR(2) NOT NULL DEFAULT 'EN',
        summary TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CONSTRAINT chk_market_reports_language CHECK (language IN ('EN', 'AR'))
      )
    `);
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_market_reports_upload_date ON market_reports(upload_date DESC)');

    // Table: Custom News Sources (Admin-managed URLs, RSS, Telegram, WhatsApp)
    await pool.query(`
      CREATE TABLE IF NOT EXISTS custom_news_sources (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        source_type TEXT NOT NULL
          CHECK (source_type IN ('url', 'rss', 'telegram_public', 'telegram_bot', 'manual')),
        source_url TEXT,
        bot_token TEXT,
        chat_id TEXT,
        language TEXT DEFAULT 'auto',
        is_active BOOLEAN DEFAULT TRUE,
        fetch_interval_hours INTEGER DEFAULT 6,
        last_fetched_at TIMESTAMPTZ,
        telegram_offset BIGINT DEFAULT 0,
        created_at TIMESTAMPTZ DEFAULT NOW()
      )
    `);

    // Table: Articles fetched from custom sources
    await pool.query(`
      CREATE TABLE IF NOT EXISTS custom_source_articles (
        id SERIAL PRIMARY KEY,
        source_id INTEGER REFERENCES custom_news_sources(id) ON DELETE CASCADE,
        content_text TEXT NOT NULL,
        content_type TEXT NOT NULL DEFAULT 'text'
          CHECK (content_type IN ('text', 'image', 'pdf', 'url_article')),
        original_url TEXT,
        external_id TEXT,
        language TEXT,
        sentiment_score REAL,
        sentiment_label TEXT,
        sentiment_processed BOOLEAN DEFAULT FALSE,
        fetched_at TIMESTAMPTZ DEFAULT NOW(),
        message_date TIMESTAMPTZ,
        UNIQUE(source_id, external_id)
      )
    `);
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_custom_articles_source ON custom_source_articles(source_id, fetched_at DESC)');

    // Table: Forecast Portfolios (user-defined stock lists for recurring Monte Carlo forecasts)
    await pool.query(`
      CREATE TABLE IF NOT EXISTS forecast_portfolios (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        symbols_json TEXT NOT NULL DEFAULT '[]',
        horizon_days INTEGER NOT NULL DEFAULT 63,
        scenario TEXT NOT NULL DEFAULT 'base',
        investment_amount REAL NOT NULL DEFAULT 10000,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(user_id, name)
      )
    `);
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_fp_user ON forecast_portfolios(user_id)');

    // Table: Portfolio Forecast Results (one row per stock per run)
    await pool.query(`
      CREATE TABLE IF NOT EXISTS portfolio_forecast_results (
        id SERIAL PRIMARY KEY,
        portfolio_id INTEGER NOT NULL REFERENCES forecast_portfolios(id) ON DELETE CASCADE,
        symbol TEXT NOT NULL,
        run_date DATE NOT NULL,
        target_date DATE NOT NULL,
        horizon_days INTEGER NOT NULL,
        scenario TEXT NOT NULL DEFAULT 'base',
        investment_amount REAL,
        expected_return_pct REAL,
        probability_positive REAL,
        worst_case_pct REAL,
        median_pct REAL,
        best_case_pct REAL,
        volatility_annual_pct REAL,
        data_points INTEGER,
        ok BOOLEAN NOT NULL DEFAULT TRUE,
        error_reason TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(portfolio_id, symbol, run_date, horizon_days, scenario)
      )
    `);
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_pfr_portfolio ON portfolio_forecast_results(portfolio_id, run_date DESC)');
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_pfr_target ON portfolio_forecast_results(target_date)');

    // Table: Portfolio Forecast Evaluations (actual vs forecasted, auto-filled by evaluate.py)
    await pool.query(`
      CREATE TABLE IF NOT EXISTS portfolio_forecast_evaluations (
        id SERIAL PRIMARY KEY,
        forecast_result_id INTEGER NOT NULL REFERENCES portfolio_forecast_results(id) ON DELETE CASCADE,
        portfolio_id INTEGER NOT NULL,
        symbol TEXT NOT NULL,
        run_date DATE NOT NULL,
        target_date DATE NOT NULL,
        expected_return_pct REAL,
        actual_return_pct REAL,
        actual_close REAL,
        error_pct REAL,
        within_5pct BOOLEAN NOT NULL DEFAULT FALSE,
        within_10pct BOOLEAN NOT NULL DEFAULT FALSE,
        evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(forecast_result_id)
      )
    `);
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_pfe_portfolio ON portfolio_forecast_evaluations(portfolio_id)');
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_pfe_symbol ON portfolio_forecast_evaluations(symbol)');

    // Table: Portfolio Daily Actuals (actual price recorded each day for in-progress forecasts)
    await pool.query(`
      CREATE TABLE IF NOT EXISTS portfolio_daily_actuals (
        id SERIAL PRIMARY KEY,
        portfolio_id INTEGER NOT NULL REFERENCES forecast_portfolios(id) ON DELETE CASCADE,
        symbol TEXT NOT NULL,
        date DATE NOT NULL,
        actual_close REAL,
        return_pct_from_start REAL,
        UNIQUE(portfolio_id, symbol, date)
      )
    `);
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_pda_portfolio ON portfolio_daily_actuals(portfolio_id, date DESC)');

    // pgvector extension — enables fast vector similarity search
    // Graceful: skips silently if extension is unavailable on this PostgreSQL instance
    try {
      await pool.query('CREATE EXTENSION IF NOT EXISTS vector');
      console.log('✅ pgvector extension ready');
    } catch (e) {
      console.log('⚠️  pgvector extension not available — will use in-app cosine similarity fallback');
    }

    // Table 21: RAG Chunks (embedded text from market_reports, news_article, event_intel)
    await pool.query(`
      CREATE TABLE IF NOT EXISTS rag_chunks (
        id          SERIAL PRIMARY KEY,
        source_type TEXT NOT NULL DEFAULT 'market_report',
        source_id   INTEGER NOT NULL,
        chunk_index INTEGER NOT NULL,
        chunk_text  TEXT NOT NULL,
        embedding   TEXT,
        source_meta TEXT,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(source_type, source_id, chunk_index)
      )
    `);
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_rag_chunks_source ON rag_chunks(source_type, source_id)');

    // Add source_meta + pgvector column to existing installs
    try { await pool.query('ALTER TABLE rag_chunks ADD COLUMN IF NOT EXISTS source_meta TEXT'); } catch(_) {}
    try {
      await pool.query('ALTER TABLE rag_chunks ADD COLUMN IF NOT EXISTS embedding_vec vector(768)');
      await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_rag_chunks_vec ON rag_chunks USING ivfflat (embedding_vec vector_cosine_ops) WITH (lists = 100)');
      console.log('✅ pgvector column + index on rag_chunks ready');
    } catch(_) {
      console.log('⚠️  pgvector column not added — extension may be unavailable');
    }

    // Table 22: Prediction Contexts (snapshot + embedding + outcome for pattern matching)
    await pool.query(`
      CREATE TABLE IF NOT EXISTS prediction_contexts (
        id                SERIAL PRIMARY KEY,
        symbol            TEXT NOT NULL,
        prediction_date   DATE NOT NULL,
        context_json      TEXT NOT NULL,
        embedding         TEXT,
        actual_outcome    TEXT,
        actual_change_pct REAL,
        created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(symbol, prediction_date)
      )
    `);
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_pc_symbol ON prediction_contexts(symbol, prediction_date DESC)');
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_pc_outcome ON prediction_contexts(actual_outcome)');

    // Table 23: News RAG Chunks (live news feed integration — embedded articles with metadata)
    await pool.query(`
      CREATE TABLE IF NOT EXISTS news_rag_chunks (
        id               TEXT PRIMARY KEY,
        article_url      TEXT NOT NULL,
        source_name      TEXT NOT NULL,
        title            TEXT NOT NULL,
        content          TEXT NOT NULL,
        chunk_index      INTEGER NOT NULL DEFAULT 0,
        published_at     TIMESTAMPTZ NOT NULL,
        ingested_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        language         TEXT NOT NULL DEFAULT 'en',
        market_tag       TEXT NOT NULL DEFAULT 'UNKNOWN',
        event_type       TEXT NOT NULL DEFAULT 'GENERAL',
        affected_assets  TEXT NOT NULL DEFAULT '[]',
        affected_sectors TEXT NOT NULL DEFAULT '[]',
        drift_direction  TEXT NOT NULL DEFAULT 'UNCERTAIN',
        drift_magnitude_estimate REAL,
        embedding        TEXT
      )
    `);
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_news_rag_published ON news_rag_chunks(published_at DESC)');
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_news_rag_market    ON news_rag_chunks(market_tag)');
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_news_rag_event     ON news_rag_chunks(event_type)');
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_news_rag_url       ON news_rag_chunks(article_url)');

    // Table 24: Drift Adjustment Log (immutable audit trail for simulation drift recalibration)
    await pool.query(`
      CREATE TABLE IF NOT EXISTS drift_adjustment_log (
        adjustment_id       TEXT PRIMARY KEY,
        chunk_id            TEXT NOT NULL,
        asset_ticker        TEXT NOT NULL,
        original_drift      REAL NOT NULL,
        adjustment_bps      REAL NOT NULL,
        adjusted_drift      REAL NOT NULL,
        decay_halflife_days INTEGER NOT NULL,
        applied_at          TIMESTAMPTZ NOT NULL,
        expires_at          TIMESTAMPTZ NOT NULL,
        event_type          TEXT NOT NULL,
        source_headline     TEXT NOT NULL,
        confidence          REAL NOT NULL,
        applied_by          TEXT NOT NULL DEFAULT 'news_drift_engine',
        audit_hash          TEXT NOT NULL
      )
    `);
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_drift_log_ticker     ON drift_adjustment_log(asset_ticker)');
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_drift_log_applied_at ON drift_adjustment_log(applied_at DESC)');
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_drift_log_expires_at ON drift_adjustment_log(expires_at)');

    // ── ETF / Instrument tables ────────────────────────────────────────────────

    // ENUMs (idempotent — EXCEPTION WHEN duplicate_object THEN NULL)
    await pool.query(`DO $$ BEGIN CREATE TYPE instrument_type AS ENUM ('EQUITY','ETF','INDEX','FX','RATE'); EXCEPTION WHEN duplicate_object THEN NULL; END $$`);
    // Add ETP subtypes to instrument_type enum (safe — ALTER TYPE IF NOT EXISTS value)
    for (const v of ['COMMODITY_ETP','GOLD_ETP','INDEX_TRACKER','STRUCTURED_NOTE','ETN','ETP','UNKNOWN_ETP','EQUITY_FUND']) {
      await pool.query(`DO $$ BEGIN ALTER TYPE instrument_type ADD VALUE IF NOT EXISTS '${v}'; EXCEPTION WHEN others THEN NULL; END $$`);
    }
    await pool.query(`DO $$ BEGIN CREATE TYPE exchange_code   AS ENUM ('EGX','NYSE','NASDAQ','LSE','XETRA','TSX','OTHER'); EXCEPTION WHEN duplicate_object THEN NULL; END $$`);
    await pool.query(`DO $$ BEGIN CREATE TYPE currency_code   AS ENUM ('EGP','USD','EUR','GBP','CAD','OTHER'); EXCEPTION WHEN duplicate_object THEN NULL; END $$`);
    await pool.query(`DO $$ BEGIN CREATE TYPE etf_region      AS ENUM ('LOCAL_EGX','GLOBAL'); EXCEPTION WHEN duplicate_object THEN NULL; END $$`);
    await pool.query(`DO $$ BEGIN CREATE TYPE doc_type        AS ENUM ('PROSPECTUS','FACTSHEET','INFO_SHEET','INDEX_METHODOLOGY','HOLDINGS_FILE','OTHER'); EXCEPTION WHEN duplicate_object THEN NULL; END $$`);

    // Table: instrument master
    await pool.query(`
      CREATE TABLE IF NOT EXISTS instrument (
        instrument_id    BIGSERIAL PRIMARY KEY,
        type             instrument_type NOT NULL DEFAULT 'ETF',
        region           etf_region,
        symbol           TEXT NOT NULL,
        isin             TEXT,
        name             TEXT,
        exchange         exchange_code,
        currency         currency_code,
        country          TEXT,
        issuer           TEXT,
        underlying_index TEXT,
        inception_date   DATE,
        is_active        BOOLEAN NOT NULL DEFAULT TRUE,
        created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE(exchange, symbol)
      )
    `);
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_instrument_symbol ON instrument(symbol)');

    // Table: instrument aliases
    await pool.query(`
      CREATE TABLE IF NOT EXISTS instrument_alias (
        instrument_alias_id BIGSERIAL PRIMARY KEY,
        instrument_id       BIGINT NOT NULL REFERENCES instrument(instrument_id) ON DELETE CASCADE,
        alias               TEXT NOT NULL,
        alias_type          TEXT NOT NULL DEFAULT 'GENERAL',
        UNIQUE(instrument_id, alias)
      )
    `);

    // Table: ETF daily price tape
    await pool.query(`
      CREATE TABLE IF NOT EXISTS etf_price_daily (
        instrument_id BIGINT NOT NULL REFERENCES instrument(instrument_id) ON DELETE CASCADE,
        trade_date    DATE NOT NULL,
        open_price    NUMERIC(18,6),
        high_price    NUMERIC(18,6),
        low_price     NUMERIC(18,6),
        close_price   NUMERIC(18,6),
        last_price    NUMERIC(18,6),
        pct_change    NUMERIC(12,6),
        value_traded  NUMERIC(24,6),
        volume        NUMERIC(24,6),
        trades        INTEGER,
        market_cap_mn NUMERIC(24,6),
        source_url    TEXT NOT NULL,
        ingested_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY(instrument_id, trade_date)
      )
    `);

    // Table: ETF NAV
    await pool.query(`
      CREATE TABLE IF NOT EXISTS etf_nav (
        instrument_id   BIGINT NOT NULL REFERENCES instrument(instrument_id) ON DELETE CASCADE,
        nav_date        DATE NOT NULL,
        nav_value       NUMERIC(18,6) NOT NULL,
        last_update_raw TEXT,
        source_url      TEXT NOT NULL,
        ingested_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY(instrument_id, nav_date)
      )
    `);

    // Table: ETF iNAV + tracking error
    await pool.query(`
      CREATE TABLE IF NOT EXISTS etf_inav (
        instrument_id  BIGINT NOT NULL REFERENCES instrument(instrument_id) ON DELETE CASCADE,
        ts             TIMESTAMPTZ NOT NULL,
        inav_value     NUMERIC(18,6),
        tracking_error NUMERIC(18,6),
        source_url     TEXT NOT NULL,
        ingested_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY(instrument_id, ts)
      )
    `);

    // Table: ETF premium/discount (computed)
    await pool.query(`
      CREATE TABLE IF NOT EXISTS etf_premium_discount_daily (
        instrument_id    BIGINT NOT NULL REFERENCES instrument(instrument_id) ON DELETE CASCADE,
        asof_date        DATE NOT NULL,
        market_price     NUMERIC(18,6) NOT NULL,
        nav_value        NUMERIC(18,6) NOT NULL,
        premium_discount NUMERIC(18,6) NOT NULL,
        nav_date_used    DATE NOT NULL,
        calc_notes       TEXT,
        created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY(instrument_id, asof_date)
      )
    `);

    // Table: ETF fund volume (AUM proxy)
    await pool.query(`
      CREATE TABLE IF NOT EXISTS etf_fund_volume (
        instrument_id   BIGINT NOT NULL REFERENCES instrument(instrument_id) ON DELETE CASCADE,
        asof_date       DATE NOT NULL,
        fund_size       NUMERIC(24,6),
        net_subs        NUMERIC(24,6),
        no_units        NUMERIC(24,6),
        last_update_raw TEXT,
        source_url      TEXT NOT NULL,
        ingested_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY(instrument_id, asof_date)
      )
    `);

    // Table: ETF holdings snapshot header
    await pool.query(`
      CREATE TABLE IF NOT EXISTS etf_holdings_snapshot (
        snapshot_id   BIGSERIAL PRIMARY KEY,
        instrument_id BIGINT NOT NULL REFERENCES instrument(instrument_id) ON DELETE CASCADE,
        snapshot_date DATE NOT NULL,
        source        TEXT NOT NULL,
        source_url    TEXT NOT NULL,
        currency      currency_code,
        total_weight  NUMERIC(18,8),
        ingested_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE(instrument_id, snapshot_date, source)
      )
    `);

    // Table: ETF holding lines (constituents)
    await pool.query(`
      CREATE TABLE IF NOT EXISTS etf_holding_line (
        snapshot_id    BIGINT NOT NULL REFERENCES etf_holdings_snapshot(snapshot_id) ON DELETE CASCADE,
        line_no        INTEGER NOT NULL,
        holding_symbol TEXT,
        holding_name   TEXT NOT NULL,
        holding_isin   TEXT,
        weight_pct     NUMERIC(18,10) NOT NULL,
        country        TEXT,
        sector         TEXT,
        asset_type     TEXT,
        PRIMARY KEY(snapshot_id, line_no)
      )
    `);
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_holding_line_symbol ON etf_holding_line(holding_symbol)');

    // Table: ETF country exposure
    await pool.query(`
      CREATE TABLE IF NOT EXISTS etf_country_exposure (
        instrument_id BIGINT NOT NULL REFERENCES instrument(instrument_id) ON DELETE CASCADE,
        asof_date     DATE NOT NULL,
        country       TEXT NOT NULL,
        weight_pct    NUMERIC(18,10) NOT NULL,
        source_url    TEXT NOT NULL,
        ingested_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY(instrument_id, asof_date, country)
      )
    `);

    // Table: RAG document metadata (PDFs: prospectuses, factsheets, info sheets)
    await pool.query(`
      CREATE TABLE IF NOT EXISTS rag_document (
        doc_id        BIGSERIAL PRIMARY KEY,
        instrument_id BIGINT REFERENCES instrument(instrument_id) ON DELETE SET NULL,
        doc_type      doc_type NOT NULL,
        title         TEXT NOT NULL,
        publisher     TEXT,
        language      TEXT,
        publish_date  DATE,
        url           TEXT NOT NULL,
        content_hash  TEXT,
        storage_uri   TEXT,
        fetched_at    TIMESTAMPTZ,
        ingested_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE(url)
      )
    `);

    // Table: RAG embedding job queue
    await pool.query(`
      CREATE TABLE IF NOT EXISTS rag_embedding_job (
        job_id        BIGSERIAL PRIMARY KEY,
        doc_id        BIGINT NOT NULL REFERENCES rag_document(doc_id) ON DELETE CASCADE,
        embed_model   TEXT NOT NULL DEFAULT 'text-embedding-005',
        status        TEXT NOT NULL DEFAULT 'PENDING',
        started_at    TIMESTAMPTZ,
        finished_at   TIMESTAMPTZ,
        error_message TEXT
      )
    `);

    console.log('✅ ETF / instrument tables ready');

    // New columns (safe — IF NOT EXISTS syntax; errors caught so lock_timeout doesn't abort init)
    try { await pool.query('ALTER TABLE user_positions ADD COLUMN IF NOT EXISTS quantity INTEGER DEFAULT 1'); } catch(_) {}
    try { await pool.query('ALTER TABLE evaluations    ADD COLUMN IF NOT EXISTS horizon_days INTEGER DEFAULT 5'); } catch(_) {}

    // Table: Price Alerts
    await pool.query(`
      CREATE TABLE IF NOT EXISTS price_alerts (
        id           BIGSERIAL PRIMARY KEY,
        user_id      BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        symbol       TEXT NOT NULL,
        condition    TEXT NOT NULL DEFAULT 'above',
        target_price NUMERIC(18,4) NOT NULL,
        active       BOOLEAN NOT NULL DEFAULT TRUE,
        triggered_at TIMESTAMPTZ,
        created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
      )
    `);
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_alerts_user   ON price_alerts(user_id)');
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_alerts_active ON price_alerts(active)');

    // Table: FX Rates History (one row per day)
    await pool.query(`
      CREATE TABLE IF NOT EXISTS fx_rates_history (
        id             BIGSERIAL PRIMARY KEY,
        date           DATE NOT NULL UNIQUE,
        usd_egp        NUMERIC(18,4),
        usd_sar        NUMERIC(18,4),
        xau_usd        NUMERIC(18,4),
        gold_24k_egp_g NUMERIC(18,4),
        gold_21k_egp_g NUMERIC(18,4),
        gold_pound_egp NUMERIC(18,4),
        created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
      )
    `);
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_fx_history_date ON fx_rates_history(date DESC)');

    // Table: Signal evaluations at multiple horizons (D+5, D+10, D+20)
    await pool.query(`
      CREATE TABLE IF NOT EXISTS stock_signal_evals (
        id                BIGSERIAL PRIMARY KEY,
        symbol            TEXT NOT NULL,
        prediction_date   DATE NOT NULL,
        horizon_days      INTEGER NOT NULL,
        predicted_signal  TEXT,
        actual_change_pct NUMERIC(18,4),
        was_correct       BOOLEAN,
        evaluated_at      DATE NOT NULL DEFAULT CURRENT_DATE,
        UNIQUE(symbol, prediction_date, horizon_days)
      )
    `);
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_sse_symbol  ON stock_signal_evals(symbol, prediction_date DESC)');
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_sse_horizon ON stock_signal_evals(horizon_days)');

    // scored_signals — Universal Investor Scoring
    await pool.query(`
      CREATE TABLE IF NOT EXISTS scored_signals (
        id               SERIAL PRIMARY KEY,
        symbol           TEXT NOT NULL,
        signal_date      DATE NOT NULL,
        action           TEXT NOT NULL DEFAULT 'HOLD',
        composite_score  REAL NOT NULL,
        scoring_mode     TEXT NOT NULL DEFAULT 'standard_100',
        score_value      TEXT NOT NULL,
        consensus_score  REAL,
        execution_score  REAL,
        regime_score     REAL,
        momentum_score   REAL,
        meets_threshold  BOOLEAN DEFAULT FALSE,
        all_formats      TEXT,
        created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(symbol, signal_date)
      )
    `);
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_scored_date   ON scored_signals(signal_date DESC)');
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_scored_symbol ON scored_signals(symbol)');

    console.log('✅ New tables (alerts, fx_history, signal_evals, scored_signals) ready');

    // Remove any KSA (.SR) stocks that may have been inserted during KSA testing
    await pool.query("DELETE FROM egx30_stocks WHERE symbol LIKE '%.SR'");

    // Seed ALL EGX stocks (~190) — disable statement_timeout for this large INSERT
    await pool.query("SET statement_timeout = 0");
    console.log('🌱 Seeding EGX stocks...');
    await pool.query(`
      INSERT INTO egx30_stocks (symbol, name_en, name_ar, sector_en, sector_ar) VALUES
      -- Banking
      ('COMI.CA', 'Commercial International Bank (CIB)', 'البنك التجاري الدولي', 'Banking', 'البنوك'),
      ('ADIB.CA', 'Abu Dhabi Islamic Bank Egypt', 'مصرف أبوظبي الإسلامي – مصر', 'Banking', 'البنوك'),
      ('QNBE.CA', 'Qatar National Bank Al Ahli', 'بنك قطر الوطني الأهلي', 'Banking', 'البنوك'),
      ('HDBK.CA', 'Housing and Development Bank', 'بنك التعمير والإسكان', 'Banking', 'البنوك'),
      ('CIEB.CA', 'Credit Agricole Egypt', 'بنك كريدي أجريكول مصر', 'Banking', 'البنوك'),
      ('CANA.CA', 'Suez Canal Bank', 'بنك قناة السويس', 'Banking', 'البنوك'),
      ('FAIT.CA', 'Faisal Islamic Bank of Egypt (EGP)', 'بنك فيصل الإسلامي المصري بالجنيه', 'Banking', 'البنوك'),
      ('FAITA.CA', 'Faisal Islamic Bank of Egypt (USD)', 'بنك فيصل الإسلامي المصري بالدولار', 'Banking', 'البنوك'),
      ('EXPA.CA', 'Export Development Bank of Egypt', 'البنك المصري لتنمية الصادرات', 'Banking', 'البنوك'),
      ('SAUD.CA', 'Al Baraka Bank Egypt', 'بنك البركة مصر', 'Banking', 'البنوك'),
      ('UBEE.CA', 'The United Bank', 'المصرف المتحد', 'Banking', 'البنوك'),
      ('EGBE.CA', 'Egyptian Gulf Bank', 'البنك المصري الخليجي', 'Banking', 'البنوك'),
      ('SAIB.CA', 'Societe Arabe Internationale de Banque', 'بنك الشركة المصرفية العربية الدولية', 'Banking', 'البنوك'),
      -- Financial Services
      ('HRHO.CA', 'EFG Hermes Holding', 'المجموعة المالية هيرمس القابضة', 'Financial Services', 'الخدمات المالية'),
      ('EFIH.CA', 'e-Finance for Digital & Financial Investments', 'إي فاينانس للاستثمارات المالية والرقمية', 'Financial Services', 'الخدمات المالية'),
      ('FWRY.CA', 'Fawry for Banking Technology', 'فوري لتكنولوجيا البنوك والمدفوعات', 'Financial Services', 'الخدمات المالية'),
      ('CCAP.CA', 'Qalaa Holdings', 'القلعة القابضة', 'Financial Services', 'الخدمات المالية'),
      ('BINV.CA', 'B Investments Holding', 'بي إنفستمنتس القابضة', 'Financial Services', 'الخدمات المالية'),
      ('CICH.CA', 'CI Capital Holding', 'سي آي كابيتال القابضة', 'Financial Services', 'الخدمات المالية'),
      ('VALU.CA', 'U Consumer Finance', 'يو للتمويل الاستهلاكي', 'Financial Services', 'الخدمات المالية'),
      ('RAYA.CA', 'Raya Holding', 'راية القابضة', 'Financial Services', 'الخدمات المالية'),
      ('CNFN.CA', 'Contact Financial Holding', 'كونتكت المالية القابضة', 'Financial Services', 'الخدمات المالية'),
      ('ACAP.CA', 'A Capital Holding', 'ايه كابيتال القابضة', 'Financial Services', 'الخدمات المالية'),
      ('ATLC.CA', 'Al Tawfeek Leasing', 'التوفيق للتأجير التمويلي', 'Financial Services', 'الخدمات المالية'),
      ('ICLE.CA', 'International Co. for Leasing', 'الدولية للتأجير التمويلي', 'Financial Services', 'الخدمات المالية'),
      ('ANFI.CA', 'Alexandria National Financial Investments', 'الاسكندرية الوطنية للاستثمارات المالية', 'Financial Services', 'الخدمات المالية'),
      ('PRMH.CA', 'Prime Holding', 'برايم القابضة للاستثمارات المالية', 'Financial Services', 'الخدمات المالية'),
      ('GRCA.CA', 'Grand Investment Capital', 'جراند انفستمنت القابضة', 'Financial Services', 'الخدمات المالية'),
      ('ASPI.CA', 'Aspire Capital Holding', 'اسباير كابيتال القابضة', 'Financial Services', 'الخدمات المالية'),
      ('BTFH.CA', 'Beltone Financial Holding', 'بلتون المالية القابضة', 'Financial Services', 'الخدمات المالية'),
      ('OFH.CA', 'Orascom Financial Holding', 'أوراسكوم المالية القابضة', 'Financial Services', 'الخدمات المالية'),
      ('RACC.CA', 'Raya Customer Experience', 'راية لخدمات مراكز الاتصالات', 'Financial Services', 'الخدمات المالية'),
      ('ODIN.CA', 'ODIN Investments', 'أودن للاستثمارات المالية', 'Financial Services', 'الخدمات المالية'),
      -- Real Estate
      ('TMGH.CA', 'Talaat Moustafa Group Holding', 'مجموعة طلعت مصطفى القابضة', 'Real Estate', 'العقارات'),
      ('PHDC.CA', 'Palm Hills Development', 'بالم هيلز للتعمير', 'Real Estate', 'العقارات'),
      ('OCDI.CA', 'SODIC', 'السادس من أكتوبر للتنمية والاستثمار', 'Real Estate', 'العقارات'),
      ('ORHD.CA', 'Orascom Development Egypt', 'أوراسكوم للتنمية مصر', 'Real Estate', 'العقارات'),
      ('EMFD.CA', 'Emaar Misr for Development', 'إعمار مصر للتنمية', 'Real Estate', 'العقارات'),
      ('MNHD.CA', 'Madinet Nasr Housing', 'مدينة نصر للإسكان والتعمير', 'Real Estate', 'العقارات'),
      ('HELI.CA', 'Heliopolis Housing & Development', 'مصر الجديدة للإسكان والتعمير', 'Real Estate', 'العقارات'),
      ('CIRA.CA', 'Cairo for Investment & Real Estate', 'القاهرة للاستثمار والتنمية العقارية', 'Real Estate', 'العقارات'),
      ('ZMID.CA', 'Zahraa El Maadi Investment', 'زهراء المعادي للاستثمار والتعمير', 'Real Estate', 'العقارات'),
      ('ARAB.CA', 'Arab Developers Holding', 'المطورون العرب القابضة', 'Real Estate', 'العقارات'),
      ('GPPL.CA', 'Golden Pyramids Plaza', 'جولدن بيراميدز بلازا', 'Real Estate', 'العقارات'),
      ('ELKA.CA', 'Cairo Housing & Development', 'القاهرة للإسكان والتعمير', 'Real Estate', 'العقارات'),
      ('UNIT.CA', 'United Housing & Development', 'المتحدة للإسكان والتعمير', 'Real Estate', 'العقارات'),
      ('PRDC.CA', 'Pioneers Properties', 'بايونيرز بروبرتيز للتنمية العمرانية', 'Real Estate', 'العقارات'),
      ('ELSH.CA', 'Al Shams Housing', 'الشمس للإسكان والتعمير', 'Real Estate', 'العقارات'),
      ('EHDR.CA', 'Egyptians for Housing', 'المصريين للإسكان والتنمية', 'Real Estate', 'العقارات'),
      ('OBRI.CA', 'El Ebour Real Estate', 'العبور للاستثمار العقاري', 'Real Estate', 'العقارات'),
      ('BONY.CA', 'Bonyan for Development', 'بنيان للتنمية والتجارة', 'Real Estate', 'العقارات'),
      ('TANM.CA', 'Tanmiya Real Estate', 'تنمية للاستثمار العقاري', 'Real Estate', 'العقارات'),
      ('IDRE.CA', 'Ismailia Development & Real Estate', 'الاسماعيلية للتطوير والتنمية العمرانية', 'Real Estate', 'العقارات'),
      ('NHPS.CA', 'National Housing Professional Syndicates', 'الوطنية للإسكان للنقابات المهنية', 'Real Estate', 'العقارات'),
      ('MAAL.CA', 'Marseille Egyptian-Khaleeji Investment', 'مرسيليا المصرية الخليجية للاستثمار العقاري', 'Real Estate', 'العقارات'),
      ('AREH.CA', 'Real Estate Egyptian Consortium', 'المجموعة المصرية العقارية', 'Real Estate', 'العقارات'),
      ('COPR.CA', 'Copper Commercial Investment', 'كوبر للاستثمار التجاري والتطوير العقاري', 'Real Estate', 'العقارات'),
      ('GIHD.CA', 'Gharbia Islamic Housing', 'الغربية الإسلامية للتنمية العمرانية', 'Real Estate', 'العقارات'),
      -- Chemicals & Fertilizers
      ('ABUK.CA', 'Abu Qir Fertilizers', 'أبو قير للأسمدة والصناعات الكيماوية', 'Chemicals', 'الكيماويات'),
      ('MFPC.CA', 'Misr Fertilizers (MOPCO)', 'مصر لإنتاج الأسمدة (موبكو)', 'Chemicals', 'الكيماويات'),
      ('SKPC.CA', 'Sidi Kerir Petrochemicals', 'سيدي كرير للبتروكيماويات', 'Chemicals', 'الكيماويات'),
      ('EGCH.CA', 'Egyptian Chemical Industries (KIMA)', 'الصناعات الكيماوية المصرية (كيما)', 'Chemicals', 'الكيماويات'),
      ('MICH.CA', 'Misr Chemical Industries', 'مصر لصناعة الكيماويات', 'Chemicals', 'الكيماويات'),
      ('KZPC.CA', 'Kafr El Zayat Pesticides', 'كفر الزيات للمبيدات والكيماويات', 'Chemicals', 'الكيماويات'),
      ('SMFR.CA', 'Samad Misr (EGYFERT)', 'سماد مصر', 'Chemicals', 'الكيماويات'),
      ('FERC.CA', 'Ferchem Misr Fertilizers', 'فيركيم مصر للأسمدة والكيماويات', 'Chemicals', 'الكيماويات'),
      -- Industrial & Manufacturing
      ('SWDY.CA', 'Elsewedy Electric', 'السويدي إليكتريك', 'Industrials', 'الصناعات'),
      ('EAST.CA', 'Eastern Company (Tobacco)', 'الشرقية – إيسترن كومباني', 'Consumer Staples', 'السلع الأساسية'),
      ('GBCO.CA', 'GB Corp (Ghabbour Auto)', 'جي بي أوتو', 'Industrials', 'الصناعات'),
      ('ORWE.CA', 'Oriental Weavers Carpets', 'النساجون الشرقيون للسجاد', 'Industrials', 'الصناعات'),
      ('ORAS.CA', 'Orascom Construction', 'أوراسكوم للإنشاءات', 'Industrials', 'الصناعات'),
      ('ESRS.CA', 'Ezz Steel', 'حديد عز', 'Materials', 'المواد'),
      ('EKHOA.CA', 'Ezz Aldekhela Steel', 'عز الدخيلة للصلب', 'Materials', 'المواد'),
      ('EKHO.CA', 'Egypt Kuwait Holding', 'القابضة المصرية الكويتية', 'Industrials', 'الصناعات'),
      ('EGAL.CA', 'Egypt Aluminum', 'مصر للألومنيوم', 'Materials', 'المواد'),
      ('IRON.CA', 'Egyptian Iron & Steel', 'الحديد والصلب المصرية', 'Materials', 'المواد'),
      ('MTIE.CA', 'MM Group for Industry & Trade', 'ام.ام جروب للصناعة والتجارة العالمية', 'Industrials', 'الصناعات'),
      ('ELEC.CA', 'Electro Cable Egypt', 'الكابلات الكهربائية المصرية', 'Industrials', 'الصناعات'),
      ('ACRO.CA', 'Acrow Misr', 'أكرو مصر للشدات والسقالات', 'Industrials', 'الصناعات'),
      ('EFIC.CA', 'Egyptian Financial & Industrial', 'المالية والصناعية المصرية', 'Industrials', 'الصناعات'),
      ('ATQA.CA', 'Misr National Steel (Ataqa)', 'مصر الوطنية للصلب (عتاقة)', 'Materials', 'المواد'),
      ('ALUM.CA', 'Arab Aluminum', 'الألومنيوم العربية', 'Materials', 'المواد'),
      ('ARVA.CA', 'Arab Valves', 'العربية للمحابس', 'Industrials', 'الصناعات'),
      ('GDWA.CA', 'Gadwa Industrial Development', 'جدوى للتنمية الصناعية', 'Industrials', 'الصناعات'),
      ('GSSC.CA', 'General Co. for Silos & Storage', 'العامة للصوامع والتخزين', 'Industrials', 'الصناعات'),
      ('ASCM.CA', 'ASEC Company for Mining (ASCOM)', 'أسيك للتعدين', 'Materials', 'المواد'),
      -- Food & Beverage
      ('JUFO.CA', 'Juhayna Food Industries', 'جهينة للصناعات الغذائية', 'Food & Beverage', 'الأغذية والمشروبات'),
      ('EFID.CA', 'Edita Food Industries', 'إيديتا للصناعات الغذائية', 'Food & Beverage', 'الأغذية والمشروبات'),
      ('DOMT.CA', 'Domty (Arabian Food Industries)', 'دومتي – الصناعات الغذائية العربية', 'Food & Beverage', 'الأغذية والمشروبات'),
      ('POUL.CA', 'Cairo Poultry Company', 'القاهرة للدواجن', 'Food & Beverage', 'الأغذية والمشروبات'),
      ('SUGR.CA', 'Delta Sugar', 'الدلتا للسكر', 'Food & Beverage', 'الأغذية والمشروبات'),
      ('OLFI.CA', 'Obour Land for Food Industries', 'عبور لاند للصناعات الغذائية', 'Food & Beverage', 'الأغذية والمشروبات'),
      ('AJWA.CA', 'AJWA for Food Industries', 'أجواء للصناعات الغذائية', 'Food & Beverage', 'الأغذية والمشروبات'),
      ('AFMC.CA', 'Alexandria Flour Mills', 'مطاحن ومخابز الإسكندرية', 'Food & Beverage', 'الأغذية والمشروبات'),
      ('ADPC.CA', 'Arab Dairy Products (Panda)', 'العربية لمنتجات الألبان (باندا)', 'Food & Beverage', 'الأغذية والمشروبات'),
      ('INFI.CA', 'Ismailia National Food Industries', 'الاسماعيلية الوطنية للصناعات الغذائية', 'Food & Beverage', 'الأغذية والمشروبات'),
      ('MPCO.CA', 'Mansoura Poultry', 'المنصورة للدواجن', 'Food & Beverage', 'الأغذية والمشروبات'),
      ('EPCO.CA', 'Egypt for Poultry', 'المصرية للدواجن', 'Food & Beverage', 'الأغذية والمشروبات'),
      ('WCDF.CA', 'Middle & West Delta Flour Mills', 'مطاحن وسط وغرب الدلتا', 'Food & Beverage', 'الأغذية والمشروبات'),
      ('UEFM.CA', 'Upper Egypt Flour Mills', 'مطاحن مصر العليا', 'Food & Beverage', 'الأغذية والمشروبات'),
      ('EDFM.CA', 'East Delta Flour Mills', 'مطاحن شرق الدلتا', 'Food & Beverage', 'الأغذية والمشروبات'),
      ('SCFM.CA', 'South Cairo & Giza Flour Mills', 'مطاحن ومخابز جنوب القاهرة والجيزة', 'Food & Beverage', 'الأغذية والمشروبات'),
      ('CEFM.CA', 'Middle Egypt Flour Mills', 'مطاحن مصر الوسطى', 'Food & Beverage', 'الأغذية والمشروبات'),
      ('MILS.CA', 'North Cairo Flour Mills', 'مطاحن ومخابز شمال القاهرة', 'Food & Beverage', 'الأغذية والمشروبات'),
      -- Pharmaceuticals
      ('PHAR.CA', 'EIPICO (Egyptian International Pharma)', 'المصرية الدولية للصناعات الدوائية', 'Pharmaceuticals', 'الأدوية'),
      ('ISPH.CA', 'Ibnsina Pharma', 'ابن سينا فارما', 'Pharmaceuticals', 'الأدوية'),
      ('RMDA.CA', 'Rameda Pharma', 'العاشر من رمضان للصناعات الدوائية (راميدا)', 'Pharmaceuticals', 'الأدوية'),
      ('BIOC.CA', 'GlaxoSmithKline Egypt', 'جلاكسو سميثكلاين مصر', 'Pharmaceuticals', 'الأدوية'),
      ('NIPH.CA', 'El-Nile Pharmaceuticals', 'النيل للأدوية والصناعات الكيماوية', 'Pharmaceuticals', 'الأدوية'),
      ('MIPH.CA', 'Minapharm Pharmaceuticals', 'مينا فارم للأدوية', 'Pharmaceuticals', 'الأدوية'),
      ('AXPH.CA', 'Alexandria Pharmaceuticals', 'الإسكندرية للأدوية والصناعات الكيماوية', 'Pharmaceuticals', 'الأدوية'),
      ('CPCI.CA', 'Cairo Pharmaceuticals', 'القاهرة للأدوية والصناعات الكيماوية', 'Pharmaceuticals', 'الأدوية'),
      ('MPCI.CA', 'Memphis Pharmaceuticals', 'ممفيس للأدوية', 'Pharmaceuticals', 'الأدوية'),
      ('OCPH.CA', 'October Pharma', 'أكتوبر فارما', 'Pharmaceuticals', 'الأدوية'),
      ('ADCI.CA', 'Arab Drug Company', 'العربية للأدوية', 'Pharmaceuticals', 'الأدوية'),
      ('SIPC.CA', 'Sabaa International Pharma', 'سبأ الدولية للأدوية', 'Pharmaceuticals', 'الأدوية'),
      ('MCRO.CA', 'Macro Group Pharmaceuticals', 'ماكرو جروب للمستحضرات الطبية', 'Pharmaceuticals', 'الأدوية'),
      -- Telecom & Technology
      ('ETEL.CA', 'Telecom Egypt', 'المصرية للاتصالات', 'Telecom', 'الاتصالات'),
      ('EGSA.CA', 'Egyptian Satellite (NileSat)', 'المصرية للأقمار الصناعية (نايل سات)', 'Telecom', 'الاتصالات'),
      ('MPRC.CA', 'Egyptian Media Production City', 'المصرية لمدينة الإنتاج الإعلامي', 'Technology', 'التكنولوجيا'),
      ('SCTS.CA', 'Suez Canal for Technology', 'قناة السويس لتوطين التكنولوجيا', 'Technology', 'التكنولوجيا'),
      -- Construction & Cement
      ('ARCC.CA', 'Arabian Cement Company', 'الأسمنت العربية', 'Construction', 'البناء والتشييد'),
      ('MCQE.CA', 'Misr Cement (Qena)', 'مصر للأسمنت (قنا)', 'Construction', 'البناء والتشييد'),
      ('SCEM.CA', 'Sinai Cement', 'أسمنت سيناء', 'Construction', 'البناء والتشييد'),
      ('MBSC.CA', 'Misr Beni Suef Cement', 'مصر بني سويف للأسمنت', 'Construction', 'البناء والتشييد'),
      ('SVCE.CA', 'South Valley Cement', 'جنوب الوادي للأسمنت', 'Construction', 'البناء والتشييد'),
      ('ENGC.CA', 'Industrial Engineering (ICON)', 'الصناعات الهندسية للإنشاء والتعمير', 'Construction', 'البناء والتشييد'),
      ('NCCW.CA', 'Nasr Co. for Civil Works', 'النصر للأعمال المدنية', 'Construction', 'البناء والتشييد'),
      ('GGCC.CA', 'Giza General Contracting', 'الجيزة العامة للمقاولات', 'Construction', 'البناء والتشييد'),
      ('UEGC.CA', 'El Saeed Contracting', 'الصعيد العامة للمقاولات', 'Construction', 'البناء والتشييد'),
      -- Energy
      ('AMOC.CA', 'Alexandria Mineral Oils', 'الإسكندرية للزيوت المعدنية', 'Energy', 'الطاقة'),
      ('TAQA.CA', 'TAQA Arabia', 'طاقة عربية', 'Energy', 'الطاقة'),
      ('MOIL.CA', 'Maridive and Oil Services', 'الخدمات الملاحية والبترولية', 'Energy', 'الطاقة'),
      ('EGAS.CA', 'Egypt Gas Company', 'غاز مصر', 'Energy', 'الطاقة'),
      ('ZEOT.CA', 'Extracted Oils & Derivatives', 'الزيوت المستخلصة ومنتجاتها', 'Energy', 'الطاقة'),
      ('NDRL.CA', 'National Drilling Company', 'الحفر الوطنية', 'Energy', 'الطاقة'),
      -- Healthcare
      ('CLHO.CA', 'Cleopatra Hospitals Group', 'مستشفى كليوباترا', 'Healthcare', 'الرعاية الصحية'),
      ('TALM.CA', 'Taaleem Management Services', 'تعليم لخدمات الإدارة', 'Healthcare', 'الرعاية الصحية'),
      ('DMCR.CA', 'Dice Medical & Scientific', 'دايس الطبية والعلمية', 'Healthcare', 'الرعاية الصحية'),
      ('AMES.CA', 'Alexandria New Medical Center', 'الإسكندرية للخدمات الطبية', 'Healthcare', 'الرعاية الصحية'),
      ('NINH.CA', 'Nozha International Hospital', 'مستشفى النزهة الدولي', 'Healthcare', 'الرعاية الصحية'),
      ('PHGC.CA', 'Premium Healthcare Group', 'بريميم هيلثكير جروب', 'Healthcare', 'الرعاية الصحية'),
      ('SPMD.CA', 'Speed Medical', 'سبيد ميديكال', 'Healthcare', 'الرعاية الصحية'),
      -- Hospitality & Tourism
      ('MHOT.CA', 'Misr Hotels', 'مصر للفنادق', 'Hospitality', 'السياحة والفنادق'),
      ('EGTS.CA', 'Egyptian Resorts Company', 'المصرية للمنتجعات السياحية', 'Hospitality', 'السياحة والفنادق'),
      ('PHTV.CA', 'Pyramisa Hotels & Resorts', 'بيراميزا للفنادق والقرى السياحية', 'Hospitality', 'السياحة والفنادق'),
      ('SPHT.CA', 'El Shams Pyramids Hotels', 'الشمس بيراميدز للمنشآت السياحية', 'Hospitality', 'السياحة والفنادق'),
      ('SDTI.CA', 'Sharm Dreams Tourism', 'شارم دريمز للاستثمار السياحي', 'Hospitality', 'السياحة والفنادق'),
      ('MENA.CA', 'Mena Tourism & Real Estate', 'مينا للاستثمار السياحي والعقاري', 'Hospitality', 'السياحة والفنادق'),
      ('RTVC.CA', 'Remco Tourism Villages', 'رمكو لإنشاء القرى السياحية', 'Hospitality', 'السياحة والفنادق'),
      ('ROTO.CA', 'Rowad Tourism', 'رواد السياحة', 'Hospitality', 'السياحة والفنادق'),
      ('MMAT.CA', 'Marsa Alam Tourism', 'مرسى علم للتنمية السياحية', 'Hospitality', 'السياحة والفنادق'),
      ('TRTO.CA', 'Trans Oceans Tours', 'عبر المحيطات للسياحة', 'Hospitality', 'السياحة والفنادق'),
      -- Investment Holdings
      ('OIH.CA', 'Orascom Investment Holding', 'أوراسكوم للاستثمار القابضة', 'Investment', 'الاستثمار'),
      ('AMIA.CA', 'Arab Moltaka Investments', 'الملتقى العربي للاستثمارات', 'Investment', 'الاستثمار'),
      ('NAHO.CA', 'Naeem Holding', 'النعيم القابضة للاستثمارات', 'Investment', 'الاستثمار'),
      ('AIHC.CA', 'Arabia Investments Holding', 'ارابيا انفستمنتس هولدنج', 'Investment', 'الاستثمار'),
      ('KWIN.CA', 'El Kahera El Watania Investment', 'القاهرة الوطنية للاستثمار', 'Investment', 'الاستثمار'),
      ('ICID.CA', 'International Co. for Investment', 'العالمية للاستثمار والتنمية', 'Investment', 'الاستثمار'),
      ('AFDI.CA', 'Al Ahly for Development', 'الأهلي للتنمية والاستثمار', 'Investment', 'الاستثمار'),
      ('SEIG.CA', 'Saudi Egyptian Investment', 'السعودية المصرية للاستثمار', 'Investment', 'الاستثمار'),
      ('AMER.CA', 'Amer Group Holding', 'مجموعة عامر القابضة', 'Investment', 'الاستثمار'),
      -- Agriculture
      ('IFAP.CA', 'International Agricultural Products', 'الدولية للمحاصيل الزراعية', 'Agriculture', 'الزراعة'),
      ('GGRN.CA', 'Go Green Agricultural Investment', 'جو جرين للاستثمار الزراعي', 'Agriculture', 'الزراعة'),
      ('WKOL.CA', 'Wadi Kom Ombo Land Reclamation', 'وادي كوم أمبو لاستصلاح الأراضي', 'Agriculture', 'الزراعة'),
      ('KRDI.CA', 'Al Khair River Agricultural', 'نهر الخير للتنمية والاستثمار الزراعي', 'Agriculture', 'الزراعة'),
      ('AALR.CA', 'General Co. for Land Reclamation', 'العامة لاستصلاح الأراضي', 'Agriculture', 'الزراعة'),
      ('EALR.CA', 'Arab Co. for Land Reclamation', 'العربية لاستصلاح الأراضي', 'Agriculture', 'الزراعة'),
      ('LUTS.CA', 'Lotus Agri Capital', 'لوتس للتنمية والاستثمار الزراعي', 'Agriculture', 'الزراعة'),
      ('ELNA.CA', 'El Nasr Manufacturing Agri Crops', 'النصر لتصنيع الحاصلات الزراعية', 'Agriculture', 'الزراعة'),
      -- Transportation & Logistics
      ('ALCN.CA', 'Alexandria Container & Cargo', 'الإسكندرية لتداول الحاويات والبضائع', 'Transportation', 'النقل واللوجستيات'),
      ('CSAG.CA', 'Canal Shipping Agencies', 'القناة للتوكيلات الملاحية', 'Transportation', 'النقل واللوجستيات'),
      ('ETRS.CA', 'Egyptian Transport Services', 'المصرية لخدمات النقل', 'Transportation', 'النقل واللوجستيات'),
      ('POCO.CA', 'Port Said Container Handling', 'بورسعيد لتداول الحاويات', 'Transportation', 'النقل واللوجستيات'),
      ('DCCC.CA', 'Damietta Container Handling', 'دمياط لتداول الحاويات', 'Transportation', 'النقل واللوجستيات'),
      -- Insurance
      ('MOIN.CA', 'Mohandes Insurance', 'المهندس للتأمين', 'Insurance', 'التأمين'),
      ('DEIN.CA', 'Delta Insurance', 'الدلتا للتأمين', 'Insurance', 'التأمين'),
      -- Education
      ('CAED.CA', 'Cairo Educational Services', 'القاهرة للخدمات التعليمية', 'Education', 'التعليم'),
      ('MOED.CA', 'Egyptian Modern Education Systems', 'المصرية لنظم التعليم الحديثة', 'Education', 'التعليم'),
      -- Consumer Goods & Textiles
      ('SPIN.CA', 'Alexandria Spinning & Weaving', 'الإسكندرية للغزل والنسيج', 'Consumer Goods', 'السلع الاستهلاكية'),
      ('DSCW.CA', 'Dice Sport & Casual Wear', 'دايس للملابس الجاهزة', 'Consumer Goods', 'السلع الاستهلاكية'),
      ('KABO.CA', 'El Nasr Clothing & Textiles', 'النصر للملابس والمنسوجات', 'Consumer Goods', 'السلع الاستهلاكية'),
      ('LCSW.CA', 'Lecico Egypt', 'ليسيكو مصر', 'Consumer Goods', 'السلع الاستهلاكية'),
      ('ECAP.CA', 'Al Ezz Ceramics & Porcelain', 'العز للسيراميك والبورسلين', 'Consumer Goods', 'السلع الاستهلاكية'),
      ('CERA.CA', 'Arab Ceramic (Ceramica)', 'العربية للخزف سيراميكا', 'Consumer Goods', 'السلع الاستهلاكية'),
      ('MEGM.CA', 'Middle East Glass Manufacturing', 'الشرق الأوسط لصناعة الزجاج', 'Consumer Goods', 'السلع الاستهلاكية'),
      ('RAKT.CA', 'General Co. for Paper (Rakta)', 'العامة لصناعة الورق (راكتا)', 'Consumer Goods', 'السلع الاستهلاكية'),
      ('UNIP.CA', 'Universal Paper & Packaging', 'يونيفرسال لصناعة مواد التعبئة والتغليف', 'Consumer Goods', 'السلع الاستهلاكية'),
      ('RUBX.CA', 'Rubex International', 'روبكس العالمية لتصنيع البلاستيك', 'Consumer Goods', 'السلع الاستهلاكية'),
      ('DTPP.CA', 'Delta Printing & Packaging', 'دلتا للطباعة والتغليف', 'Consumer Goods', 'السلع الاستهلاكية'),
      ('EPPK.CA', 'El Ahram Printing & Packaging', 'الأهرام للطباعة والتغليف', 'Consumer Goods', 'السلع الاستهلاكية'),
      ('COSG.CA', 'Cairo Oil & Soap', 'القاهرة للزيوت والصابون', 'Consumer Goods', 'السلع الاستهلاكية'),
      ('MOSC.CA', 'Misr Oils & Soap', 'مصر للزيوت والصابون', 'Consumer Goods', 'السلع الاستهلاكية'),
      ('MFSC.CA', 'Egypt Free Shops', 'مصر للأسواق الحرة', 'Consumer Goods', 'السلع الاستهلاكية')
      ON CONFLICT (symbol) DO UPDATE SET
        name_en = EXCLUDED.name_en,
        name_ar = EXCLUDED.name_ar,
        sector_en = EXCLUDED.sector_en,
        sector_ar = EXCLUDED.sector_ar,
        is_active = TRUE,
        updated_at = CURRENT_TIMESTAMP
    `);
    console.log('✅ EGX stocks seeded');

    // Re-enable statement_timeout for index creation (30s per index)
    await pool.query("SET statement_timeout = '30s'");

    // Create indexes
    console.log('📊 Creating indexes...');
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_prices_symbol_date ON prices(symbol, date)');
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_news_symbol_date ON news(symbol, date)');
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_predictions_symbol ON predictions(symbol, prediction_date)');
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_predictions_date ON predictions(prediction_date)');
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_consensus_symbol ON consensus_results(symbol, prediction_date)');
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_consensus_date ON consensus_results(prediction_date)');
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_users_email_lower ON users(email_lower)');
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_watchlist_user ON user_watchlist(user_id)');

    // Migration: reclassify EGX commodity funds from 'ETF' → 'COMMODITY_ETP'
    // issuer column was set to cls_en ('COMMODITY') by etf_egx_mubasher.py
    try {
      const res = await pool.query(`UPDATE instrument SET type = 'COMMODITY_ETP' WHERE exchange = 'EGX' AND issuer = 'COMMODITY' AND type = 'ETF'`);
      if (res.rowCount > 0) console.log(`✅ Reclassified ${res.rowCount} EGX commodity fund(s) → COMMODITY_ETP`);
    } catch(e) { console.log('⚠️  Commodity ETP migration skipped:', e.message); }

    console.log('✅ Database initialized successfully!');

    // Get stats
    const statsQueries = {
      totalPrices: 'SELECT COUNT(*) as count FROM prices',
      totalPredictions: 'SELECT COUNT(*) as count FROM predictions',
      stocksTracked: 'SELECT COUNT(DISTINCT symbol) as count FROM prices',
    };

    console.log('\n📊 Database Statistics:');
    for (const [key, query] of Object.entries(statsQueries)) {
      const result = await pool.query(query);
      console.log(`   ${key}: ${result.rows[0].count}`);
    }

  } catch (error) {
    console.error('❌ Database initialization failed:', error);
    process.exit(1);
  } finally {
    await pool.end();
  }
}

initializeDatabase().then(() => {
  process.exit(0);
}).catch(() => {
  process.exit(1);
});
