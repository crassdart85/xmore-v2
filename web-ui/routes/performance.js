/**
 * Performance API Routes
 * Investor-grade, public performance endpoints.
 * No auth required â€” this is transparency.
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
const DEFAULT_ROUND_TRIP_COST_PCT = 0.725;

function perTradeCostPct(row) {
    const rtc = Number(row?.round_trip_cost_egp);
    const pve = Number(row?.position_value_egp);
    if (Number.isFinite(rtc) && Number.isFinite(pve) && pve > 0) {
        return (rtc / pve) * 100;
    }
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


// â”€â”€â”€ PUBLIC: Overall performance summary â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
router.get('/summary', async (req, res) => {
    try {
        const days = Math.min(parseInt(req.query.days) || 365, 365);
        const liveFilter = isPostgres
            ? `(is_live = TRUE OR is_live IS NULL)`
            : `(is_live = 1 OR is_live IS NULL)`;
        const simFilter = isPostgres
            ? `(is_simulated = FALSE OR is_simulated IS NULL)`
            : `(is_simulated = 0 OR is_simulated IS NULL)`;
        const dateFilter = isPostgres
            ? `recommendation_date >= CURRENT_DATE - (${ph(1)} * INTERVAL '1 day')`
            : `recommendation_date >= date('now', '-' || ${ph(1)} || ' days')`;

        let rows = [], simCount = 0, earliestLive = null;
        let metricsIncludeSimulated = false;
        try {
            // Try live-only first (is_simulated = FALSE OR NULL)
            rows = await dbAll(`
                SELECT recommendation_date, actual_next_day_return, benchmark_1d_return, alpha_1d, was_correct,
                       round_trip_cost_egp, position_value_egp
                FROM trade_recommendations
                WHERE actual_next_day_return IS NOT NULL
                AND ${liveFilter}
                AND ${simFilter}
                AND ${dateFilter}
                ORDER BY recommendation_date ASC
            `, [days]);
            // If live-only returns nothing, fall back to all evaluated rows (including simulated)
            if (!rows.length) {
                metricsIncludeSimulated = true;
                rows = await dbAll(`
                    SELECT recommendation_date, actual_next_day_return, benchmark_1d_return, alpha_1d, was_correct,
                           round_trip_cost_egp, position_value_egp
                    FROM trade_recommendations
                    WHERE actual_next_day_return IS NOT NULL
                    AND ${liveFilter}
                    AND ${dateFilter}
                    ORDER BY recommendation_date ASC
                `, [days]);
            }
            // Count simulated rows for data_transparency
            try {
                const totalRow = await dbGet(`SELECT COUNT(*) AS cnt FROM trade_recommendations WHERE actual_next_day_return IS NOT NULL AND ${liveFilter} AND ${dateFilter}`, [days]);
                simCount = parseInt(totalRow?.cnt || 0) - (metricsIncludeSimulated ? 0 : rows.length);
                earliestLive = rows[0]?.recommendation_date || null;
            } catch (_) {}
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
        // KSA risk-free rate (SAIBOR 3M ~4.89% annual) — used for all Sharpe calculations
        const KSA_TRADING_DAYS = 250;
        const KSA_RF_ANNUAL = 0.0489;
        const _dailyRf = Math.pow(1 + KSA_RF_ANNUAL, 1 / KSA_TRADING_DAYS) - 1;
        const _sharpeKsa = (arr) => {
            if (arr.length < 2) return 0;
            const m = mean(arr), s = stdev(arr);
            return s > 0 ? ((m - _dailyRf) / s) * Math.sqrt(KSA_TRADING_DAYS) : 0;
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
            const returnsArrGross = subset.map(r => toNum(r.actual_next_day_return));
            const costsPct = subset.map(perTradeCostPct);
            const returnsArr = returnsArrGross.map((r, i) => r - costsPct[i]); // Net (primary reporting basis)
            const benchArr = subset.map(r => toNum(r.benchmark_1d_return));
            const alphaArrGross = subset.map((r, i) =>
                r.alpha_1d == null ? returnsArrGross[i] - benchArr[i] : toNum(r.alpha_1d)
            );
            const alphaArr = returnsArr.map((r, i) => r - benchArr[i]); // Net alpha (primary)
            const wins = subset.filter(r => r.was_correct === true || r.was_correct === 1 || r.was_correct === 't').length;
            const vol = stdev(returnsArr) * Math.sqrt(KSA_TRADING_DAYS);
            const volGross = stdev(returnsArrGross) * Math.sqrt(KSA_TRADING_DAYS);
            const sharpe = _sharpeKsa(returnsArr);
            const sharpeGross = _sharpeKsa(returnsArrGross);
            return {
                trades: total,
                wins,
                losses: total - wins,
                win_rate: total ? (wins / total) * 100 : 0,
                avg_return_1d: mean(returnsArr),
                avg_return_1d_gross: mean(returnsArrGross),
                avg_alpha_1d: mean(alphaArr),
                avg_alpha_1d_gross: mean(alphaArrGross),
                avg_benchmark_1d: mean(benchArr),
                beat_benchmark_count: alphaArr.filter(a => a > 0).length,
                beat_benchmark_count_gross: alphaArrGross.filter(a => a > 0).length,
                volatility: vol,
                volatility_gross: volGross,
                sharpe_ratio: sharpe,
                sharpe_ratio_gross: sharpeGross,
                max_drawdown: calcMaxDrawdown(returnsArr),
                max_drawdown_gross: calcMaxDrawdown(returnsArrGross),
                profit_factor: calcProfitFactor(returnsArr),
                profit_factor_gross: calcProfitFactor(returnsArrGross),
                avg_cost_per_trade_pct: mean(costsPct),
                cost_drag_total_pct: costsPct.reduce((a, b) => a + b, 0)
            };
        };

        const allStats = buildStats(rows);
        const latestDate = asDate(rows[rows.length - 1].recommendation_date);
        const filterDays = (n) => rows.filter(r => (latestDate - asDate(r.recommendation_date)) <= (n * 24 * 3600 * 1000));
        const r30 = buildStats(filterDays(30));
        const r60 = buildStats(filterDays(60));
        const r90 = buildStats(filterDays(90));

        // "Since quality gates" slice — signals emitted on or after Tier 1 deployment
        const IMPROVEMENT_DATE = '2026-03-21';
        const sinceRows = rows.filter(r => String(r.recommendation_date || '').substring(0, 10) >= IMPROVEMENT_DATE);
        const rSince = sinceRows.length ? buildStats(sinceRows) : null;

        // â”€â”€ Institutional metrics (KSA-correct risk-free rate: SAIBOR 4.89%) â”€â”€
        // Note: KSA_TRADING_DAYS, KSA_RF_ANNUAL, _dailyRf, _sharpeKsa are defined above buildStats
        const calcSharpeKsa = _sharpeKsa; // alias for institutional_metrics block
        const calcSortinoKsa = (arr) => {
            const m = mean(arr), dn = arr.filter(v => v < 0);
            if (!dn.length) return 99.9;
            const ds = stdev(dn);
            return ds > 0 ? ((m - _dailyRf) / ds) * Math.sqrt(KSA_TRADING_DAYS) : 99.9;
        };
        const calcCalmar = (arr, mdd) => {
            if (arr.length < 20 || !mdd) return 0;
            const ann = Math.pow(1 + mean(arr), KSA_TRADING_DAYS) - 1;
            return ann / Math.abs(mdd);
        };
        const calcBeta = (pArr, bArr) => {
            const n = Math.min(pArr.length, bArr.length);
            if (n < 2) return 0;
            const mp = mean(pArr.slice(0, n)), mb = mean(bArr.slice(0, n));
            const cov = pArr.slice(0, n).reduce((a, v, i) => a + (v - mp) * (bArr[i] - mb), 0) / (n - 1);
            const vb = Math.pow(stdev(bArr.slice(0, n)), 2);
            return vb > 0 ? cov / vb : 0;
        };
        const calcIR = (pArr, bArr) => {
            const n = Math.min(pArr.length, bArr.length);
            if (n < 2) return 0;
            const ex = pArr.slice(0, n).map((v, i) => v - bArr[i]);
            const te = stdev(ex);
            return te > 0 ? (mean(ex) / te) * Math.sqrt(KSA_TRADING_DAYS) : 0;
        };
        const calcCapture = (pArr, bArr, up) => {
            const n = Math.min(pArr.length, bArr.length);
            const days = [];
            for (let i = 0; i < n; i++) if (up ? bArr[i] > 0 : bArr[i] < 0) days.push([pArr[i], bArr[i]]);
            if (!days.length) return 0;
            const ap = mean(days.map(d => d[0])), ab = mean(days.map(d => d[1]));
            return ab !== 0 ? ap / ab : 0;
        };
        const calcDdDetails = (arr) => {
            let cum = 0, peak = 0, maxDd = 0, ddEnd = 0, ddStart = 0, pkIdx = 0;
            arr.forEach((r, i) => {
                cum += r;
                if (cum > peak) { peak = cum; pkIdx = i; }
                const dd = peak > 0 ? (cum - peak) / peak : 0;
                if (dd < maxDd) { maxDd = dd; ddEnd = i; ddStart = pkIdx; }
            });
            let rec = null;
            const peakV = arr.slice(0, ddStart + 1).reduce((a, b) => a + b, 0);
            let c2 = peakV;
            for (let i = ddEnd + 1; i < arr.length; i++) { c2 += arr[i]; if (c2 >= peakV) { rec = i - ddEnd; break; } }
            return { pct: maxDd, dur: ddEnd - ddStart, rec, recovered: rec !== null };
        };
        const calcWL = (arr) => {
            const wins = arr.filter(v => v > 0), losses = arr.filter(v => v < 0);
            const wr = arr.length ? wins.length / arr.length : 0;
            const aw = wins.length ? mean(wins) : 0, al = losses.length ? mean(losses) : 0;
            const wl = al !== 0 ? Math.abs(aw / al) : 99;
            const pf = losses.length ? wins.reduce((a, b) => a + b, 0) / Math.abs(losses.reduce((a, b) => a + b, 0)) : 99;
            let cW = 0, cL = 0, mW = 0, mL = 0;
            arr.forEach(v => { if (v > 0) { cW++; cL = 0; mW = Math.max(mW, cW); } else if (v < 0) { cL++; cW = 0; mL = Math.max(mL, cL); } else { cW = cL = 0; } });
            return { wr, aw, al, wl, pf, exp: wr * aw + (1 - wr) * al, mW, mL };
        };

        const allRGross = rows.map(r => toNum(r.actual_next_day_return));
        const allCosts = rows.map(perTradeCostPct);
        const allR = allRGross.map((r, i) => r - allCosts[i]); // Net returns (primary)
        const benchR = rows.map(r => toNum(r.benchmark_1d_return));
        const mddAll = calcMaxDrawdown(allR);
        const mddGross = calcMaxDrawdown(allRGross);
        const ddDet = calcDdDetails(allR);
        const wl = calcWL(allR);
        const wlGross = calcWL(allRGross);
        const tradeCount = rows.length;
        const qWarn = tradeCount < 30
            ? `Only ${tradeCount} completed trades. Minimum 30 required for reliable metrics. Displayed metrics are indicative only.` : '';

        const institutional_metrics = {
            reporting_basis: 'net_of_transaction_costs',
            data_transparency: {
                signals_in_metrics:         rows.length,
                simulated_signals_excluded: metricsIncludeSimulated ? 0 : simCount,
                metrics_basis:              metricsIncludeSimulated ? 'live_and_simulated' : 'live_only',
                earliest_signal_date:       earliestLive,
                note: metricsIncludeSimulated
                    ? 'No live-only evaluated signals found; metrics include historical simulation data.'
                    : 'Metrics based on live pipeline predictions only.',
            },
            sharpe_ratio:             Number(calcSharpeKsa(allR).toFixed(2)),
            sortino_ratio:            Number(calcSortinoKsa(allR).toFixed(2)),
            calmar_ratio:             Number(calcCalmar(allR, mddAll).toFixed(2)),
            max_drawdown_pct:         `${(ddDet.pct * 100).toFixed(1)}%`,
            max_drawdown_duration_days: ddDet.dur,
            max_drawdown_recovered:   ddDet.recovered,
            recovery_duration_days:   ddDet.rec,
            information_ratio:        Number(calcIR(allR, benchR).toFixed(2)),
            beta_vs_benchmark:        Number(calcBeta(allR, benchR).toFixed(2)),
            up_capture_ratio:         Number(calcCapture(allR, benchR, true).toFixed(2)),
            down_capture_ratio:       Number(calcCapture(allR, benchR, false).toFixed(2)),
            win_loss_ratio:           Number(wl.wl.toFixed(2)),
            expectancy_pct:           `${wl.exp >= 0 ? '+' : ''}${wl.exp.toFixed(2)}%`,
            profit_factor:            Number(wl.pf.toFixed(2)),
            consecutive_wins_max:     wl.mW,
            consecutive_losses_max:   wl.mL,
            risk_free_rate_applied:   '4.89%',
            minimum_trades_met:       tradeCount >= 30,
            data_quality_warning:     qWarn,
            avg_cost_per_trade_pct:   Number((allCosts.length ? mean(allCosts) : 0).toFixed(4)),
            cost_drag_total_pct:      Number(allCosts.reduce((a, b) => a + b, 0).toFixed(2)),
            gross_secondary: {
                sharpe_ratio_gross: Number(calcSharpeKsa(allRGross).toFixed(2)),
                sortino_ratio_gross: Number(calcSortinoKsa(allRGross).toFixed(2)),
                calmar_ratio_gross: Number(calcCalmar(allRGross, mddGross).toFixed(2)),
                profit_factor_gross: Number(wlGross.pf.toFixed(2))
            }
        };

        return res.json({
            available: true,
            reporting_basis: 'net_of_transaction_costs',
            institutional_metrics,
            global: {
                total_predictions: allStats.trades,
                wins: allStats.wins,
                losses: allStats.losses,
                win_rate: Number(allStats.win_rate.toFixed(1)),
                avg_return_1d: Number(allStats.avg_return_1d.toFixed(3)),
                avg_return_1d_net: Number(allStats.avg_return_1d.toFixed(3)),
                avg_return_1d_gross: Number(allStats.avg_return_1d_gross.toFixed(3)),
                avg_return_5d: 0,
                avg_alpha_1d: Number(allStats.avg_alpha_1d.toFixed(3)),
                avg_alpha_1d_gross: Number(allStats.avg_alpha_1d_gross.toFixed(3)),
                avg_benchmark_1d: Number(allStats.avg_benchmark_1d.toFixed(3)),
                beat_benchmark_pct: allStats.trades ? Math.round((allStats.beat_benchmark_count / allStats.trades) * 100) : 0,
                beat_benchmark_pct_gross: allStats.trades ? Math.round((allStats.beat_benchmark_count_gross / allStats.trades) * 100) : 0,
                meets_minimum: allStats.trades >= 100,
                first_prediction: rows[0].recommendation_date,
                last_prediction: rows[rows.length - 1].recommendation_date,
                sharpe_ratio: Number(allStats.sharpe_ratio.toFixed(3)),
                sharpe_ratio_gross: Number(allStats.sharpe_ratio_gross.toFixed(3)),
                max_drawdown: Number(allStats.max_drawdown.toFixed(3)),
                max_drawdown_gross: Number(allStats.max_drawdown_gross.toFixed(3)),
                volatility: Number(allStats.volatility.toFixed(3)),
                volatility_gross: Number(allStats.volatility_gross.toFixed(3)),
                profit_factor: Number(allStats.profit_factor.toFixed(3)),
                profit_factor_gross: Number(allStats.profit_factor_gross.toFixed(3)),
                avg_cost_per_trade_pct: Number(allStats.avg_cost_per_trade_pct.toFixed(4)),
                cost_drag_total_pct: Number(allStats.cost_drag_total_pct.toFixed(2))
            },
            rolling: {
                "30d": {
                    trades: r30.trades,
                    win_rate: Number(r30.win_rate.toFixed(1)),
                    alpha: Number(r30.avg_alpha_1d.toFixed(3)),
                    alpha_gross: Number(r30.avg_alpha_1d_gross.toFixed(3)),
                    sharpe_ratio: Number(r30.sharpe_ratio.toFixed(3)),
                    sharpe_ratio_gross: Number(r30.sharpe_ratio_gross.toFixed(3)),
                    max_drawdown: Number(r30.max_drawdown.toFixed(3)),
                    max_drawdown_gross: Number(r30.max_drawdown_gross.toFixed(3)),
                    volatility: Number(r30.volatility.toFixed(3)),
                    volatility_gross: Number(r30.volatility_gross.toFixed(3)),
                    profit_factor: Number(r30.profit_factor.toFixed(3)),
                    profit_factor_gross: Number(r30.profit_factor_gross.toFixed(3)),
                    avg_cost_per_trade_pct: Number(r30.avg_cost_per_trade_pct.toFixed(4))
                },
                "60d": {
                    trades: r60.trades,
                    win_rate: Number(r60.win_rate.toFixed(1)),
                    alpha: Number(r60.avg_alpha_1d.toFixed(3)),
                    alpha_gross: Number(r60.avg_alpha_1d_gross.toFixed(3)),
                    sharpe_ratio: Number(r60.sharpe_ratio.toFixed(3)),
                    sharpe_ratio_gross: Number(r60.sharpe_ratio_gross.toFixed(3)),
                    max_drawdown: Number(r60.max_drawdown.toFixed(3)),
                    max_drawdown_gross: Number(r60.max_drawdown_gross.toFixed(3)),
                    volatility: Number(r60.volatility.toFixed(3)),
                    volatility_gross: Number(r60.volatility_gross.toFixed(3)),
                    profit_factor: Number(r60.profit_factor.toFixed(3)),
                    profit_factor_gross: Number(r60.profit_factor_gross.toFixed(3)),
                    avg_cost_per_trade_pct: Number(r60.avg_cost_per_trade_pct.toFixed(4))
                },
                "90d": {
                    trades: r90.trades,
                    win_rate: Number(r90.win_rate.toFixed(1)),
                    alpha: Number(r90.avg_alpha_1d.toFixed(3)),
                    alpha_gross: Number(r90.avg_alpha_1d_gross.toFixed(3)),
                    sharpe_ratio: Number(r90.sharpe_ratio.toFixed(3)),
                    sharpe_ratio_gross: Number(r90.sharpe_ratio_gross.toFixed(3)),
                    max_drawdown: Number(r90.max_drawdown.toFixed(3)),
                    max_drawdown_gross: Number(r90.max_drawdown_gross.toFixed(3)),
                    volatility: Number(r90.volatility.toFixed(3)),
                    volatility_gross: Number(r90.volatility_gross.toFixed(3)),
                    profit_factor: Number(r90.profit_factor.toFixed(3)),
                    profit_factor_gross: Number(r90.profit_factor_gross.toFixed(3)),
                    avg_cost_per_trade_pct: Number(r90.avg_cost_per_trade_pct.toFixed(4))
                },
                "since_improvement": rSince ? {
                    trades:       rSince.trades,
                    improvement_date: IMPROVEMENT_DATE,
                    win_rate:     Number(rSince.win_rate.toFixed(1)),
                    alpha:        Number(rSince.avg_alpha_1d.toFixed(3)),
                    sharpe_ratio: Number(rSince.sharpe_ratio.toFixed(3)),
                    max_drawdown: Number(rSince.max_drawdown.toFixed(3))
                } : { trades: 0, improvement_date: IMPROVEMENT_DATE }
            },
            disclaimer: "Primary metrics are net of transaction costs and based on live predictions. Gross pre-cost metrics are included as secondary fields."
        });
    } catch (err) {
        console.error('Performance summary error:', err);
        res.status(500).json({ error: 'Failed to load performance summary.' });
    }
});



// â”€â”€â”€ PUBLIC: Per-agent comparison â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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


// â”€â”€â”€ PUBLIC: Per-stock performance â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
router.get('/by-stock', async (req, res) => {
    try {
        const days = Math.min(parseInt(req.query.days) || 90, 365);
        const liveFilter = isPostgres ? '(tr.is_live = TRUE OR tr.is_live IS NULL)' : '(tr.is_live = 1 OR tr.is_live IS NULL)';
        const dateFilter = isPostgres
            ? `tr.recommendation_date >= CURRENT_DATE - (${ph(1)} * INTERVAL '1 day')`
            : `tr.recommendation_date >= date('now', '-' || ${ph(1)} || ' days')`;

        const rows = await dbAll(`
            SELECT
                tr.symbol,
                ${isPostgres ? 's.name_en, s.name_ar, s.sector_en' : "tr.symbol AS name_en, '' AS name_ar, '' AS sector_en"},
                COUNT(*) AS total,
                SUM(CASE WHEN tr.was_correct = ${boolTrue()} THEN 1 ELSE 0 END) AS correct,
                ${isPostgres ? `ROUND(AVG(tr.actual_next_day_return - (${costPctSql('tr')}))::numeric, 3)` : `ROUND(AVG(tr.actual_next_day_return - (${costPctSql('tr')})), 3)`} AS avg_return,
                ${isPostgres ? `ROUND(AVG(COALESCE(tr.alpha_1d, tr.actual_next_day_return - tr.benchmark_1d_return) - (${costPctSql('tr')}))::numeric, 3)` : `ROUND(AVG(COALESCE(tr.alpha_1d, tr.actual_next_day_return - tr.benchmark_1d_return) - (${costPctSql('tr')})), 3)`} AS avg_alpha,
                ${isPostgres ? 'ROUND(AVG(tr.actual_next_day_return)::numeric, 3)' : 'ROUND(AVG(tr.actual_next_day_return), 3)'} AS avg_return_gross,
                ${isPostgres ? 'ROUND(AVG(COALESCE(tr.alpha_1d, tr.actual_next_day_return - tr.benchmark_1d_return))::numeric, 3)' : 'ROUND(AVG(COALESCE(tr.alpha_1d, tr.actual_next_day_return - tr.benchmark_1d_return)), 3)'} AS avg_alpha_gross,
                ${isPostgres
                ? `ROUND((SUM(CASE WHEN tr.was_correct = TRUE THEN 1 ELSE 0 END))::numeric / NULLIF(COUNT(*), 0) * 100, 1)`
                : `ROUND(CAST(SUM(CASE WHEN tr.was_correct = 1 THEN 1 ELSE 0 END) AS REAL) / NULLIF(COUNT(*), 0) * 100, 1)`
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


// â”€â”€â”€ PUBLIC: Equity curve data â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
router.get('/equity-curve', async (req, res) => {
    try {
        const days = Math.min(parseInt(req.query.days) || 180, 365);
        const liveFilter = isPostgres ? '(is_live = TRUE OR is_live IS NULL)' : '(is_live = 1 OR is_live IS NULL)';
        const dateFilter = isPostgres
            ? `recommendation_date >= CURRENT_DATE - (${ph(1)} * INTERVAL '1 day')`
            : `recommendation_date >= date('now', '-' || ${ph(1)} || ' days')`;

        const rows = await dbAll(`
            SELECT
                recommendation_date AS date,
                ${isPostgres ? 'ROUND(AVG(actual_next_day_return)::numeric, 4)' : 'ROUND(AVG(actual_next_day_return), 4)'} AS xmore_gross,
                ${isPostgres ? `ROUND(AVG(${costPctSql()})::numeric, 4)` : `ROUND(AVG(${costPctSql()}), 4)`} AS avg_cost_pct,
                ${isPostgres ? 'ROUND(AVG(benchmark_1d_return)::numeric, 4)' : 'ROUND(AVG(benchmark_1d_return), 4)'} AS tasi
            FROM trade_recommendations
            WHERE actual_next_day_return IS NOT NULL
            AND ${liveFilter}
            AND ${dateFilter}
            GROUP BY recommendation_date
            ORDER BY recommendation_date ASC
        `, [days]);

        let xmoreCum = 0, xmoreCumGross = 0, tasiCum = 0;
        const series = rows.map(r => {
            const gross = parseFloat(r.xmore_gross) || 0;
            const cost = parseFloat(r.avg_cost_pct) || 0;
            const net = gross - cost;
            xmoreCum += net;
            xmoreCumGross += gross;
            tasiCum += parseFloat(r.tasi) || 0;
            return {
                date: r.date,
                xmore: Math.round(xmoreCum * 100) / 100,
                xmore_gross: Math.round(xmoreCumGross * 100) / 100,
                tasi: Math.round(tasiCum * 100) / 100,
                alpha: Math.round((xmoreCum - tasiCum) * 100) / 100,
                alpha_gross: Math.round((xmoreCumGross - tasiCum) * 100) / 100
            };
        });

        return res.json({
            reporting_basis: 'net_of_transaction_costs',
            series,
            total_xmore: series.length ? series[series.length - 1].xmore : 0,
            total_xmore_gross: series.length ? series[series.length - 1].xmore_gross : 0,
            total_tasi: series.length ? series[series.length - 1].tasi : 0,
            total_alpha: series.length ? series[series.length - 1].alpha : 0,
            total_alpha_gross: series.length ? series[series.length - 1].alpha_gross : 0
        });
    } catch (err) {
        if (isTableMissing(err)) {
            return res.json({
                reporting_basis: 'net_of_transaction_costs',
                series: [],
                total_xmore: 0,
                total_xmore_gross: 0,
                total_tasi: 0,
                total_alpha: 0,
                total_alpha_gross: 0
            });
        }
        console.error('Equity curve error:', err);
        res.status(500).json({ error: 'Failed to load equity curve.' });
    }
});


// â”€â”€â”€ PUBLIC: Open predictions (transparency) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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


// â”€â”€â”€ PUBLIC: Prediction history (auditable) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
                cr.is_simulated,
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


// â”€â”€â”€ PUBLIC: Audit trail (for trust) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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


// â”€â”€â”€ PUBLIC: Full institutional report (JSON) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
router.get('/full-report', async (req, res) => {
    try {
        const days = Math.min(parseInt(req.query.days) || 90, 365);
        const liveFilter = isPostgres ? `(is_live = TRUE OR is_live IS NULL)` : `(is_live = 1 OR is_live IS NULL)`;
        const dateFilter = isPostgres
            ? `recommendation_date >= CURRENT_DATE - (${ph(1)} * INTERVAL '1 day')`
            : `recommendation_date >= date('now', '-' || ${ph(1)} || ' days')`;

        let rows = [];
        try {
            rows = await dbAll(`
                SELECT recommendation_date, actual_next_day_return, benchmark_1d_return, alpha_1d, was_correct,
                       round_trip_cost_egp, position_value_egp
                FROM trade_recommendations
                WHERE actual_next_day_return IS NOT NULL
                AND ${liveFilter}
                AND ${dateFilter}
                ORDER BY recommendation_date ASC
            `, [days]);
        } catch (e) {
            if (isTableMissing(e)) return res.json({ available: false });
            throw e;
        }
        if (!rows.length) return res.json({ available: false, message: 'No resolved predictions yet.' });

        const toNum = v => Number(v || 0);
        const mean = arr => arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : 0;
        const stdev = arr => {
            if (arr.length < 2) return 0;
            const m = mean(arr);
            return Math.sqrt(arr.reduce((a, v) => a + (v - m) ** 2, 0) / (arr.length - 1));
        };
        const TRADING_DAYS = 250, KSA_RF = 0.06;
        const dailyRf = Math.pow(1 + KSA_RF, 1 / TRADING_DAYS) - 1;

        const allRGross  = rows.map(r => toNum(r.actual_next_day_return));
        const costs = rows.map(perTradeCostPct);
        const allR = allRGross.map((r, i) => r - costs[i]);
        const benchR = rows.map(r => toNum(r.benchmark_1d_return));
        const window = 30;
        const rollingSharpe = [];
        for (let i = window; i <= allR.length; i++) {
            const w = allR.slice(i - window, i);
            const m = mean(w), s = stdev(w);
            rollingSharpe.push({ day_index: i - 1, sharpe: s > 0 ? Number(((m - dailyRf) / s * Math.sqrt(TRADING_DAYS)).toFixed(4)) : 0 });
        }

        // Equity curve
        let cum = 100;
        const equityCurve = allR.map(r => { cum *= (1 + r / 100); return Number(cum.toFixed(4)); });

        const tradeCount = rows.length;
        const warnings = [];
        if (tradeCount < 30) warnings.push(`Only ${tradeCount} completed trades. Minimum 30 required for reliable metrics.`);
        if (days < 60) warnings.push('Performance period under 60 days. Annualized figures may be misleading.');

        return res.json({
            available: true,
            reporting_basis: 'net_of_transaction_costs',
            period_days: days,
            generated_at: new Date().toISOString(),
            trade_count: tradeCount,
            equity_curve: equityCurve,
            rolling_sharpe_30d: rollingSharpe,
            benchmark_returns: benchR,
            portfolio_returns: allR,
            portfolio_returns_gross: allRGross,
            risk_free_rate_used: KSA_RF,
            minimum_trades_met: tradeCount >= 30,
            avg_cost_per_trade_pct: Number((costs.length ? mean(costs) : 0).toFixed(4)),
            total_cost_drag_pct: Number(costs.reduce((a, b) => a + b, 0).toFixed(2)),
            data_quality_warning: warnings.join(' | '),
        });
    } catch (err) {
        console.error('Full report error:', err);
        res.status(500).json({ error: 'Failed to generate full report.' });
    }
});


// â”€â”€â”€ PUBLIC: Investor PDF export (HTML) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
router.get('/export-summary', async (req, res) => {
    try {
        const days = Math.min(parseInt(req.query.days) || 90, 365);
        const liveFilter = isPostgres ? `(is_live = TRUE OR is_live IS NULL)` : `(is_live = 1 OR is_live IS NULL)`;
        const dateFilter = isPostgres
            ? `recommendation_date >= CURRENT_DATE - (${ph(1)} * INTERVAL '1 day')`
            : `recommendation_date >= date('now', '-' || ${ph(1)} || ' days')`;

        let rows = [];
        try {
            rows = await dbAll(`
                SELECT recommendation_date, actual_next_day_return, benchmark_1d_return, alpha_1d,
                       round_trip_cost_egp, position_value_egp
                FROM trade_recommendations
                WHERE actual_next_day_return IS NOT NULL AND ${liveFilter} AND ${dateFilter}
                ORDER BY recommendation_date ASC
            `, [days]);
        } catch (e) { rows = []; }

        const toNum = v => Number(v || 0);
        const mean  = arr => arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : 0;
        const stdev = arr => { if (arr.length < 2) return 0; const m = mean(arr); return Math.sqrt(arr.reduce((a, v) => a + (v - m) ** 2, 0) / (arr.length - 1)); };
        const TRADING_DAYS = 250, KSA_RF = 0.06;
        const dailyRf = Math.pow(1 + KSA_RF, 1 / TRADING_DAYS) - 1;
        const allRGross = rows.map(r => toNum(r.actual_next_day_return));
        const costs = rows.map(perTradeCostPct);
        const allR = allRGross.map((r, i) => r - costs[i]); // Net primary
        const benchR  = rows.map(r => toNum(r.benchmark_1d_return));
        const calcSharpe = arr => { const m = mean(arr), s = stdev(arr); return s > 0 ? (m - dailyRf) / s * Math.sqrt(TRADING_DAYS) : 0; };
        const calcSortino = arr => { const m = mean(arr), dn = arr.filter(v => v < 0); if (!dn.length) return 99.9; const ds = stdev(dn); return ds > 0 ? (m - dailyRf) / ds * Math.sqrt(TRADING_DAYS) : 99.9; };
        const calcMdd = arr => { let cum = 0, pk = 0, mdd = 0; arr.forEach(r => { cum += r; if (cum > pk) pk = cum; const dd = pk > 0 ? (cum - pk) / pk : 0; if (dd < mdd) mdd = dd; }); return mdd; };
        const calcCalmar = (arr, mdd) => { if (arr.length < 20 || !mdd) return 0; return (Math.pow(1 + mean(arr), TRADING_DAYS) - 1) / Math.abs(mdd); };
        const calcIR = (pArr, bArr) => { const n = Math.min(pArr.length, bArr.length); if (n < 2) return 0; const ex = pArr.slice(0, n).map((v, i) => v - bArr[i]); const te = stdev(ex); return te > 0 ? mean(ex) / te * Math.sqrt(TRADING_DAYS) : 0; };

        // Build SVG equity curve (max 200 points)
        const step = Math.max(1, Math.floor(allR.length / 200));
        const svgPoints = [];
        let c = 100;
        allR.forEach((r, i) => { c *= (1 + r / 100); if (i % step === 0) svgPoints.push(c); });
        const svgW = 700, svgH = 160;
        const minY = Math.min(...svgPoints) * 0.98, maxY = Math.max(...svgPoints) * 1.02;
        const px = (i) => (i / (svgPoints.length - 1)) * svgW;
        const py = (v) => svgH - ((v - minY) / (maxY - minY)) * svgH;
        const pathD = svgPoints.map((v, i) => `${i === 0 ? 'M' : 'L'}${px(i).toFixed(1)},${py(v).toFixed(1)}`).join(' ');
        const svgEquity = `<svg viewBox="0 0 ${svgW} ${svgH}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:160px">
            <defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#10b981" stop-opacity="0.3"/><stop offset="100%" stop-color="#10b981" stop-opacity="0"/></linearGradient></defs>
            <path d="${pathD} L${svgW},${svgH} L0,${svgH} Z" fill="url(#g)"/>
            <path d="${pathD}" fill="none" stroke="#10b981" stroke-width="2"/>
        </svg>`;

        const mdd = calcMdd(allR);
        const sharpe = calcSharpe(allR), sortino = calcSortino(allR), calmar = calcCalmar(allR, mdd), ir = calcIR(allR, benchR);
        const wins = allR.filter(v => v > 0), losses = allR.filter(v => v < 0);
        const wr = allR.length ? (wins.length / allR.length * 100).toFixed(1) : 0;
        const pf = losses.length ? (wins.reduce((a, b) => a + b, 0) / Math.abs(losses.reduce((a, b) => a + b, 0))).toFixed(2) : 'â€”';
        const totalRet = ((allR.reduce((a, b) => a + b, 0))).toFixed(2);
        const totalRetGross = ((allRGross.reduce((a, b) => a + b, 0))).toFixed(2);
        const benchTotal = (benchR.reduce((a, b) => a + b, 0)).toFixed(2);
        const alpha = (Number(totalRet) - Number(benchTotal)).toFixed(2);
        const alphaGross = (Number(totalRetGross) - Number(benchTotal)).toFixed(2);
        const genDate = new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
        const periodStart = rows.length ? String(rows[0].recommendation_date).slice(0, 10) : 'â€”';
        const periodEnd   = rows.length ? String(rows[rows.length - 1].recommendation_date).slice(0, 10) : 'â€”';

        const fmtPct = (v, dec = 2) => `${v >= 0 ? '+' : ''}${Number(v).toFixed(dec)}%`;
        const fmtNum = (v, dec = 2) => Number(v).toFixed(dec);
        const warn = rows.length < 30 ? `<div style="background:#fef3c7;border:1px solid #f59e0b;padding:8px 14px;border-radius:6px;margin-bottom:16px;font-size:12px;color:#92400e">âš  Only ${rows.length} completed trades. Minimum 30 required for statistically reliable metrics.</div>` : '';

        const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Xmore2 Performance Report â€” ${genDate}</title>
<style>
  @page { size: A4; margin: 18mm; }
  * { box-sizing: border-box; }
  body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; color: #111; background: #fff; margin: 0; padding: 0; }
  h1 { font-size: 20px; margin: 0 0 2px; color: #111; }
  h2 { font-size: 13px; margin: 18px 0 8px; border-bottom: 1px solid #e5e7eb; padding-bottom: 4px; color: #374151; }
  .header { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 16px; }
  .header-meta { text-align: right; font-size: 11px; color: #6b7280; }
  .grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 14px; }
  .grid-2 { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
  .card { border: 1px solid #e5e7eb; border-radius: 8px; padding: 10px 14px; }
  .card-label { font-size: 10px; color: #6b7280; margin-bottom: 3px; }
  .card-value { font-size: 18px; font-weight: 700; }
  .green { color: #059669; } .red { color: #dc2626; } .amber { color: #d97706; }
  table { width: 100%; border-collapse: collapse; font-size: 11px; }
  th { background: #f9fafb; padding: 6px 10px; text-align: left; border-bottom: 1px solid #e5e7eb; font-weight: 600; }
  td { padding: 5px 10px; border-bottom: 1px solid #f3f4f6; }
  .highlight { font-weight: 700; color: #d97706; }
  .footer { margin-top: 18px; font-size: 10px; color: #9ca3af; text-align: center; border-top: 1px solid #e5e7eb; padding-top: 8px; }
  @media print { body { -webkit-print-color-adjust: exact; print-color-adjust: exact; } }
</style>
</head>
<body>
<div class="header">
  <div>
    <h1>Xmore2 â€” Tadawul Trading Performance</h1>
    <div style=”color:#6b7280;font-size:11px”>Performance Report Â· ${periodStart} â†’ ${periodEnd} Â· ${rows.length} resolved predictions</div>
  </div>
  <div class=”header-meta”>Generated: ${genDate}<br>Risk-free rate: SAMA 6.00%</div>
</div>
${warn}
<h2>Return Quality (Net of Transaction Costs)</h2>
<div class="grid">
  <div class="card"><div class="card-label">Net Sharpe Ratio</div><div class="card-value ${sharpe >= 1.5 ? 'green' : sharpe >= 0.8 ? 'amber' : 'red'}">${fmtNum(sharpe)}</div></div>
  <div class="card"><div class="card-label">Net Sortino Ratio</div><div class="card-value ${sortino >= 2 ? 'green' : sortino >= 1 ? 'amber' : 'red'}">${fmtNum(sortino)}</div></div>
  <div class="card"><div class="card-label">Net Calmar Ratio</div><div class="card-value ${calmar >= 2 ? 'green' : calmar >= 1 ? 'amber' : 'red'}">${fmtNum(calmar)}</div></div>
  <div class="card"><div class="card-label">Net Information Ratio</div><div class="card-value ${ir >= 0.75 ? 'green' : ir >= 0.4 ? 'amber' : 'red'}">${fmtNum(ir)}</div></div>
</div>
<h2>Risk Profile</h2>
<div class="grid">
  <div class="card"><div class="card-label">Net Max Drawdown</div><div class="card-value ${mdd > -0.1 ? 'green' : mdd > -0.2 ? 'amber' : 'red'}">${(mdd * 100).toFixed(1)}%</div></div>
  <div class="card"><div class="card-label">Win Rate</div><div class="card-value ${Number(wr) >= 55 ? 'green' : Number(wr) >= 45 ? 'amber' : 'red'}">${wr}%</div></div>
  <div class="card"><div class="card-label">Net Profit Factor</div><div class="card-value ${Number(pf) >= 2 ? 'green' : Number(pf) >= 1 ? 'amber' : 'red'}">${pf}</div></div>
  <div class="card"><div class="card-label">Net Total Alpha</div><div class="card-value ${Number(alpha) >= 0 ? 'green' : 'red'}">${fmtPct(alpha)}</div></div>
</div>
<h2>Equity Curve (Net Cumulative Portfolio Value)</h2>
${svgEquity}
<h2>Benchmark Comparison</h2>
<table>
  <thead><tr><th>Metric</th><th>Xmore2</th><th>TASI Benchmark</th></tr></thead>
  <tbody>
    <tr><td>Total Return (Net)</td><td class="${Number(totalRet) >= 0 ? 'highlight' : ''}">${fmtPct(totalRet)}</td><td>${fmtPct(benchTotal)}</td></tr>
    <tr><td>Total Return (Gross, secondary)</td><td>${fmtPct(totalRetGross)}</td><td>${fmtPct(benchTotal)}</td></tr>
    <tr><td>Alpha vs Benchmark (Net)</td><td class="highlight">${fmtPct(alpha)}</td><td>â€”</td></tr>
    <tr><td>Alpha vs Benchmark (Gross, secondary)</td><td>${fmtPct(alphaGross)}</td><td>â€”</td></tr>
    <tr><td>Sharpe Ratio (Net)</td><td class="highlight">${fmtNum(sharpe)}</td><td>â€”</td></tr>
    <tr><td>Profit Factor (Net)</td><td class="${Number(pf) >= 1 ? 'highlight' : ''}">${pf}</td><td>â€”</td></tr>
    <tr><td>Max Drawdown (Net)</td><td class="${mdd > -0.1 ? 'highlight' : ''}">${(mdd * 100).toFixed(1)}%</td><td>â€”</td></tr>
    <tr><td>Avg Cost per Trade</td><td>${fmtPct(costs.length ? mean(costs) : 0, 3)}</td><td>â€”</td></tr>
  </tbody>
</table>
<div class="footer">Generated by Xmore2 &nbsp;|&nbsp; Primary reporting basis: net of transaction costs &nbsp;|&nbsp; Gross metrics shown only as secondary context.</div>
</body>
</html>`;

        res.setHeader('Content-Type', 'text/html; charset=utf-8');
        return res.send(html);
    } catch (err) {
        console.error('Export summary error:', err);
        res.status(500).send('<h1>Failed to generate export.</h1>');
    }
});


module.exports = { router, attachDb: attachDb };

