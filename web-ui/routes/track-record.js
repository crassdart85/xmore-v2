/**
 * Track Record API Routes
 * Public investor-facing endpoints. No authentication required.
 * Shows all live signals (is_live = TRUE OR NULL), including historical simulation
 * rows clearly tagged is_simulated = TRUE. The frontend labels simulated rows with
 * an amber SIM badge. KPI metrics include all evaluated predictions.
 */

const express = require('express');
const router = express.Router();

let db;
let isPostgres = false;

function attachDb(database, pg) {
    db = database;
    isPostgres = pg;
}

// â”€â”€ DB helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
function liveFilter() {
    return isPostgres
        ? '(is_live = TRUE OR is_live IS NULL)'
        : '(is_live = 1 OR is_live IS NULL)';
}
function dateWindow(days, col = 'recommendation_date') {
    return isPostgres
        ? `${col} >= CURRENT_DATE - (${days} * INTERVAL '1 day')`
        : `${col} >= date('now', '-${days} days')`;
}
function round(expr) {
    return isPostgres ? `ROUND(${expr}::numeric, 4)` : `ROUND(${expr}, 4)`;
}
const DEFAULT_ROUND_TRIP_COST_PCT = 0.725;

function toNum(v) {
    const n = Number(v);
    return Number.isFinite(n) ? n : 0;
}

function mean(arr) {
    return arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : 0;
}

function stdev(arr) {
    if (arr.length < 2) return 0;
    const m = mean(arr);
    return Math.sqrt(arr.reduce((a, v) => a + ((v - m) ** 2), 0) / (arr.length - 1));
}

function calcProfitFactor(returnsArr) {
    const grossProfit = returnsArr.filter(v => v > 0).reduce((a, b) => a + b, 0);
    const grossLoss = Math.abs(returnsArr.filter(v => v < 0).reduce((a, b) => a + b, 0));
    if (grossLoss === 0) return grossProfit > 0 ? 9.99 : null;
    return grossProfit / grossLoss;
}

function calcMaxDrawdownAbs(returnsArr) {
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
}

function perTradeCostPct(row) {
    const rtc = toNum(row?.round_trip_cost_egp);
    const pve = toNum(row?.position_value_egp);
    if (pve > 0) return (rtc / pve) * 100;
    return DEFAULT_ROUND_TRIP_COST_PCT;
}

function costPctSql(alias = '') {
    const p = alias ? `${alias}.` : '';
    return `CASE
        WHEN ${p}round_trip_cost_egp IS NOT NULL
         AND ${p}position_value_egp IS NOT NULL
         AND ${p}position_value_egp > 0
        THEN (${p}round_trip_cost_egp / ${p}position_value_egp) * 100
        ELSE ${DEFAULT_ROUND_TRIP_COST_PCT}
    END`;
}

