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
    await safeCreateIndex(pool, 'CREATE INDEX IF NOT EXISTS idx_consensus_ksa ON consensus_results(market_id, symbol, date DESC)');

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
