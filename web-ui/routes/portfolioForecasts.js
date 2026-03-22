'use strict';
/**
 * Portfolio Forecasts Routes
 * All endpoints under /api/portfolio-forecasts
 *
 * GET    /                  — list user's portfolios
 * POST   /                  — create portfolio
 * PUT    /:id               — update portfolio
 * DELETE /:id               — delete portfolio
 * POST   /:id/run           — run forecasts for all stocks, store results
 * GET    /:id/results       — latest forecast results + evaluation status
 * GET    /:id/history       — all historical runs with accuracy
 */

const express = require('express');
const router = express.Router();
const { authMiddleware } = require('../middleware/auth');
const { simulateStock } = require('../services/forecastEngine');
const { resolveMarketSymbol } = require('../services/marketUniverse');

let _db = null;
let _isPostgres = false;

function attachDb(db, isPostgres) {
    _db = db;
    _isPostgres = !!isPostgres;
}

// ── DB helpers ──────────────────────────────────────────────────────────────

function ph(n) { return _isPostgres ? `$${n}` : '?'; }

function dbAll(query, params) {
    return new Promise((resolve, reject) => {
        _db.all(query, params, (err, rows) => {
            if (err) reject(err); else resolve(rows || []);
        });
    });
}

function dbGet(query, params) {
    return new Promise((resolve, reject) => {
        _db.get(query, params, (err, row) => {
            if (err) reject(err); else resolve(row || null);
        });
    });
}

function dbRun(query, params) {
    return new Promise((resolve, reject) => {
        if (_db.run) {
            _db.run(query, params, function (err) {
                if (err) reject(err);
                else resolve({ changes: this ? this.changes : 0, lastID: this ? this.lastID : null });
            });
        } else {
            // PostgreSQL via pool returns result directly
            _db.all(query, params, (err, rows) => {
                if (err) reject(err);
                else resolve({ rows, changes: rows ? rows.length : 0 });
            });
        }
    });
}

function normSql(q) {
    if (_isPostgres) return q.replace(/\?/g, (_, i) => { let c = 0; return q.slice(0, _).replace(/\?/g, () => `$${++c}`) && `$${++c}`; });
    return q;
}

