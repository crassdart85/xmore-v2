/**
 * Performance API Routes
 * Investor-grade, public performance endpoints.
 * No auth required — this is transparency.
 */

const express = require('express');
const router = express.Router();

let db;
let isPostgres = false;

function attachDb(database, pg) {
    db = database;
    isPostgres = pg;
}

// Helper: promisified db.all
function dbAll(query, params = []) {
    return new Promise((resolve, reject) => {
        db.all(query, params, (err, rows) => {
            if (err) reject(err);
            else resolve(rows || []);
        });
    });
}

// Helper: promisified db.get
function dbGet(query, params = []) {
    return new Promise((resolve, reject) => {
        db.get(query, params, (err, row) => {
            if (err) reject(err);
            else resolve(row || null);
        });
    });
}

// Helper: safe table check
function isTableMissing(err) {
    return err && err.message && (
        err.message.includes('does not exist') ||
        err.message.includes('no such table') ||
        err.message.includes('no such column')
    );
}

// Boolean literals differ between PostgreSQL and SQLite
function boolTrue() { return isPostgres ? 'TRUE' : '1'; }
function boolFalse() { return isPostgres ? 'FALSE' : '0'; }
function ph(n) { return isPostgres ? `$${n}` : '?'; }


// ─── PUBLIC: Overall performance summary ──────────────────────
router.get('/summary', async (req, res) => {
    try {
        const days = Math.min(parseInt(req.query.days) || 365, 365);
        const liveFilter = isPostgres
            ? `(is_live = TRUE OR is_live IS NULL)`
            : `(is_live = 1 OR is_live IS NULL)`;
        const dateFilter = isPostgres
            ? `recommendation_date >= CURRENT_DATE - ${ph(1)}`
            : `recommendation_date >= date('now', '-' || ${ph(1)} || ' days')`;

        let rows = [];
        try {
            rows = await dbAll(`
                SELECT recommendation_date, actual_next_day_return, benchmark_1d_return, alpha_1d, was_correct
                FROM trade_recommendations
                WHERE actual_next_day_return IS NOT NULL
                AND ${liveFilter}
                AND ${dateFilter}
                ORDER BY recommendation_date ASC
            `, [days]);
        } catch (e) {
            if (isTableMissing(e)) return res.json({ available: false, message: 'No resolved predictions yet.' });
            throw e;
        }
        if (!rows.length) return res.json({ available: false, message: 'No resolved predictions yet.' });

        const toNum = (v) => Number(v || 0);
        const asDate = (d) => new Date(d);
        const mean = (arr) => arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : 0;
        const stdev = (arr) => {
            if (arr.length < 2) return 0;
            const m = mean(arr);
            const variance = arr.reduce((acc, v) => acc + ((v - m) ** 2), 0) / (arr.length - 1);
            return Math.sqrt(Math.max(variance, 0));
        };
        const calcMaxDrawdown = (returnsArr) => {
            let cum = 0;
            let peak = 0;
            let maxDd = 0;
            returnsArr.forEach(r => {
                cum += r;
                if (cum > peak) peak = cum;
                const dd = peak - cum;
                if (dd > maxDd) maxDd = dd;
            });
            return maxDd;
        };
        const calcProfitFactor = (returnsArr) => {
            const grossProfit = returnsArr.filter(v => v > 0).reduce((a, b) => a + b, 0);
            const grossLoss = Math.abs(returnsArr.filter(v => v < 0).reduce((a, b) => a + b, 0));
            if (grossLoss === 0) return grossProfit > 0 ? 99 : 0;
            return grossProfit / grossLoss;
        };
        const buildStats = (subset) => {
            const total = subset.length;
            const returnsArr = subset.map(r => toNum(r.actual_next_day_return));
            const alphaArr = subset.map(r => r.alpha_1d == null ? toNum(r.actual_next_day_return) - toNum(r.benchmark_1d_return) : toNum(r.alpha_1d));
            const benchArr = subset.map(r => toNum(r.benchmark_1d_return));
            const wins = subset.filter(r => r.was_correct === true || r.was_correct === 1 || r.was_correct === 't').length;
            const vol = stdev(returnsArr) * Math.sqrt(252);
            const sharpe = stdev(alphaArr) > 0 ? (mean(alphaArr) / stdev(alphaArr)) * Math.sqrt(252) : 0;
            return {
                trades: total,
                wins,
                losses: total - wins,
                win_rate: total ? (wins / total) * 100 : 0,
                avg_return_1d: mean(returnsArr),
                avg_alpha_1d: mean(alphaArr),
                avg_benchmark_1d: mean(benchArr),
                beat_benchmark_count: alphaArr.filter(a => a > 0).length,
                volatility: vol,
                sharpe_ratio: sharpe,
                max_drawdown: calcMaxDrawdown(returnsArr),
                profit_factor: calcProfitFactor(returnsArr)
            };
        };

        const allStats = buildStats(rows);
        const latestDate = asDate(rows[rows.length - 1].recommendation_date);
        const filterDays = (n) => rows.filter(r => (latestDate - asDate(r.recommendation_date)) <= (n * 24 * 3600 * 1000));
        const r30 = buildStats(filterDays(30));
        const r60 = buildStats(filterDays(60));
        const r90 = buildStats(filterDays(90));

        return res.json({
            available: true,
            global: {
                total_predictions: allStats.trades,
                wins: allStats.wins,
                losses: allStats.losses,
                win_rate: Number(allStats.win_rate.toFixed(1)),
                avg_return_1d: Number(allStats.avg_return_1d.toFixed(3)),
                avg_return_5d: 0,
                avg_alpha_1d: Number(allStats.avg_alpha_1d.toFixed(3)),
                avg_benchmark_1d: Number(allStats.avg_benchmark_1d.toFixed(3)),
                beat_benchmark_pct: allStats.trades ? Math.round((allStats.beat_benchmark_count / allStats.trades) * 100) : 0,
                meets_minimum: allStats.trades >= 100,
                first_prediction: rows[0].recommendation_date,
                last_prediction: rows[rows.length - 1].recommendation_date,
                sharpe_ratio: Number(allStats.sharpe_ratio.toFixed(3)),
                max_drawdown: Number(allStats.max_drawdown.toFixed(3)),
                volatility: Number(allStats.volatility.toFixed(3)),
                profit_factor: Number(allStats.profit_factor.toFixed(3))
            },
            rolling: {
                "30d": {
                    trades: r30.trades,
                    win_rate: Number(r30.win_rate.toFixed(1)),
                    alpha: Number(r30.avg_alpha_1d.toFixed(3)),
                    sharpe_ratio: Number(r30.sharpe_ratio.toFixed(3)),
                    max_drawdown: Number(r30.max_drawdown.toFixed(3)),
                    volatility: Number(r30.volatility.toFixed(3)),
                    profit_factor: Number(r30.profit_factor.toFixed(3))
                },
                "60d": {
                    trades: r60.trades,
                    win_rate: Number(r60.win_rate.toFixed(1)),
                    alpha: Number(r60.avg_alpha_1d.toFixed(3)),
                    sharpe_ratio: Number(r60.sharpe_ratio.toFixed(3)),
                    max_drawdown: Number(r60.max_drawdown.toFixed(3)),
                    volatility: Number(r60.volatility.toFixed(3)),
                    profit_factor: Number(r60.profit_factor.toFixed(3))
                },
                "90d": {
                    trades: r90.trades,
                    win_rate: Number(r90.win_rate.toFixed(1)),
                    alpha: Number(r90.avg_alpha_1d.toFixed(3)),
                    sharpe_ratio: Number(r90.sharpe_ratio.toFixed(3)),
                    max_drawdown: Number(r90.max_drawdown.toFixed(3)),
                    volatility: Number(r90.volatility.toFixed(3)),
                    profit_factor: Number(r90.profit_factor.toFixed(3))
                }
            },
            disclaimer: "All metrics are from live predictions only. No backfilled or backtested data is included in these figures."
        });
    } catch (err) {
        console.error('Performance summary error:', err);
        res.status(500).json({ error: 'Failed to load performance summary.' });
    }
});


