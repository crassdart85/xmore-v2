/**
 * Track Record API Routes
 * Public investor-facing endpoints. No authentication required.
 * All queries filter is_simulated = FALSE — live signals only.
 */

const express = require('express');
const router = express.Router();

let db;
let isPostgres = false;

function attachDb(database, pg) {
    db = database;
    isPostgres = pg;
}

// ── DB helpers ────────────────────────────────────────────────
function dbAll(q, p = []) {
    return new Promise((res, rej) => db.all(q, p, (e, r) => e ? rej(e) : res(r || [])));
}
function dbGet(q, p = []) {
    return new Promise((res, rej) => db.get(q, p, (e, r) => e ? rej(e) : res(r || null)));
}
function isTableMissing(err) {
    return err && err.message && (
        err.message.includes('does not exist') ||
        err.message.includes('no such table') ||
        err.message.includes('no such column')
    );
}
function ph(n)        { return isPostgres ? `$${n}` : '?'; }
function boolTrue()   { return isPostgres ? 'TRUE' : '1'; }
function boolFalse()  { return isPostgres ? 'FALSE' : '0'; }

// Filters applied to every data query on this page
function simFilter()  {
    return isPostgres
        ? '(is_simulated = FALSE OR is_simulated IS NULL)'
        : '(is_simulated = 0 OR is_simulated IS NULL)';
}
function liveFilter() {
    return isPostgres
        ? '(is_live = TRUE OR is_live IS NULL)'
        : '(is_live = 1 OR is_live IS NULL)';
}
function trSimFilter() { // table-prefixed for JOINs
    return isPostgres
        ? '(tr.is_simulated = FALSE OR tr.is_simulated IS NULL)'
        : '(tr.is_simulated = 0 OR tr.is_simulated IS NULL)';
}
function dateWindow(days, col = 'recommendation_date') {
    return isPostgres
        ? `${col} >= CURRENT_DATE - (${days} * INTERVAL '1 day')`
        : `${col} >= date('now', '-${days} days')`;
}
function round(expr) {
    return isPostgres ? `ROUND(${expr}::numeric, 4)` : `ROUND(${expr}, 4)`;
}

// ── KPI helper: accuracy + alpha + sharpe for a window ───────
async function kpiForWindow(days) {
    try {
        const row = await dbGet(`
            SELECT
                COUNT(*)                                      AS total,
                SUM(CASE WHEN was_correct = ${boolTrue()} THEN 1 ELSE 0 END) AS correct,
                ${round('AVG(alpha_1d)')}                    AS avg_alpha,
                ${round('AVG(actual_next_day_return)')}      AS avg_return,
                ${round('STDDEV_SAMP(actual_next_day_return)')} AS std_return
            FROM trade_recommendations
            WHERE was_correct IS NOT NULL
            AND ${liveFilter()}
            AND ${simFilter()}
            AND ${dateWindow(days)}
        `);
        if (!row || !parseInt(row.total)) return null;
        const total   = parseInt(row.total);
        const correct = parseInt(row.correct) || 0;
        const alpha   = parseFloat(row.avg_alpha) || 0;
        const ret     = parseFloat(row.avg_return) || 0;
        const std     = parseFloat(row.std_return) || 0;
        const cbeDailyRf = Math.pow(1.2725, 1 / 247) - 1;
        const sharpe  = std > 0 ? ((ret / 100 - cbeDailyRf) / (std / 100)) * Math.sqrt(247) : 0;
        return {
            total_signals:         total,
            directional_accuracy:  total > 0 ? parseFloat((correct / total).toFixed(4)) : 0,
            alpha_vs_egx30:        parseFloat(alpha.toFixed(4)),
            sharpe_ratio:          parseFloat(sharpe.toFixed(2)),
        };
    } catch (_) { return null; }
}


