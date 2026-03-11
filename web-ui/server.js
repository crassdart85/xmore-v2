console.log('=== SERVER.JS STARTING ===');
const express = require('express');
const cors = require('cors');
const path = require('path');
const cookieParser = require('cookie-parser');

// Route modules
const { router: authRouter, attachDb: attachAuthDb } = require('./routes/auth');
const { router: stocksRouter, attachDb: attachStocksDb } = require('./routes/stocks');
const { router: watchlistRouter, attachDb: attachWatchlistDb } = require('./routes/watchlist');
const { router: tradesRouter, attachDb: attachTradesDb } = require('./routes/trades');
const { router: briefingRouter, attachDb: attachBriefingDb } = require('./routes/briefing');
const { router: performanceRouter, attachDb: attachPerformanceDb } = require('./routes/performance');
const { router: adminRouter, attachDb: attachAdminDb } = require('./routes/admin');
const { router: timemachineRouter, attachDb: attachTimemachineDb } = require('./routes/timemachine');
const { router: portfolioForecastsRouter, attachDb: attachPortfolioForecastsDb } = require('./routes/portfolioForecasts');
const { router: ragRouter, attachDb: attachRagDb } = require('./routes/rag');
const { router: etfRouter, attachDb: attachEtfDb } = require('./routes/etf');

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
const corsAllowedOrigins = (process.env.CORS_ALLOWED_ORIGINS || '')
  .split(',')
  .map(s => s.trim())
  .filter(Boolean);
app.use(cors({
  origin: (origin, cb) => {
    // No origin header (server-to-server, same-origin GET, etc.) — always allow
    if (!origin) return cb(null, true);
    // Explicit allowlist configured — use it
    if (corsAllowedOrigins.length) {
      return corsAllowedOrigins.includes(origin)
        ? cb(null, true)
        : cb(new Error('CORS origin not allowed'));
    }
    // No allowlist configured — allow same-origin (browser sends Origin on POST
    // even for same-origin requests, so we must permit it)
    return cb(null, true);
  },
  credentials: true
}));
app.use(express.json());
app.use(cookieParser());

app.use(express.static(path.join(__dirname, 'public')));

// ============================================
// DATABASE CONNECTION (PostgreSQL or SQLite)
// ============================================

const DATABASE_URL = process.env.DATABASE_URL;

let db;

if (DATABASE_URL) {
  // Production: PostgreSQL
  const { Pool } = require('pg');
  const pool = new Pool({ connectionString: DATABASE_URL, ssl: { rejectUnauthorized: false } });

  db = {
    _isPostgres: true,
    all: (query, params, callback) => {
      pool.query(query, params)
        .then(result => callback(null, result.rows))
        .catch(err => callback(err));
    },
    get: (query, params, callback) => {
      pool.query(query, params)
        .then(result => callback(null, result.rows[0] || null))
        .catch(err => callback(err));
    },
    run: (query, params, callback) => {
      pool.query(query, params)
        .then(result => callback(null, result))
        .catch(err => callback(err));
    }
  };

  pool.query('SELECT 1')
    .then(() => console.log('✅ Connected to PostgreSQL database'))
    .catch(err => console.error('❌ PostgreSQL connection failed:', err));

} else {
  // Local: SQLite
  try {
    const sqlite3 = require('sqlite3').verbose();
    const dbPath = path.join(__dirname, '..', 'stocks.db');
    // OPEN_READWRITE for auth writes; OPEN_CREATE if db doesn't exist yet
    const sqliteDb = new sqlite3.Database(dbPath, sqlite3.OPEN_READWRITE | sqlite3.OPEN_CREATE, (err) => {
      if (err) {
        console.error('❌ Database connection failed:', err);
      } else {
        console.log('✅ Connected to SQLite database (read/write)');
        // Enable WAL mode for better concurrent reads/writes
        sqliteDb.run('PRAGMA journal_mode=WAL');
        sqliteDb.run('PRAGMA foreign_keys=ON');
      }
    });

    db = {
      _isPostgres: false,
      all: (query, params, callback) => sqliteDb.all(query, params, callback),
      get: (query, params, callback) => sqliteDb.get(query, params, callback),
      run: (query, params, callback) => sqliteDb.run(query, params, callback)
    };
  } catch (err) {
    console.warn('⚠️  SQLite not available (this is normal on Render). Using PostgreSQL only.');
    // Create a dummy db object that will fail gracefully
    db = {
      all: (query, params, callback) => callback(new Error('No database configured')),
      get: (query, params, callback) => callback(new Error('No database configured')),
      run: (query, params, callback) => callback(new Error('No database configured'))
    };
  }
}

// ... existing endpoints ...

// ============================================
// AUTH, STOCKS, WATCHLIST & TRADES ROUTES
// ============================================

