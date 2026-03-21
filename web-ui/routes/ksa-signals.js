/**
 * KSA Signals API Routes
 * All queries partition by market_id = 'KSA'
 * Mirrors EGX signal routes with SAR currency and .SR tickers
 */
'use strict';

const express = require('express');
const router  = express.Router();

let db, isPostgres;
function attachDb(_db, _pg) { db = _db; isPostgres = _pg; }

const ph = (n) => isPostgres ? `$${n}` : '?';
const simFilter = () => isPostgres
    ? `(is_simulated = FALSE OR is_simulated IS NULL)`
    : `(is_simulated = 0 OR is_simulated IS NULL)`;

// GET /api/ksa/signals/latest — last 20 KSA signals
router.get('/signals/latest', async (req, res) => {
    try {
        const rows = await db.all(`
            SELECT symbol, final_signal, conviction, xmore_score, confidence,
                   bull_score, bear_score, agent_agreement, timestamp,
                   drivers_json, risk_level, expected_move
            FROM consensus_results
            WHERE market_id = 'KSA'
            ORDER BY timestamp DESC
            LIMIT 20
        `);
        const result = rows.map(r => ({
            ...r,
            drivers: (() => { try { return JSON.parse(r.drivers_json || '[]'); } catch { return []; } })(),
            drivers_json: undefined,
        }));
        res.json({ available: true, signals: result });
    } catch (e) {
        console.error('[KSA] /signals/latest error:', e);
        res.status(500).json({ error: 'Failed to load KSA signals' });
    }
});

// GET /api/ksa/signals/today — today's pre-market signals
router.get('/signals/today', async (req, res) => {
    try {
        const dateClause = isPostgres
            ? `DATE(timestamp) = CURRENT_DATE`
            : `DATE(timestamp) = DATE('now')`;
        const rows = await db.all(`
            SELECT symbol, final_signal, conviction, xmore_score, confidence,
                   bull_score, bear_score, agent_agreement, timestamp,
                   drivers_json, risk_level, expected_move, regime_flag
            FROM consensus_results
            WHERE market_id = 'KSA'
              AND ${dateClause}
            ORDER BY xmore_score DESC
        `);
        const result = rows.map(r => ({
            ...r,
            drivers: (() => { try { return JSON.parse(r.drivers_json || '[]'); } catch { return []; } })(),
            drivers_json: undefined,
        }));
        res.json({ available: true, date: new Date().toISOString().slice(0, 10), signals: result });
    } catch (e) {
        res.status(500).json({ error: 'Failed to load today\'s KSA signals' });
    }
});

// GET /api/ksa/performance/summary — KSA win rate, Sharpe, profit factor
router.get('/performance/summary', async (req, res) => {
    try {
        const rows = await db.all(`
            SELECT actual_next_day_return, benchmark_1d_return, was_correct,
                   alpha_1d, recommendation_date
            FROM trade_recommendations
            WHERE market_id = 'KSA'
              AND actual_next_day_return IS NOT NULL
              AND ${simFilter()}
            ORDER BY recommendation_date ASC
        `);

        if (!rows.length) return res.json({ available: false, message: 'No KSA evaluated signals yet.' });

        const toNum = v => Number(v || 0);
        const mean  = arr => arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : 0;
        const stdev = arr => {
            if (arr.length < 2) return 0;
            const m = mean(arr);
            return Math.sqrt(arr.reduce((a, v) => a + (v - m) ** 2, 0) / (arr.length - 1));
        };

        // KSA: SAIBOR 3M 4.89% annual
        const SAIBOR_3M  = 0.0489;
        const TRADING_DAYS = 250;
        const dailyRf    = Math.pow(1 + SAIBOR_3M, 1 / TRADING_DAYS) - 1;

        const returns    = rows.map(r => toNum(r.actual_next_day_return));
        const bench      = rows.map(r => toNum(r.benchmark_1d_return));
        const wins       = rows.filter(r => r.was_correct === true || r.was_correct === 1 || r.was_correct === 't').length;
        const winRate    = rows.length ? (wins / rows.length) * 100 : 0;

        const m = mean(returns), s = stdev(returns);
        const sharpe  = s > 0 ? ((m - dailyRf) / s) * Math.sqrt(TRADING_DAYS) : 0;

        const profits = returns.filter(v => v > 0).reduce((a, b) => a + b, 0);
        const losses  = Math.abs(returns.filter(v => v < 0).reduce((a, b) => a + b, 0));
        const pf      = losses > 0 ? profits / losses : (profits > 0 ? 99 : 0);

        const alpha30rows = rows.slice(-30);
        const alpha30 = mean(alpha30rows.map((r, i) => toNum(r.actual_next_day_return) - toNum(r.benchmark_1d_return)));

        res.json({
            available:     true,
            total_signals: rows.length,
            win_rate:      Number(winRate.toFixed(1)),
            sharpe_ratio:  Number(sharpe.toFixed(2)),
            profit_factor: Number(pf.toFixed(2)),
            alpha_30d:     Number((alpha30 * 100).toFixed(2)),
            risk_free_rate: 'SAIBOR 3M 4.89%',
            currency:      'SAR',
        });
    } catch (e) {
        console.error('[KSA] performance/summary error:', e);
        res.status(500).json({ error: 'Failed to load KSA performance' });
    }
});

// GET /api/ksa/regime — current TASI regime
router.get('/regime', async (req, res) => {
    try {
        const row = await db.get(`
            SELECT regime_label_en, regime_label_ar, regime_confidence,
                   n_regimes, trading_date
            FROM regime_log
            WHERE market_id = 'KSA'
            ORDER BY trading_date DESC
            LIMIT 1
        `);
        if (!row) return res.json({ available: false, label: 'Unknown' });
        res.json({ available: true, ...row });
    } catch (e) {
        res.json({ available: false, label: 'Unknown' });
    }
});

// GET /api/ksa/signals/:ticker/history
router.get('/signals/:ticker/history', async (req, res) => {
    const ticker = req.params.ticker.toUpperCase();
    try {
        const rows = await db.all(`
            SELECT symbol, final_signal, conviction, xmore_score, timestamp,
                   bull_score, bear_score, agent_agreement, regime_flag
            FROM consensus_results
            WHERE market_id = 'KSA'
              AND symbol = ${ph(1)}
            ORDER BY timestamp DESC
            LIMIT 60
        `, [ticker]);
        res.json({ available: true, ticker, history: rows });
    } catch (e) {
        res.status(500).json({ error: 'Failed to load ticker history' });
    }
});

// GET /api/ksa/health
router.get('/health', async (req, res) => {
    try {
        const row = await db.get(`SELECT COUNT(*) AS cnt FROM consensus_results WHERE market_id = 'KSA'`);
        res.json({ status: 'ok', market: 'KSA', total_signals: Number(row?.cnt || 0) });
    } catch (e) {
        res.status(500).json({ status: 'error', error: e.message });
    }
});

module.exports = { router, attachDb };