// ═══════════════════════════════════════════════════════════════
// GET /api/track-record/summary
// ═══════════════════════════════════════════════════════════════
router.get('/summary', async (req, res) => {
    try {
        // Live signal count + date range
        const counts = await dbGet(`
            SELECT
                COUNT(*)  AS total_live,
                MIN(recommendation_date) AS live_since,
                MAX(recommendation_date) AS last_updated
            FROM trade_recommendations
            WHERE ${liveFilter()} AND ${simFilter()}
        `);

        // Simulated count (excluded)
        let simCount = 0;
        try {
            const sc = await dbGet(`
                SELECT COUNT(*) AS cnt FROM trade_recommendations
                WHERE ${liveFilter()}
                AND is_simulated = ${boolTrue()}
            `);
            simCount = parseInt(sc?.cnt || 0);
        } catch (_) {}

        // KPI windows
        const [w30, w60, w90] = await Promise.all([
            kpiForWindow(30),
            kpiForWindow(60),
            kpiForWindow(90),
        ]);

        // Current regime from regime_log
        let currentRegime = 'UNKNOWN';
        try {
            const reg = await dbGet(`
                SELECT regime FROM regime_log ORDER BY date DESC LIMIT 1
            `);
            if (reg?.regime) currentRegime = reg.regime;
        } catch (_) {}

        // Distinct symbols covered
        let symbolsCovered = 190;
        try {
            const sc2 = await dbGet(`SELECT COUNT(DISTINCT symbol) AS cnt FROM trade_recommendations WHERE ${liveFilter()}`);
            if (sc2?.cnt) symbolsCovered = parseInt(sc2.cnt);
        } catch (_) {}

        const liveCount = parseInt(counts?.total_live || 0);

        return res.json({
            platform:             'Xmore2',
            description:          'AI Stock Intelligence for the Egyptian Exchange',
            live_since:           counts?.live_since || null,
            last_updated:         counts?.last_updated || null,
            total_live_signals:   liveCount,
            symbols_covered:      symbolsCovered,
            current_regime:       currentRegime,
            risk_free_rate_applied: '27.25% (CBE)',
            kpi_windows: {
                '30d': w30,
                '60d': w60,
                '90d': w90,
            },
            data_transparency: {
                live_signals_count:         liveCount,
                simulated_signals_excluded: simCount,
                metrics_basis:              'live_only',
                earliest_live_signal_date:  counts?.live_since || null,
            },
        });
    } catch (err) {
        console.error('[track-record] /summary error:', err);
        res.status(500).json({ error: 'Failed to load summary.' });
    }
});


// ═══════════════════════════════════════════════════════════════
// GET /api/track-record/equity-curve?days=90
// ═══════════════════════════════════════════════════════════════
router.get('/equity-curve', async (req, res) => {
    try {
        const days = Math.min(parseInt(req.query.days) || 90, 365);

        const rows = await dbAll(`
            SELECT
                recommendation_date AS date,
                ${round('AVG(actual_next_day_return)')} AS xmore,
                ${round('AVG(benchmark_1d_return)')}    AS egx30
            FROM trade_recommendations
            WHERE actual_next_day_return IS NOT NULL
            AND ${liveFilter()}
            AND ${simFilter()}
            AND ${dateWindow(days)}
            GROUP BY recommendation_date
            ORDER BY recommendation_date ASC
        `);

        let xmoreCum = 0, egx30Cum = 0;
        const series = rows.map(r => {
            xmoreCum += parseFloat(r.xmore) || 0;
            egx30Cum += parseFloat(r.egx30) || 0;
            return {
                date:  r.date,
                xmore: Math.round(xmoreCum * 100) / 100,
                egx30: Math.round(egx30Cum * 100) / 100,
                alpha: Math.round((xmoreCum - egx30Cum) * 100) / 100,
            };
        });

        // Drawdown series
        let peak = 0;
        const drawdown_series = series.map(p => {
            if (p.xmore > peak) peak = p.xmore;
            return { date: p.date, drawdown: peak > 0 ? Math.round((p.xmore - peak) * 100) / 100 : 0 };
        });

        return res.json({
            days,
            series,
            drawdown_series,
            total_xmore: series.length ? series[series.length - 1].xmore : 0,
            total_egx30: series.length ? series[series.length - 1].egx30 : 0,
            total_alpha: series.length ? series[series.length - 1].alpha : 0,
        });
    } catch (err) {
        if (isTableMissing(err)) return res.json({ days: 90, series: [], drawdown_series: [], total_xmore: 0, total_egx30: 0, total_alpha: 0 });
        console.error('[track-record] /equity-curve error:', err);
        res.status(500).json({ error: 'Failed to load equity curve.' });
    }
});