// Attach DB to route modules
const isPostgres = !!DATABASE_URL;
attachAuthDb(db, isPostgres);
attachStocksDb(db);
attachWatchlistDb(db, isPostgres);
attachTradesDb(db);
attachBriefingDb(db, isPostgres);
attachPerformanceDb(db, isPostgres);
attachAdminDb(db, isPostgres);
attachTimemachineDb(db, isPostgres);
attachPortfolioForecastsDb(db, isPostgres);
attachRagDb(db, isPostgres);
attachEtfDb(db, isPostgres);

app.use('/api', authRouter);
app.use('/api', stocksRouter);
app.use('/api', watchlistRouter);
app.use('/api/trades', tradesRouter);
app.use('/api/briefing', briefingRouter);
app.use('/api/performance-v2', performanceRouter);
// Admin login — public endpoint, not protected by requireAdminSecret
app.post('/api/admin/login', express.json(), (req, res) => {
  const { username, password } = req.body || {};
  const expectedUser = process.env.ADMIN_USERNAME || 'admin';
  const expectedPass = process.env.ADMIN_PASSWORD;
  if (!expectedPass) {
    return res.status(503).json({ error: 'Admin credentials not configured. Set ADMIN_PASSWORD environment variable.' });
  }
  if (!username || !password || username !== expectedUser || password !== expectedPass) {
    return res.status(401).json({ error: 'Invalid username or password' });
  }
  const jwt = require('jsonwebtoken');
  const jwtSecret = process.env.JWT_SECRET || 'dev-fallback-secret';
  const token = jwt.sign({ role: 'admin', user: username }, jwtSecret, { expiresIn: '8h' });
  res.json({ ok: true, token });
});

app.use('/api/admin', adminRouter);
app.use('/api/timemachine', timemachineRouter);
app.use('/api/portfolio-forecasts', portfolioForecastsRouter);
app.use('/api/rag', ragRouter);
app.use('/api/etf', etfRouter);

// ============================================
// API ENDPOINTS
// ============================================

// 1. Get latest predictions
app.get('/api/predictions', (req, res) => {
  const query = `
    SELECT symbol, agent_name, prediction, confidence, metadata, prediction_date, target_date
    FROM predictions
    WHERE prediction_date = (SELECT MAX(prediction_date) FROM predictions)
    ORDER BY symbol, agent_name
  `;

  db.all(query, [], (err, rows) => {
    if (err) {
      console.error('Error executing query for /api/predictions:', err);
      res.status(500).json({ error: err.message });
    } else {
      res.json({
        disclaimer: 'Xmore is an information and analytics tool, not a licensed investment advisor. This is not financial advice. Past performance does not guarantee future results.',
        predictions: rows || []
      });
    }
  });
});

// 2. Get agent performance (accuracy)
app.get('/api/performance', (req, res) => {
  // Use different boolean syntax for PostgreSQL vs SQLite
  const boolTrue = DATABASE_URL ? 'true' : '1';
  const query = `
    SELECT
      agent_name,
      COUNT(*) as total_predictions,
      SUM(CASE WHEN was_correct = ${boolTrue} THEN 1 ELSE 0 END) as correct_predictions,
      ROUND(AVG(CASE WHEN was_correct = ${boolTrue} THEN 1.0 ELSE 0.0 END) * 100, 1) as accuracy
    FROM evaluations
    GROUP BY agent_name
  `;

  db.all(query, [], (err, rows) => {
    if (err) {
      // Table might not exist yet (PostgreSQL: "does not exist", SQLite: "no such table")
      if (err.message && (err.message.includes('does not exist') || err.message.includes('no such table'))) {
        res.json([]);
      } else {
        res.status(500).json({ error: err.message });
      }
    } else {
      res.json(rows || []);
    }
  });
});

