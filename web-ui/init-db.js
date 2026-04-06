console.log('=== INIT-DB.JS STARTING ===');
const { Pool } = require('pg');

const DATABASE_URL = process.env.DATABASE_URL;
console.log('DATABASE_URL exists:', !!DATABASE_URL);

if (!DATABASE_URL) {
  console.log('âš ï¸  No DATABASE_URL found. Skipping database initialization.');
  process.exit(0);
}

// Set a global timeout - exit after 600 seconds no matter what
const TIMEOUT_MS = 600000;
const timeoutId = setTimeout(() => {
  console.error('âŒ Database initialization timed out after 600 seconds');
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
 * SET LOCAL is transaction-scoped and cannot be overridden externally â€”
 * it applies for the duration of the enclosing transaction only.
 *
 * Errors (lock timeout, statement timeout, concurrent run) are caught
 * and logged as warnings; they never abort the whole init.
 */
async function safeCreateIndex(db, sql) {
  try {
    await db.query('BEGIN');
    await db.query("SET LOCAL lock_timeout = '5s'");
    await db.query('SET LOCAL statement_timeout = 0'); // no cap on index build time
    await db.query(sql);
    await db.query('COMMIT');
  } catch (e) {
    try { await db.query('ROLLBACK'); } catch (_) {}
    console.warn(`âš ï¸  DDL skipped (lock timeout / concurrent run): ${e.message.split('\n')[0]}`);
  }
}

async function initializeDatabase() {
  console.log('ðŸ”§ Initializing PostgreSQL database...');
  console.log('ðŸ“ Connecting to:', DATABASE_URL.replace(/:[^:@]+@/, ':****@'));

  try {
    // Test connection
    console.log('â³ Testing database connection...');
    await pool.query('SELECT 1');
    console.log('âœ… Connected to PostgreSQL');

    // lock_timeout: fail fast if we can't acquire a DDL lock within 5s
    // (covers concurrent GH Actions jobs holding AccessExclusiveLock).
    // statement_timeout=0: index BUILD time is intentionally unlimited â€”
    // lock_timeout already protects against lock hangs. Capping build time
    // caused all 47 index creations to timeout at 30s each, consuming the
    // entire 300s global window before the server could start.
    // Both settings are session-level; with max:1 pool they apply to every
    // subsequent pool.query() call on this same connection.
    await pool.query("SET lock_timeout = '5s'");
    await pool.query("SET statement_timeout = '0'");
    console.log('â±  lock_timeout=5s  statement_timeout=0 (unlimited)');

    // Create tables
    console.log('ðŸ“‹ Creating tables...');

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
      console.log('âœ… Added reasoning column to predictions');
    } catch (err) {
      // Column may already exist, that's fine
    }

    // Add xmore_score column to consensus_results if not exists
    try {
      await pool.query('ALTER TABLE consensus_results ADD COLUMN IF NOT EXISTS xmore_score REAL');
      console.log('âœ… Added xmore_score column to consensus_results');
    } catch (err) { /* already exists */ }
    try { await pool.query('ALTER TABLE consensus_results ADD COLUMN IF NOT EXISTS calibrated_confidence REAL'); } catch (err) { /* already exists */ }
    try { await pool.query('ALTER TABLE consensus_results ADD COLUMN IF NOT EXISTS expected_edge_pct REAL'); } catch (err) { /* already exists */ }
    try { await pool.query('ALTER TABLE consensus_results ADD COLUMN IF NOT EXISTS ranking_score REAL'); } catch (err) { /* already exists */ }
    try { await pool.query('ALTER TABLE consensus_results ADD COLUMN IF NOT EXISTS weight_profile_json TEXT'); } catch (err) { /* already exists */ }
    try { await pool.query('ALTER TABLE consensus_results ADD COLUMN IF NOT EXISTS calibration_meta_json TEXT'); } catch (err) { /* already exists */ }

    // Signal enrichment columns (drivers, risk_level, expected_move, enrichment_regime, signal_label, liquidity_score)
    try { await pool.query('ALTER TABLE consensus_results ADD COLUMN IF NOT EXISTS drivers_json TEXT'); } catch (err) { /* already exists */ }
    try { await pool.query('ALTER TABLE consensus_results ADD COLUMN IF NOT EXISTS risk_level TEXT'); } catch (err) { /* already exists */ }
    try { await pool.query('ALTER TABLE consensus_results ADD COLUMN IF NOT EXISTS expected_move TEXT'); } catch (err) { /* already exists */ }
    try { await pool.query('ALTER TABLE consensus_results ADD COLUMN IF NOT EXISTS enrichment_regime TEXT'); } catch (err) { /* already exists */ }
    try { await pool.query('ALTER TABLE consensus_results ADD COLUMN IF NOT EXISTS signal_label TEXT'); } catch (err) { /* already exists */ }
    try { await pool.query('ALTER TABLE consensus_results ADD COLUMN IF NOT EXISTS liquidity_score TEXT'); } catch (err) { /* already exists */ }

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
    console.log('âœ… backtest_results table ready');

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
    console.log('âœ… agent_performance_daily table ready');

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
    console.log('âœ… regime_log table ready');

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
    console.log('âœ… etf_signals table ready');

    // ============================================
    // AUTH & WATCHLIST TABLES
    // ============================================

    // Table 8: Users
    console.log('ðŸ“Š Creating users table...');
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

    // Table 9: KSA Stocks reference (legacy table name: egx30_stocks)
    console.log('ðŸ“Š Creating egx30_stocks table...');
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
    console.log('ðŸ“Š Creating user_watchlist table...');
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
    console.log('ðŸ“Š Creating user_positions table...');
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
    console.log('ðŸ“Š Creating trade_recommendations table...');
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

    // pgvector extension â€” enables fast vector similarity search
    // Graceful: skips silently if extension is unavailable on this PostgreSQL instance
    try {
      await pool.query('CREATE EXTENSION IF NOT EXISTS vector');
      console.log('âœ… pgvector extension ready');
    } catch (e) {
      console.log('âš ï¸  pgvector extension not available â€” will use in-app cosine similarity fallback');
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
      console.log('âœ… pgvector column + index on rag_chunks ready');
    } catch(_) {
      console.log('âš ï¸  pgvector column not added â€” extension may be unavailable');
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

    // Table 23: News RAG Chunks (live news feed integration â€” embedded articles with metadata)
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

    // â”€â”€ ETF / Instrument tables â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    // ENUMs (idempotent â€” EXCEPTION WHEN duplicate_object THEN NULL)
    await pool.query(`DO $$ BEGIN CREATE TYPE instrument_type AS ENUM ('EQUITY','ETF','INDEX','FX','RATE'); EXCEPTION WHEN duplicate_object THEN NULL; END $$`);
    // Add ETP subtypes to instrument_type enum (safe â€” ALTER TYPE IF NOT EXISTS value)
    for (const v of ['COMMODITY_ETP','GOLD_ETP','INDEX_TRACKER','STRUCTURED_NOTE','ETN','ETP','UNKNOWN_ETP','EQUITY_FUND']) {
      await pool.query(`DO $$ BEGIN ALTER TYPE instrument_type ADD VALUE IF NOT EXISTS '${v}'; EXCEPTION WHEN others THEN NULL; END $$`);
    }
    await pool.query(`DO $$ BEGIN CREATE TYPE exchange_code   AS ENUM ('TADAWUL','EGX','NYSE','NASDAQ','LSE','XETRA','TSX','OTHER'); EXCEPTION WHEN duplicate_object THEN NULL; END $$`);
    await pool.query(`DO $$ BEGIN CREATE TYPE currency_code   AS ENUM ('SAR','EGP','USD','EUR','GBP','CAD','OTHER'); EXCEPTION WHEN duplicate_object THEN NULL; END $$`);
    await pool.query(`DO $$ BEGIN CREATE TYPE etf_region      AS ENUM ('LOCAL_KSA','LOCAL_EGX','GLOBAL'); EXCEPTION WHEN duplicate_object THEN NULL; END $$`);
    // Ensure new enum values exist for existing DBs (backwards-compat migration)
    for (const [enumName, val] of [['exchange_code','TADAWUL'],['currency_code','SAR'],['etf_region','LOCAL_KSA']]) {
      await pool.query(`DO $$ BEGIN ALTER TYPE ${enumName} ADD VALUE IF NOT EXISTS '${val}'; EXCEPTION WHEN others THEN NULL; END $$`);
    }
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

    console.log('âœ… ETF / instrument tables ready');

    // New columns (safe â€” IF NOT EXISTS syntax; errors caught so lock_timeout doesn't abort init)
    try { await pool.query('ALTER TABLE user_positions ADD COLUMN IF NOT EXISTS quantity INTEGER DEFAULT 1'); } catch(_) {}
    try { await pool.query('ALTER TABLE evaluations    ADD COLUMN IF NOT EXISTS horizon_days INTEGER DEFAULT 5'); } catch(_) {}

    // KSA multi-market columns
    try { await pool.query("ALTER TABLE prices ADD COLUMN IF NOT EXISTS market_id TEXT"); } catch(_) {}
    try { await pool.query("ALTER TABLE consensus_results ADD COLUMN IF NOT EXISTS signal_date DATE"); } catch(_) {}

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

    // scored_signals â€” Universal Investor Scoring
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

    // signal_ic_log â€” Information Coefficient monitoring (Spearman rank IC per symbol)
    await pool.query(`
      CREATE TABLE IF NOT EXISTS signal_ic_log (
        id            SERIAL PRIMARY KEY,
        computed_at   TIMESTAMP NOT NULL DEFAULT NOW(),
        window_days   INTEGER NOT NULL,
        symbol        TEXT,
        ic_value      REAL NOT NULL,
        sample_size   INTEGER NOT NULL
      )
    `);
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_ic_log_date   ON signal_ic_log(computed_at DESC)');
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_ic_log_symbol ON signal_ic_log(symbol)');

    // agent_weights_log â€” audit trail for softmax dynamic agent weights
    await pool.query(`
      CREATE TABLE IF NOT EXISTS agent_weights_log (
        id          SERIAL PRIMARY KEY,
        agent_name  TEXT NOT NULL,
        weight      REAL NOT NULL,
        accuracy    REAL,
        sample_size INTEGER NOT NULL DEFAULT 0,
        computed_at TIMESTAMP NOT NULL DEFAULT NOW()
      )
    `);
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_agent_weights_log_date ON agent_weights_log(computed_at DESC)');

    // confidence_score on predictions (consensus confidence)
    await safeDDL(pool, 'ALTER TABLE predictions ADD COLUMN IF NOT EXISTS confidence_score REAL');

    // Calibrated evaluation metrics on evaluations table
    await safeDDL(pool, 'ALTER TABLE evaluations ADD COLUMN IF NOT EXISTS magnitude_score REAL');
    await safeDDL(pool, 'ALTER TABLE evaluations ADD COLUMN IF NOT EXISTS calibration_score REAL');
    await safeDDL(pool, 'ALTER TABLE evaluations ADD COLUMN IF NOT EXISTS signal_strength REAL');
    await safeDDL(pool, 'ALTER TABLE evaluations ADD COLUMN IF NOT EXISTS actual_return REAL');

    // macro_indicators â€” cached KSA macro data (SAMA rate, USD/SAR, CPI, GDP)
    await pool.query(`
      CREATE TABLE IF NOT EXISTS macro_indicators (
        id          SERIAL PRIMARY KEY,
        indicator   TEXT NOT NULL,
        value       REAL NOT NULL,
        period      TEXT NOT NULL,
        source      TEXT NOT NULL,
        fetched_at  TIMESTAMP DEFAULT NOW()
      )
    `);
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_macro_indicator ON macro_indicators(indicator, fetched_at DESC)');

    // job_locks â€” advisory locking to prevent concurrent pipeline steps
    await pool.query(`
      CREATE TABLE IF NOT EXISTS job_locks (
        job_name    TEXT PRIMARY KEY,
        locked_at   TIMESTAMP NOT NULL DEFAULT NOW(),
        expires_at  TIMESTAMP NOT NULL
      )
    `);

    console.log('âœ… New tables (alerts, fx_history, signal_evals, scored_signals, signal_ic_log, agent_weights_log, job_locks) ready');

    // Seed KSA stocks (Tadawul) â€” disable statement_timeout for INSERT
    await pool.query("SET statement_timeout = 0");
    console.log('á¼³1 Seeding KSA stocks...');
    await pool.query(`
      INSERT INTO egx30_stocks (symbol, name_en, name_ar, sector_en, sector_ar) VALUES
      ('1010.SR', 'Riyad Bank', 'Ø¨Ù†Ùƒ Ø§Ù„Ø±ÙŠØ§Ø¶', 'Banking', 'Ø§Ù„Ø¨Ù†ÙˆÙƒ'),
      ('1020.SR', 'Bank Aljazira', 'Ø¨Ù†Ùƒ Ø§Ù„Ø¬Ø²ÙŠØ±Ø©', 'Banking', 'Ø§Ù„Ø¨Ù†ÙˆÙƒ'),
      ('1030.SR', 'Saudi Investment Bank', 'Ø§Ù„Ø¨Ù†Ùƒ Ø§Ù„Ø³Ø¹ÙˆØ¯ÙŠ Ù„Ù„Ø§Ø³ØªØ«Ù…Ø§Ø±', 'Banking', 'Ø§Ù„Ø¨Ù†ÙˆÙƒ'),
      ('1050.SR', 'Banque Saudi Fransi', 'Ø¨Ù†Ùƒ Ø§Ù„Ø¨Ù„Ø§Ø¯ Ø§Ù„ÙØ±Ù†Ø³ÙŠ', 'Banking', 'Ø§Ù„Ø¨Ù†ÙˆÙƒ'),
      ('1060.SR', 'Saudi Awwal Bank', 'Ø§Ù„Ø¨Ù†Ùƒ Ø§Ù„Ø³Ø¹ÙˆØ¯ÙŠ Ø§Ù„Ø£ÙˆÙ„', 'Banking', 'Ø§Ù„Ø¨Ù†ÙˆÙƒ'),
      ('1080.SR', 'Arab National Bank', 'Ø§Ù„Ø¨Ù†Ùƒ Ø§Ù„Ø¹Ø±Ø¨ÙŠ Ø§Ù„ÙˆØ·Ù†ÙŠ', 'Banking', 'Ø§Ù„Ø¨Ù†ÙˆÙƒ'),
      ('1120.SR', 'Al Rajhi Bank', 'Ù…ØµØ±Ù Ø§Ù„Ø±Ø§Ø¬Ø­ÙŠ', 'Banking', 'Ø§Ù„Ø¨Ù†ÙˆÙƒ'),
      ('1140.SR', 'Bank Albilad', 'Ø¨Ù†Ùƒ Ø§Ù„Ø¨Ù„Ø§Ø¯', 'Banking', 'Ø§Ù„Ø¨Ù†ÙˆÙƒ'),
      ('1150.SR', 'Alinma Bank', 'Ù…ØµØ±Ù Ø§Ù„Ø¥Ù†Ù…Ø§Ø¡', 'Banking', 'Ø§Ù„Ø¨Ù†ÙˆÙƒ'),
      ('1180.SR', 'Saudi National Bank', 'Ø§Ù„Ø¨Ù†Ùƒ Ø§Ù„Ø£Ù‡Ù„ÙŠ Ø§Ù„Ø³Ø¹ÙˆØ¯ÙŠ', 'Banking', 'Ø§Ù„Ø¨Ù†ÙˆÙƒ'),
      ('1211.SR', 'Maaden', 'Ù…Ø¹Ø§Ø¯Ù†', 'Materials', 'Ø§Ù„Ù…ÙˆØ§Ø¯'),
      ('1810.SR', 'Seera Group', 'Ù…Ø¬Ù…ÙˆØ¹Ø© Ø³ÙŠØ±Ø§', 'Consumer Discretionary', 'Ø§Ù„Ø³Ù„Ø¹ Ø§Ù„Ø§Ø³ØªÙ‡Ù„Ø§ÙƒÙŠØ© Ø§Ù„ÙƒÙ…Ø§Ù„ÙŠØ©'),
      ('2010.SR', 'SABIC', 'Ø³Ø§Ø¨Ùƒ', 'Materials', 'Ø§Ù„Ù…ÙˆØ§Ø¯'),
      ('2020.SR', 'SABIC Agri-Nutrients', 'Ø³Ø§Ø¨Ùƒ Ù„Ù„Ù…ØºØ°ÙŠØ§Øª Ø§Ù„Ø²Ø±Ø§Ø¹ÙŠØ©', 'Materials', 'Ø§Ù„Ù…ÙˆØ§Ø¯'),
      ('2060.SR', 'National Industrialization', 'Ø§Ù„ØªØµÙ†ÙŠØ¹ Ø§Ù„ÙˆØ·Ù†ÙŠØ©', 'Industrials', 'Ø§Ù„ØµÙ†Ø§Ø¹Ø©'),
      ('2082.SR', 'ACWA Power', 'Ø£ÙƒÙˆØ§ Ø¨Ø§ÙˆØ±', 'Utilities', 'Ø§Ù„Ù…Ø±Ø§ÙÙ‚'),
      ('2222.SR', 'Saudi Aramco', 'Ø£Ø±Ø§Ù…ÙƒÙˆ Ø§Ù„Ø³Ø¹ÙˆØ¯ÙŠØ©', 'Energy', 'Ø§Ù„Ø·Ø§Ù‚Ø©'),
      ('2280.SR', 'Almarai', 'Ø§Ù„Ù…Ø±Ø§Ø¹ÙŠ', 'Consumer Staples', 'Ø§Ù„Ø³Ù„Ø¹ Ø§Ù„Ø§Ø³ØªÙ‡Ù„Ø§ÙƒÙŠØ© Ø§Ù„Ø£Ø³Ø§Ø³ÙŠØ©'),
      ('2290.SR', 'Yanbu National Petrochemical', 'ÙŠÙ†Ø¨Ø¹ Ù„Ù„Ø¨ØªØ±ÙˆÙƒÙŠÙ…Ø§ÙˆÙŠØ§Øª', 'Materials', 'Ø§Ù„Ù…ÙˆØ§Ø¯'),
      ('2310.SR', 'Sahara International Petrochemical', 'ØµØ­Ø§Ø±Ù‰ Ø§Ù„Ø¯ÙˆÙ„ÙŠØ© Ù„Ù„Ø¨ØªØ±ÙˆÙƒÙŠÙ…Ø§ÙˆÙŠØ§Øª', 'Materials', 'Ø§Ù„Ù…ÙˆØ§Ø¯'),
      ('2330.SR', 'Advanced Petrochemical', 'Ø§Ù„Ù…ØªÙ‚Ø¯Ù…Ø© Ù„Ù„Ø¨ØªØ±ÙˆÙƒÙŠÙ…Ø§ÙˆÙŠØ§Øª', 'Materials', 'Ø§Ù„Ù…ÙˆØ§Ø¯'),
      ('2350.SR', 'Saudi Kayan Petrochemical', 'ÙƒÙŠØ§Ù† Ø§Ù„Ø³Ø¹ÙˆØ¯ÙŠØ© Ù„Ù„Ø¨ØªØ±ÙˆÙƒÙŠÙ…Ø§ÙˆÙŠØ§Øª', 'Materials', 'Ø§Ù„Ù…ÙˆØ§Ø¯'),
      ('2380.SR', 'Petro Rabigh', 'Ø¨ØªØ±Ùˆ Ø±Ø§Ø¨Øº', 'Materials', 'Ø§Ù„Ù…ÙˆØ§Ø¯'),
      ('3030.SR', 'Saudi Cement', 'Ø£Ø³Ù…Ù†Øª Ø§Ù„Ø³Ø¹ÙˆØ¯ÙŠØ©', 'Materials', 'Ø§Ù„Ù…ÙˆØ§Ø¯'),
      ('3040.SR', 'Qassim Cement', 'Ø£Ø³Ù…Ù†Øª Ø§Ù„Ù‚ØµÙŠÙ…', 'Materials', 'Ø§Ù„Ù…ÙˆØ§Ø¯'),
      ('3050.SR', 'Southern Province Cement', 'Ø£Ø³Ù…Ù†Øª Ø§Ù„Ù…Ù†Ø·Ù‚Ø© Ø§Ù„Ø¬Ù†ÙˆØ¨ÙŠØ©', 'Materials', 'Ø§Ù„Ù…ÙˆØ§Ø¯'),
      ('3060.SR', 'Yanbu Cement', 'Ø£Ø³Ù…Ù†Øª ÙŠÙ†Ø¨Ø¹', 'Materials', 'Ø§Ù„Ù…ÙˆØ§Ø¯'),
      ('3080.SR', 'Eastern Province Cement', 'Ø£Ø³Ù…Ù†Øª Ø§Ù„Ù…Ù†Ø·Ù‚Ø© Ø§Ù„Ø´Ø±Ù‚ÙŠØ©', 'Materials', 'Ø§Ù„Ù…ÙˆØ§Ø¯'),
      ('3090.SR', 'Tabuk Cement', 'Ø£Ø³Ù…Ù†Øª ØªØ¨ÙˆÙƒ', 'Materials', 'Ø§Ù„Ù…ÙˆØ§Ø¯'),
      ('4002.SR', 'Mouwasat Medical', 'Ø§Ù„Ù…ÙˆØ³Ù‰ Ø§Ù„Ø·Ø¨ÙŠØ©', 'Healthcare', 'Ø§Ù„Ø±Ø¹Ø§ÙŠØ© Ø§Ù„ØµØ­ÙŠØ©'),
      ('4003.SR', 'United Electronics', 'Ø§Ù„ÙŠÙƒØªØ±ÙˆÙ†ÙŠØ§Øª Ø§Ù„Ù…ØªØ­Ø¯Ø©', 'Consumer Discretionary', 'Ø§Ù„Ø³Ù„Ø¹ Ø§Ù„Ø§Ø³ØªÙ‡Ù„Ø§ÙƒÙŠØ© Ø§Ù„ÙƒÙ…Ø§Ù„ÙŠØ©'),
      ('4004.SR', 'Dallah Healthcare', 'Ø¯Ù„Ù‡ Ø§Ù„ØµØ­ÙŠØ©', 'Healthcare', 'Ø§Ù„Ø±Ø¹Ø§ÙŠØ© Ø§Ù„ØµØ­ÙŠØ©'),
      ('4013.SR', 'Dr. Sulaiman Al Habib', 'Ù…Ø¬Ù…ÙˆØ¹Ø© Ø¯. Ø³Ù„ÙŠÙ…Ø§Ù† Ø§Ù„Ø­Ø¨ÙŠØ¨', 'Healthcare', 'Ø§Ù„Ø±Ø¹Ø§ÙŠØ© Ø§Ù„ØµØ­ÙŠØ©'),
      ('4190.SR', 'Jarir Marketing', 'Ø¬Ø±ÙŠØ± Ù„Ù„ØªØ³ÙˆÙŠÙ‚', 'Consumer Discretionary', 'Ø§Ù„Ø³Ù„Ø¹ Ø§Ù„Ø§Ø³ØªÙ‡Ù„Ø§ÙƒÙŠØ© Ø§Ù„ÙƒÙ…Ø§Ù„ÙŠØ©'),
      ('4300.SR', 'Dar Al Arkan', 'Ø¯Ø§Ø± Ø§Ù„Ø£Ø±ÙƒØ§Ù†', 'Real Estate', 'Ø§Ù„Ø¹Ù‚Ø§Ø±Ø§Øª'),
      ('4321.SR', 'Cenomi Centers', 'Ø³ÙŠÙ†ÙˆÙ…ÙŠ Ø³Ù†ØªØ±Ø²', 'Real Estate', 'Ø§Ù„Ø¹Ù‚Ø§Ø±Ø§Øª'),
      ('4323.SR', 'Sumou Real Estate', 'Ø³Ù…Ùˆ Ø§Ù„Ø¹Ù‚Ø§Ø±ÙŠØ©', 'Real Estate', 'Ø§Ù„Ø¹Ù‚Ø§Ø±Ø§Øª'),
      ('5110.SR', 'Saudi Electricity', 'Ø§Ù„ÙƒÙ‡Ø±Ø¨Ø§Ø¡ Ø§Ù„Ø³Ø¹ÙˆØ¯ÙŠØ©', 'Utilities', 'Ø§Ù„Ù…Ø±Ø§ÙÙ‚'),
      ('7010.SR', 'stc', 'Ø§Ù„Ø§ØªØµØ§Ù„Ø§Øª Ø§Ù„Ø³Ø¹ÙˆØ¯ÙŠØ©', 'Telecommunications', 'Ø§Ù„Ø§ØªØµØ§Ù„Ø§Øª'),
      ('7202.SR', 'solutions by stc', 'Ø³Ù„ÙˆØ´Ù†Ø² Ø¨ÙŠ Ø¥Ø³ ØªÙŠ Ø³ÙŠ', 'Technology', 'Ø§Ù„ØªÙƒÙ†ÙˆÙ„ÙˆØ¬ÙŠØ§'),
      ('7203.SR', 'Elm', 'Ø¥Ù„Ù…', 'Technology', 'Ø§Ù„ØªÙƒÙ†ÙˆÙ„ÙˆØ¬ÙŠØ§')
      ON CONFLICT (symbol) DO UPDATE SET
        name_en = EXCLUDED.name_en,
        name_ar = EXCLUDED.name_ar,
        sector_en = EXCLUDED.sector_en,
        sector_ar = EXCLUDED.sector_ar,
        is_active = TRUE,
        updated_at = CURRENT_TIMESTAMP
    `);
    console.log('âœ… KSA stocks seeded');

    // Re-enable statement_timeout for index creation (30s per index)
    await pool.query("SET statement_timeout = '30s'");

    // Create indexes
    console.log('ðŸ“Š Creating indexes...');
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_prices_symbol_date ON prices(symbol, date)');
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_news_symbol_date ON news(symbol, date)');
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_predictions_symbol ON predictions(symbol, prediction_date)');
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_predictions_date ON predictions(prediction_date)');
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_consensus_symbol ON consensus_results(symbol, prediction_date)');
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_consensus_date ON consensus_results(prediction_date)');
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_users_email_lower ON users(email_lower)');
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_watchlist_user ON user_watchlist(user_id)');

    // Migration (legacy EGX): reclassify commodity funds from 'ETF' â†’ 'COMMODITY_ETP'
    // Kept for backwards compat; uses exchange='EGX' filter, no-op on KSA-only DBs
    try {
      const res = await pool.query(`UPDATE instrument SET type = 'COMMODITY_ETP' WHERE exchange = 'EGX' AND issuer = 'COMMODITY' AND type = 'ETF'`);
      if (res.rowCount > 0) console.log(`âœ… Reclassified ${res.rowCount} EGX commodity fund(s) â†’ COMMODITY_ETP`);
    } catch(e) { console.log('âš ï¸  Commodity ETP migration skipped:', e.message); }

    console.log('âœ… Database initialized successfully!');

    // Get stats
    const statsQueries = {
      totalPrices: 'SELECT COUNT(*) as count FROM prices',
      totalPredictions: 'SELECT COUNT(*) as count FROM predictions',
      stocksTracked: 'SELECT COUNT(DISTINCT symbol) as count FROM prices',
    };

    console.log('\nðŸ“Š Database Statistics:');
    for (const [key, query] of Object.entries(statsQueries)) {
      const result = await pool.query(query);
      console.log(`   ${key}: ${result.rows[0].count}`);
    }

  } catch (error) {
    console.error('âŒ Database initialization failed:', error);
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