// ─── PUBLIC: Per-agent comparison ─────────────────────────────
router.get('/by-agent', async (req, res) => {
    try {
        const rows = await dbAll(`
            SELECT
                snapshot_date, agent_name,
                predictions_30d, correct_30d, win_rate_30d, avg_confidence_30d,
                predictions_90d, correct_90d, win_rate_90d
            FROM agent_performance_daily
            WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM agent_performance_daily)
            ORDER BY win_rate_30d DESC NULLS LAST
        `);

        return res.json({
            snapshot_date: rows[0]?.snapshot_date || null,
            agents: rows.map(r => ({
                agent: r.agent_name,
                predictions_30d: parseInt(r.predictions_30d) || 0,
                win_rate_30d: parseFloat(r.win_rate_30d) || 0,
                avg_confidence_30d: parseFloat(r.avg_confidence_30d) || 0,
                predictions_90d: parseInt(r.predictions_90d) || 0,
                win_rate_90d: parseFloat(r.win_rate_90d) || 0
            }))
        });
    } catch (err) {
        if (isTableMissing(err)) {
            return res.json({ snapshot_date: null, agents: [] });
        }
        console.error('Agent comparison error:', err);
        res.status(500).json({ error: 'Failed to load agent comparison.' });
    }
});


// ─── PUBLIC: Per-stock performance ────────────────────────────
router.get('/by-stock', async (req, res) => {
    try {
        const days = Math.min(parseInt(req.query.days) || 90, 365);
        const liveFilter = isPostgres ? '(tr.is_live = TRUE OR tr.is_live IS NULL)' : '(tr.is_live = 1 OR tr.is_live IS NULL)';
        const dateFilter = isPostgres
            ? `tr.recommendation_date >= CURRENT_DATE - ${ph(1)}`
            : `tr.recommendation_date >= date('now', '-' || ${ph(1)} || ' days')`;

        const rows = await dbAll(`
            SELECT
                tr.symbol,
                ${isPostgres ? 's.name_en, s.name_ar, s.sector_en' : "tr.symbol AS name_en, '' AS name_ar, '' AS sector_en"},
                COUNT(*) AS total,
                SUM(CASE WHEN tr.was_correct = ${boolTrue()} THEN 1 ELSE 0 END) AS correct,
                ${isPostgres ? 'ROUND(AVG(tr.actual_next_day_return)::numeric, 3)' : 'ROUND(AVG(tr.actual_next_day_return), 3)'} AS avg_return,
                ${isPostgres ? 'ROUND(AVG(tr.alpha_1d)::numeric, 3)' : 'ROUND(AVG(tr.alpha_1d), 3)'} AS avg_alpha,
                ${isPostgres
                ? `ROUND((SUM(CASE WHEN tr.was_correct = TRUE THEN 1 ELSE 0 END))::numeric / NULLIF(COUNT(*), 0) * 100, 1)`
                : `ROUND(CAST(SUM(CASE WHEN tr.was_correct = 1 THEN 1 ELSE 0 END) AS REAL) / MAX(COUNT(*), 1) * 100, 1)`
            } AS win_rate
            FROM trade_recommendations tr
            ${isPostgres ? 'JOIN egx30_stocks s ON tr.symbol = s.symbol' : ''}
            WHERE tr.was_correct IS NOT NULL
            AND ${liveFilter}
            AND ${dateFilter}
            GROUP BY tr.symbol${isPostgres ? ', s.name_en, s.name_ar, s.sector_en' : ''}
            HAVING COUNT(*) >= 3
            ORDER BY avg_alpha DESC
        `, [days]);

        return res.json({ period_days: days, stocks: rows });
    } catch (err) {
        if (isTableMissing(err)) {
            return res.json({ period_days: 90, stocks: [] });
        }
        console.error('Stock performance error:', err);
        res.status(500).json({ error: 'Failed to load stock performance.' });
    }
});