// 2b. Detailed performance metrics (Phase 1 Task 4)
app.get('/api/performance/detailed', (req, res) => {
  const boolTrue = DATABASE_URL ? 'true' : '1';

  // We'll run multiple queries and combine results
  const results = { overall: {}, per_agent: {}, per_stock: {}, monthly: [] };
  let completed = 0;
  const totalQueries = 4;

  function checkDone() {
    completed++;
    if (completed === totalQueries) {
      res.json(results);
    }
  }

  // 1. Overall metrics
  db.get(`
    SELECT
      COUNT(*) as total_predictions,
      SUM(CASE WHEN was_correct = ${boolTrue} THEN 1 ELSE 0 END) as correct_predictions,
      ROUND(AVG(CASE WHEN was_correct = ${boolTrue} THEN 1.0 ELSE 0.0 END) * 100, 1) as directional_accuracy,
      ROUND(AVG(actual_change_pct), 4) as avg_return_per_signal,
      ROUND(AVG(CASE WHEN prediction = 'UP' AND was_correct = ${boolTrue} THEN 1.0
                       WHEN prediction = 'UP' THEN 0.0 END) * 100, 1) as win_rate_buy,
      ROUND(AVG(CASE WHEN prediction = 'DOWN' AND was_correct = ${boolTrue} THEN 1.0
                       WHEN prediction = 'DOWN' THEN 0.0 END) * 100, 1) as win_rate_sell,
      MIN(actual_change_pct) as max_drawdown
    FROM evaluations
  `, [], (err, row) => {
    if (err || !row) {
      results.overall = {
        directional_accuracy: 0, total_predictions: 0, correct_predictions: 0,
        avg_return_per_signal: 0, win_rate_buy: 0, win_rate_sell: 0, max_drawdown: 0
      };
    } else {
      results.overall = {
        directional_accuracy: row.directional_accuracy || 0,
        total_predictions: row.total_predictions || 0,
        correct_predictions: row.correct_predictions || 0,
        avg_return_per_signal: row.avg_return_per_signal || 0,
        win_rate_buy: row.win_rate_buy || 0,
        win_rate_sell: row.win_rate_sell || 0,
        max_drawdown: row.max_drawdown || 0
      };
    }
    checkDone();
  });

  // 2. Per-agent metrics
  db.all(`
    SELECT
      agent_name,
      COUNT(*) as total,
      SUM(CASE WHEN was_correct = ${boolTrue} THEN 1 ELSE 0 END) as correct,
      ROUND(AVG(CASE WHEN was_correct = ${boolTrue} THEN 1.0 ELSE 0.0 END) * 100, 1) as accuracy
    FROM evaluations
    GROUP BY agent_name
    ORDER BY accuracy DESC
  `, [], (err, rows) => {
    if (!err && rows) {
      rows.forEach(r => {
        results.per_agent[r.agent_name] = {
          accuracy: r.accuracy || 0,
          total: r.total || 0,
          correct: r.correct || 0
        };
      });
    }
    checkDone();
  });

  // 3. Per-stock metrics
  db.all(`
    SELECT
      symbol,
      COUNT(*) as predictions,
      ROUND(AVG(CASE WHEN was_correct = ${boolTrue} THEN 1.0 ELSE 0.0 END) * 100, 1) as accuracy,
      ROUND(AVG(actual_change_pct), 4) as avg_return
    FROM evaluations
    GROUP BY symbol
    ORDER BY accuracy DESC
  `, [], (err, rows) => {
    if (!err && rows) {
      rows.forEach(r => {
        results.per_stock[r.symbol] = {
          accuracy: r.accuracy || 0,
          avg_return: r.avg_return || 0,
          predictions: r.predictions || 0
        };
      });
    }
    checkDone();
  });

  // 4. Monthly breakdown
  const monthExtract = DATABASE_URL
    ? "TO_CHAR(p.prediction_date::date, 'YYYY-MM')"
    : "strftime('%Y-%m', p.prediction_date)";

  db.all(`
    SELECT
      ${monthExtract} as month,
      COUNT(*) as predictions,
      ROUND(AVG(CASE WHEN e.was_correct = ${boolTrue} THEN 1.0 ELSE 0.0 END) * 100, 1) as accuracy,
      ROUND(AVG(e.actual_change_pct), 4) as avg_return
    FROM evaluations e
    JOIN predictions p ON e.prediction_id = p.id
    GROUP BY ${monthExtract}
    ORDER BY month DESC
    LIMIT 12
  `, [], (err, rows) => {
    if (!err && rows) {
      results.monthly = rows.map(r => ({
        month: r.month,
        accuracy: r.accuracy || 0,
        predictions: r.predictions || 0,
        avg_return: r.avg_return || 0
      }));
    }
    checkDone();
  });
});

// 3. Get latest stock prices (open, high, low, close, volume + intraday change)
app.get('/api/prices', (req, res) => {
  // Returns the single most-recent row per symbol.
  // change / change_pct are computed as close - open (intraday proxy).
  const query = DATABASE_URL
    ? `SELECT DISTINCT ON (p.symbol)
         p.symbol, p.date,
         p.open, p.high, p.low, p.close, p.volume,
         ROUND((p.close - p.open)::numeric, 4)                          AS change,
         ROUND(((p.close - p.open) / NULLIF(p.open, 0) * 100)::numeric, 2) AS change_pct
       FROM prices p
       ORDER BY p.symbol, p.date DESC`
    : `SELECT p.symbol, p.date,
         p.open, p.high, p.low, p.close, p.volume,
         ROUND(p.close - p.open, 4)                               AS change,
         ROUND((p.close - p.open) / NULLIF(p.open, 0) * 100, 2)  AS change_pct
       FROM prices p
       INNER JOIN (
         SELECT symbol, MAX(date) AS max_date
         FROM prices
         GROUP BY symbol
       ) latest ON p.symbol = latest.symbol AND p.date = latest.max_date
       ORDER BY p.symbol`;

  db.all(query, [], (err, rows) => {
    if (err) {
      res.status(500).json({ error: err.message });
    } else {
      res.json(rows || []);
    }
  });
});