// Simpler placeholder replacement for postgres
function adaptSql(sql) {
    if (!_isPostgres) return sql;
    let i = 0;
    return sql.replace(/\?/g, () => `$${++i}`);
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function parseSymbols(json) {
    try { return JSON.parse(json) || []; } catch { return []; }
}

const VALID_SCENARIOS = ['base', 'bull', 'bear'];
const MAX_STOCKS = 30;

// ── Routes ───────────────────────────────────────────────────────────────────

// GET / — list portfolios for authenticated user
router.get('/', authMiddleware, async (req, res) => {
    try {
        const userId = req.userId;
        const rows = await dbAll(
            adaptSql('SELECT id, name, symbols_json, horizon_days, scenario, investment_amount, created_at, updated_at FROM forecast_portfolios WHERE user_id = ? ORDER BY updated_at DESC'),
            [userId]
        );
        const portfolios = rows.map(r => ({
            ...r,
            symbols: parseSymbols(r.symbols_json),
        }));
        res.json({ portfolios });
    } catch (err) {
        console.error('GET /portfolio-forecasts error:', err);
        res.status(500).json({ error: err.message });
    }
});

// POST / — create portfolio
router.post('/', authMiddleware, async (req, res) => {
    try {
        const userId = req.userId;
        const { name, symbols, horizon_days = 63, scenario = 'base', investment_amount = 10000 } = req.body;

        if (!name || !name.trim()) return res.status(400).json({ error: 'Portfolio name is required' });
        if (!Array.isArray(symbols) || symbols.length === 0) return res.status(400).json({ error: 'At least one stock is required' });
        if (symbols.length > MAX_STOCKS) return res.status(400).json({ error: `Maximum ${MAX_STOCKS} stocks per portfolio` });
        if (!VALID_SCENARIOS.includes(scenario)) return res.status(400).json({ error: 'Invalid scenario' });

        const symbolsJson = JSON.stringify(symbols.map(s => String(s).trim().toUpperCase()));

        if (_isPostgres) {
            const result = await dbAll(
                'INSERT INTO forecast_portfolios (user_id, name, symbols_json, horizon_days, scenario, investment_amount) VALUES ($1,$2,$3,$4,$5,$6) RETURNING id',
                [userId, name.trim(), symbolsJson, horizon_days, scenario, investment_amount]
            );
            return res.json({ ok: true, id: result[0].id });
        } else {
            const r = await dbRun(
                'INSERT INTO forecast_portfolios (user_id, name, symbols_json, horizon_days, scenario, investment_amount) VALUES (?,?,?,?,?,?)',
                [userId, name.trim(), symbolsJson, horizon_days, scenario, investment_amount]
            );
            return res.json({ ok: true, id: r.lastID });
        }
    } catch (err) {
        if (err.message && err.message.includes('UNIQUE')) return res.status(409).json({ error: 'A portfolio with this name already exists' });
        console.error('POST /portfolio-forecasts error:', err);
        res.status(500).json({ error: err.message });
    }
});

// PUT /:id — update portfolio
router.put('/:id', authMiddleware, async (req, res) => {
    try {
        const userId = req.userId;
        const id = parseInt(req.params.id);
        const { name, symbols, horizon_days, scenario, investment_amount } = req.body;

        const portfolio = await dbGet(adaptSql('SELECT id, user_id FROM forecast_portfolios WHERE id = ? AND user_id = ?'), [id, userId]);
        if (!portfolio) return res.status(404).json({ error: 'Portfolio not found' });

        const updates = [];
        const params = [];

        if (name !== undefined) { updates.push('name = ?'); params.push(name.trim()); }
        if (symbols !== undefined) {
            if (symbols.length > MAX_STOCKS) return res.status(400).json({ error: `Maximum ${MAX_STOCKS} stocks per portfolio` });
            updates.push('symbols_json = ?');
            params.push(JSON.stringify(symbols.map(s => String(s).trim().toUpperCase())));
        }
        if (horizon_days !== undefined) { updates.push('horizon_days = ?'); params.push(horizon_days); }
        if (scenario !== undefined) {
            if (!VALID_SCENARIOS.includes(scenario)) return res.status(400).json({ error: 'Invalid scenario' });
            updates.push('scenario = ?'); params.push(scenario);
        }
        if (investment_amount !== undefined) { updates.push('investment_amount = ?'); params.push(investment_amount); }
        updates.push('updated_at = CURRENT_TIMESTAMP');

        if (updates.length === 1) return res.json({ ok: true }); // only timestamp

        params.push(id);
        await dbRun(adaptSql(`UPDATE forecast_portfolios SET ${updates.join(', ')} WHERE id = ?`), params);
        res.json({ ok: true });
    } catch (err) {
        console.error('PUT /portfolio-forecasts/:id error:', err);
        res.status(500).json({ error: err.message });
    }
});

// DELETE /:id — delete portfolio
router.delete('/:id', authMiddleware, async (req, res) => {
    try {
        const userId = req.userId;
        const id = parseInt(req.params.id);
        const portfolio = await dbGet(adaptSql('SELECT id FROM forecast_portfolios WHERE id = ? AND user_id = ?'), [id, userId]);
        if (!portfolio) return res.status(404).json({ error: 'Portfolio not found' });
        await dbRun(adaptSql('DELETE FROM forecast_portfolios WHERE id = ?'), [id]);
        res.json({ ok: true });
    } catch (err) {
        console.error('DELETE /portfolio-forecasts/:id error:', err);
        res.status(500).json({ error: err.message });
    }
});

// POST /:id/run — run forecasts for all stocks in portfolio, store results
router.post('/:id/run', authMiddleware, async (req, res) => {
    try {
        const userId = req.userId;
        const id = parseInt(req.params.id);

        const portfolio = await dbGet(adaptSql('SELECT * FROM forecast_portfolios WHERE id = ? AND user_id = ?'), [id, userId]);
        if (!portfolio) return res.status(404).json({ error: 'Portfolio not found' });

        const symbols = parseSymbols(portfolio.symbols_json);
        if (symbols.length === 0) return res.status(400).json({ error: 'Portfolio has no stocks' });

        const horizon = portfolio.horizon_days || 63;
        const scenario = portfolio.scenario || 'base';
        const amount = portfolio.investment_amount || 10000;

        const today = new Date().toISOString().split('T')[0];
        const targetDate = new Date(Date.now() + horizon * 24 * 60 * 60 * 1000).toISOString().split('T')[0];

        // Run all forecasts in parallel
        const forecastPromises = symbols.map(async (symbol) => {
            try {
                const sym = await resolveMarketSymbol(symbol, _db);
                const result = await simulateStock(sym, amount, horizon, scenario, _db);
                return { symbol: sym, result };
            } catch (err) {
                return { symbol, result: { ok: false, error: String(err.message || err) } };
            }
        });

        const forecasts = await Promise.all(forecastPromises);

        // Store each result, upsert on conflict
        const stored = [];
        for (const { symbol, result } of forecasts) {
            const ok = result.ok !== false ? 1 : 0;
            const params = [
                id, symbol, today, targetDate, horizon, scenario, amount,
                ok ? (result.expected_return_pct ?? null) : null,
                ok ? (result.probability_positive ?? null) : null,
                ok ? (result.worst_case_value != null ? ((result.worst_case_value - amount) / amount * 100) : null) : null,
                ok ? (result.median_value    != null ? ((result.median_value    - amount) / amount * 100) : null) : null,
                ok ? (result.best_case_value != null ? ((result.best_case_value - amount) / amount * 100) : null) : null,
                ok ? (result.volatility_annual_pct ?? null) : null,
                ok ? (result.data_points ?? null) : null,
                ok,
                ok ? null : (result.error || 'unknown error'),
            ];

            if (_isPostgres) {
                await dbAll(
                    `INSERT INTO portfolio_forecast_results
                     (portfolio_id, symbol, run_date, target_date, horizon_days, scenario, investment_amount,
                      expected_return_pct, probability_positive, worst_case_pct, median_pct, best_case_pct,
                      volatility_annual_pct, data_points, ok, error_reason)
                     VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
                     ON CONFLICT (portfolio_id, symbol, run_date, horizon_days, scenario)
                     DO UPDATE SET
                       expected_return_pct = EXCLUDED.expected_return_pct,
                       probability_positive = EXCLUDED.probability_positive,
                       worst_case_pct = EXCLUDED.worst_case_pct,
                       median_pct = EXCLUDED.median_pct,
                       best_case_pct = EXCLUDED.best_case_pct,
                       volatility_annual_pct = EXCLUDED.volatility_annual_pct,
                       data_points = EXCLUDED.data_points,
                       ok = EXCLUDED.ok,
                       error_reason = EXCLUDED.error_reason`,
                    params
                );
            } else {
                await dbRun(
                    `INSERT OR REPLACE INTO portfolio_forecast_results
                     (portfolio_id, symbol, run_date, target_date, horizon_days, scenario, investment_amount,
                      expected_return_pct, probability_positive, worst_case_pct, median_pct, best_case_pct,
                      volatility_annual_pct, data_points, ok, error_reason)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`,
                    params
                );
            }

            stored.push({
                symbol,
                ok: !!ok,
                run_date: today,
                target_date: targetDate,
                horizon_days: horizon,
                scenario,
                investment_amount: amount,
                expected_return_pct:   ok ? result.expected_return_pct   : null,
                probability_positive:  ok ? result.probability_positive  : null,
                worst_case_pct:        ok ? (result.worst_case_value != null ? ((result.worst_case_value - amount) / amount * 100) : null) : null,
                median_pct:            ok ? (result.median_value    != null ? ((result.median_value    - amount) / amount * 100) : null) : null,
                best_case_pct:         ok ? (result.best_case_value != null ? ((result.best_case_value - amount) / amount * 100) : null) : null,
                volatility_annual_pct: ok ? result.volatility_annual_pct : null,
                data_points:           ok ? result.data_points           : null,
                error_reason:          ok ? null : (result.error || 'unknown error'),
            });
        }

        // Update portfolio timestamp
        await dbRun(adaptSql('UPDATE forecast_portfolios SET updated_at = CURRENT_TIMESTAMP WHERE id = ?'), [id]);

        res.json({ ok: true, run_date: today, target_date: targetDate, results: stored });
    } catch (err) {
        console.error('POST /portfolio-forecasts/:id/run error:', err);
        res.status(500).json({ error: err.message });
    }
});

// GET /:id/results — latest forecast results + evaluation status
router.get('/:id/results', authMiddleware, async (req, res) => {
    try {
        const userId = req.userId;
        const id = parseInt(req.params.id);

        const portfolio = await dbGet(adaptSql('SELECT * FROM forecast_portfolios WHERE id = ? AND user_id = ?'), [id, userId]);
        if (!portfolio) return res.status(404).json({ error: 'Portfolio not found' });

        // Get latest run date
        const latest = await dbGet(adaptSql('SELECT MAX(run_date) as run_date FROM portfolio_forecast_results WHERE portfolio_id = ?'), [id]);
        if (!latest || !latest.run_date) return res.json({ portfolio, results: [], run_date: null });

        const runDate = latest.run_date;

        // Get results + evaluations for the latest run
        const rows = await dbAll(adaptSql(`
            SELECT r.*,
                   e.actual_return_pct, e.actual_close, e.error_pct,
                   e.within_5pct, e.within_10pct, e.evaluated_at,
                   CASE WHEN e.id IS NOT NULL THEN 1 ELSE 0 END as evaluated
            FROM portfolio_forecast_results r
            LEFT JOIN portfolio_forecast_evaluations e ON r.id = e.forecast_result_id
            WHERE r.portfolio_id = ? AND r.run_date = ?
            ORDER BY r.expected_return_pct DESC NULLS LAST
        `), [id, runDate]);

        // Fetch latest daily actual per symbol for in-progress tracking
        let dailyMap = {};
        try {
            const dailyRows = await dbAll(adaptSql(`
                SELECT da.symbol, da.date as daily_date, da.actual_close as daily_close,
                       da.return_pct_from_start as daily_return_pct
                FROM portfolio_daily_actuals da
                WHERE da.portfolio_id = ?
                  AND da.date = (
                      SELECT MAX(da2.date) FROM portfolio_daily_actuals da2
                      WHERE da2.portfolio_id = da.portfolio_id AND da2.symbol = da.symbol
                  )
            `), [id]);
            for (const dr of dailyRows) dailyMap[dr.symbol] = dr;
        } catch (_) { /* table may not exist yet on older deployments */ }

        // Compute progress days
        const today = new Date().toISOString().split('T')[0];
        const results = rows.map(r => {
            const runMs    = new Date(r.run_date).getTime();
            const todayMs  = new Date(today).getTime();
            const daysPast = Math.max(0, Math.round((todayMs - runMs) / 86400000));
            const daily    = dailyMap[r.symbol] || null;
            return {
                ...r,
                days_elapsed:     daysPast,
                daily_date:       daily ? daily.daily_date   : null,
                daily_close:      daily ? daily.daily_close  : null,
                daily_return_pct: daily ? daily.daily_return_pct : null,
            };
        });

        res.json({
            portfolio: { ...portfolio, symbols: parseSymbols(portfolio.symbols_json) },
            run_date: runDate,
            results,
        });
    } catch (err) {
        console.error('GET /portfolio-forecasts/:id/results error:', err);
        res.status(500).json({ error: err.message });
    }
});

// GET /:id/history — all runs with accuracy summary
router.get('/:id/history', authMiddleware, async (req, res) => {
    try {
        const userId = req.userId;
        const id = parseInt(req.params.id);

        const portfolio = await dbGet(adaptSql('SELECT id FROM forecast_portfolios WHERE id = ? AND user_id = ?'), [id, userId]);
        if (!portfolio) return res.status(404).json({ error: 'Portfolio not found' });

        const rows = await dbAll(adaptSql(`
            SELECT r.run_date, r.target_date, r.horizon_days, r.scenario,
                   COUNT(r.id)                                    AS stock_count,
                   COUNT(e.id)                                    AS evaluated_count,
                   ROUND(AVG(e.error_pct), 2)                    AS avg_error_pct,
                   ROUND(AVG(CASE WHEN e.within_10pct THEN 1.0 ELSE 0.0 END) * 100, 1) AS within_10pct_rate
            FROM portfolio_forecast_results r
            LEFT JOIN portfolio_forecast_evaluations e ON r.id = e.forecast_result_id
            WHERE r.portfolio_id = ?
            GROUP BY r.run_date, r.target_date, r.horizon_days, r.scenario
            ORDER BY r.run_date DESC
        `), [id]);

        res.json({ history: rows });
    } catch (err) {
        console.error('GET /portfolio-forecasts/:id/history error:', err);
        res.status(500).json({ error: err.message });
    }
});

module.exports = { router, attachDb };