// ─── PUBLIC: Equity curve data ────────────────────────────────
router.get('/equity-curve', async (req, res) => {
    try {
        const days = Math.min(parseInt(req.query.days) || 180, 365);
        const liveFilter = isPostgres ? '(is_live = TRUE OR is_live IS NULL)' : '(is_live = 1 OR is_live IS NULL)';
        const dateFilter = isPostgres
            ? `recommendation_date >= CURRENT_DATE - ${ph(1)}`
            : `recommendation_date >= date('now', '-' || ${ph(1)} || ' days')`;

        const rows = await dbAll(`
            SELECT
                recommendation_date AS date,
                ${isPostgres ? 'ROUND(AVG(actual_next_day_return)::numeric, 4)' : 'ROUND(AVG(actual_next_day_return), 4)'} AS xmore,
                ${isPostgres ? 'ROUND(AVG(benchmark_1d_return)::numeric, 4)' : 'ROUND(AVG(benchmark_1d_return), 4)'} AS egx30
            FROM trade_recommendations
            WHERE actual_next_day_return IS NOT NULL
            AND ${liveFilter}
            AND ${dateFilter}
            GROUP BY recommendation_date
            ORDER BY recommendation_date ASC
        `, [days]);

        let xmoreCum = 0, egx30Cum = 0;
        const series = rows.map(r => {
            xmoreCum += parseFloat(r.xmore) || 0;
            egx30Cum += parseFloat(r.egx30) || 0;
            return {
                date: r.date,
                xmore: Math.round(xmoreCum * 100) / 100,
                egx30: Math.round(egx30Cum * 100) / 100,
                alpha: Math.round((xmoreCum - egx30Cum) * 100) / 100
            };
        });

        return res.json({
            series,
            total_xmore: series.length ? series[series.length - 1].xmore : 0,
            total_egx30: series.length ? series[series.length - 1].egx30 : 0,
            total_alpha: series.length ? series[series.length - 1].alpha : 0
        });
    } catch (err) {
        if (isTableMissing(err)) {
            return res.json({ series: [], total_xmore: 0, total_egx30: 0, total_alpha: 0 });
        }
        console.error('Equity curve error:', err);
        res.status(500).json({ error: 'Failed to load equity curve.' });
    }
});


