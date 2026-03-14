/**
 * Universal Investor Scoring API Routes
 * GET /api/signals/scored          — today's signals with composite scores in chosen mode
 * GET /api/signals/scored/compare  — side-by-side comparison across all 6 modes
 * GET /api/signals/morning-brief   — concise morning brief (top BUYs, summary stats)
 */

const express = require('express');
const router  = express.Router();

let db;
let isPostgres = false;

function attachDb(database, pg) {
    db         = database;
    isPostgres = pg;
}

// ─── Helpers ─────────────────────────────────────────────────────

function dbAll(sql, params = []) {
    return new Promise((resolve, reject) => {
        db.all(sql, params, (err, rows) => {
            if (err) reject(err); else resolve(rows || []);
        });
    });
}

function dbGet(sql, params = []) {
    return new Promise((resolve, reject) => {
        db.get(sql, params, (err, row) => {
            if (err) reject(err); else resolve(row || null);
        });
    });
}

function ph(n) { return isPostgres ? `$${n}` : '?'; }

function isTableMissing(err) {
    return err && err.message && (
        err.message.includes('does not exist') ||
        err.message.includes('no such table') ||
        err.message.includes('no such column')
    );
}

// Validate mode param (fall back to standard_100 if unknown)
const VALID_MODES = ['xmore_native', 'standard_100', 'letter_grade', 'stars', 'signal_tier', 'conviction'];
function safeMode(raw) {
    return VALID_MODES.includes(raw) ? raw : 'standard_100';
}

// Parse all_formats JSON stored as TEXT in DB
function parseAllFormats(row) {
    if (!row) return row;
    if (row.all_formats && typeof row.all_formats === 'string') {
        try { row.all_formats = JSON.parse(row.all_formats); } catch (_) {}
    }
    return row;
}

// Mode thresholds for highlighting
const MODE_THRESHOLDS = {
    xmore_native: 0.62,
    standard_100: 62,
    letter_grade: 'B',
    stars:        3.5,
    signal_tier:  'B',
    conviction:   'MEDIUM',
};

// Human-readable mode labels
const MODE_LABELS = {
    xmore_native: 'Xmore Score (0–1)',
    standard_100: 'Score (0–100)',
    letter_grade: 'Grade',
    stars:        'Stars (★)',
    signal_tier:  'Tier',
    conviction:   'Conviction',
};


// ─── GET /scored ─────────────────────────────────────────────────

/**
 * Returns today's scored signals in the requested mode.
 * Query params:
 *   mode   — one of the 6 modes (default: standard_100)
 *   days   — lookback days (default: 1, max: 30)
 *   action — filter by BUY/SELL/HOLD (optional)
 *   min_score — minimum composite_score 0–1 (optional)
 */
router.get('/scored', async (req, res) => {
    try {
        const mode      = safeMode(req.query.mode);
        const days      = Math.min(parseInt(req.query.days) || 1, 30);
        const action    = (req.query.action || '').toUpperCase();
        const minScore  = parseFloat(req.query.min_score) || 0;

        const dateFilter = isPostgres
            ? `signal_date >= CURRENT_DATE - INTERVAL '${days} days'`
            : `signal_date >= date('now', '-${days} days')`;

        let sql    = `SELECT * FROM scored_signals WHERE ${dateFilter} AND composite_score >= ${ph(1)}`;
        let params = [minScore];

        if (action && ['BUY', 'SELL', 'HOLD'].includes(action)) {
            sql    += ` AND action = ${ph(2)}`;
            params.push(action);
        }
        sql += ` ORDER BY composite_score DESC`;

        const rows = await dbAll(sql, params);
        const signals = rows.map(r => {
            r = parseAllFormats(r);
            const allFmt = r.all_formats || {};
            return {
                symbol:          r.symbol,
                signal_date:     r.signal_date,
                action:          r.action,
                composite_score: r.composite_score,
                score:           allFmt[mode] !== undefined ? allFmt[mode] : r.score_value,
                mode,
                mode_label:      MODE_LABELS[mode],
                meets_threshold: r.meets_threshold === 1 || r.meets_threshold === true,
                components: {
                    consensus:  r.consensus_score,
                    execution:  r.execution_score,
                    regime:     r.regime_score,
                    momentum:   r.momentum_score,
                },
                all_formats: allFmt,
            };
        });

        res.json({
            mode,
            mode_label:  MODE_LABELS[mode],
            threshold:   MODE_THRESHOLDS[mode],
            period_days: days,
            count:       signals.length,
            signals,
        });

    } catch (err) {
        if (isTableMissing(err)) {
            return res.json({ mode: safeMode(req.query.mode), count: 0, signals: [], error: 'scored_signals table not yet created' });
        }
        console.error('[scoring/scored]', err.message);
        res.status(500).json({ error: err.message });
    }
});


// ─── GET /scored/compare ─────────────────────────────────────────

