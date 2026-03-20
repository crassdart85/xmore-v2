console.log('=== SERVER.JS STARTING ===');
const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const path = require('path');
const cookieParser = require('cookie-parser');
const crypto = require('crypto');
const rateLimitPkg = require('express-rate-limit');
const { optionalAuth, JWT_SECRET } = require('./middleware/auth');

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
const { router: scoringRouter, attachDb: attachScoringDb } = require('./routes/scoring');
const { router: trackRecordRouter, attachDb: attachTrackRecordDb } = require('./routes/track-record');
const { router: screeningRouter, attachDb: attachScreeningDb } = require('./routes/screening');

const app = express();
const PORT = process.env.PORT || 3000;
const IS_PROD = process.env.NODE_ENV === 'production';
const rateLimit = rateLimitPkg.rateLimit || rateLimitPkg;
const ipKeyGenerator = rateLimitPkg.ipKeyGenerator || ((ip) => ip);

// Middleware
const corsAllowedOrigins = (process.env.CORS_ALLOWED_ORIGINS || '')
  .split(',')
  .map(s => s.trim())
  .filter(Boolean);

function normalizeOrigin(origin) {
  try {
    return new URL(origin).origin;
  } catch (_err) {
    return null;
  }
}

function buildAllowedOrigins(req) {
  const origins = new Set(corsAllowedOrigins.map(normalizeOrigin).filter(Boolean));
  const host = req.get('x-forwarded-host') || req.get('host');
  const proto = req.get('x-forwarded-proto') || req.protocol || 'https';

  if (host) {
    origins.add(`${proto}://${host}`);
    origins.add(`https://${host}`);
  }

  origins.add('https://xmore-project.onrender.com');
  origins.add('https://xmore-v2.onrender.com');

  const vercelUrl = process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : null;
  if (vercelUrl) origins.add(vercelUrl);

  const publicAppUrl = normalizeOrigin(process.env.PUBLIC_APP_URL || '');
  if (publicAppUrl) origins.add(publicAppUrl);

  return origins;
}

app.set('trust proxy', 1);
app.use(helmet({
  contentSecurityPolicy: false
}));

app.use(cors((req, cb) => {
  const requestOrigin = req.get('origin');

  // No origin header (server-to-server, health checks, direct same-origin navigations).
  if (!requestOrigin) {
    return cb(null, { origin: true, credentials: true });
  }

  const normalizedRequestOrigin = normalizeOrigin(requestOrigin);
  const allowedOrigins = buildAllowedOrigins(req);

  if (normalizedRequestOrigin && allowedOrigins.has(normalizedRequestOrigin)) {
    return cb(null, { origin: true, credentials: true });
  }

  if (!IS_PROD) {
    return cb(null, { origin: true, credentials: true });
  }

  return cb(new Error('CORS origin not allowed'));
}));
app.use(express.json({ limit: '10kb' }));
app.use(cookieParser());

const apiLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 300,
  keyGenerator: (req) => ipKeyGenerator(req.ip || req.socket?.remoteAddress || ''),
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: 'Too many requests. Please slow down and try again shortly.' }
});