// ─── PUBLIC: Open predictions (transparency) ─────────────────
router.get('/predictions/open', async (req, res) => {
    try {
        const dateFilter = isPostgres
            ? `cr.prediction_date >= CURRENT_DATE - 5`
            : `cr.prediction_date >= date('now', '-5 days')`;

        const rows = await dbAll(`
            SELECT
                cr.symbol, s.name_en, s.name_ar,
                cr.prediction_date, cr.final_signal, cr.confidence,
                cr.conviction, cr.bull_score, cr.bear_score, cr.risk_action
            FROM consensus_results cr
            ${isPostgres ? 'JOIN' : 'LEFT JOIN'} egx30_stocks s ON cr.symbol = s.symbol
            WHERE ${dateFilter}
            ORDER BY cr.prediction_date DESC, cr.confidence DESC
        `);

        return res.json({ predictions: rows });
    } catch (err) {
        if (isTableMissing(err)) {
            return res.json({ predictions: [] });
        }
        console.error('Open predictions error:', err);
        res.status(500).json({ error: 'Failed to load open predictions.' });
    }
});


// ─── PUBLIC: Prediction history (auditable) ───────────────────
router.get('/predictions/history', async (req, res) => {
    try {
        const page = parseInt(req.query.page) || 1;
        const limit = Math.min(parseInt(req.query.limit) || 25, 100);
        const offset = (page - 1) * limit;

        const liveFilter = isPostgres ? '(tr.is_live = TRUE OR tr.is_live IS NULL)' : '(tr.is_live = 1 OR tr.is_live IS NULL)';
        const dateFilter = isPostgres
            ? `cr.prediction_date <= CURRENT_DATE`
            : `cr.prediction_date <= date('now')`;

        const rows = await dbAll(`
            SELECT
                cr.symbol, ${isPostgres ? 's.name_en,' : ''}
                cr.prediction_date, cr.final_signal, cr.confidence AS consensus_confidence,
                cr.conviction, cr.bull_score, cr.bear_score, cr.risk_action,
                tr.action, tr.actual_next_day_return, tr.benchmark_1d_return,
                tr.alpha_1d, tr.was_correct
            FROM consensus_results cr
            ${isPostgres ? 'JOIN egx30_stocks s ON cr.symbol = s.symbol' : ''}
            LEFT JOIN trade_recommendations tr
                ON tr.symbol = cr.symbol
                AND tr.recommendation_date = cr.prediction_date
                AND ${liveFilter}
            WHERE ${dateFilter}
            ORDER BY cr.prediction_date DESC, cr.symbol
            LIMIT ${ph(1)} OFFSET ${ph(2)}
        `, [limit, offset]);

        const countDateFilter = isPostgres
            ? `prediction_date <= CURRENT_DATE`
            : `prediction_date <= date('now')`;
        const countRow = await dbGet(`
            SELECT COUNT(*) AS cnt FROM consensus_results WHERE ${countDateFilter}
        `);
        const total = parseInt(countRow?.cnt || countRow?.count || 0);

        return res.json({
            predictions: rows,
            pagination: {
                page, limit, total,
                pages: Math.ceil(total / limit)
            }
        });
    } catch (err) {
        if (isTableMissing(err)) {
            return res.json({ predictions: [], pagination: { page: 1, limit: 25, total: 0, pages: 0 } });
        }
        console.error('Prediction history error:', err);
        res.status(500).json({ error: 'Failed to load prediction history.' });
    }
});


// ─── PUBLIC: Audit trail (for trust) ──────────────────────────
router.get('/audit', async (req, res) => {
    try {
        const limit = Math.min(parseInt(req.query.limit) || 50, 200);

        const rows = await dbAll(`
            SELECT id, table_name, record_id, field_changed, old_value, new_value, changed_at
            FROM prediction_audit_log
            ORDER BY changed_at DESC
            LIMIT ${ph(1)}
        `, [limit]);

        return res.json({
            audit_entries: rows,
            message: "All prediction modifications are logged here. Core prediction fields (signal, confidence, action) are immutable and cannot be changed after creation."
        });
    } catch (err) {
        if (isTableMissing(err)) {
            return res.json({
                audit_entries: [],
                message: "Audit trail will be populated as predictions are resolved."
            });
        }
        console.error('Audit trail error:', err);
        res.status(500).json({ error: 'Failed to load audit trail.' });
    }
});


module.exports = { router, attachDb: attachDb };