/**
 * Returns signals with all 6 scores side-by-side.
 * Useful for the dashboard mode selector.
 * Query params: days (default 1), action filter (optional)
 */
router.get('/scored/compare', async (req, res) => {
    try {
        const days   = Math.min(parseInt(req.query.days) || 1, 30);
        const action = (req.query.action || '').toUpperCase();

        const dateFilter = isPostgres
            ? `signal_date >= CURRENT_DATE - INTERVAL '${days} days'`
            : `signal_date >= date('now', '-${days} days')`;

        let sql    = `SELECT * FROM scored_signals WHERE ${dateFilter}`;
        let params = [];

        if (action && ['BUY', 'SELL', 'HOLD'].includes(action)) {
            sql    += ` AND action = ${ph(1)}`;
            params.push(action);
        }
        sql += ` ORDER BY composite_score DESC`;

        const rows = await dbAll(sql, params);

        const signals = rows.map(r => {
            r = parseAllFormats(r);
            const allFmt = r.all_formats || {};
            return {
                symbol:          r.symbol,
                signal_date:     r.signal_date,
                action:          r.action,
                composite_score: r.composite_score,
                meets_threshold: r.meets_threshold === 1 || r.meets_threshold === true,
                scores: {
                    xmore_native: allFmt.xmore_native,
                    standard_100: allFmt.standard_100,
                    letter_grade: allFmt.letter_grade,
                    stars:        allFmt.stars,
                    signal_tier:  allFmt.signal_tier,
                    conviction:   allFmt.conviction,
                },
                components: {
                    consensus:  r.consensus_score,
                    execution:  r.execution_score,
                    regime:     r.regime_score,
                    momentum:   r.momentum_score,
                },
            };
        });

        res.json({
            period_days: days,
            count:       signals.length,
            modes:       VALID_MODES,
            mode_labels: MODE_LABELS,
            thresholds:  MODE_THRESHOLDS,
            signals,
        });

    } catch (err) {
        if (isTableMissing(err)) {
            return res.json({ count: 0, signals: [], error: 'scored_signals table not yet created' });
        }
        console.error('[scoring/compare]', err.message);
        res.status(500).json({ error: err.message });
    }
});


// ─── GET /morning-brief ──────────────────────────────────────────

/**
 * Concise morning brief: top BUY signals + summary stats.
 * Query params: mode (default standard_100), top_n (default 5)
 */
router.get('/morning-brief', async (req, res) => {
    try {
        const mode  = safeMode(req.query.mode);
        const topN  = Math.min(parseInt(req.query.top_n) || 5, 20);

        const dateFilter = isPostgres
            ? `signal_date = CURRENT_DATE`
            : `signal_date = date('now')`;

        // Top BUYs
        const buySql = `
            SELECT * FROM scored_signals
            WHERE ${dateFilter} AND action = 'BUY'
            ORDER BY composite_score DESC
            LIMIT ${ph(1)}`;
        const buyRows = await dbAll(buySql, [topN]);

        // Stats
        const statSql = `
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN action = 'BUY' THEN 1 ELSE 0 END) AS buys,
                SUM(CASE WHEN action = 'SELL' THEN 1 ELSE 0 END) AS sells,
                AVG(composite_score) AS avg_composite,
                SUM(CASE WHEN meets_threshold = ${isPostgres ? 'TRUE' : '1'} THEN 1 ELSE 0 END) AS above_threshold
            FROM scored_signals
            WHERE ${dateFilter}`;
        const stats = await dbGet(statSql, []);

        const topBuys = buyRows.map(r => {
            r = parseAllFormats(r);
            const allFmt = r.all_formats || {};
            return {
                symbol:          r.symbol,
                score:           allFmt[mode] !== undefined ? allFmt[mode] : r.score_value,
                composite_score: r.composite_score,
                meets_threshold: r.meets_threshold === 1 || r.meets_threshold === true,
                components: {
                    consensus:  r.consensus_score,
                    execution:  r.execution_score,
                    regime:     r.regime_score,
                    momentum:   r.momentum_score,
                },
            };
        });

        res.json({
            date:        new Date().toISOString().slice(0, 10),
            mode,
            mode_label:  MODE_LABELS[mode],
            threshold:   MODE_THRESHOLDS[mode],
            summary: {
                total:           stats ? parseInt(stats.total) : 0,
                buys:            stats ? parseInt(stats.buys)  : 0,
                sells:           stats ? parseInt(stats.sells) : 0,
                avg_composite:   stats ? parseFloat((stats.avg_composite || 0).toFixed(3)) : null,
                above_threshold: stats ? parseInt(stats.above_threshold) : 0,
            },
            top_buys: topBuys,
        });

    } catch (err) {
        if (isTableMissing(err)) {
            return res.json({ summary: { total: 0, buys: 0, sells: 0 }, top_buys: [], error: 'scored_signals table not yet created' });
        }
        console.error('[scoring/morning-brief]', err.message);
        res.status(500).json({ error: err.message });
    }
});


module.exports = { router, attachDb };