// â”€â”€ KPI helper: accuracy + alpha + sharpe + beat + PF + max DD â”€
async function kpiForWindow(days) {
    try {
        const rows = await dbAll(`
            SELECT
                recommendation_date,
                actual_next_day_return,
                benchmark_1d_return,
                alpha_1d,
                was_correct,
                round_trip_cost_egp,
                position_value_egp
            FROM trade_recommendations
            WHERE was_correct IS NOT NULL
            AND ${liveFilter()}
            AND ${dateWindow(days)}
            ORDER BY recommendation_date ASC
        `);
        if (!rows.length) return null;

        const total = rows.length;
        const correct = rows.filter(r => r.was_correct === true || r.was_correct === 1 || r.was_correct === 't').length;

        const returnsGross = rows.map(r => toNum(r.actual_next_day_return));
        const bench = rows.map(r => toNum(r.benchmark_1d_return));
        const costsPct = rows.map(perTradeCostPct);
        const returnsNet = returnsGross.map((r, i) => r - costsPct[i]);

        const alphaGross = rows.map((r, i) =>
            r.alpha_1d == null ? (returnsGross[i] - bench[i]) : toNum(r.alpha_1d)
        );
        const alphaNet = returnsNet.map((r, i) => r - bench[i]);

        const cbeDailyRf = Math.pow(1.2725, 1 / 247) - 1;
        const calcSharpe = arr => {
            const m = mean(arr), s = stdev(arr);
            if (s <= 0) return 0;
            return ((m / 100) - cbeDailyRf) / (s / 100) * Math.sqrt(247);
        };
        const calcSortino = arr => {
            const m = mean(arr);
            const downside = arr.filter(v => v < 0);
            if (!downside.length) return 99.9;
            const ds = stdev(downside);
            if (ds <= 0) return 99.9;
            return ((m / 100) - cbeDailyRf) / (ds / 100) * Math.sqrt(247);
        };
        const calcVol = arr => {
            const s = stdev(arr);
            return s > 0 ? (s / 100) * Math.sqrt(247) : 0;
        };

        const beatNet = alphaNet.filter(a => a > 0).length;
        const beatGross = alphaGross.filter(a => a > 0).length;

        const pfNet = calcProfitFactor(returnsNet);
        const pfGross = calcProfitFactor(returnsGross);
        const mddNet = calcMaxDrawdownAbs(returnsNet);
        const mddGross = calcMaxDrawdownAbs(returnsGross);

        // Reliability gate: ratio metrics (Sharpe, Sortino, max-DD, profit
        // factor) are noise below ~20 trades, especially after major system
        // changes (quality gates, cost gate). Expose a reliability flag so
        // the UI can show a "Preliminary" badge instead of misleading numbers.
        const MIN_SAMPLE_RELIABLE    = 30;
        const MIN_SAMPLE_PRELIMINARY = 10;
        const sample_reliability =
            total >= MIN_SAMPLE_RELIABLE    ? 'high'       :
            total >= MIN_SAMPLE_PRELIMINARY ? 'preliminary':
                                              'insufficient';
        const firstDate = rows[0]?.recommendation_date || null;
        const lastDate  = rows[rows.length - 1]?.recommendation_date || null;

        return {
            reporting_basis:       'net_of_transaction_costs',
            total_signals:         total,
            directional_accuracy:  total > 0 ? parseFloat((correct / total).toFixed(4)) : 0,
            sample_reliability,
            sample_window_start:   firstDate,
            sample_window_end:     lastDate,

            // Primary (net)
            alpha_vs_egx30:        parseFloat(mean(alphaNet).toFixed(4)),
            avg_return_1d:         parseFloat(mean(returnsNet).toFixed(4)),
            avg_alpha_1d:          parseFloat(mean(alphaNet).toFixed(4)),
            sharpe_ratio:          parseFloat(calcSharpe(returnsNet).toFixed(2)),
            sortino_ratio:         parseFloat(calcSortino(returnsNet).toFixed(2)),
            beat_benchmark_pct:    total > 0 ? parseFloat(((beatNet / total) * 100).toFixed(1)) : 0,
            profit_factor:         pfNet == null ? null : parseFloat(pfNet.toFixed(4)),
            max_drawdown:          parseFloat(mddNet.toFixed(2)),
            volatility:            parseFloat(calcVol(returnsNet).toFixed(4)),
            avg_cost_per_trade_pct: parseFloat(mean(costsPct).toFixed(4)),
            cost_drag_total_pct:   parseFloat(costsPct.reduce((a, b) => a + b, 0).toFixed(2)),

            // Secondary (gross)
            alpha_vs_egx30_gross:  parseFloat(mean(alphaGross).toFixed(4)),
            avg_return_1d_gross:   parseFloat(mean(returnsGross).toFixed(4)),
            avg_alpha_1d_gross:    parseFloat(mean(alphaGross).toFixed(4)),
            sharpe_ratio_gross:    parseFloat(calcSharpe(returnsGross).toFixed(2)),
            sortino_ratio_gross:   parseFloat(calcSortino(returnsGross).toFixed(2)),
            beat_benchmark_pct_gross: total > 0 ? parseFloat(((beatGross / total) * 100).toFixed(1)) : 0,
            profit_factor_gross:   pfGross == null ? null : parseFloat(pfGross.toFixed(4)),
            max_drawdown_gross:    parseFloat(mddGross.toFixed(2)),
            volatility_gross:      parseFloat(calcVol(returnsGross).toFixed(4)),
        };
    } catch (e) {
        console.error('[track-record] kpiForWindow error:', e);
        return null;
    }
}


// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// GET /api/track-record/summary
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
router.get('/summary', async (req, res) => {
    try {
        // Live signal count + date range
        // Use both the original signal date (recommendation_date) and the last modification time (updated_at)
        // so "Last Updated" reflects the latest evaluation / refresh even if signals themselves are unchanged.
        const counts = await dbGet(`
            SELECT
                COUNT(*)  AS total_live,
                MIN(recommendation_date) AS live_since,
                MAX(recommendation_date) AS last_signal_date,
                MAX(updated_at) AS last_updated
            FROM trade_recommendations
            WHERE ${liveFilter()}
        `);

        // Fresher "last updated" â€” use latest across prices + consensus + evaluations
        // (updated daily even when no new user-specific trade recs are generated)
        let lastUpdated = counts?.last_updated || counts?.last_signal_date || null;
        try {
            const fresh = await dbGet(`
                SELECT GREATEST(
                    COALESCE((SELECT MAX(date) FROM prices), '1970-01-01'::date),
                    COALESCE((SELECT MAX(prediction_date) FROM consensus_results), '1970-01-01'::date),
                    COALESCE((SELECT MAX(evaluated_at) FROM stock_signal_evals), '1970-01-01'::date),
                    COALESCE((SELECT MAX(signal_date) FROM scored_signals), '1970-01-01'::date),
                    COALESCE((SELECT MAX(updated_at) FROM trade_recommendations), '1970-01-01'::date),
                    COALESCE('${lastUpdated || '1970-01-01'}'::date, '1970-01-01'::date)
                ) AS freshest
            `);
            if (fresh?.freshest) lastUpdated = fresh.freshest;
        } catch (_) {
            // SQLite fallback
            try {
                const p  = await dbGet(`SELECT MAX(date) AS d FROM prices`);
                const c  = await dbGet(`SELECT MAX(prediction_date) AS d FROM consensus_results`);
                const se = await dbGet(`SELECT MAX(evaluated_at) AS d FROM stock_signal_evals`).catch(() => null);
                const ss = await dbGet(`SELECT MAX(signal_date) AS d FROM scored_signals`).catch(() => null);
                const ur = await dbGet(`SELECT MAX(updated_at) AS d FROM trade_recommendations`).catch(() => null);
                const candidates = [lastUpdated, p?.d, c?.d, se?.d, ss?.d, ur?.d].filter(Boolean).sort();
                if (candidates.length) lastUpdated = candidates[candidates.length - 1];
            } catch (_2) {}
        }

        // Simulated count (included, labelled SIM in UI)
        let simCount = 0;
        try {
            const sc = await dbGet(`
                SELECT COUNT(*) AS cnt FROM trade_recommendations
                WHERE ${liveFilter()}
                AND is_simulated = ${boolTrue()}
            `);
            simCount = parseInt(sc?.cnt || 0);
        } catch (_) {}

        // KPI windows (run in parallel)
        const [w30, w60, w90, w180, w365] = await Promise.all([
            kpiForWindow(30),
            kpiForWindow(60),
            kpiForWindow(90),
            kpiForWindow(180),
            kpiForWindow(365),
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

        // Information coefficient (latest from signal_ic_log)
        let ic = null;
        try {
            const icRow = await dbGet(`
                SELECT ic_value, sample_size, computed_at
                FROM signal_ic_log
                ORDER BY computed_at DESC LIMIT 1
            `);
            if (icRow && icRow.ic_value !== null) {
                ic = {
                    value: parseFloat(icRow.ic_value),
                    sample_size: parseInt(icRow.sample_size || 0),
                    computed_at: icRow.computed_at,
                };
            }
        } catch (_) {}

        // Calibrated evaluation metrics (magnitude + calibration averages)
        let calibrated_metrics = null;
        try {
            const calRow = await dbGet(`
                SELECT AVG(magnitude_score)    AS avg_magnitude,
                       AVG(calibration_score)  AS avg_calibration,
                       COUNT(*)                AS sample_size
                FROM evaluations
                WHERE magnitude_score IS NOT NULL
            `);
            if (calRow && calRow.sample_size > 0) {
                calibrated_metrics = {
                    avg_magnitude_score: parseFloat((calRow.avg_magnitude || 0).toFixed(4)),
                    avg_calibration_score: parseFloat((calRow.avg_calibration || 0).toFixed(4)),
                    sample_size: parseInt(calRow.sample_size),
                };
            }
        } catch (_) {}

        return res.json({
            platform:             'Xmore2',
            description:          'Market Intelligence for the Egyptian Exchange',
            reporting_basis:      'net_of_transaction_costs',
            live_since:           counts?.live_since || null,
            last_updated:         lastUpdated || null,
            total_live_signals:   liveCount,
            symbols_covered:      symbolsCovered,
            current_regime:       currentRegime,
            risk_free_rate_applied: '27.25% (CBE)',
            ic,
            calibrated_metrics,
            kpi_windows: {
                '30d':  w30,
                '60d':  w60,
                '90d':  w90,
                '180d': w180,
                '365d': w365,
            },
            data_transparency: {
                total_signals_count:        liveCount,
                simulated_signals_included: simCount,
                metrics_basis:              'live_and_simulated',
                earliest_signal_date:       counts?.live_since || null,
                note:                       'Primary KPIs are net of transaction costs. Simulated rows are clearly tagged SIM in the prediction log.',
            },
        });
    } catch (err) {
        console.error('[track-record] /summary error:', err);
        res.status(500).json({ error: 'Failed to load summary.' });
    }
});


// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// GET /api/track-record/equity-curve?days=90
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
router.get('/equity-curve', async (req, res) => {
    try {
        const days = Math.min(parseInt(req.query.days) || 90, 365);

        const rows = await dbAll(`
            SELECT
                recommendation_date AS date,
                ${round('AVG(actual_next_day_return)')} AS xmore_gross,
                ${round(`AVG(${costPctSql()})`)} AS avg_cost_pct,
                ${round('AVG(benchmark_1d_return)')}    AS egx30
            FROM trade_recommendations
            WHERE actual_next_day_return IS NOT NULL
            AND ${liveFilter()}
            AND ${dateWindow(days)}
            GROUP BY recommendation_date
            ORDER BY recommendation_date ASC
        `);

        let xmoreCum = 0, xmoreCumGross = 0, egx30Cum = 0;
        const series = rows.map(r => {
            const gross = parseFloat(r.xmore_gross) || 0;
            const cost = parseFloat(r.avg_cost_pct) || 0;
            const net = gross - cost;
            xmoreCum += net;
            xmoreCumGross += gross;
            egx30Cum += parseFloat(r.egx30) || 0;
            return {
                date:  r.date,
                xmore: Math.round(xmoreCum * 100) / 100,
                xmore_gross: Math.round(xmoreCumGross * 100) / 100,
                egx30: Math.round(egx30Cum * 100) / 100,
                alpha: Math.round((xmoreCum - egx30Cum) * 100) / 100,
                alpha_gross: Math.round((xmoreCumGross - egx30Cum) * 100) / 100,
            };
        });

        // Drawdown series
        let peak = 0;
        const drawdown_series = series.map(p => {
            if (p.xmore > peak) peak = p.xmore;
            return { date: p.date, drawdown: peak > 0 ? Math.round((p.xmore - peak) * 100) / 100 : 0 };
        });

        return res.json({
            reporting_basis: 'net_of_transaction_costs',
            days,
            series,
            drawdown_series,
            total_xmore: series.length ? series[series.length - 1].xmore : 0,
            total_xmore_gross: series.length ? series[series.length - 1].xmore_gross : 0,
            total_egx30: series.length ? series[series.length - 1].egx30 : 0,
            total_alpha: series.length ? series[series.length - 1].alpha : 0,
            total_alpha_gross: series.length ? series[series.length - 1].alpha_gross : 0,
        });
    } catch (err) {
        if (isTableMissing(err)) return res.json({
            reporting_basis: 'net_of_transaction_costs',
            days: 90,
            series: [],
            drawdown_series: [],
            total_xmore: 0,
            total_xmore_gross: 0,
            total_egx30: 0,
            total_alpha: 0,
            total_alpha_gross: 0
        });
        console.error('[track-record] /equity-curve error:', err);
        res.status(500).json({ error: 'Failed to load equity curve.' });
    }
});


// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// GET /api/track-record/agents
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
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


// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// GET /api/track-record/top-stocks?days=90&limit=10
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
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
                ${round(`AVG(COALESCE(tr.alpha_1d, tr.actual_next_day_return - tr.benchmark_1d_return) - (${costPctSql('tr')}))`)} AS avg_alpha,
                ${round(`AVG(tr.actual_next_day_return - (${costPctSql('tr')}))`)}  AS avg_return,
                ${round('AVG(COALESCE(tr.alpha_1d, tr.actual_next_day_return - tr.benchmark_1d_return))')} AS avg_alpha_gross,
                ${round('AVG(tr.actual_next_day_return)')}  AS avg_return_gross,
                ${isPostgres
                    ? `ROUND(MAX((tr.actual_next_day_return - (${costPctSql('tr')})))::numeric, 4)`
                    : `ROUND(MAX((tr.actual_next_day_return - (${costPctSql('tr')}))), 4)`
                }                                            AS best_return,
                ${round('MAX(tr.actual_next_day_return)')}   AS best_return_gross,
                ${isPostgres
                    ? `ROUND((SUM(CASE WHEN tr.was_correct = TRUE THEN 1 ELSE 0 END))::numeric / NULLIF(COUNT(*), 0) * 100, 1)`
                    : `ROUND(CAST(SUM(CASE WHEN tr.was_correct = 1 THEN 1 ELSE 0 END) AS REAL) / MAX(COUNT(*), 1) * 100, 1)`
                }                                            AS win_rate
            FROM trade_recommendations tr
            ${isPostgres ? 'LEFT JOIN egx30_stocks s ON tr.symbol = s.symbol' : ''}
            WHERE tr.was_correct IS NOT NULL
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
            alpha_avg_net:        parseFloat(r.avg_alpha) || 0,
            alpha_avg:            parseFloat(r.avg_alpha) || 0,
            avg_return_net:       parseFloat(r.avg_return) || 0,
            avg_return:           parseFloat(r.avg_return) || 0,
            alpha_avg_gross:      parseFloat(r.avg_alpha_gross) || 0,
            avg_return_gross:     parseFloat(r.avg_return_gross) || 0,
            best_signal_return_net: parseFloat(r.best_return) || 0,
            best_signal_return:   parseFloat(r.best_return) || 0,
            best_signal_return_gross: parseFloat(r.best_return_gross) || 0,
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
            reporting_basis:  'net_of_transaction_costs',
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


// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// GET /api/track-record/backtest?limit=20
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
router.get('/backtest', async (req, res) => {
    try {
        const limit = Math.min(parseInt(req.query.limit) || 20, 100);
        const rows = await dbAll(`
            SELECT symbol, run_date, accuracy, directional_accuracy,
                   signal_pnl_pct, n_rows AS total_signals_tested
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


// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// GET /api/track-record/predictions?page=1&limit=25&signal=&days=90&outcome=
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
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
                tr.close_price AS entry_price,
                tr.target_price,
                tr.stop_loss_price AS stop_price,
                tr.actual_next_day_return                AS actual_return,
                tr.benchmark_1d_return                   AS benchmark_return,
                tr.alpha_1d                              AS alpha,
                tr.was_correct,
                tr.is_live,
                tr.is_simulated,
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
                signal:           r.signal || 'â€”',
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


// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// GET /api/track-record/predictions/export?days=90&signal=
// CSV download â€” no auth, live signals only
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
router.get('/predictions/export', async (req, res) => {
    try {
        const days   = Math.min(parseInt(req.query.days) || 90, 365);
        const signal = req.query.signal || '';
        const symbol = (req.query.symbol || '').toUpperCase();

        const conds = [
            liveFilter().replace(/\b(is_live)\b/g, 'tr.is_live'),
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
                tr.close_price      AS entry_price,
                tr.target_price,
                tr.stop_loss_price  AS stop_price,
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


// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// GET /api/track-record/signal-distribution?days=90
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
router.get('/signal-distribution', async (req, res) => {
  const days = Math.min(parseInt(req.query.days) || 90, 365);
  try {
    // Overall counts
    const counts = await dbAll(`
      SELECT action,
             COUNT(*) AS total,
             SUM(CASE WHEN was_correct = ${boolTrue()} THEN 1 ELSE 0 END) AS correct
      FROM trade_recommendations
      WHERE recommendation_date >= ${isPostgres
        ? `NOW() - INTERVAL '${days} days'`
        : `date('now', '-${days} days')`}
        AND action IN ('BUY','SELL','HOLD')
      GROUP BY action
    `);
    // Daily signal counts for the last 30 days (for trend line)
    const daily = await dbAll(`
      SELECT recommendation_date AS date,
             SUM(CASE WHEN action='BUY'  THEN 1 ELSE 0 END) AS buy_count,
             SUM(CASE WHEN action='SELL' THEN 1 ELSE 0 END) AS sell_count,
             SUM(CASE WHEN action='HOLD' THEN 1 ELSE 0 END) AS hold_count,
             COUNT(*) AS total_count
      FROM trade_recommendations
      WHERE recommendation_date >= ${isPostgres
        ? `NOW() - INTERVAL '30 days'`
        : `date('now', '-30 days')`}
      GROUP BY recommendation_date
      ORDER BY recommendation_date ASC
    `);
    const totals = { BUY: 0, SELL: 0, HOLD: 0 };
    const wins   = { BUY: 0, SELL: 0, HOLD: 0 };
    for (const r of counts) {
      const k = r.action;
      totals[k] = parseInt(r.total)   || 0;
      wins[k]   = parseInt(r.correct) || 0;
    }
    res.json({ totals, wins, daily: daily.map(r => ({
      date: r.date, buy: parseInt(r.buy_count)||0,
      sell: parseInt(r.sell_count)||0, hold: parseInt(r.hold_count)||0,
    }))});
  } catch (err) {
    if (isTableMissing(err)) return res.json({ totals:{BUY:0,SELL:0,HOLD:0}, wins:{BUY:0,SELL:0,HOLD:0}, daily:[] });
    console.error('[track-record] /signal-distribution', err);
    res.status(500).json({ error: 'Failed' });
  }
});


// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// GET /api/track-record/sector-accuracy?days=90
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
router.get('/sector-accuracy', async (req, res) => {
  const days = Math.min(parseInt(req.query.days) || 90, 365);
  try {
    let rows;
    if (isPostgres) {
      rows = await dbAll(`
        SELECT COALESCE(s.sector_en, 'Other') AS sector,
               COUNT(*) AS signal_count,
               SUM(CASE WHEN tr.actual_next_day_return > 0 AND tr.action='BUY'  THEN 1
                        WHEN tr.actual_next_day_return < 0 AND tr.action='SELL' THEN 1
                        ELSE 0 END) AS win_count,
               ${round(`AVG(tr.actual_next_day_return - (${costPctSql('tr')}))`)} AS avg_return,
               ${round(`AVG(COALESCE(tr.alpha_1d, tr.actual_next_day_return - tr.benchmark_1d_return) - (${costPctSql('tr')}))`)} AS avg_alpha,
               ${round('AVG(tr.actual_next_day_return)')} AS avg_return_gross,
               ${round('AVG(COALESCE(tr.alpha_1d, tr.actual_next_day_return - tr.benchmark_1d_return))')} AS avg_alpha_gross
        FROM trade_recommendations tr
        LEFT JOIN egx30_stocks s ON s.symbol = tr.symbol
        WHERE tr.recommendation_date >= NOW() - INTERVAL '${days} days'
          AND tr.action IN ('BUY','SELL')
          AND tr.actual_next_day_return IS NOT NULL
        GROUP BY COALESCE(s.sector_en, 'Other')
        HAVING COUNT(*) >= 3
        ORDER BY avg_return DESC
        LIMIT 15
      `);
    } else {
      rows = await dbAll(`
        SELECT COALESCE(s.sector_en, 'Other') AS sector,
               COUNT(*) AS signal_count,
               SUM(CASE WHEN tr.actual_next_day_return > 0 AND tr.action='BUY'  THEN 1
                        WHEN tr.actual_next_day_return < 0 AND tr.action='SELL' THEN 1
                        ELSE 0 END) AS win_count,
               ROUND(AVG(tr.actual_next_day_return - (${costPctSql('tr')})),4) AS avg_return,
               ROUND(AVG(COALESCE(tr.alpha_1d, tr.actual_next_day_return - tr.benchmark_1d_return) - (${costPctSql('tr')})),4) AS avg_alpha,
               ROUND(AVG(tr.actual_next_day_return),4) AS avg_return_gross,
               ROUND(AVG(COALESCE(tr.alpha_1d, tr.actual_next_day_return - tr.benchmark_1d_return)),4) AS avg_alpha_gross
        FROM trade_recommendations tr
        LEFT JOIN egx30_stocks s ON s.symbol = tr.symbol
        WHERE tr.recommendation_date >= date('now', '-${days} days')
          AND tr.action IN ('BUY','SELL')
          AND tr.actual_next_day_return IS NOT NULL
        GROUP BY COALESCE(s.sector_en, 'Other')
        HAVING COUNT(*) >= 3
        ORDER BY avg_return DESC
        LIMIT 15
      `);
    }
    res.json(rows.map(r => ({
      reporting_basis: 'net_of_transaction_costs',
      sector:       r.sector,
      signal_count: parseInt(r.signal_count) || 0,
      win_count:    parseInt(r.win_count)    || 0,
      win_rate:     r.signal_count > 0 ? parseFloat((r.win_count / r.signal_count).toFixed(4)) : 0,
      avg_return:   parseFloat(r.avg_return) || 0,
      avg_alpha:    parseFloat(r.avg_alpha)  || 0,
      avg_return_gross: parseFloat(r.avg_return_gross) || 0,
      avg_alpha_gross:  parseFloat(r.avg_alpha_gross)  || 0,
    })));
  } catch (err) {
    if (isTableMissing(err)) return res.json([]);
    console.error('[track-record] /sector-accuracy', err);
    res.status(500).json({ error: 'Failed' });
  }
});


// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// GET /api/track-record/regime-stats
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
router.get('/regime-stats', async (req, res) => {
  try {
    // Join trade_recommendations with regime_log on date
    let rows;
    if (isPostgres) {
      rows = await dbAll(`
        SELECT COALESCE(rl.regime, 'Unknown') AS regime,
               COUNT(*) AS signal_count,
               SUM(CASE WHEN tr.actual_next_day_return > 0 AND tr.action='BUY'  THEN 1
                        WHEN tr.actual_next_day_return < 0 AND tr.action='SELL' THEN 1
                        ELSE 0 END) AS win_count,
               ${round(`AVG(tr.actual_next_day_return - (${costPctSql('tr')}))`)} AS avg_return,
               ${round(`AVG(COALESCE(tr.alpha_1d, tr.actual_next_day_return - tr.benchmark_1d_return) - (${costPctSql('tr')}))`)} AS avg_alpha,
               ${round('AVG(tr.actual_next_day_return)')} AS avg_return_gross,
               ${round('AVG(COALESCE(tr.alpha_1d, tr.actual_next_day_return - tr.benchmark_1d_return))')} AS avg_alpha_gross
        FROM trade_recommendations tr
        LEFT JOIN regime_log rl ON rl.date = tr.recommendation_date
        WHERE tr.action IN ('BUY','SELL')
          AND tr.actual_next_day_return IS NOT NULL
        GROUP BY COALESCE(rl.regime, 'Unknown')
        ORDER BY signal_count DESC
      `);
    } else {
      rows = await dbAll(`
        SELECT COALESCE(rl.regime, 'Unknown') AS regime,
               COUNT(*) AS signal_count,
               SUM(CASE WHEN tr.actual_next_day_return > 0 AND tr.action='BUY'  THEN 1
                        WHEN tr.actual_next_day_return < 0 AND tr.action='SELL' THEN 1
                        ELSE 0 END) AS win_count,
               ROUND(AVG(tr.actual_next_day_return - (${costPctSql('tr')})),4) AS avg_return,
               ROUND(AVG(COALESCE(tr.alpha_1d, tr.actual_next_day_return - tr.benchmark_1d_return) - (${costPctSql('tr')})),4) AS avg_alpha,
               ROUND(AVG(tr.actual_next_day_return),4) AS avg_return_gross,
               ROUND(AVG(COALESCE(tr.alpha_1d, tr.actual_next_day_return - tr.benchmark_1d_return)),4) AS avg_alpha_gross
        FROM trade_recommendations tr
        LEFT JOIN regime_log rl ON rl.date = tr.recommendation_date
        WHERE tr.action IN ('BUY','SELL')
          AND tr.actual_next_day_return IS NOT NULL
        GROUP BY COALESCE(rl.regime, 'Unknown')
        ORDER BY signal_count DESC
      `);
    }
    res.json(rows.map(r => ({
      reporting_basis: 'net_of_transaction_costs',
      regime:       r.regime,
      signal_count: parseInt(r.signal_count) || 0,
      win_count:    parseInt(r.win_count)    || 0,
      win_rate:     r.signal_count > 0 ? parseFloat((r.win_count / r.signal_count).toFixed(4)) : 0,
      avg_return:   parseFloat(r.avg_return) || 0,
      avg_alpha:    parseFloat(r.avg_alpha)  || 0,
      avg_return_gross: parseFloat(r.avg_return_gross) || 0,
      avg_alpha_gross:  parseFloat(r.avg_alpha_gross)  || 0,
    })));
  } catch (err) {
    if (isTableMissing(err)) return res.json([]);
    console.error('[track-record] /regime-stats', err);
    res.status(500).json({ error: 'Failed' });
  }
});


// â”€â”€ GET /api/track-record/etf-signals â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
router.get('/etf-signals', async (req, res) => {
  try {
    const iid = isPostgres ? 'instrument_id' : 'id';
    const latest = await dbAll(
      `SELECT s.symbol, s.signal, s.confidence, s.signal_date,
              s.ma_signal, s.rsi_signal, s.nav_signal, s.momentum_signal,
              s.rsi_value, s.nav_premium_pct, s.close_price,
              i.name, i.type, i.region
       FROM etf_signals s
       JOIN instrument i ON i.${iid} = s.instrument_id
       WHERE s.signal_date = (
           SELECT MAX(s2.signal_date) FROM etf_signals s2
           WHERE s2.instrument_id = s.instrument_id
       )
       ORDER BY s.confidence DESC`,
      []
    );
    const cutoff30 = new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10);
    const dist = await dbAll(
      `SELECT signal, COUNT(*) AS cnt FROM etf_signals
       WHERE signal_date >= ${isPostgres ? '$1' : '?'}
       GROUP BY signal`,
      [cutoff30]
    );
    res.json({ latest, dist });
  } catch (err) {
    if (isTableMissing(err)) return res.json({ latest: [], dist: [] });
    console.error('[track-record] /etf-signals error:', err);
    res.status(500).json({ error: 'Failed to load ETF signals.' });
  }
});

// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// GET /api/track-record/signals/batch?ids=2026-03-01-COMI.CA,...
// Used by client-side tracker to fetch resolved P&L
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
router.get('/signals/batch', async (req, res) => {
  try {
    const ids = (req.query.ids || '').split(',').filter(Boolean).slice(0, 50);
    if (!ids.length) return res.json([]);

    const results = await Promise.all(ids.map(async id => {
      // id format: "date-symbol"
      const parts = id.split('-');
      if (parts.length < 2) return null;
      const symbol = parts[parts.length - 1];
      const date   = parts.slice(0, parts.length - 1).join('-');
      try {
        const row = await dbGet(`
          SELECT recommendation_date AS date, symbol,
                 actual_next_day_return AS actual_1d,
                 alpha_1d AS alpha,
                 was_correct AS hit
          FROM trade_recommendations
          WHERE symbol = ${ph(1)} AND recommendation_date = ${ph(2)}
          LIMIT 1
        `, [symbol, date]);
        if (!row) return null;
        return {
          id,
          symbol:   row.symbol,
          date:     row.date,
          actual_1d: row.actual_1d != null ? parseFloat(row.actual_1d) : null,
          alpha:    row.alpha != null ? parseFloat(row.alpha) : null,
          hit:      row.hit === true || row.hit === 1 || row.hit === 't',
        };
      } catch (_) { return null; }
    }));

    return res.json(results.filter(Boolean));
  } catch (err) {
    console.error('[track-record] /signals/batch error:', err);
    res.status(500).json({ error: 'Failed.' });
  }
});

module.exports = { router, attachDb };