// 4. Get latest sentiment scores
app.get('/api/sentiment', (req, res) => {
  // Get the most recent sentiment for each stock
  const query = DATABASE_URL
    ? `SELECT DISTINCT ON (symbol) symbol, date, avg_sentiment, sentiment_label, article_count
       FROM sentiment_scores
       ORDER BY symbol, date DESC`
    : `SELECT s.symbol, s.date, s.avg_sentiment, s.sentiment_label, s.article_count
       FROM sentiment_scores s
       INNER JOIN (
         SELECT symbol, MAX(date) as max_date
         FROM sentiment_scores
         GROUP BY symbol
       ) latest ON s.symbol = latest.symbol AND s.date = latest.max_date
       ORDER BY s.symbol`;

  db.all(query, [], (err, rows) => {
    if (err) {
      // Table might not exist yet
      if (err.message && err.message.includes('no such table')) {
        res.json([]);
      } else {
        res.status(500).json({ error: err.message });
      }
    } else {
      res.json(rows || []);
    }
  });
});

// 5. Get system stats
app.get('/api/stats', (req, res) => {
  const queries = {
    totalPrices: 'SELECT COUNT(*) as count FROM prices',
    totalPredictions: 'SELECT COUNT(*) as count FROM predictions',
    stocksTracked: 'SELECT COUNT(DISTINCT symbol) as count FROM prices',
    latestDate: 'SELECT MAX(date) as date FROM prices'
  };

  const stats = {};
  let completed = 0;

  Object.keys(queries).forEach(key => {
    db.get(queries[key], [], (err, row) => {
      if (!err && row) {
        stats[key] = row.count || row.date;
      }
      completed++;
      if (completed === Object.keys(queries).length) {
        res.json(stats);
      }
    });
  });
});

// 6. Get prediction evaluations (for results comparison)
app.get('/api/evaluations', (req, res) => {
  const boolTrue = DATABASE_URL ? 'true' : '1';
  const query = `
    SELECT
      e.symbol,
      e.agent_name,
      e.prediction,
      e.actual_outcome,
      e.was_correct,
      e.actual_change_pct,
      p.prediction_date,
      p.target_date
    FROM evaluations e
    JOIN predictions p ON e.prediction_id = p.id
    ORDER BY p.target_date DESC, e.symbol, e.agent_name
    LIMIT 100
  `;

  db.all(query, [], (err, rows) => {
    if (err) {
      if (err.message && (err.message.includes('does not exist') || err.message.includes('no such table'))) {
        res.json([]);
      } else {
        res.status(500).json({ error: err.message });
      }
    } else {
      res.json(rows || []);
    }
  });
});

// ============================================
// CONSENSUS API ENDPOINTS (3-Layer Pipeline)
// ============================================

// 7. Get latest consensus results for all stocks
app.get('/api/consensus', (req, res) => {
  const query = DATABASE_URL
    ? `SELECT DISTINCT ON (symbol)
         symbol, prediction_date, final_signal, conviction, confidence, xmore_score,
         risk_adjusted, agent_agreement, agents_agreeing, agents_total,
         majority_direction, bull_score, bear_score, risk_action, risk_score,
         display_json, risk_assessment_json
       FROM consensus_results
       ORDER BY symbol, prediction_date DESC`
    : `SELECT c.symbol, c.prediction_date, c.final_signal, c.conviction, c.confidence, c.xmore_score,
         c.risk_adjusted, c.agent_agreement, c.agents_agreeing, c.agents_total,
         c.majority_direction, c.bull_score, c.bear_score, c.risk_action, c.risk_score,
         c.display_json, c.risk_assessment_json
       FROM consensus_results c
       INNER JOIN (
         SELECT symbol, MAX(prediction_date) as max_date
         FROM consensus_results
         GROUP BY symbol
       ) latest ON c.symbol = latest.symbol AND c.prediction_date = latest.max_date
       ORDER BY c.symbol`;

  db.all(query, [], (err, rows) => {
    if (err) {
      if (err.message && (err.message.includes('does not exist') || err.message.includes('no such table'))) {
        res.json([]);
      } else {
        res.status(500).json({ error: err.message });
      }
    } else {
      // Parse JSON fields
      const parsed = (rows || []).map(row => {
        try {
          row.display = row.display_json ? JSON.parse(row.display_json) : {};
          row.risk_assessment = row.risk_assessment_json ? JSON.parse(row.risk_assessment_json) : {};
        } catch (e) {
          row.display = {};
          row.risk_assessment = {};
        }
        delete row.display_json;
        delete row.risk_assessment_json;
        return row;
      });
      res.json(parsed);
    }
  });
});