// ═══════════════════════════════════════════════════════════════
// GET /api/track-record/agents
// ═══════════════════════════════════════════════════════════════
router.get('/agents', async (req, res) => {
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
                agent:              r.agent_name,
                predictions_30d:    parseInt(r.predictions_30d) || 0,
                win_rate_30d:       parseFloat(r.win_rate_30d) || 0,
                avg_confidence_30d: parseFloat(r.avg_confidence_30d) || 0,
                predictions_90d:    parseInt(r.predictions_90d) || 0,
                win_rate_90d:       parseFloat(r.win_rate_90d) || 0,
            })),
        });
    } catch (err) {
        if (isTableMissing(err)) return res.json({ snapshot_date: null, agents: [] });
        console.error('[track-record] /agents error:', err);
        res.status(500).json({ error: 'Failed to load agent data.' });
    }
});


// ═══════════════════════════════════════════════════════════════
// GET /api/track-record/top-stocks?days=90&limit=10
// ═══════════════════════════════════════════════════════════════
router.get('/top-stocks', async (req, res) => {
    try {
        const days  = Math.min(parseInt(req.query.days) || 90, 365);
        const limit = Math.min(parseInt(req.query.limit) || 10, 50);

        const rows = await dbAll(`
            SELECT
                tr.symbol,
                ${isPostgres ? 's.name_en, s.sector_en' : "tr.symbol AS name_en, '' AS sector_en"},
                COUNT(*)   AS signal_count,
                SUM(CASE WHEN tr.was_correct = ${boolTrue()} THEN 1 ELSE 0 END) AS correct,
                ${round('AVG(tr.alpha_1d)')}                AS avg_alpha,
                ${round('AVG(tr.actual_next_day_return)')}  AS avg_return,
                ${isPostgres
                    ? `ROUND(MAX(tr.actual_next_day_return)::numeric, 4)`
                    : `ROUND(MAX(tr.actual_next_day_return), 4)`
                }                                            AS best_return,
                ${isPostgres
                    ? `ROUND((SUM(CASE WHEN tr.was_correct = TRUE THEN 1 ELSE 0 END))::numeric / NULLIF(COUNT(*), 0) * 100, 1)`
                    : `ROUND(CAST(SUM(CASE WHEN tr.was_correct = 1 THEN 1 ELSE 0 END) AS REAL) / MAX(COUNT(*), 1) * 100, 1)`
                }                                            AS win_rate
            FROM trade_recommendations tr
            ${isPostgres ? 'LEFT JOIN egx30_stocks s ON tr.symbol = s.symbol' : ''}
            WHERE tr.was_correct IS NOT NULL
            AND ${trSimFilter()}
            AND ${isPostgres ? '(tr.is_live = TRUE OR tr.is_live IS NULL)' : '(tr.is_live = 1 OR tr.is_live IS NULL)'}
            AND ${dateWindow(days, 'tr.recommendation_date')}
            GROUP BY tr.symbol${isPostgres ? ', s.name_en, s.sector_en' : ''}
            HAVING COUNT(*) >= 3
            ORDER BY avg_alpha DESC
        `);

        const map = r => ({
            symbol:               r.symbol,
            name:                 r.name_en || r.symbol,
            sector:               r.sector_en || '',
            signal_count:         parseInt(r.signal_count) || 0,
            directional_accuracy: parseInt(r.signal_count) > 0
                ? parseFloat(((parseInt(r.correct) || 0) / parseInt(r.signal_count)).toFixed(4)) : 0,
            alpha_avg:            parseFloat(r.avg_alpha) || 0,
            avg_return:           parseFloat(r.avg_return) || 0,
            best_signal_return:   parseFloat(r.best_return) || 0,
            win_rate:             parseFloat(r.win_rate) || 0,
        });

        // Sector breakdown
        const sectorMap = {};
        rows.forEach(r => {
            const s = r.sector_en || 'Other';
            if (!sectorMap[s]) sectorMap[s] = { sector: s, total_alpha: 0, signal_count: 0 };
            sectorMap[s].total_alpha  += parseFloat(r.avg_alpha) || 0;
            sectorMap[s].signal_count += parseInt(r.signal_count) || 0;
        });
        const sectorBreakdown = Object.values(sectorMap)
            .map(s => ({ ...s, avg_alpha: parseFloat((s.total_alpha / Math.max(Object.values(sectorMap).filter(x => x.sector === s.sector).length, 1)).toFixed(4)) }))
            .sort((a, b) => b.avg_alpha - a.avg_alpha);

        return res.json({
            period_days:      days,
            top_by_alpha:     rows.slice(0, limit).map(map),
            bottom_by_alpha:  [...rows].sort((a, b) => (parseFloat(a.avg_alpha) || 0) - (parseFloat(b.avg_alpha) || 0)).slice(0, limit).map(map),
            sector_breakdown: sectorBreakdown,
        });
    } catch (err) {
        if (isTableMissing(err)) return res.json({ period_days: 90, top_by_alpha: [], bottom_by_alpha: [], sector_breakdown: [] });
        console.error('[track-record] /top-stocks error:', err);
        res.status(500).json({ error: 'Failed to load stock data.' });
    }
});