app.use('/api', apiLimiter);

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
    .then(() => console.log('âœ… Connected to PostgreSQL database'))
    .catch(err => console.error('âŒ PostgreSQL connection failed:', err));

} else {
  // Local: SQLite
  try {
    const sqlite3 = require('sqlite3').verbose();
    const dbPath = path.join(__dirname, '..', 'stocks.db');
    // OPEN_READWRITE for auth writes; OPEN_CREATE if db doesn't exist yet
    const sqliteDb = new sqlite3.Database(dbPath, sqlite3.OPEN_READWRITE | sqlite3.OPEN_CREATE, (err) => {
      if (err) {
        console.error('âŒ Database connection failed:', err);
      } else {
        console.log('âœ… Connected to SQLite database (read/write)');
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
    console.warn('âš ï¸  SQLite not available (this is normal on Render). Using PostgreSQL only.');
    // Create a dummy db object that will fail gracefully
    db = {
      all: (query, params, callback) => callback(new Error('No database configured')),
      get: (query, params, callback) => callback(new Error('No database configured')),
      run: (query, params, callback) => callback(new Error('No database configured'))
    };
  }
}

// ... existing endpoints ...

function dbAllAsync(query, params = []) {
  return new Promise((resolve, reject) => {
    db.all(query, params, (err, rows) => err ? reject(err) : resolve(rows || []));
  });
}

function dbGetAsync(query, params = []) {
  return new Promise((resolve, reject) => {
    db.get(query, params, (err, row) => err ? reject(err) : resolve(row || null));
  });
}

function isTableMissing(err) {
  return err && err.message && (
    err.message.includes('does not exist') ||
    err.message.includes('no such table') ||
    err.message.includes('no such column')
  );
}

function normalizeBool(value) {
  return value === true || value === 1 || value === 't' || value === 'true';
}

async function buildConsensusCalibrationState() {
  const state = { overallAccuracy: 0.5, bins: {}, samples: 0 };
  try {
    const rows = await dbAllAsync(`
      SELECT p.confidence, e.was_correct
      FROM evaluations e
      JOIN predictions p ON p.id = e.prediction_id
      WHERE e.agent_name = 'Consensus'
        AND p.confidence IS NOT NULL
      ORDER BY e.evaluated_at DESC
      LIMIT 1200
    `, []);
    if (!rows.length) return state;

    let hits = 0;
    const bins = {};
    rows.forEach(row => {
      const confidence = Number(row.confidence || 0);
      const bucket = Math.max(0, Math.min(90, Math.floor(confidence / 10) * 10));
      const entry = bins[bucket] || { count: 0, hits: 0 };
      const ok = normalizeBool(row.was_correct) ? 1 : 0;
      entry.count += 1;
      entry.hits += ok;
      hits += ok;
      bins[bucket] = entry;
    });

    state.samples = rows.length;
    state.overallAccuracy = hits / rows.length;
    Object.keys(bins).forEach(bucket => {
      const entry = bins[bucket];
      state.bins[bucket] = {
        count: entry.count,
        empiricalAccuracy: entry.hits / entry.count
      };
    });
    return state;
  } catch (err) {
    if (!isTableMissing(err)) console.warn('[consensus calibration]', err.message);
    return state;
  }
}

function applyConsensusCalibration(rawConfidence, calibrationState) {
  const raw = Number(rawConfidence || 0);
  const bucket = Math.max(0, Math.min(90, Math.floor(raw / 10) * 10));
  const overall = Number(calibrationState?.overallAccuracy || 0.5);
  const bucketMeta = calibrationState?.bins?.[bucket] || null;
  const bucketCount = Number(bucketMeta?.count || 0);
  const empirical = Number(bucketMeta?.empiricalAccuracy ?? overall);
  const smoothed = ((empirical * bucketCount) + (overall * 20)) / (bucketCount + 20);
  const calibrated = Math.max(0, Math.min(100, (raw * 0.45) + (smoothed * 100 * 0.55)));
  return {
    rawConfidence: Number(raw.toFixed(2)),
    calibratedConfidence: Number(calibrated.toFixed(2)),
    bucket,
    bucketSamples: bucketCount,
    empiricalAccuracy: Number(empirical.toFixed(4)),
    overallAccuracy: Number(overall.toFixed(4))
  };
}

async function buildExpectedEdgeState() {
  const state = {};
  try {
    const rows = await dbAllAsync(`
      SELECT symbol, prediction, actual_change_pct, was_correct
      FROM evaluations
      WHERE agent_name = 'Consensus'
        AND actual_change_pct IS NOT NULL
      ORDER BY evaluated_at DESC
      LIMIT 2500
    `, []);
    rows.forEach(row => {
      const prediction = String(row.prediction || '').toUpperCase();
      if (!['UP', 'DOWN', 'BUY', 'SELL'].includes(prediction)) return;
      const actualChange = Number(row.actual_change_pct || 0);
      const realizedEdge = (prediction === 'UP' || prediction === 'BUY') ? actualChange : -actualChange;

      const keys = [`${row.symbol}|${prediction}`, `_GLOBAL_|${prediction}`];
      keys.forEach(key => {
        const entry = state[key] || { count: 0, wins: 0, winSum: 0, lossSum: 0, lossCount: 0 };
        entry.count += 1;
        if (realizedEdge > 0) {
          entry.wins += 1;
          entry.winSum += realizedEdge;
        } else if (realizedEdge < 0) {
          entry.lossSum += Math.abs(realizedEdge);
          entry.lossCount += 1;
        } else if (normalizeBool(row.was_correct)) {
          entry.wins += 1;
        }
        state[key] = entry;
      });
    });

    Object.keys(state).forEach(key => {
      const entry = state[key];
      entry.winRate = entry.count ? entry.wins / entry.count : 0.5;
      entry.avgWin = entry.wins ? entry.winSum / entry.wins : 1.5;
      entry.avgLoss = entry.lossCount ? entry.lossSum / entry.lossCount : 1.0;
    });
    return state;
  } catch (err) {
    if (!isTableMissing(err)) console.warn('[expected edge]', err.message);
    return state;
  }
}

function estimateExpectedEdge(symbol, prediction, calibrationMeta, edgeState) {
  const direction = String(prediction || '').toUpperCase();
  if (!['UP', 'DOWN', 'BUY', 'SELL'].includes(direction)) {
    return { expectedEdgePct: 0, rankingScore: 0, profileScope: 'neutral', profileSamples: 0 };
  }

  const entry = edgeState[`${symbol}|${direction}`] || edgeState[`_GLOBAL_|${direction}`] || null;
  const calibrated = Number(calibrationMeta?.calibratedConfidence || 0) / 100;
  const histWinRate = Number(entry?.winRate ?? calibrated ?? 0.5);
  const avgWin = Number(entry?.avgWin ?? 1.5);
  const avgLoss = Number(entry?.avgLoss ?? 1.0);
  const blendedWin = (histWinRate * 0.45) + (calibrated * 0.55);
  const estimatedCost = 0.70;
  const expectedEdge = (blendedWin * avgWin) - ((1 - blendedWin) * avgLoss) - estimatedCost;
  const rankingScore = expectedEdge * (0.75 + calibrated);

  return {
    expectedEdgePct: Number(expectedEdge.toFixed(3)),
    rankingScore: Number(rankingScore.toFixed(3)),
    profileScope: edgeState[`${symbol}|${direction}`] ? 'symbol' : 'global',
    profileSamples: Number(entry?.count || 0),
    historicalWinRate: Number(histWinRate.toFixed(4)),
    avgWinPct: Number(avgWin.toFixed(4)),
    avgLossPct: Number(avgLoss.toFixed(4)),
    estimatedCostPct: estimatedCost
  };
}

function enrichConsensusRow(row, calibrationState, edgeState) {
  const calibrationMeta = applyConsensusCalibration(row.calibrated_confidence ?? row.confidence, calibrationState);
  const edgeMeta = estimateExpectedEdge(row.symbol, row.final_signal, calibrationMeta, edgeState);
  return {
    ...row,
    calibrated_confidence: row.calibrated_confidence != null
      ? Number(row.calibrated_confidence)
      : calibrationMeta.calibratedConfidence,
    expected_edge_pct: row.expected_edge_pct != null
      ? Number(row.expected_edge_pct)
      : edgeMeta.expectedEdgePct,
    ranking_score: row.ranking_score != null
      ? Number(row.ranking_score)
      : edgeMeta.rankingScore,
    calibration_meta: {
      ...calibrationMeta,
      ...edgeMeta
    }
  };
}

function ageHoursFromDate(value) {
  if (!value) return null;
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return null;
  return (Date.now() - dt.getTime()) / 3600000;
}

function freshnessStatus(ageHours, thresholdHours) {
  if (ageHours == null) return 'unknown';
  if (ageHours <= thresholdHours) return 'fresh';
  if (ageHours <= thresholdHours * 2) return 'warning';
  return 'stale';
}

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
attachScoringDb(db, isPostgres);
attachTrackRecordDb(db, isPostgres);
attachScreeningDb(db, isPostgres);

app.use('/api', authRouter);
app.use('/api', stocksRouter);
app.use('/api', watchlistRouter);
app.use('/api/trades', tradesRouter);
app.use('/api/briefing', briefingRouter);
app.use('/api/performance-v2', performanceRouter);
// Admin login â€” public endpoint, not protected by requireAdminSecret
app.post('/api/admin/login', express.json(), (req, res) => {
  const { username, password } = req.body || {};
  const expectedUser = process.env.ADMIN_USERNAME || 'admin';
  const expectedPass = process.env.ADMIN_PASSWORD;
  if (!expectedPass) {
    return res.status(503).json({ error: 'Admin credentials not configured. Set ADMIN_PASSWORD environment variable.' });
  }

  const providedUser = String(username || '');
  const providedPass = String(password || '');
  const safeEquals = (a, b) => {
    const aBuf = Buffer.from(String(a));
    const bBuf = Buffer.from(String(b));
    if (aBuf.length !== bBuf.length) return false;
    return crypto.timingSafeEqual(aBuf, bBuf);
  };

  if (!providedUser || !providedPass || !safeEquals(providedUser, expectedUser) || !safeEquals(providedPass, expectedPass)) {
    return res.status(401).json({ error: 'Invalid username or password' });
  }
  const jwt = require('jsonwebtoken');
  const token = jwt.sign({ role: 'admin', user: providedUser }, JWT_SECRET, { expiresIn: '8h' });
  res.json({ ok: true, token });
});

app.use('/api/admin', adminRouter);
app.use('/api/timemachine', timemachineRouter);
app.use('/api/portfolio-forecasts', portfolioForecastsRouter);
app.use('/api/rag', ragRouter);
app.use('/api/etf', etfRouter);
app.use('/api/signals', scoringRouter);
app.use('/api/track-record', trackRecordRouter);
app.use('/api/screening', screeningRouter);

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

app.get('/api/intelligence/changes', optionalAuth, async (req, res) => {
  try {
    const calibrationState = await buildConsensusCalibrationState();
    const edgeState = await buildExpectedEdgeState();
    const limit = Math.min(parseInt(req.query.limit, 10) || 8, 20);

    const latestDates = await dbAllAsync(
      `SELECT DISTINCT prediction_date FROM consensus_results ORDER BY prediction_date DESC LIMIT 2`,
      []
    ).catch(err => isTableMissing(err) ? [] : Promise.reject(err));

    const currentDate = latestDates[0]?.prediction_date || null;
    const previousDate = latestDates[1]?.prediction_date || null;
    let signalChanges = [];

    if (currentDate) {
      const datePh = DATABASE_URL ? '$1' : '?';
      const currentRows = await dbAllAsync(
        `SELECT symbol, prediction_date, final_signal, conviction, confidence,
                calibrated_confidence, expected_edge_pct, ranking_score, xmore_score
         FROM consensus_results
         WHERE prediction_date = ${datePh}`,
        [currentDate]
      ).catch(err => isTableMissing(err) ? [] : Promise.reject(err));
      const previousRows = previousDate ? await dbAllAsync(
        `SELECT symbol, prediction_date, final_signal, conviction, confidence,
                calibrated_confidence, expected_edge_pct, ranking_score, xmore_score
         FROM consensus_results
         WHERE prediction_date = ${datePh}`,
        [previousDate]
      ).catch(err => isTableMissing(err) ? [] : Promise.reject(err)) : [];

      const previousMap = new Map(previousRows.map(row => [row.symbol, row]));
      signalChanges = currentRows.map(row => {
        const enriched = enrichConsensusRow(row, calibrationState, edgeState);
        const prev = previousMap.get(row.symbol);
        const prevEnriched = prev ? enrichConsensusRow(prev, calibrationState, edgeState) : null;
        const signalChanged = !!prevEnriched && prevEnriched.final_signal !== enriched.final_signal;
        const convictionChanged = !!prevEnriched && prevEnriched.conviction !== enriched.conviction;
        const edgeDelta = Number((enriched.expected_edge_pct || 0) - Number(prevEnriched?.expected_edge_pct || 0));
        const confDelta = Number((enriched.calibrated_confidence || 0) - Number(prevEnriched?.calibrated_confidence || 0));
        return {
          symbol: enriched.symbol,
          current_signal: enriched.final_signal,
          previous_signal: prevEnriched?.final_signal || null,
          current_conviction: enriched.conviction,
          previous_conviction: prevEnriched?.conviction || null,
          current_expected_edge_pct: enriched.expected_edge_pct || 0,
          previous_expected_edge_pct: prevEnriched?.expected_edge_pct ?? null,
          current_calibrated_confidence: enriched.calibrated_confidence || 0,
          previous_calibrated_confidence: prevEnriched?.calibrated_confidence ?? null,
          edge_delta_pct: Number(edgeDelta.toFixed(3)),
          confidence_delta: Number(confDelta.toFixed(2)),
          signal_changed: signalChanged,
          conviction_changed: convictionChanged,
          ranking_score: enriched.ranking_score || 0,
          changed: signalChanged || convictionChanged || Math.abs(edgeDelta) >= 0.25 || Math.abs(confDelta) >= 4
        };
      })
      .filter(item => item.changed)
      .sort((a, b) => {
        if (a.signal_changed !== b.signal_changed) return a.signal_changed ? -1 : 1;
        return Math.abs(b.edge_delta_pct) - Math.abs(a.edge_delta_pct);
      })
      .slice(0, limit);
    }

    let forecastChanges = [];
    if (req.userId) {
      const portfolioIdPh = DATABASE_URL ? '$1' : '?';
      const portfolioRunPh = DATABASE_URL ? '$2' : '?';
      const latestRuns = await dbAllAsync(
        `SELECT DISTINCT r.run_date
         FROM portfolio_forecast_results r
         JOIN forecast_portfolios fp ON fp.id = r.portfolio_id
         WHERE fp.user_id = ${portfolioIdPh}
         ORDER BY r.run_date DESC
         LIMIT 2`,
        [req.userId]
      ).catch(err => isTableMissing(err) ? [] : Promise.reject(err));

      const currentRun = latestRuns[0]?.run_date || null;
      const previousRun = latestRuns[1]?.run_date || null;
      if (currentRun && previousRun) {
        const currentRows = await dbAllAsync(
          `SELECT fp.name AS portfolio_name, r.portfolio_id, r.symbol, r.expected_return_pct
           FROM portfolio_forecast_results r
           JOIN forecast_portfolios fp ON fp.id = r.portfolio_id
           WHERE fp.user_id = ${portfolioIdPh}
             AND r.run_date = ${portfolioRunPh}`,
          [req.userId, currentRun]
        );
        const previousRows = await dbAllAsync(
          `SELECT r.portfolio_id, r.symbol, r.expected_return_pct
           FROM portfolio_forecast_results r
           JOIN forecast_portfolios fp ON fp.id = r.portfolio_id
           WHERE fp.user_id = ${portfolioIdPh}
             AND r.run_date = ${portfolioRunPh}`,
          [req.userId, previousRun]
        );
        const prevMap = new Map(previousRows.map(row => [`${row.portfolio_id}|${row.symbol}`, row]));
        forecastChanges = currentRows.map(row => {
          const prev = prevMap.get(`${row.portfolio_id}|${row.symbol}`);
          const currentVal = Number(row.expected_return_pct || 0);
          const previousVal = Number(prev?.expected_return_pct || 0);
          return {
            portfolio_name: row.portfolio_name,
            symbol: row.symbol,
            current_expected_return_pct: currentVal,
            previous_expected_return_pct: prev ? previousVal : null,
            delta_expected_return_pct: Number((currentVal - previousVal).toFixed(2))
          };
        })
        .filter(item => item.previous_expected_return_pct != null && Math.abs(item.delta_expected_return_pct) >= 1)
        .sort((a, b) => Math.abs(b.delta_expected_return_pct) - Math.abs(a.delta_expected_return_pct))
        .slice(0, 6);
      }
    }

    const macroChanges = [];
    try {
      const fxRows = await dbAllAsync(
        `SELECT date, usd_egp, gold_21k_egp_g
         FROM fx_rates_history
         ORDER BY date DESC
         LIMIT 2`,
        []
      );
      if (fxRows.length >= 2) {
        const latest = fxRows[0];
        const previous = fxRows[1];
        macroChanges.push({
          label: 'USD/EGP',
          current: Number(latest.usd_egp || 0),
          previous: Number(previous.usd_egp || 0),
          delta: Number((Number(latest.usd_egp || 0) - Number(previous.usd_egp || 0)).toFixed(4))
        });
        macroChanges.push({
          label: 'Gold 21K',
          current: Number(latest.gold_21k_egp_g || 0),
          previous: Number(previous.gold_21k_egp_g || 0),
          delta: Number((Number(latest.gold_21k_egp_g || 0) - Number(previous.gold_21k_egp_g || 0)).toFixed(2))
        });
      }
    } catch (err) {
      if (!isTableMissing(err)) throw err;
    }

    try {
      const regimes = await dbAllAsync(
        `SELECT date, regime FROM regime_log ORDER BY date DESC LIMIT 2`,
        []
      );
      if (regimes.length >= 1) {
        macroChanges.push({
          label: 'Market Regime',
          current: regimes[0].regime,
          previous: regimes[1]?.regime || null,
          delta: regimes[1] ? (regimes[0].regime === regimes[1].regime ? 0 : 1) : null
        });
      }
    } catch (err) {
      if (!isTableMissing(err)) throw err;
    }

    res.json({
      as_of: currentDate,
      signal_changes: signalChanges,
      forecast_changes: forecastChanges,
      macro_changes: macroChanges
    });
  } catch (err) {
    console.error('Error executing /api/intelligence/changes:', err);
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/intelligence/quality', optionalAuth, async (req, res) => {
  try {
    const freshness = {};
    const sources = [
      { key: 'prices', sql: `SELECT MAX(date) AS latest_value FROM prices`, thresholdHours: 36 },
      { key: 'predictions', sql: `SELECT MAX(prediction_date) AS latest_value FROM predictions`, thresholdHours: 36 },
      { key: 'consensus', sql: `SELECT MAX(prediction_date) AS latest_value FROM consensus_results`, thresholdHours: 36 },
      { key: 'news', sql: `SELECT MAX(date) AS latest_value FROM news`, thresholdHours: 24 },
      { key: 'sentiment', sql: `SELECT MAX(date) AS latest_value FROM sentiment_scores`, thresholdHours: 36 },
      { key: 'fx_rates', sql: `SELECT MAX(date) AS latest_value FROM fx_rates_history`, thresholdHours: 36 }
    ];

    for (const source of sources) {
      try {
        const row = await dbGetAsync(source.sql, []);
        const latestValue = row?.latest_value || null;
        const ageHours = ageHoursFromDate(latestValue);
        freshness[source.key] = {
          latest_value: latestValue,
          age_hours: ageHours == null ? null : Number(ageHours.toFixed(2)),
          status: freshnessStatus(ageHours, source.thresholdHours)
        };
      } catch (err) {
        freshness[source.key] = { latest_value: null, age_hours: null, status: isTableMissing(err) ? 'missing' : 'error' };
      }
    }

    if (req.userId) {
      try {
        const portfolioRow = await dbGetAsync(
          `SELECT MAX(updated_at) AS latest_value FROM forecast_portfolios WHERE user_id = ${DATABASE_URL ? '$1' : '?'}`,
          [req.userId]
        );
        const ageHours = ageHoursFromDate(portfolioRow?.latest_value || null);
        freshness.forecasts = {
          latest_value: portfolioRow?.latest_value || null,
          age_hours: ageHours == null ? null : Number(ageHours.toFixed(2)),
          status: freshnessStatus(ageHours, 72)
        };
      } catch (err) {
        freshness.forecasts = { latest_value: null, age_hours: null, status: isTableMissing(err) ? 'missing' : 'error' };
      }
    }

    const drift = [];
    try {
      const rows = await dbAllAsync(
        `SELECT agent_name, snapshot_date, win_rate_30d, win_rate_90d
         FROM agent_performance_daily
         ORDER BY snapshot_date DESC, agent_name ASC`,
        []
      );
      const latestByAgent = new Map();
      const previousByAgent = new Map();
      rows.forEach(row => {
        if (!latestByAgent.has(row.agent_name)) {
          latestByAgent.set(row.agent_name, row);
        } else if (!previousByAgent.has(row.agent_name)) {
          previousByAgent.set(row.agent_name, row);
        }
      });
      latestByAgent.forEach((row, agentName) => {
        const previous = previousByAgent.get(agentName);
        const win30 = Number(row.win_rate_30d || 0);
        const win90 = Number(row.win_rate_90d || 0);
        const prev30 = Number(previous?.win_rate_30d || win30);
        const driftGap = win30 - win90;
        const snapshotDelta = win30 - prev30;
        let status = 'stable';
        if (driftGap <= -10 || snapshotDelta <= -8) status = 'degrading';
        else if (driftGap >= 8 || snapshotDelta >= 8) status = 'improving';
        drift.push({
          agent_name: agentName,
          snapshot_date: row.snapshot_date,
          win_rate_30d: Number(win30.toFixed(2)),
          win_rate_90d: Number(win90.toFixed(2)),
          drift_gap: Number(driftGap.toFixed(2)),
          snapshot_delta: Number(snapshotDelta.toFixed(2)),
          status
        });
      });
    } catch (err) {
      if (!isTableMissing(err)) throw err;
    }

    const freshnessStatuses = Object.values(freshness).map(item => item.status);
    const degradingAgents = drift.filter(item => item.status === 'degrading').length;
    const overallStatus = freshnessStatuses.includes('stale') || freshnessStatuses.includes('error')
      ? 'attention'
      : degradingAgents > 0
        ? 'watch'
        : 'healthy';

    res.json({
      overall_status: overallStatus,
      freshness,
      drift
    });
  } catch (err) {
    console.error('Error executing /api/intelligence/quality:', err);
    res.status(500).json({ error: err.message });
  }
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
         calibrated_confidence, expected_edge_pct, ranking_score,
         risk_adjusted, agent_agreement, agents_agreeing, agents_total,
         majority_direction, bull_score, bear_score, risk_action, risk_score,
         display_json, risk_assessment_json, calibration_meta_json, weight_profile_json
       FROM consensus_results
       ORDER BY symbol, prediction_date DESC`
    : `SELECT c.symbol, c.prediction_date, c.final_signal, c.conviction, c.confidence, c.xmore_score,
         c.calibrated_confidence, c.expected_edge_pct, c.ranking_score,
         c.risk_adjusted, c.agent_agreement, c.agents_agreeing, c.agents_total,
         c.majority_direction, c.bull_score, c.bear_score, c.risk_action, c.risk_score,
         c.display_json, c.risk_assessment_json, c.calibration_meta_json, c.weight_profile_json
       FROM consensus_results c
       INNER JOIN (
         SELECT symbol, MAX(prediction_date) as max_date
         FROM consensus_results
         GROUP BY symbol
       ) latest ON c.symbol = latest.symbol AND c.prediction_date = latest.max_date
       ORDER BY c.symbol`;

  db.all(query, [], async (err, rows) => {
    if (err) {
      if (err.message && (err.message.includes('does not exist') || err.message.includes('no such table'))) {
        res.json([]);
      } else {
        res.status(500).json({ error: err.message });
      }
    } else {
      const calibrationState = await buildConsensusCalibrationState();
      const edgeState = await buildExpectedEdgeState();
      const parsed = (rows || []).map(row => {
        try {
          row.display = row.display_json ? JSON.parse(row.display_json) : {};
          row.risk_assessment = row.risk_assessment_json ? JSON.parse(row.risk_assessment_json) : {};
          row.calibration_meta = row.calibration_meta_json ? JSON.parse(row.calibration_meta_json) : {};
          row.weight_profile = row.weight_profile_json ? JSON.parse(row.weight_profile_json) : {};
        } catch (e) {
          row.display = {};
          row.risk_assessment = {};
          row.calibration_meta = {};
          row.weight_profile = {};
        }
        delete row.display_json;
        delete row.risk_assessment_json;
        delete row.calibration_meta_json;
        delete row.weight_profile_json;
        return enrichConsensusRow(row, calibrationState, edgeState);
      }).sort((a, b) => {
        const diff = Number(b.ranking_score || 0) - Number(a.ranking_score || 0);
        return diff !== 0 ? diff : String(a.symbol).localeCompare(String(b.symbol));
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
      symbol, prediction_date, final_signal, conviction, confidence, xmore_score,
      calibrated_confidence, expected_edge_pct, ranking_score,
      risk_adjusted, agent_agreement, agents_agreeing, agents_total,
      majority_direction, bull_score, bear_score, risk_action, risk_score,
      bull_case_json, bear_case_json, risk_assessment_json,
      agent_signals_json, reasoning_chain_json, display_json,
      calibration_meta_json, weight_profile_json
    FROM consensus_results
    WHERE symbol = ${placeholder}
    ORDER BY prediction_date DESC
    LIMIT 1
  `;

  db.get(query, [symbol], async (err, row) => {
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
        row.calibration_meta = row.calibration_meta_json ? JSON.parse(row.calibration_meta_json) : {};
        row.weight_profile = row.weight_profile_json ? JSON.parse(row.weight_profile_json) : {};
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
      delete row.calibration_meta_json;
      delete row.weight_profile_json;
      const calibrationState = await buildConsensusCalibrationState();
      const edgeState = await buildExpectedEdgeState();
      res.json(enrichConsensusRow(row, calibrationState, edgeState));
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
// DERIVATIVES â€” Black-Scholes computed inline (no external service)
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
    if (!egp || !sar) throw new Error('Missing EGP/SAR rates');
    // Fetch gold spot price from Yahoo Finance (GC=F futures, USD/troy oz)
    const TROY_OZ_TO_GRAMS = 31.1035;
    let goldData = {};
    try {
      const goldRaw = await new Promise((resolve, reject) => {
        https.get(
          'https://query1.finance.yahoo.com/v8/finance/chart/GC%3DF?interval=1d&range=1d',
          { headers: { 'User-Agent': 'Mozilla/5.0' } },
          (r) => {
            let body = '';
            r.on('data', d => body += d);
            r.on('end', () => { try { resolve(JSON.parse(body)); } catch (e) { reject(e); } });
          }
        ).on('error', reject);
      });
      const xauUsd = goldRaw?.chart?.result?.[0]?.meta?.regularMarketPrice;
      if (xauUsd && xauUsd > 0) {
        const gold24K = (xauUsd / TROY_OZ_TO_GRAMS) * egp;
        goldData = {
          XAU_USD:         +xauUsd.toFixed(2),
          GOLD_24K_EGP_G:  +gold24K.toFixed(2),
          GOLD_21K_EGP_G:  +(gold24K * 21 / 24).toFixed(2),
          GOLD_18K_EGP_G:  +(gold24K * 18 / 24).toFixed(2),
          GOLD_POUND_EGP:  +(gold24K * 21 / 24 * 8).toFixed(2),
        };
      }
    } catch (_) { /* gold fetch failed â€” omit gold fields */ }
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
// PER-STOCK BRIEF
// ============================================
const _briefCache = new Map(); // symbol -> { text, ts }

app.get('/api/stocks/:symbol/brief', async (req, res) => {
  const symbol = (req.params.symbol || '').toUpperCase().replace(/[^A-Z0-9.]/g, '');
  if (!symbol) return res.status(400).json({ error: 'Invalid symbol' });

  // Serve cache if fresh (1h)
  const cached = _briefCache.get(symbol);
  if (cached && Date.now() - cached.ts < 3_600_000) return res.json({ brief: cached.text, symbol, cached: true });

  const GOOGLE_API_KEY = process.env.GOOGLE_API_KEY;
  if (!GOOGLE_API_KEY) return res.status(503).json({ error: 'Brief service not configured' });

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
    const https = require('https');
    const body = JSON.stringify({ contents: [{ parts: [{ text: prompt }] }] });
    const text = await new Promise((resolve, reject) => {
      const req = https.request({
        hostname: 'generativelanguage.googleapis.com',
        path: `/v1beta/models/gemini-2.5-flash:generateContent?key=${GOOGLE_API_KEY}`,
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) },
      }, r => {
        let d = '';
        r.on('data', c => d += c);
        r.on('end', () => {
          try {
            const j = JSON.parse(d);
            resolve(j?.candidates?.[0]?.content?.parts?.[0]?.text || 'Brief unavailable.');
          } catch (e) { reject(e); }
        });
      });
      req.on('error', reject);
      req.write(body);
      req.end();
    });
    _briefCache.set(symbol, { text, ts: Date.now() });
    res.json({ brief: text, symbol });
  } catch (err) {
    res.status(502).json({ error: 'Brief failed: ' + err.message });
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

app.get('/track-record', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'track-record.html'));
});

app.use((err, req, res, next) => {
  if (!err) return next();

  const isApiRequest = req.path.startsWith('/api/');
  if (!isApiRequest) return next(err);

  if (err instanceof SyntaxError && err.status === 400 && 'body' in err) {
    return res.status(400).json({ error: 'Invalid JSON payload' });
  }

  console.error('API error middleware:', err.stack || err.message || err);
  return res.status(err.status || 500).json({ error: err.message || 'Internal server error' });
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

console.log(`â³ Starting server on port ${PORT}...`);
app.listen(PORT, '0.0.0.0', () => {
  console.log(`ðŸš€ Server running on port ${PORT}`);
  console.log(`ðŸ“Š Dashboard available`);
});