// 8. Get detailed consensus for a specific stock
app.get('/api/consensus/:symbol', (req, res) => {
  const { symbol } = req.params;
  const placeholder = DATABASE_URL ? '$1' : '?';

  const query = `
    SELECT
      symbol, prediction_date, final_signal, conviction, confidence,
      risk_adjusted, agent_agreement, agents_agreeing, agents_total,
      majority_direction, bull_score, bear_score, risk_action, risk_score,
      bull_case_json, bear_case_json, risk_assessment_json,
      agent_signals_json, reasoning_chain_json, display_json
    FROM consensus_results
    WHERE symbol = ${placeholder}
    ORDER BY prediction_date DESC
    LIMIT 1
  `;

  db.get(query, [symbol], (err, row) => {
    if (err) {
      if (err.message && (err.message.includes('does not exist') || err.message.includes('no such table'))) {
        res.json(null);
      } else {
        res.status(500).json({ error: err.message });
      }
    } else if (!row) {
      res.json(null);
    } else {
      // Parse all JSON fields
      try {
        row.bull_case = row.bull_case_json ? JSON.parse(row.bull_case_json) : {};
        row.bear_case = row.bear_case_json ? JSON.parse(row.bear_case_json) : {};
        row.risk_assessment = row.risk_assessment_json ? JSON.parse(row.risk_assessment_json) : {};
        row.agent_signals = row.agent_signals_json ? JSON.parse(row.agent_signals_json) : [];
        row.reasoning_chain = row.reasoning_chain_json ? JSON.parse(row.reasoning_chain_json) : [];
        row.display = row.display_json ? JSON.parse(row.display_json) : {};
      } catch (e) {
        console.error('Error parsing consensus JSON:', e);
      }
      // Remove raw JSON fields
      delete row.bull_case_json;
      delete row.bear_case_json;
      delete row.risk_assessment_json;
      delete row.agent_signals_json;
      delete row.reasoning_chain_json;
      delete row.display_json;
      res.json(row);
    }
  });
});

// 9. Get portfolio risk overview
app.get('/api/risk/overview', (req, res) => {
  // Get latest consensus for all stocks and compute portfolio-level risk
  const query = DATABASE_URL
    ? `SELECT DISTINCT ON (symbol)
         symbol, final_signal, conviction, risk_action, risk_score,
         bull_score, bear_score, risk_assessment_json
       FROM consensus_results
       ORDER BY symbol, prediction_date DESC`
    : `SELECT c.symbol, c.final_signal, c.conviction, c.risk_action, c.risk_score,
         c.bull_score, c.bear_score, c.risk_assessment_json
       FROM consensus_results c
       INNER JOIN (
         SELECT symbol, MAX(prediction_date) as max_date
         FROM consensus_results
         GROUP BY symbol
       ) latest ON c.symbol = latest.symbol AND c.prediction_date = latest.max_date
       ORDER BY c.symbol`;

  db.all(query, [], (err, rows) => {
    if (err) {
      if (err.message && (err.message.includes('does not exist') || err.message.includes('no such table'))) {
        res.json({ stocks: [], summary: { total: 0, blocked: 0, flagged: 0, passed: 0, avg_risk: 0 } });
      } else {
        res.status(500).json({ error: err.message });
      }
    } else {
      const stocks = (rows || []).map(r => {
        let riskFlags = [];
        try {
          const ra = r.risk_assessment_json ? JSON.parse(r.risk_assessment_json) : {};
          riskFlags = ra.risk_flags || [];
        } catch (e) { /* ignore */ }

        return {
          symbol: r.symbol,
          signal: r.final_signal,
          conviction: r.conviction,
          risk_action: r.risk_action,
          risk_score: r.risk_score,
          bull_score: r.bull_score,
          bear_score: r.bear_score,
          risk_flags: riskFlags
        };
      });

      const summary = {
        total: stocks.length,
        blocked: stocks.filter(s => s.risk_action === 'BLOCK').length,
        flagged: stocks.filter(s => s.risk_action === 'FLAG').length,
        downgraded: stocks.filter(s => s.risk_action === 'DOWNGRADE').length,
        passed: stocks.filter(s => s.risk_action === 'PASS').length,
        avg_risk: stocks.length > 0
          ? Math.round(stocks.reduce((sum, s) => sum + (s.risk_score || 0), 0) / stocks.length)
          : 0
      };

      res.json({ stocks, summary });
    }
  });
});

// ============================================
// DERIVATIVES — Black-Scholes computed inline (no external service)
// ============================================

// Abramowitz & Stegun approximation for standard normal CDF
function _normCDF(x) {
  const a1=0.254829592,a2=-0.284496736,a3=1.421413741,a4=-1.453152027,a5=1.061405429,p=0.3275911;
  const sign = x < 0 ? -1 : 1;
  const t = 1 / (1 + p * Math.abs(x));
  const poly = t*(a1+t*(a2+t*(a3+t*(a4+t*a5))));
  return 0.5 * (1 + sign * (1 - poly * Math.exp(-x*x/2)));
}
function _normPDF(x) { return Math.exp(-0.5*x*x) / Math.sqrt(2*Math.PI); }