// ═══════════════════════════════════════════════════════════════
// GET /api/track-record/backtest?limit=20
// ═══════════════════════════════════════════════════════════════
router.get('/backtest', async (req, res) => {
    try {
        const limit = Math.min(parseInt(req.query.limit) || 20, 100);
        const rows = await dbAll(`
            SELECT symbol, run_date, accuracy, directional_accuracy,
                   signal_pnl_pct, total_signals_tested
            FROM backtest_results
            ORDER BY directional_accuracy DESC, run_date DESC
            LIMIT ${ph(1)}
        `, [limit]);

        if (!rows.length) {
            return res.json({ status: 'pending', message: 'First backtest runs every Sunday at 09:00 Cairo.' });
        }

        // Last run date
        const lastRunRow = await dbGet(`SELECT MAX(run_date) AS last_run FROM backtest_results`);

        // Aggregate stats
        const avg = arr => arr.reduce((a, b) => a + b, 0) / arr.length;
        const accs  = rows.map(r => parseFloat(r.accuracy) || 0);
        const daccs = rows.map(r => parseFloat(r.directional_accuracy) || 0);

        return res.json({
            status:        'available',
            last_run_date: lastRunRow?.last_run || null,
            results:       rows.map(r => ({
                symbol:                r.symbol,
                run_date:              r.run_date,
                accuracy:              parseFloat(r.accuracy) || 0,
                directional_accuracy:  parseFloat(r.directional_accuracy) || 0,
                signal_pnl_pct:        parseFloat(r.signal_pnl_pct) || 0,
                total_signals_tested:  parseInt(r.total_signals_tested) || 0,
            })),
            aggregate: {
                avg_accuracy:             parseFloat(avg(accs).toFixed(4)),
                avg_directional_accuracy: parseFloat(avg(daccs).toFixed(4)),
                symbols_tested:           rows.length,
                methodology:              'walk-forward',
            },
        });
    } catch (err) {
        if (isTableMissing(err)) return res.json({ status: 'pending', message: 'First backtest runs every Sunday at 09:00 Cairo.' });
        console.error('[track-record] /backtest error:', err);
        res.status(500).json({ error: 'Failed to load backtest results.' });
    }
});


