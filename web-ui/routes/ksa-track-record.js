/**
 * KSA Track Record API Routes
 * CRITICAL: ALL queries use (is_simulated = FALSE OR is_simulated IS NULL)
 * NULL rows are live signals — never exclude them.
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

function dbAll(query, params = []) {
    return new Promise((resolve, reject) => {
        db.all(query, params, (err, rows) => err ? reject(err) : resolve(rows || []));
    });
}

function dbGet(query, params = []) {
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

// Shared helpers
const toNum  = v => Number(v || 0);
const mean   = arr => arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : 0;
const stdev  = arr => {
    if (arr.length < 2) return 0;
    const m = mean(arr);
    return Math.sqrt(arr.reduce((a, v) => a + (v - m) ** 2, 0) / (arr.length - 1));
};
const SAIBOR_3M    = 0.0489;
const TRADING_DAYS = 250;
const dailyRf      = Math.pow(1 + SAIBOR_3M, 1 / TRADING_DAYS) - 1;
const sharpeKsa    = arr => {
    const s = stdev(arr);
    return s > 0 ? ((mean(arr) - dailyRf) / s) * Math.sqrt(TRADING_DAYS) : 0;
};
const maxDrawdown  = arr => {
    let cum = 0, peak = 0, mdd = 0;
    arr.forEach(r => { cum += r; if (cum > peak) peak = cum; const dd = peak - cum; if (dd > mdd) mdd = dd; });
    return mdd;
};

// GET /api/ksa/track-record/summary
router.get('/track-record/summary', async (req, res) => {
    try {
        const rows = await dbAll(`
            SELECT actual_next_day_return, benchmark_1d_return, was_correct,
                   alpha_1d, recommendation_date
            FROM trade_recommendations
            WHERE market_id = 'KSA'
              AND symbol LIKE '%.SR'
              AND actual_next_day_return IS NOT NULL
              AND ${simFilter()}
            ORDER BY recommendation_date ASC
        `);

        if (!rows.length) return res.json({ available: false });

        const returns  = rows.map(r => toNum(r.actual_next_day_return));
        const bench    = rows.map(r => toNum(r.benchmark_1d_return));
        const wins     = rows.filter(r => r.was_correct === true || r.was_correct === 1 || r.was_correct === 't').length;
        const total    = rows.length;
        const winRate  = total ? (wins / total) * 100 : 0;
        const sharpe   = sharpeKsa(returns);
        const mdd      = maxDrawdown(returns);
        const alpha30  = rows.slice(-30);
        const alpha30v = mean(alpha30.map((r, i) => toNum(r.actual_next_day_return) - toNum(bench[total - 30 + i])));

        res.json({
            available: true,
            total_signals: total,
            win_rate:      Number(winRate.toFixed(1)),
            sharpe_ratio:  Number(sharpe.toFixed(2)),
            max_drawdown:  Number((mdd * 100).toFixed(2)),
            alpha_30d:     Number((alpha30v * 100).toFixed(3)),
            first_signal:  rows[0].recommendation_date,
            last_signal:   rows[total - 1].recommendation_date,
            risk_free:     'SAIBOR 3M 4.89%',
            benchmark:     'TASI',
            currency:      'SAR',
        });
    } catch (e) {
        console.error('[KSA] track-record/summary error:', e);
        res.status(500).json({ error: 'Failed to load KSA track record summary' });
    }
});

// GET /api/ksa/track-record/equity-curve
router.get('/track-record/equity-curve', async (req, res) => {
    try {
        const rows = await dbAll(`
            SELECT recommendation_date, actual_next_day_return, benchmark_1d_return
            FROM trade_recommendations
            WHERE market_id = 'KSA'
              AND symbol LIKE '%.SR'
              AND actual_next_day_return IS NOT NULL
              AND ${simFilter()}
            ORDER BY recommendation_date ASC
        `);

        let xmoreCum = 0, tasiCum = 0;
        const series = rows.map(r => {
            xmoreCum += toNum(r.actual_next_day_return);
            tasiCum  += toNum(r.benchmark_1d_return);
            return {
                date:        String(r.recommendation_date).slice(0, 10),
                xmore:       Math.round(xmoreCum * 100) / 100,
                tasi:        Math.round(tasiCum * 100) / 100,
                alpha:       Math.round((xmoreCum - tasiCum) * 100) / 100,
            };
        });

        const xmore = series.map(point => ({ time: point.date, value: point.xmore }));
        const benchmark = series.map(point => ({ time: point.date, value: point.tasi }));

        res.json({
            available:   series.length > 0,
            series,
            xmore,
            benchmark,
            total_xmore: series.length ? series[series.length - 1].xmore : 0,
            total_tasi:  series.length ? series[series.length - 1].tasi : 0,
            total_alpha: series.length ? series[series.length - 1].alpha : 0,
        });
    } catch (e) {
        res.status(500).json({ error: 'Failed to load equity curve' });
    }
});

// GET /api/ksa/track-record/agent-breakdown
router.get('/track-record/agent-breakdown', async (req, res) => {
    try {
        const rows = await dbAll(`
            SELECT agent_name,
                   COUNT(*) AS total,
                   SUM(CASE WHEN was_correct ${isPostgres ? '= TRUE' : '= 1'} THEN 1 ELSE 0 END) AS correct,
                   AVG(actual_next_day_return) AS avg_return
            FROM trade_recommendations
            WHERE market_id = 'KSA'
              AND symbol LIKE '%.SR'
              AND actual_next_day_return IS NOT NULL
              AND ${simFilter()}
            GROUP BY agent_name
            ORDER BY ${isPostgres ? 'correct::float' : 'CAST(correct AS REAL)'} / NULLIF(total, 0) DESC
        `);

        res.json({
            available: rows.length > 0,
            agents: rows.map(r => ({
                agent:      r.agent_name,
                total:      Number(r.total),
                correct:    Number(r.correct),
                win_rate:   r.total > 0 ? Number(((r.correct / r.total) * 100).toFixed(1)) : 0,
                avg_return: Number((toNum(r.avg_return) * 100).toFixed(3)),
            })),
        });
    } catch (e) {
        res.status(500).json({ error: 'Failed to load agent breakdown' });
    }
});

// GET /api/ksa/track-record/predictions?page=1&per_page=50
router.get('/track-record/predictions', async (req, res) => {
    const page    = Math.max(1, parseInt(req.query.page || '1'));
    const perPage = Math.min(100, parseInt(req.query.per_page || '50'));
    const offset  = (page - 1) * perPage;

    try {
        const countRow = await dbGet(`
            SELECT COUNT(*) AS cnt FROM trade_recommendations
            WHERE market_id = 'KSA' AND symbol LIKE '%.SR' AND ${simFilter()}
        `);
        const total = Number(countRow?.cnt || 0);

        let rows = [];
        try {
            rows = await dbAll(`
                SELECT recommendation_date, symbol, signal_type,
                       actual_next_day_return, was_correct, alpha_1d,
                       xmore_score, notes
                FROM trade_recommendations
                WHERE market_id = 'KSA'
                  AND symbol LIKE '%.SR'
                  AND ${simFilter()}
                ORDER BY recommendation_date DESC
                LIMIT ${ph(1)} OFFSET ${ph(2)}
            `, [perPage, offset]);
        } catch (err) {
            if (!isTableMissing(err)) throw err;
        }

        const predictions = rows.map(row => ({
            date: row.recommendation_date,
            trading_date: row.recommendation_date,
            symbol: row.symbol,
            ticker: row.symbol,
            signal: row.signal_type || 'HOLD',
            outcome: row.was_correct == null
                ? 'pending'
                : (row.was_correct === true || row.was_correct === 1 || row.was_correct === 't')
                    ? 'correct'
                    : 'incorrect',
            alpha: row.alpha_1d != null ? Number(row.alpha_1d) * 100 : null,
            alpha_pct: row.alpha_1d != null ? Number(row.alpha_1d) * 100 : null,
            dcf_label: null,
            valuation_label: null,
            shariah_compliant: null,
            xmore_score: row.xmore_score != null ? Number(row.xmore_score) : null,
            notes: row.notes || null,
        }));

        res.json({
            available:   true,
            total,
            page,
            per_page:    perPage,
            total_pages: Math.ceil(total / perPage),
            predictions,
        });
    } catch (e) {
        res.status(500).json({ error: 'Failed to load predictions' });
    }
});

// GET /api/ksa/track-record/signals/batch?ids=1,2,3
router.get('/track-record/signals/batch', async (req, res) => {
    const ids = (req.query.ids || '').split(',').map(Number).filter(Boolean).slice(0, 50);
    if (!ids.length) return res.json({ signals: [] });

    try {
        const placeholders = ids.map((_, i) => ph(i + 1)).join(',');
        const rows = await dbAll(`
            SELECT id, symbol, final_signal, conviction, xmore_score, timestamp,
                   bull_score, bear_score, agent_agreement
            FROM consensus_results
            WHERE market_id = 'KSA'
              AND symbol LIKE '%.SR'
              AND id IN (${placeholders})
        `, ids);
        res.json({ signals: rows });
    } catch (e) {
        res.status(500).json({ error: 'Failed to load batch signals' });
    }
});

module.exports = { router, attachDb };