function _bsm(S, K, T, r, sigma, q=0) {
  const sqrtT = Math.sqrt(T);
  const d1 = (Math.log(S/K) + (r - q + 0.5*sigma*sigma)*T) / (sigma*sqrtT);
  const d2 = d1 - sigma*sqrtT;
  const call = S*Math.exp(-q*T)*_normCDF(d1) - K*Math.exp(-r*T)*_normCDF(d2);
  const put  = K*Math.exp(-r*T)*_normCDF(-d2) - S*Math.exp(-q*T)*_normCDF(-d1);
  const delta = Math.exp(-q*T)*_normCDF(d1);
  const gamma = Math.exp(-q*T)*_normPDF(d1) / (S*sigma*sqrtT);
  const theta = (-(S*Math.exp(-q*T)*_normPDF(d1)*sigma)/(2*sqrtT) - r*K*Math.exp(-r*T)*_normCDF(d2) + q*S*Math.exp(-q*T)*_normCDF(d1)) / 365;
  const vega  = S*Math.exp(-q*T)*_normPDF(d1)*sqrtT / 100;  // per 1% vol move
  const rho   = K*T*Math.exp(-r*T)*_normCDF(d2) / 100;
  return { call, put, delta, gamma, theta, vega, rho, d1, d2 };
}