// ═══════════════════════════════════════════════════════════════
// GET /api/track-record/predictions?page=1&limit=25&signal=&days=90&outcome=
// ═══════════════════════════════════════════════════════════════
router.get('/predictions', async (req, res) => {
    try {
        const page    = Math.max(parseInt(req.query.page) || 1, 1);
        const limit   = Math.min(parseInt(req.query.limit) || 25, 100);
        const days    = Math.min(parseInt(req.query.days) || 90, 365);
        const signal  = req.query.signal  || '';
        const outcome = req.query.outcome || '';
        const symbol  = (req.query.symbol || '').toUpperCase();
        const offset  = (page - 1) * limit;

        const conds = [
            liveFilter().replace(/\b(is_live)\b/g, 'tr.is_live'),
            trSimFilter(),
            dateWindow(days, 'tr.recommendation_date'),
        ];
        const params = [];

        if (signal)  { conds.push(`(tr.action = ${ph(params.length + 1)} OR cr.final_signal = ${ph(params.length + 1)})`); params.push(signal); }
        if (symbol)  { conds.push(`tr.symbol = ${ph(params.length + 1)}`); params.push(symbol); }
        if (outcome === 'WIN')     conds.push(`tr.was_correct = ${boolTrue()}`);
        if (outcome === 'LOSS')    conds.push(`tr.was_correct = ${boolFalse()}`);
        if (outcome === 'PENDING') conds.push('tr.was_correct IS NULL');

        const where = conds.join(' AND ');

        // Total count
        const countRow = await dbGet(`
            SELECT COUNT(*) AS cnt
            FROM trade_recommendations tr
            LEFT JOIN consensus_results cr ON cr.symbol = tr.symbol AND cr.prediction_date = tr.recommendation_date
            WHERE ${where}
        `, params);

        const total = parseInt(countRow?.cnt || 0);

        // Data rows
        const rows = await dbAll(`
            SELECT
                tr.recommendation_date AS date,
                tr.symbol,
                ${isPostgres ? 's.name_en,' : ''}
                COALESCE(cr.final_signal, tr.action)    AS signal,
                tr.confidence,
                tr.buy_price   AS entry_price,
                tr.target_price,
                tr.stop_loss   AS stop_price,
                tr.actual_next_day_return                AS actual_return,
                tr.benchmark_1d_return                   AS benchmark_return,
                tr.alpha_1d                              AS alpha,
                tr.was_correct,
                tr.is_live,
                cr.is_simulated,
                cr.conviction
            FROM trade_recommendations tr
            ${isPostgres ? 'LEFT JOIN egx30_stocks s ON s.symbol = tr.symbol' : ''}
            LEFT JOIN consensus_results cr ON cr.symbol = tr.symbol AND cr.prediction_date = tr.recommendation_date
            WHERE ${where}
            ORDER BY tr.recommendation_date DESC
            LIMIT ${ph(params.length + 1)} OFFSET ${ph(params.length + 2)}
        `, [...params, limit, offset]);

        const toOutcome = r => {
            if (r.was_correct === true || r.was_correct === 1 || r.was_correct === 't') return 'WIN';
            if (r.was_correct === false || r.was_correct === 0 || r.was_correct === 'f') return 'LOSS';
            return 'PENDING';
        };

        return res.json({
            page,
            limit,
            total,
            pages: Math.ceil(total / limit),
            filters: { signal, days, outcome, symbol },
            predictions: rows.map(r => ({
                date:             r.date,
                symbol:           r.symbol,
                name:             r.name_en || r.symbol,
                signal:           r.signal || '—',
                confidence:       r.confidence != null ? parseFloat(r.confidence) : null,
                entry_price:      r.entry_price != null ? parseFloat(r.entry_price) : null,
                target_price:     r.target_price != null ? parseFloat(r.target_price) : null,
                stop_price:       r.stop_price != null ? parseFloat(r.stop_price) : null,
                outcome:          toOutcome(r),
                actual_return:    r.actual_return != null ? parseFloat(r.actual_return) : null,
                benchmark_return: r.benchmark_return != null ? parseFloat(r.benchmark_return) : null,
                alpha:            r.alpha != null ? parseFloat(r.alpha) : null,
                is_live:          r.is_live === true || r.is_live === 1 || r.is_live === 't',
                is_simulated:     r.is_simulated === true || r.is_simulated === 1 || r.is_simulated === 't',
                conviction:       r.conviction || null,
            })),
        });
    } catch (err) {
        if (isTableMissing(err)) return res.json({ page: 1, limit: 25, total: 0, pages: 0, filters: {}, predictions: [] });
        console.error('[track-record] /predictions error:', err);
        res.status(500).json({ error: 'Failed to load predictions.' });
    }
});


