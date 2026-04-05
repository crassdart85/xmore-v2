'use strict';
console.log('=== INIT-DB-KSA.JS STARTING ===');

const { Pool } = require('pg');

const DATABASE_URL = process.env.DATABASE_URL;
console.log('DATABASE_URL exists:', !!DATABASE_URL);

if (!DATABASE_URL) {
  console.log('⚠️  No DATABASE_URL found. Skipping database initialization.');
  process.exit(0);
}

const TIMEOUT_MS = 600000;
const timeoutId = setTimeout(() => {
  console.error('❌ Database initialization timed out after 600 seconds');
  process.exit(1);
}, TIMEOUT_MS);
timeoutId.unref();

const pool = new Pool({
  connectionString: DATABASE_URL,
  ssl: { rejectUnauthorized: false },
  connectionTimeoutMillis: 10000,
  idleTimeoutMillis: 30000,
  max: 1,
});

async function safeCreateIndex(db, sql) {
  try {
    await db.query('BEGIN');
    await db.query("SET LOCAL lock_timeout = '5s'");
    await db.query('SET LOCAL statement_timeout = 0');
    await db.query(sql);
    await db.query('COMMIT');
  } catch (e) {
    try { await db.query('ROLLBACK'); } catch (_) {}
    console.warn(`⚠️  DDL skipped: ${e.message.split('\n')[0]}`);
  }
}

async function safeExec(db, sql) {
  try {
    await db.query('BEGIN');
    await db.query("SET LOCAL lock_timeout = '5s'");
    await db.query('SET LOCAL statement_timeout = 0');
    await db.query(sql);
    await db.query('COMMIT');
  } catch (e) {
    try { await db.query('ROLLBACK'); } catch (_) {}
    console.warn(`âš ï¸  DDL skipped: ${e.message.split('\n')[0]}`);
  }
}