app.get('/api/derivatives/brief/:ticker', (req, res) => {
  try {
    const ticker = req.params.ticker;
    const S     = parseFloat(req.query.S)     || 10;
    const K     = parseFloat(req.query.K)     || S;
    const T     = parseFloat(req.query.T)     || 0.5;
    const r     = parseFloat(req.query.r)     || 0.085;
    const sigma = parseFloat(req.query.sigma) || 0.25;

    if (S <= 0 || K <= 0 || T <= 0 || sigma <= 0)
      return res.status(422).json({ error: 'Invalid parameters: S, K, T, sigma must be > 0' });

    const g = _bsm(S, K, T, r, sigma);
    const straddle     = g.call + g.put;
    const straddlePct  = straddle / S * 100;
    const deltaDollar  = g.delta * S * 0.01;

    const narrative = `${ticker} \u2014 ATM call trades at EGP ${g.call.toFixed(2)}, put at EGP ${g.put.toFixed(2)}. ` +
      `Straddle cost ${straddle.toFixed(2)} (${straddlePct.toFixed(1)}% of spot). ` +
      `Delta ${g.delta.toFixed(2)} \u2014 a 1% spot move gains/loses EGP ${deltaDollar.toFixed(2)}. ` +
      `Theta bleeds EGP ${Math.abs(g.theta).toFixed(2)}/day. Vol sensitivity EGP ${g.vega.toFixed(2)} per 1% vol move.`;

    res.json({
      ticker,
      narrative,
      metrics: {
        call_price: g.call, put_price: g.put, straddle, straddle_pct: straddlePct,
        delta: g.delta, delta_dollar: deltaDollar, gamma: g.gamma,
        theta: g.theta, vega: g.vega, rho: g.rho,
        sigma_used: sigma, S, K, T, r,
      },
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/derivatives/price', (req, res) => {
  try {
    const { S, K, T, r=0.085, sigma=0.25, option_type='call', q=0 } = req.body;
    if (!S || !K || !T) return res.status(422).json({ error: 'S, K, T are required' });
    const g = _bsm(parseFloat(S), parseFloat(K), parseFloat(T), parseFloat(r), parseFloat(sigma), parseFloat(q));
    const price = option_type === 'put' ? g.put : g.call;
    res.json({ price, delta: g.delta, gamma: g.gamma, theta: g.theta, vega: g.vega, rho: g.rho, sigma_used: sigma });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ============================================
// BACKTEST RESULTS API
// ============================================
app.get('/api/backtest/results', (req, res) => {
  const sym = req.query.symbol;
  let sql, params;
  if (sym) {
    const ph = DATABASE_URL ? '$1' : '?';
    sql = `SELECT * FROM backtest_results WHERE symbol = ${ph} ORDER BY run_date DESC LIMIT 10`;
    params = [sym.toUpperCase()];
  } else {
    sql = DATABASE_URL
      ? `SELECT DISTINCT ON (symbol) * FROM backtest_results ORDER BY symbol, run_date DESC`
      : `SELECT br.* FROM backtest_results br INNER JOIN (SELECT symbol, MAX(run_date) AS d FROM backtest_results GROUP BY symbol) l ON br.symbol=l.symbol AND br.run_date=l.d ORDER BY br.directional_accuracy DESC`;
    params = [];
  }
  db.all(sql, params, (err, rows) => {
    if (err) {
      if (err.message && (err.message.includes('does not exist') || err.message.includes('no such table'))) return res.json([]);
      return res.status(500).json({ error: err.message });
    }
    res.json((rows || []).map(r => ({ ...r, fold_scores: r.fold_scores_json ? JSON.parse(r.fold_scores_json) : [] })));
  });
});

// ============================================
// FX RATES (with gold)
// ============================================
let _fxCache = null, _fxCacheTime = 0;
app.get('/api/fx-rates', async (req, res) => {
  const now = Date.now();
  if (_fxCache && now - _fxCacheTime < 3_600_000) return res.json(_fxCache);
  try {
    const https = require('https');
    const raw = await new Promise((resolve, reject) => {
      https.get('https://open.er-api.com/v6/latest/USD', (r) => {
        let body = '';
        r.on('data', d => body += d);
        r.on('end', () => { try { resolve(JSON.parse(body)); } catch (e) { reject(e); } });
      }).on('error', reject);
    });
    const egp = raw.rates && raw.rates.EGP;
    const sar = raw.rates && raw.rates.SAR;
    const xau = raw.rates && raw.rates.XAU;   // troy oz per 1 USD
    if (!egp || !sar) throw new Error('Missing EGP/SAR rates');
    // Gold calculations: XAU rate = troy oz per USD, so 1 troy oz = 1/xau USD
    const TROY_OZ_TO_GRAMS = 31.1035;
    let goldData = {};
    if (xau && xau > 0) {
      const xauUsd  = 1 / xau;                                     // USD per troy oz
      const gold24K = (xauUsd / TROY_OZ_TO_GRAMS) * egp;           // EGP per gram 24K
      goldData = {
        XAU_USD:         +xauUsd.toFixed(2),
        GOLD_24K_EGP_G:  +gold24K.toFixed(2),
        GOLD_21K_EGP_G:  +(gold24K * 21 / 24).toFixed(2),
        GOLD_18K_EGP_G:  +(gold24K * 18 / 24).toFixed(2),
        GOLD_POUND_EGP:  +(gold24K * 21 / 24 * 8).toFixed(2),     // 8g 21K = Egyptian gold pound
      };
    }
    _fxCache = {
      USD_EGP: +egp.toFixed(2),
      USD_SAR: +sar.toFixed(4),
      SAR_EGP: +(egp / sar).toFixed(4),
      ...goldData,
      updated: new Date().toISOString(),
    };
    _fxCacheTime = now;
    // Store in fx_rates_history (one row per day, upsert)
    const today = new Date().toISOString().split('T')[0];
    const histSql = db._isPostgres
      ? `INSERT INTO fx_rates_history (date, usd_egp, usd_sar, xau_usd, gold_24k_egp_g, gold_21k_egp_g, gold_pound_egp)
         VALUES ($1,$2,$3,$4,$5,$6,$7) ON CONFLICT (date) DO UPDATE SET
         usd_egp=EXCLUDED.usd_egp, usd_sar=EXCLUDED.usd_sar, xau_usd=EXCLUDED.xau_usd,
         gold_24k_egp_g=EXCLUDED.gold_24k_egp_g, gold_21k_egp_g=EXCLUDED.gold_21k_egp_g,
         gold_pound_egp=EXCLUDED.gold_pound_egp`
      : `INSERT OR REPLACE INTO fx_rates_history (date, usd_egp, usd_sar, xau_usd, gold_24k_egp_g, gold_21k_egp_g, gold_pound_egp)
         VALUES (?,?,?,?,?,?,?)`;
    db.run(histSql, [today, _fxCache.USD_EGP, _fxCache.USD_SAR, goldData.XAU_USD || null,
      goldData.GOLD_24K_EGP_G || null, goldData.GOLD_21K_EGP_G || null, goldData.GOLD_POUND_EGP || null],
      () => {}); // fire-and-forget
    res.json(_fxCache);
  } catch (err) {
    if (_fxCache) return res.json(_fxCache);   // serve stale on error
    res.status(502).json({ error: err.message });
  }
});

// ============================================
// FX RATES HISTORY
// ============================================
app.get('/api/fx-rates/history', (req, res) => {
  const days = Math.min(90, parseInt(req.query.days) || 30);
  const sql = DATABASE_URL
    ? `SELECT date, usd_egp, xau_usd, gold_24k_egp_g, gold_21k_egp_g, gold_pound_egp
       FROM fx_rates_history ORDER BY date DESC LIMIT $1`
    : `SELECT date, usd_egp, xau_usd, gold_24k_egp_g, gold_21k_egp_g, gold_pound_egp
       FROM fx_rates_history ORDER BY date DESC LIMIT ?`;
  db.all(sql, [days], (err, rows) => {
    if (err) {
      if (err.message && (err.message.includes('does not exist') || err.message.includes('no such table'))) return res.json([]);
      return res.status(500).json({ error: err.message });
    }
    res.json((rows || []).reverse()); // oldest first for charts
  });
});

// ============================================
// PER-STOCK AI BRIEF
// ============================================
const _briefCache = new Map(); // symbol -> { text, ts }

app.get('/api/stocks/:symbol/brief', async (req, res) => {
  const symbol = (req.params.symbol || '').toUpperCase().replace(/[^A-Z0-9.]/g, '');
  if (!symbol) return res.status(400).json({ error: 'Invalid symbol' });

  // Serve cache if fresh (1h)
  const cached = _briefCache.get(symbol);
  if (cached && Date.now() - cached.ts < 3_600_000) return res.json({ brief: cached.text, symbol, cached: true });

  const GOOGLE_API_KEY = process.env.GOOGLE_API_KEY;
  if (!GOOGLE_API_KEY) return res.status(503).json({ error: 'AI brief not configured' });

  // Gather context from db
  const ctx = await new Promise(resolve => {
    const sql = DATABASE_URL
      ? `SELECT c.final_signal, c.conviction, c.confidence, c.xmore_score, c.bull_score, c.bear_score,
                p.close FROM consensus_results c
         LEFT JOIN (SELECT symbol, close FROM prices WHERE symbol=$1 ORDER BY date DESC LIMIT 1) p ON p.symbol=c.symbol
         WHERE c.symbol=$1 ORDER BY c.prediction_date DESC LIMIT 1`
      : `SELECT c.final_signal, c.conviction, c.confidence, c.xmore_score, c.bull_score, c.bear_score,
                p.close FROM consensus_results c
         LEFT JOIN (SELECT symbol, close FROM prices WHERE symbol=? ORDER BY date DESC LIMIT 1) p ON p.symbol=c.symbol
         WHERE c.symbol=? ORDER BY c.prediction_date DESC LIMIT 1`;
    const params = DATABASE_URL ? [symbol] : [symbol, symbol];
    db.get(sql, params, (err, row) => resolve(row || {}));
  });

  const prompt = `You are a concise EGX (Egyptian Exchange) stock analyst. Write a 3-sentence professional brief for ${symbol}.
Data: Signal=${ctx.final_signal||'N/A'}, Conviction=${ctx.conviction||'N/A'}, Confidence=${ctx.confidence||'N/A'}%, XmoreScore=${ctx.xmore_score||'N/A'}, BullScore=${ctx.bull_score||'N/A'}, BearScore=${ctx.bear_score||'N/A'}, Price=${ctx.close||'N/A'} EGP.
Format: 1) Current stance and signal quality 2) Key risk factor 3) Short-term outlook. Be direct, no disclaimers.`;

  try {
    const { GoogleGenAI } = require('@google/genai');
    const genai = new GoogleGenAI({ apiKey: GOOGLE_API_KEY });
    const result = await genai.models.generateContent({
      model: 'gemini-2.5-flash',
      contents: [{ parts: [{ text: prompt }] }],
    });
    const text = result?.candidates?.[0]?.content?.parts?.[0]?.text || 'Brief unavailable.';
    _briefCache.set(symbol, { text, ts: Date.now() });
    res.json({ brief: text, symbol });
  } catch (err) {
    res.status(502).json({ error: 'AI brief failed: ' + err.message });
  }
});

// ============================================
// STOCK SIGNAL MULTI-HORIZON (D+5/D+10/D+20)
// ============================================
app.get('/api/signal-accuracy', (req, res) => {
  const horizon = parseInt(req.query.horizon) || 5;
  const limit = Math.min(100, parseInt(req.query.limit) || 30);
  const sql = DATABASE_URL
    ? `SELECT symbol, horizon_days,
         COUNT(*) as total,
         SUM(CASE WHEN was_correct THEN 1 ELSE 0 END) as correct,
         ROUND(100.0 * SUM(CASE WHEN was_correct THEN 1 ELSE 0 END) / COUNT(*), 1) as accuracy_pct,
         AVG(actual_change_pct) as avg_change_pct
       FROM stock_signal_evals
       WHERE horizon_days = $1
       GROUP BY symbol, horizon_days
       HAVING COUNT(*) >= 3
       ORDER BY accuracy_pct DESC LIMIT $2`
    : `SELECT symbol, horizon_days,
         COUNT(*) as total,
         SUM(CASE WHEN was_correct THEN 1 ELSE 0 END) as correct,
         ROUND(100.0 * SUM(CASE WHEN was_correct THEN 1 ELSE 0 END) / COUNT(*), 1) as accuracy_pct,
         AVG(actual_change_pct) as avg_change_pct
       FROM stock_signal_evals
       WHERE horizon_days = ?
       GROUP BY symbol, horizon_days
       HAVING COUNT(*) >= 3
       ORDER BY accuracy_pct DESC LIMIT ?`;
  db.all(sql, [horizon, limit], (err, rows) => {
    if (err) {
      if (err.message && (err.message.includes('does not exist') || err.message.includes('no such table'))) return res.json([]);
      return res.status(500).json({ error: err.message });
    }
    res.json(rows || []);
  });
});

// ============================================
// FRONTEND ROUTE
// ============================================
app.get('/admin', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'admin.html'));
});

app.get('/pro', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'pro.html'));
});

app.get('/docs', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'docs.html'));
});

app.get('/session', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'session.html'));
});

app.get('/landing', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'landing.html'));
});

app.get('*', (req, res) => {
  // Don't serve index.html for /api routes that weren't matched
  if (req.path.startsWith('/api/')) {
    return res.status(404).json({ error: 'Not found' });
  }
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});


// ============================================
// START SERVER
// ============================================

console.log(`⏳ Starting server on port ${PORT}...`);
app.listen(PORT, '0.0.0.0', () => {
  console.log(`🚀 Server running on port ${PORT}`);
  console.log(`📊 Dashboard available`);
});