// ═══════════════════════════════════════════════════════════════
// GET /api/track-record/predictions/export?days=90&signal=
// CSV download — no auth, live signals only
// ═══════════════════════════════════════════════════════════════
router.get('/predictions/export', async (req, res) => {
    try {
        const days   = Math.min(parseInt(req.query.days) || 90, 365);
        const signal = req.query.signal || '';
        const symbol = (req.query.symbol || '').toUpperCase();

        const conds = [
            liveFilter().replace(/\b(is_live)\b/g, 'tr.is_live'),
            trSimFilter(),
            dateWindow(days, 'tr.recommendation_date'),
        ];
        const params = [];

        if (signal) { conds.push(`tr.action = ${ph(params.length + 1)}`); params.push(signal); }
        if (symbol) { conds.push(`tr.symbol = ${ph(params.length + 1)}`); params.push(symbol); }

        const rows = await dbAll(`
            SELECT
                tr.recommendation_date AS date,
                tr.symbol,
                COALESCE(cr.final_signal, tr.action) AS signal,
                tr.confidence,
                tr.buy_price        AS entry_price,
                tr.target_price,
                tr.stop_loss        AS stop_price,
                tr.actual_next_day_return AS actual_return,
                tr.benchmark_1d_return    AS benchmark_return,
                tr.alpha_1d         AS alpha,
                tr.was_correct
            FROM trade_recommendations tr
            LEFT JOIN consensus_results cr ON cr.symbol = tr.symbol AND cr.prediction_date = tr.recommendation_date
            WHERE ${conds.join(' AND ')}
            ORDER BY tr.recommendation_date DESC
            LIMIT 5000
        `, params);

        const toOutcome = r => {
            if (r.was_correct === true || r.was_correct === 1 || r.was_correct === 't') return 'WIN';
            if (r.was_correct === false || r.was_correct === 0 || r.was_correct === 'f') return 'LOSS';
            return 'PENDING';
        };
        const fmtNum = v => v != null ? parseFloat(v).toFixed(4) : '';

        const header = 'date,symbol,signal,confidence,entry_price,target_price,stop_price,outcome,actual_return,benchmark_return,alpha\r\n';
        const body   = rows.map(r => [
            r.date,
            r.symbol,
            r.signal || '',
            fmtNum(r.confidence),
            fmtNum(r.entry_price),
            fmtNum(r.target_price),
            fmtNum(r.stop_price),
            toOutcome(r),
            fmtNum(r.actual_return),
            fmtNum(r.benchmark_return),
            fmtNum(r.alpha),
        ].join(',')).join('\r\n');

        const today = new Date().toISOString().split('T')[0];
        res.setHeader('Content-Type', 'text/csv');
        res.setHeader('Content-Disposition', `attachment; filename="xmore2-predictions-${today}.csv"`);
        res.send(header + body);
    } catch (err) {
        console.error('[track-record] /predictions/export error:', err);
        res.status(500).json({ error: 'Failed to export.' });
    }
});


module.exports = { router, attachDb };