async function initializeDatabase() {
  console.log('🔧 Initializing KSA PostgreSQL database (Tadawul)...');

  try {
    await pool.query('SELECT 1');
    console.log('✅ Connected to PostgreSQL');

    await pool.query("SET lock_timeout = '5s'");
    await pool.query("SET statement_timeout = '0'");

    // ── KSA Stocks table ──────────────────────────────────────────────────
    console.log('📊 Creating ksa_stocks table...');
    await pool.query(`
      CREATE TABLE IF NOT EXISTS ksa_stocks (
        id         SERIAL PRIMARY KEY,
        symbol     TEXT NOT NULL UNIQUE,
        name_en    TEXT NOT NULL,
        name_ar    TEXT,
        sector_en  TEXT,
        sector_ar  TEXT,
        market_id  TEXT NOT NULL DEFAULT 'KSA',
        created_at TIMESTAMPTZ DEFAULT NOW()
      )
    `);
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_ksa_stocks_symbol ON ksa_stocks(symbol)');
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_ksa_stocks_sector ON ksa_stocks(sector_en)');

    // ── Shared tables (market_id partitioned) ────────────────────────────
    console.log('📋 Creating shared signal/news tables...');

    await pool.query(`
      CREATE TABLE IF NOT EXISTS trade_recommendations (
        id                  SERIAL PRIMARY KEY,
        symbol              TEXT NOT NULL,
        recommendation_date DATE NOT NULL,
        target_date         DATE,
        signal_type         TEXT,
        confidence          NUMERIC(5,2),
        xmore_score         NUMERIC(6,2),
        bull_score          NUMERIC(6,2),
        bear_score          NUMERIC(6,2),
        notes               TEXT,
        was_correct         BOOLEAN,
        actual_outcome      TEXT,
        alpha_1d            NUMERIC(10,6),
        is_simulated        BOOLEAN DEFAULT FALSE,
        market_id           TEXT DEFAULT 'KSA',
        created_at          TIMESTAMPTZ DEFAULT NOW()
      )
    `);
    await safeExec(pool, `ALTER TABLE trade_recommendations ADD COLUMN IF NOT EXISTS market_id TEXT DEFAULT 'KSA'`);
    await safeExec(pool, `ALTER TABLE trade_recommendations ADD COLUMN IF NOT EXISTS signal_type TEXT`);
    await safeExec(pool, `ALTER TABLE trade_recommendations ADD COLUMN IF NOT EXISTS xmore_score REAL`);
    await safeExec(pool, `ALTER TABLE trade_recommendations ADD COLUMN IF NOT EXISTS notes TEXT`);
    await safeExec(pool, `ALTER TABLE trade_recommendations ADD COLUMN IF NOT EXISTS actual_next_day_return REAL`);
    await safeExec(pool, `ALTER TABLE trade_recommendations ADD COLUMN IF NOT EXISTS benchmark_1d_return REAL`);
    await safeExec(pool, `ALTER TABLE trade_recommendations ADD COLUMN IF NOT EXISTS alpha_1d REAL`);
    await safeExec(pool, `ALTER TABLE trade_recommendations ADD COLUMN IF NOT EXISTS was_correct BOOLEAN`);
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_tr_ksa_symbol ON trade_recommendations(symbol, recommendation_date DESC)');
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_tr_ksa_market ON trade_recommendations(market_id, recommendation_date DESC)');

    await pool.query(`
      CREATE TABLE IF NOT EXISTS signals (
        id          SERIAL PRIMARY KEY,
        symbol      TEXT NOT NULL,
        date        DATE NOT NULL,
        agent_name  TEXT NOT NULL,
        prediction  TEXT,
        confidence  NUMERIC(5,2),
        reasoning   JSONB,
        market_id   TEXT DEFAULT 'KSA',
        created_at  TIMESTAMPTZ DEFAULT NOW()
      )
    `);
    await safeExec(pool, `ALTER TABLE signals ADD COLUMN IF NOT EXISTS market_id TEXT DEFAULT 'KSA'`);
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_signals_ksa ON signals(market_id, symbol, date DESC)');

    await pool.query(`
      CREATE TABLE IF NOT EXISTS consensus_results (
        id               SERIAL PRIMARY KEY,
        symbol           TEXT NOT NULL,
        date             DATE NOT NULL,
        final_signal     TEXT,
        confidence       NUMERIC(5,2),
        xmore_score      NUMERIC(6,2),
        bull_score       NUMERIC(6,2),
        bear_score       NUMERIC(6,2),
        agent_signals    JSONB,
        regime_label     TEXT,
        market_id        TEXT DEFAULT 'KSA',
        created_at       TIMESTAMPTZ DEFAULT NOW()
      )
    `);
    await safeExec(pool, `ALTER TABLE consensus_results ADD COLUMN IF NOT EXISTS market_id TEXT DEFAULT 'KSA'`);
    await safeExec(pool, `ALTER TABLE consensus_results ADD COLUMN IF NOT EXISTS prediction_date DATE`);
    await safeExec(pool, `ALTER TABLE consensus_results ADD COLUMN IF NOT EXISTS conviction TEXT`);
    await safeExec(pool, `ALTER TABLE consensus_results ADD COLUMN IF NOT EXISTS signal_count INTEGER`);
    // Back-fill prediction_date from date for existing rows
    await safeExec(pool, `UPDATE consensus_results SET prediction_date = date WHERE prediction_date IS NULL`);
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_consensus_ksa ON consensus_results(market_id, symbol, date DESC)');
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_consensus_pred ON consensus_results(market_id, symbol, prediction_date DESC)');

    await pool.query(`
      CREATE TABLE IF NOT EXISTS news (
        id               SERIAL PRIMARY KEY,
        title            TEXT NOT NULL,
        date             TIMESTAMPTZ,
        source           TEXT,
        url              TEXT,
        sentiment_score  NUMERIC(5,4),
        ticker_mentions  JSONB,
        direction        TEXT,
        post_type        TEXT,
        channel_weight   NUMERIC(4,2),
        market_id        TEXT DEFAULT 'KSA',
        created_at       TIMESTAMPTZ DEFAULT NOW()
      )
    `);
    await safeExec(pool, `ALTER TABLE news ADD COLUMN IF NOT EXISTS market_id TEXT DEFAULT 'KSA'`);
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_news_ksa ON news(market_id, date DESC)');

    await pool.query(`
      CREATE TABLE IF NOT EXISTS regime_log (
        id               SERIAL PRIMARY KEY,
        date             DATE NOT NULL,
        regime_label_en  TEXT,
        regime_label_ar  TEXT,
        regime_confidence NUMERIC(5,4),
        current_regime   INTEGER,
        n_regimes        INTEGER,
        market_id        TEXT DEFAULT 'KSA',
        created_at       TIMESTAMPTZ DEFAULT NOW()
      )
    `);
    await safeExec(pool, `ALTER TABLE regime_log ADD COLUMN IF NOT EXISTS market_id TEXT DEFAULT 'KSA'`);
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_regime_ksa ON regime_log(market_id, date DESC)');

    await pool.query(`
      CREATE TABLE IF NOT EXISTS agent_performance_daily (
        id          SERIAL PRIMARY KEY,
        date        DATE NOT NULL,
        agent_name  TEXT NOT NULL,
        win_rate    NUMERIC(5,4),
        alpha       NUMERIC(10,6),
        total       INTEGER,
        market_id   TEXT DEFAULT 'KSA',
        UNIQUE(date, agent_name, market_id)
      )
    `);
    await safeExec(pool, `ALTER TABLE agent_performance_daily ADD COLUMN IF NOT EXISTS market_id TEXT DEFAULT 'KSA'`);

    // ── KSA-specific tables ───────────────────────────────────────────────
    console.log('📋 Creating KSA-specific tables...');

    await pool.query(`
      CREATE TABLE IF NOT EXISTS ksa_dcf_valuations (
        id                  SERIAL PRIMARY KEY,
        ticker              TEXT NOT NULL,
        valuation_date      DATE NOT NULL,
        wacc                NUMERIC(6,4),
        terminal_growth     NUMERIC(6,4),
        fair_value_base     NUMERIC(18,4),
        fair_value_bull     NUMERIC(18,4),
        fair_value_bear     NUMERIC(18,4),
        composite_value     NUMERIC(18,4),
        composite_upside_pct NUMERIC(8,4),
        valuation_label     TEXT,
        confidence          NUMERIC(5,4),
        notes               TEXT,
        market_id           TEXT DEFAULT 'KSA',
        created_at          TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(ticker, valuation_date)
      )
    `);
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_dcf_ticker ON ksa_dcf_valuations(ticker, valuation_date DESC)');
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_dcf_label  ON ksa_dcf_valuations(valuation_label)');

    await pool.query(`
      CREATE TABLE IF NOT EXISTS ksa_company_fundamentals (
        id               SERIAL PRIMARY KEY,
        ticker           TEXT NOT NULL,
        fetched_date     DATE NOT NULL,
        pe_ratio         NUMERIC(10,4),
        pb_ratio         NUMERIC(10,4),
        roe              NUMERIC(8,4),
        debt_equity      NUMERIC(10,4),
        dividend_yield   NUMERIC(8,6),
        payout_ratio     NUMERIC(8,4),
        free_cash_flow   NUMERIC(24,2),
        revenue_growth   NUMERIC(8,4),
        eps              NUMERIC(12,4),
        dps              NUMERIC(12,4),
        near_52w_high    BOOLEAN DEFAULT FALSE,
        near_52w_low     BOOLEAN DEFAULT FALSE,
        value_flag       BOOLEAN DEFAULT FALSE,
        momentum_flag    BOOLEAN DEFAULT FALSE,
        shariah_compliant BOOLEAN,
        is_banking       BOOLEAN DEFAULT FALSE,
        market_id        TEXT DEFAULT 'KSA',
        updated_at       TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(ticker, fetched_date)
      )
    `);
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_fundamentals_ticker ON ksa_company_fundamentals(ticker, fetched_date DESC)');

    await pool.query(`
      CREATE TABLE IF NOT EXISTS ksa_material_events (
        id           SERIAL PRIMARY KEY,
        ticker       TEXT NOT NULL,
        market_id    TEXT DEFAULT 'KSA',
        event_type   TEXT,
        event_date   TIMESTAMPTZ,
        headline     TEXT,
        source       TEXT,
        is_material  BOOLEAN DEFAULT FALSE,
        classification TEXT,
        created_at   TIMESTAMPTZ DEFAULT NOW()
      )
    `);
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_events_ticker ON ksa_material_events(ticker, event_date DESC)');

    await pool.query(`
      CREATE TABLE IF NOT EXISTS price_alerts (
        id           SERIAL PRIMARY KEY,
        user_id      INTEGER NOT NULL,
        symbol       TEXT NOT NULL,
        condition    TEXT NOT NULL CHECK (condition IN ('above','below')),
        target_price NUMERIC(18,4) NOT NULL,
        active       BOOLEAN DEFAULT TRUE,
        triggered_at TIMESTAMPTZ,
        created_at   TIMESTAMPTZ DEFAULT NOW()
      )
    `);
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_alerts_user ON price_alerts(user_id, active)');
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_alerts_symbol ON price_alerts(symbol, active)');

    await pool.query(`
      CREATE TABLE IF NOT EXISTS system_config (
        key        TEXT PRIMARY KEY,
        value      TEXT,
        updated_at TIMESTAMPTZ DEFAULT NOW()
      )
    `);

    await pool.query(`
      CREATE TABLE IF NOT EXISTS prices (
        id        SERIAL PRIMARY KEY,
        symbol    TEXT NOT NULL,
        date      DATE NOT NULL,
        open      NUMERIC(18,4),
        high      NUMERIC(18,4),
        low       NUMERIC(18,4),
        close     NUMERIC(18,4),
        volume    BIGINT,
        market_id TEXT DEFAULT 'KSA',
        UNIQUE(symbol, date)
      )
    `);
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_prices_ksa ON prices(symbol, date DESC)');

    // ── Seed Tadawul stocks ───────────────────────────────────────────────
    console.log('🌱 Seeding Tadawul (KSA) stocks...');
    await pool.query(`
      INSERT INTO ksa_stocks (symbol, name_en, name_ar, sector_en, sector_ar, market_id) VALUES
        ('1180.SR', 'Al Rajhi Bank', 'مصرف الراجحي', 'Banking', 'البنوك', 'KSA'),
        ('1120.SR', 'Al Jazira Bank', 'بنك الجزيرة', 'Banking', 'البنوك', 'KSA'),
        ('1140.SR', 'Al Bilad Bank', 'بنك البلاد', 'Banking', 'البنوك', 'KSA'),
        ('1010.SR', 'Riyad Bank', 'بنك الرياض', 'Banking', 'البنوك', 'KSA'),
        ('1020.SR', 'Bank AlJazira', 'بنك الجزيرة', 'Banking', 'البنوك', 'KSA'),
        ('1030.SR', 'Saudi Investment Bank', 'البنك السعودي للاستثمار', 'Banking', 'البنوك', 'KSA'),
        ('1050.SR', 'Banque Saudi Fransi', 'بنك ساب السعودي الفرنسي', 'Banking', 'البنوك', 'KSA'),
        ('1060.SR', 'Saudi Arabian British Bank', 'البنك السعودي البريطاني', 'Banking', 'البنوك', 'KSA'),
        ('1080.SR', 'Arab National Bank', 'البنك العربي الوطني', 'Banking', 'البنوك', 'KSA'),
        ('1150.SR', 'Alinma Bank', 'مصرف الإنماء', 'Banking', 'البنوك', 'KSA'),
        ('1160.SR', 'Al-Rajhi Takaful', 'الراجحي للتكافل', 'Insurance', 'التأمين', 'KSA'),
        ('1170.SR', 'Saudi National Bank', 'البنك الأهلي السعودي', 'Banking', 'البنوك', 'KSA'),
        ('2222.SR', 'Saudi Aramco', 'أرامكو السعودية', 'Energy', 'الطاقة', 'KSA'),
        ('2010.SR', 'SABIC', 'سابك', 'Petrochemicals', 'البتروكيماويات', 'KSA'),
        ('2020.SR', 'Saudi Industrial Investment', 'الاستثمار الصناعي السعودي', 'Petrochemicals', 'البتروكيماويات', 'KSA'),
        ('2030.SR', 'SAFCO', 'سافكو', 'Petrochemicals', 'البتروكيماويات', 'KSA'),
        ('2060.SR', 'Yanbu National Petrochemicals', 'ينساب', 'Petrochemicals', 'البتروكيماويات', 'KSA'),
        ('2080.SR', 'National Industrialization', 'التصنيع الوطنية', 'Petrochemicals', 'البتروكيماويات', 'KSA'),
        ('2090.SR', 'National Petrochemical', 'الوطنية للبتروكيماويات', 'Petrochemicals', 'البتروكيماويات', 'KSA'),
        ('2100.SR', 'Gulf International Services', 'الخليج الدولية للخدمات', 'Energy', 'الطاقة', 'KSA'),
        ('7010.SR', 'Saudi Telecom Company', 'شركة الاتصالات السعودية', 'Telecom', 'الاتصالات', 'KSA'),
        ('7020.SR', 'Etihad Etisalat (Mobily)', 'اتحاد اتصالات (موبايلي)', 'Telecom', 'الاتصالات', 'KSA'),
        ('7030.SR', 'Zain KSA', 'زين السعودية', 'Telecom', 'الاتصالات', 'KSA'),
        ('4003.SR', 'Extra (United Electronics)', 'إكسترا', 'Retail', 'التجزئة', 'KSA'),
        ('4050.SR', 'Savola Group', 'مجموعة صافولا', 'Food & Beverages', 'الأغذية والمشروبات', 'KSA'),
        ('4061.SR', 'Almarai', 'المراعي', 'Food & Beverages', 'الأغذية والمشروبات', 'KSA'),
        ('4001.SR', 'Aldrees Petroleum & Transport', 'الدريس للبترول', 'Retail', 'التجزئة', 'KSA'),
        ('4190.SR', 'Jarir Marketing', 'مكتبة جرير', 'Retail', 'التجزئة', 'KSA'),
        ('4240.SR', 'Fawaz Alhokair', 'فواز الحكير', 'Retail', 'التجزئة', 'KSA'),
        ('4321.SR', 'Abdullah Al Othaim Markets', 'أسواق عبدالله العثيم', 'Retail', 'التجزئة', 'KSA'),
        ('4020.SR', 'Dar Al Arkan Real Estate', 'دار الأركان', 'Real Estate', 'العقارات', 'KSA'),
        ('4040.SR', 'Saudi Real Estate', 'شركة العقارية', 'Real Estate', 'العقارات', 'KSA'),
        ('4100.SR', 'Emaar The Economic City', 'إعمار المدينة الاقتصادية', 'Real Estate', 'العقارات', 'KSA'),
        ('4150.SR', 'Taiba Investments', 'طيبة للاستثمار', 'Real Estate', 'العقارات', 'KSA'),
        ('2110.SR', 'Saudi Steel Pipe', 'الأنابيب السعودية للصلب', 'Materials', 'المواد', 'KSA'),
        ('2120.SR', 'Astra Industrial Group', 'مجموعة أسترا الصناعية', 'Industrials', 'الصناعات', 'KSA'),
        ('2130.SR', 'Saudi Ceramics', 'السيراميك السعودي', 'Building Materials', 'مواد البناء', 'KSA'),
        ('2140.SR', 'Al Hassan Ghazi Ibrahim Shaker', 'شركة شاكر', 'Industrials', 'الصناعات', 'KSA'),
        ('2150.SR', 'Saudi Printing & Packaging', 'الطباعة والتغليف السعودية', 'Industrials', 'الصناعات', 'KSA'),
        ('3001.SR', 'Cement - Yamama', 'يمامة للإسمنت', 'Building Materials', 'مواد البناء', 'KSA'),
        ('3002.SR', 'Saudi Cement', 'الإسمنت السعودية', 'Building Materials', 'مواد البناء', 'KSA'),
        ('3003.SR', 'Qassim Cement', 'إسمنت القصيم', 'Building Materials', 'مواد البناء', 'KSA'),
        ('4002.SR', 'Dallah Healthcare', 'دله الصحية', 'Healthcare', 'الرعاية الصحية', 'KSA'),
        ('4005.SR', 'National Medical Care', 'الرعاية الطبية الوطنية', 'Healthcare', 'الرعاية الصحية', 'KSA'),
        ('4007.SR', 'Mouwasat Medical Services', 'مواساة للخدمات الطبية', 'Healthcare', 'الرعاية الصحية', 'KSA'),
        ('4009.SR', 'Al Hammadi', 'الحمادي', 'Healthcare', 'الرعاية الصحية', 'KSA'),
        ('8010.SR', 'Tawuniya', 'التعاونية', 'Insurance', 'التأمين', 'KSA'),
        ('8020.SR', 'BUPA Arabia', 'بوبا العربية', 'Insurance', 'التأمين', 'KSA'),
        ('8030.SR', 'Medgulf', 'ميدغلف', 'Insurance', 'التأمين', 'KSA'),
        ('4030.SR', 'Saudi Airlines Catering', 'الخطوط الجوية للتموين', 'Transportation', 'النقل', 'KSA'),
        ('4031.SR', 'Bahri (National Shipping)', 'البحري', 'Transportation', 'النقل', 'KSA')
      ON CONFLICT (symbol) DO UPDATE SET
        name_en   = EXCLUDED.name_en,
        name_ar   = EXCLUDED.name_ar,
        sector_en = EXCLUDED.sector_en,
        sector_ar = EXCLUDED.sector_ar
    `);
    console.log('✅ Tadawul stocks seeded (51 companies)');

    // ── RAG / knowledge-base tables ─────────────────────────────────────────
    console.log('📚 Creating RAG knowledge-base tables...');

    await pool.query(`
      CREATE TABLE IF NOT EXISTS rag_document (
        doc_id       BIGSERIAL PRIMARY KEY,
        doc_type     TEXT NOT NULL DEFAULT 'knowledge',
        title        TEXT NOT NULL,
        publisher    TEXT,
        language     TEXT DEFAULT 'en',
        publish_date DATE,
        url          TEXT NOT NULL DEFAULT '',
        content_hash TEXT,
        storage_uri  TEXT,
        fetched_at   TIMESTAMPTZ,
        ingested_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
        market_id    TEXT DEFAULT 'KSA',
        UNIQUE(url, market_id)
      )
    `);
    await safeExec(pool, `ALTER TABLE rag_document ADD COLUMN IF NOT EXISTS market_id TEXT DEFAULT 'KSA'`);
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
    await pool.query(`
      CREATE TABLE IF NOT EXISTS rag_chunks (
        chunk_id    BIGSERIAL PRIMARY KEY,
        doc_id      BIGINT NOT NULL REFERENCES rag_document(doc_id) ON DELETE CASCADE,
        chunk_index INTEGER NOT NULL,
        chunk_text  TEXT NOT NULL,
        embedding_json TEXT,
        market_id   TEXT DEFAULT 'KSA'
      )
    `);
    await safeExec(pool, `ALTER TABLE rag_chunks ADD COLUMN IF NOT EXISTS market_id TEXT DEFAULT 'KSA'`);
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_rag_doc_market  ON rag_document(market_id)');
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_rag_chunks_doc  ON rag_chunks(doc_id)');
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_rag_job_status  ON rag_embedding_job(status)');
    // Optional pgvector — adds embedding_vec column if extension is available
    try {
      await pool.query('CREATE EXTENSION IF NOT EXISTS vector');
      await pool.query('ALTER TABLE rag_chunks ADD COLUMN IF NOT EXISTS embedding_vec vector(768)');
      await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_rag_chunks_vec ON rag_chunks USING ivfflat (embedding_vec vector_cosine_ops) WITH (lists = 100)');
      console.log('✅ pgvector extension + column ready');
    } catch (_) {
      console.log('⚠️  pgvector not available — using embedding_json fallback');
    }

    // Seed KSA knowledge-base entries (upsert on url+market_id)
    const ksaDocs = [
      { title: 'Saudi Exchange (Tadawul) Trading Rules Overview',        publisher: 'Tadawul', language: 'en', url: 'internal://ksa/tadawul-trading-rules', content_hash: 'ksa-001', content: `The Saudi Exchange (Tadawul) is the principal securities exchange in Saudi Arabia. Trading hours: 10:00–15:00 AST (UTC+3) Sunday to Thursday. The exchange is closed on Fridays and Saturdays and Saudi public holidays. The benchmark index is the Tadawul All Share Index (TASI). All securities are denominated in Saudi Riyal (SAR). Price movement limits: most equities have a daily move limit of ±10%. Settlement cycle: T+2. Short selling is permitted subject to CMA regulations. Foreign investors may hold up to 49% of most listed companies (Strategic 100% in some sectors with MISA approval). Minimum lot size: 1 share. Transaction costs include brokerage commission (~0.15–0.25%), CMA levy (0.0033%), Tadawul fee (0.0046%), plus 15% VAT on fees.` },
      { title: 'SAMA Monetary Policy & SAR Peg', publisher: 'SAMA', language: 'en', url: 'internal://ksa/sama-monetary-policy', content_hash: 'ksa-002', content: `The Saudi Central Bank (SAMA) maintains the Saudi Riyal (SAR) peg to the US Dollar at a fixed rate of 3.75 SAR per USD (established 1986). Saudi Arabia does not conduct independent monetary policy; it mirrors US Federal Reserve decisions to maintain the peg. The key SAMA policy rate (repo rate) closely tracks the US Fed Funds rate. As of 2024–2025, the SAMA repo rate is approximately 5.5–6.0%. Saudi Arabia targets low inflation (~2–3%) supported by domestic fuel and utility subsidies. The country holds the world's largest official foreign exchange reserves after China and Japan (~$450 billion). Gold reserves are modest (~323 tonnes). Saudi Arabia is the world's largest crude oil exporter and OPEC's de facto leader; oil revenues dominate the fiscal budget.` },
      { title: 'Saudi Vision 2030 & Market Structural Shifts',           publisher: 'PIF/MCI', language: 'en', url: 'internal://ksa/vision-2030-market', content_hash: 'ksa-003', content: `Saudi Vision 2030 targets reducing oil dependence: non-oil GDP contribution target 50%+ (up from ~40% in 2016). Key Vision 2030 sectors driving Tadawul listings: Tourism (NEOM, Red Sea, Diriyah), Logistics & Transport (KAEC, Riyadh Air), Healthcare & Pharma, Financial Services (fintech, insurance), Entertainment & Sports. The Public Investment Fund (PIF) is the sovereign wealth fund (~$900 billion AUM, target $2 trillion by 2030). PIF is both a direct investor and a driver of IPO activity on Tadawul. Saudi Aramco IPO (2019, 2022) at 8.5 trillion SAR market cap is the world's largest listed company. The Capital Market Authority (CMA) is the securities regulator. Tadawul introduced the Parallel Market (Nomu) for SME listings with lighter regulations.` },
      { title: 'Tadawul Sector Breakdown & Key Stocks',                  publisher: 'Tadawul', language: 'en', url: 'internal://ksa/sector-breakdown', content_hash: 'ksa-004', content: `Tadawul main sectors by market cap: Energy (2222.SR Saudi Aramco — dominates at ~80% of total market cap), Petrochemicals (2010.SR SABIC), Banking (1180.SR Al Rajhi Bank, 1170.SR SNB, 1010.SR Riyad Bank, 1050.SR Saudi Fransi, 1060.SR SABB, 1080.SR Arab National Bank, 1150.SR Alinma), Telecom (7010.SR STC, 7020.SR Mobily), Real Estate (4020.SR Dar Al Arkan, 4100.SR Emaar EC), Insurance (8010.SR Tawuniya, 8020.SR BUPA Arabia), Healthcare (4002.SR Dallah, 4005.SR NMCC, 4007.SR Mouwasat), Retail (4190.SR Jarir, 4321.SR Al Othaim), Transportation (4031.SR Bahri). Banking sector average P/E: 15–18x. Energy sector (Aramco) average P/E: 14–17x. Market P/E at TASI level: approximately 18–22x. Dividend yields: Banking 3–5%, Energy (Aramco) ~3%.` },
      { title: 'KSA Technical Analysis Context',                          publisher: 'Xmore', language: 'en', url: 'internal://ksa/technical-context', content_hash: 'ksa-005', content: `TASI (Tadawul All Share Index) base reference: ~12,000 points (2023 average). TASI 52-week range typically 10,500–13,500. Aramco (2222.SR) is the heaviest constituent (~80% weight) making TASI heavily correlated with oil prices and Saudi Aramco sentiment. Saudi banks (Al Rajhi, SNB, Riyad Bank) together contribute ~10–12% of TASI weight. Technical analysis works well on Tadawul liquid names (Aramco, Al Rajhi, SABIC, STC) with tight bid-ask spreads. Less liquid names (<1M SAR daily turnover) may exhibit false breakouts due to thin order books. ATR-based stops are effective: typical ATR for large-caps 0.5–1.5% daily, small-caps 1.5–3%. RSI overbought threshold 70, oversold 30 — same as global norms. Key support/resistance levels often align with round SAR numbers (e.g. 30 SAR, 50 SAR, 100 SAR for major stocks). Earnings seasons: quarterly, typically 1–2 weeks after quarter end. Ex-dividend dates affect price technically; dividend announcements can move stocks 2–5%.` },
      { title: 'Shariah Compliance & Islamic Finance on Tadawul',         publisher: 'CMA', language: 'en', url: 'internal://ksa/shariah-compliance', content_hash: 'ksa-006', content: `Approximately 85–90% of Tadawul-listed companies are classified as Shariah-compliant by the major Islamic screening bodies (Tadawul/Fikra, AAOIFI, S&P Shariah). Shariah-compliant status excludes: interest-bearing financial institutions (conventional banks are generally non-compliant), companies deriving >5% revenue from prohibited activities (alcohol, pork, conventional insurance, weapons). Most Saudi banks are structured as fully Islamic banks (Al Rajhi, Alinma, Bank Albilad) or dual-window (SNB, Riyad Bank). The Saudi Tadawul provides a list of Shariah-compliant equities updated semi-annually. Shariah-compliant ETFs and sukuk are actively listed. Xmore system marks is_banking=true for Saudi bank stocks; analysts should consider Islamic finance metrics (Return on Islamic Assets, Murabaha margin) rather than NIM for these.` },
    ];

    for (const doc of ksaDocs) {
      const { content, ...meta } = doc;
      await pool.query(`
        INSERT INTO rag_document (doc_type, title, publisher, language, url, content_hash, market_id, fetched_at)
        VALUES ('knowledge', $1, $2, $3, $4, $5, 'KSA', NOW())
        ON CONFLICT (url, market_id) DO NOTHING
      `, [meta.title, meta.publisher, meta.language, meta.url, meta.content_hash]);
    }
    console.log('✅ KSA RAG knowledge-base seeded (6 documents)');

    // signal_ic_log — Information Coefficient monitoring (Spearman rank IC per symbol)
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

    // ── Agent Weights Log ─────────────────────────────────────────────────
    console.log('⚖️  Creating agent_weights_log table...');
    await pool.query(`
      CREATE TABLE IF NOT EXISTS agent_weights_log (
        id SERIAL PRIMARY KEY,
        agent_name TEXT NOT NULL,
        weight REAL NOT NULL,
        accuracy REAL,
        sample_size INTEGER NOT NULL DEFAULT 0,
        computed_at TIMESTAMP NOT NULL DEFAULT NOW()
      )
    `);
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_agent_weights_log_date ON agent_weights_log(computed_at DESC)');

    // confidence_score on predictions (consensus confidence) + calibrated evaluation columns
    await safeExec(pool, 'ALTER TABLE predictions ADD COLUMN IF NOT EXISTS confidence_score REAL');
    await safeExec(pool, 'ALTER TABLE evaluations ADD COLUMN IF NOT EXISTS magnitude_score REAL');
    await safeExec(pool, 'ALTER TABLE evaluations ADD COLUMN IF NOT EXISTS calibration_score REAL');
    await safeExec(pool, 'ALTER TABLE evaluations ADD COLUMN IF NOT EXISTS signal_strength REAL');
    await safeExec(pool, 'ALTER TABLE evaluations ADD COLUMN IF NOT EXISTS actual_return REAL');

    // ── Macro Indicators ─────────────────────────────────────────────────
    console.log('🌐 Creating macro_indicators table...');
    await pool.query(`
      CREATE TABLE IF NOT EXISTS macro_indicators (
        id SERIAL PRIMARY KEY,
        indicator TEXT NOT NULL,
        value REAL NOT NULL,
        period TEXT,
        source TEXT,
        fetched_at TIMESTAMP NOT NULL DEFAULT NOW()
      )
    `);
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_macro_indicator ON macro_indicators(indicator, fetched_at DESC)');

    // ── Job Locks ────────────────────────────────────────────────────────
    console.log('🔒 Creating job_locks table...');
    await pool.query(`
      CREATE TABLE IF NOT EXISTS job_locks (
        job_name TEXT PRIMARY KEY,
        locked_at TIMESTAMP NOT NULL DEFAULT NOW(),
        expires_at TIMESTAMP NOT NULL
      )
    `);

    console.log('\n✅ KSA database initialization complete!');
    console.log('📈 Market: Saudi Exchange (Tadawul) — تداول');
    console.log('💱 Currency: SAR (Saudi Riyal)');
    console.log('📅 Trading: Sun–Thu, 10:00–15:00 AST');

  } catch (err) {
    console.error('❌ Database initialization error:', err.message);
    throw err;
  } finally {
    await pool.end();
    clearTimeout(timeoutId);
  }
}

initializeDatabase()
  .then(() => { console.log('🎉 init-db-ksa.js complete'); process.exit(0); })
  .catch(err => { console.error('💥 Fatal:', err.message); process.exit(1); });
