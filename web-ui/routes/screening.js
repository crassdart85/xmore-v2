/**
 * Screening & Portfolio Construction Routes
 *
 * GET  /api/screening/top-picks          â€” today's best 5 stocks (cached 1 h)
 * GET  /api/screening/sector-focus       â€” top 3 sectors by buy-signal strength
 * GET  /api/screening/ranked-signals     â€” BUY signals sorted by confidence + win-rate
 * POST /api/screening/portfolio-builder  â€” build a portfolio for a given SAR budget
 */

const { spawn } = require('child_process');
const path = require('path');

const express = require('express');
const router = express.Router();

// Float tolerance used for budget and risk constraint validation (in SAR)
const BUDGET_TOLERANCE_SAR = 1.0; // float tolerance for budget/risk constraints

let db;
let isPostgres = false;

function attachDb(database, pg) {
    db = database;
    isPostgres = !!pg;
}

// â”€â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function dbAll(sql, params = []) {
    return new Promise((resolve, reject) => {
        db.all(sql, params, (err, rows) => {
            if (err) reject(err); else resolve(rows || []);
        });
    });
}

function isTableMissing(err) {
    return err && err.message && (
        err.message.includes('does not exist') ||
        err.message.includes('no such table') ||
        err.message.includes('no such column')
    );
}

/**
 * Execute Python screening engine via child_process.
 * The Python helper CLI accepts:  --action <action> [--date <date>] [--budget <n>] [--risk <n>]
 */
function runScreeningPython(args, timeoutMs = 20000) {
    return new Promise((resolve, reject) => {
        const pythonBin = process.env.PYTHON_BIN || 'python3';
        const scriptPath = path.join(__dirname, '..', '..', 'engines', 'screening_cli.py');
        const child = spawn(pythonBin, [scriptPath, ...args], {
            env: { ...process.env },
            timeout: timeoutMs,
        });

        let stdout = '';
        let stderr = '';
        child.stdout.on('data', d => { stdout += d.toString(); });
        child.stderr.on('data', d => { stderr += d.toString(); });

        child.on('close', code => {
            if (code !== 0) {
                return reject(new Error(`screening_cli exited ${code}: ${stderr.slice(0, 300)}`));
            }
            try {
                resolve(JSON.parse(stdout));
            } catch (e) {
                reject(new Error(`JSON parse error: ${e.message}. Output: ${stdout.slice(0, 200)}`));
            }
        });

        child.on('error', reject);
    });
}

// â”€â”€â”€ In-memory cache (1 hour TTL) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

const _cache = {};

function cacheGet(key) {
    const entry = _cache[key];
    if (!entry) return null;
    if (Date.now() - entry.ts > 3600 * 1000) {
        delete _cache[key];
        return null;
    }
    return entry.data;
}

function cacheSet(key, data) {
    _cache[key] = { data, ts: Date.now() };
}

// â”€â”€â”€ GET /top-picks â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

/**
 * Returns today's top 5 stock picks with rationale.
 * Results are cached for 1 hour to avoid redundant computation.
 *
 * Query params:
 *   date  â€” override date (YYYY-MM-DD), defaults to today
 *   top_n â€” number of picks (default 5, max 10)
 */
router.get('/top-picks', async (req, res) => {
    try {
        const pickDate = req.query.date || new Date().toISOString().slice(0, 10);
        const topN     = Math.min(parseInt(req.query.top_n) || 5, 10);
        const cacheKey = `top-picks:${pickDate}:${topN}`;

        const cached = cacheGet(cacheKey);
        if (cached) return res.json(cached);

        // Try reading pre-computed picks from DB first
        const ph1 = isPostgres ? '$1' : '?';
        const ph2 = isPostgres ? '$2' : '?';
        const sql = `
            SELECT rank, symbol, consensus_signal, conviction, sentiment_score,
                   weighted_score, entry_price, target_price, rationale
            FROM daily_top_picks
            WHERE pick_date = ${ph1}
            ORDER BY rank
            LIMIT ${ph2}
        `;

        let rows = await dbAll(sql, [pickDate, topN]);

        // If no pre-computed picks exist, compute on-the-fly via Python CLI
        if (!rows || rows.length === 0) {
            try {
                const result = await runScreeningPython(
                    ['--action', 'top-picks', '--date', pickDate, '--top_n', String(topN)]
                );
                rows = result.picks || [];
            } catch (pyErr) {
                console.warn('[screening/top-picks] Python CLI failed:', pyErr.message);
                rows = [];
            }
        }

        const payload = {
            pick_date:  pickDate,
            count:      rows.length,
            picks:      rows,
            generated_at: new Date().toISOString(),
            cached:     false,
        };

        if (rows.length > 0) cacheSet(cacheKey, { ...payload, cached: true });
        res.json(payload);

    } catch (err) {
        if (isTableMissing(err)) {
            return res.json({ pick_date: null, count: 0, picks: [], error: 'daily_top_picks table not yet created' });
        }
        console.error('[screening/top-picks]', err.message);
        res.status(500).json({ error: err.message });
    }
});

// â”€â”€â”€ GET /sector-focus â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

/**
 * Returns the top 3 sectors by buy-signal strength.
 *
 * Query params:
 *   date  â€” override date (YYYY-MM-DD), defaults to today
 *   top_n â€” number of sectors (default 3, max 10)
 */
router.get('/sector-focus', async (req, res) => {
    try {
        const rotDate = req.query.date || new Date().toISOString().slice(0, 10);
        const topN    = Math.min(parseInt(req.query.top_n) || 3, 10);
        const cacheKey = `sector-focus:${rotDate}:${topN}`;

        const cached = cacheGet(cacheKey);
        if (cached) return res.json(cached);

        const ph1 = isPostgres ? '$1' : '?';
        const ph2 = isPostgres ? '$2' : '?';
        const sql = `
            SELECT rank, sector, buy_signal_count, avg_conviction,
                   volatility_20d, composite_score, recommended_allocation
            FROM daily_sector_rotation
            WHERE rotation_date = ${ph1}
            ORDER BY rank
            LIMIT ${ph2}
        `;

        let rows = await dbAll(sql, [rotDate, topN]);

        if (!rows || rows.length === 0) {
            try {
                const result = await runScreeningPython(
                    ['--action', 'sector-rotation', '--date', rotDate, '--top_n', String(topN)]
                );
                rows = result.sectors || [];
            } catch (pyErr) {
                console.warn('[screening/sector-focus] Python CLI failed:', pyErr.message);
                rows = [];
            }
        }

        const payload = {
            rotation_date:  rotDate,
            count:          rows.length,
            sectors:        rows,
            generated_at:   new Date().toISOString(),
        };

        if (rows.length > 0) cacheSet(cacheKey, payload);
        res.json(payload);

    } catch (err) {
        if (isTableMissing(err)) {
            return res.json({ rotation_date: null, count: 0, sectors: [], error: 'daily_sector_rotation table not yet created' });
        }
        console.error('[screening/sector-focus]', err.message);
        res.status(500).json({ error: err.message });
    }
});

// â”€â”€â”€ GET /ranked-signals â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

/**
 * Returns active BUY signals sorted by confidence, recent win-rate, and freshness.
 *
 * Query params:
 *   date  â€” override date (YYYY-MM-DD), defaults to today
 *   limit â€” max rows (default 30, max 100)
 */
router.get('/ranked-signals', async (req, res) => {
    try {
        const signalDate = req.query.date || new Date().toISOString().slice(0, 10);
        const limit      = Math.min(parseInt(req.query.limit) || 30, 100);

        // Win-rate sub-query (last 20 predictions per symbol)
        const winRateSub = `
            SELECT symbol,
                   CAST(SUM(CASE WHEN was_correct = 1 THEN 1 ELSE 0 END) AS REAL)
                       / NULLIF(COUNT(*), 0) AS recent_win_rate
            FROM (
                SELECT symbol, was_correct,
                       ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY evaluated_at DESC) AS rn
                FROM evaluations
                WHERE was_correct IS NOT NULL
            ) ranked
            WHERE rn <= 20
            GROUP BY symbol
        `;

        const daysOldExpr = isPostgres
            ? "DATE_PART('day', CURRENT_DATE - cr.prediction_date::DATE)"
            : "JULIANDAY('now') - JULIANDAY(cr.prediction_date)";

        const ph1 = isPostgres ? '$1' : '?';
        const ph2 = isPostgres ? '$2' : '?';

        const sql = `
            SELECT cr.symbol,
                   cr.final_signal        AS signal,
                   cr.confidence,
                   cr.conviction,
                   cr.prediction_date     AS signal_date,
                   cr.momentum_alignment,
                   COALESCE(wr.recent_win_rate, 0.5) AS recent_win_rate,
                   ${daysOldExpr}         AS days_old,
                   COALESCE(p.close, 0)   AS entry_price,
                   COALESCE(p.close * 1.05, 0) AS target_price
            FROM consensus_results cr
            LEFT JOIN (${winRateSub}) wr ON wr.symbol = cr.symbol
            LEFT JOIN (
                SELECT symbol, close
                FROM prices
                WHERE (symbol, date) IN (
                    SELECT symbol, MAX(date) FROM prices GROUP BY symbol
                )
            ) p ON p.symbol = cr.symbol
            WHERE cr.prediction_date = ${ph1}
              AND cr.symbol LIKE '%.SR'
              AND cr.final_signal IN ('BUY', 'STRONG_BUY', 'UP')
              AND cr.risk_action NOT IN ('BLOCK')
            ORDER BY cr.confidence DESC,
                     COALESCE(wr.recent_win_rate, 0.5) DESC,
                     ${daysOldExpr} ASC
            LIMIT ${ph2}
        `;

        const rows = await dbAll(sql, [signalDate, limit]);

        const signals = rows.map(r => {
            const entryPrice   = parseFloat(r.entry_price);
            const targetPrice  = parseFloat(r.target_price);
            return {
                symbol:             r.symbol,
                signal:             r.signal,
                confidence:         parseFloat(r.confidence || 0),
                conviction:         r.conviction,
                signal_date:        r.signal_date,
                momentum_alignment: r.momentum_alignment != null ? parseFloat(r.momentum_alignment) : null,
                recent_win_rate:    parseFloat((parseFloat(r.recent_win_rate || 0.5)).toFixed(4)),
                days_old:           Math.round(parseFloat(r.days_old || 0)),
                entry_price:        entryPrice > 0 ? entryPrice : null,
                target_price:       targetPrice > 0 ? parseFloat(targetPrice.toFixed(2)) : null,
            };
        });

        res.json({
            signal_date: signalDate,
            count:       signals.length,
            signals,
        });

    } catch (err) {
        if (isTableMissing(err)) {
            return res.json({ signal_date: null, count: 0, signals: [], error: 'consensus_results or evaluations table not yet populated' });
        }
        console.error('[screening/ranked-signals]', err.message);
        res.status(500).json({ error: err.message });
    }
});

// â”€â”€â”€ POST /portfolio-builder â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

/**
 * Build a SAR-denominated portfolio from active KSA BUY signals.
 *
 * Body (JSON):
 *   budgetSAR            {number}  â€” total budget in SAR (required; budgetEGP accepted as alias)
 *   riskTolerancePercent {number}  â€” max % of budget to risk (default 5)
 *   date                 {string}  â€” signal date override (default today)
 */
router.post('/portfolio-builder', express.json(), async (req, res) => {
    try {
        const { budgetSAR, budgetEGP, riskTolerancePercent = 5, date: signalDate } = req.body || {};
        const rawBudget = budgetSAR ?? budgetEGP;

        if (!rawBudget || isNaN(Number(rawBudget)) || Number(rawBudget) <= 0) {
            return res.status(400).json({ error: 'budgetSAR must be a positive number' });
        }

        const budget    = Number(rawBudget);
        const riskPct   = Math.min(Math.max(Number(riskTolerancePercent) || 5, 0.5), 30);
        const today     = signalDate || new Date().toISOString().slice(0, 10);
        const maxRisk   = budget * riskPct / 100;
        const maxPerPos = budget * 0.15;

        // Fetch ranked BUY signals directly from DB
        const daysOldExpr = isPostgres
            ? "DATE_PART('day', CURRENT_DATE - cr.prediction_date::DATE)"
            : "JULIANDAY('now') - JULIANDAY(cr.prediction_date)";

        const winRateSub = `
            SELECT symbol,
                   CAST(SUM(CASE WHEN was_correct = 1 THEN 1 ELSE 0 END) AS REAL)
                       / NULLIF(COUNT(*), 0) AS recent_win_rate
            FROM (
                SELECT symbol, was_correct,
                       ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY evaluated_at DESC) AS rn
                FROM evaluations
                WHERE was_correct IS NOT NULL
            ) ranked
            WHERE rn <= 20
            GROUP BY symbol
        `;

        const ph1 = isPostgres ? '$1' : '?';
        const candidateSql = `
            SELECT cr.symbol,
                   cr.final_signal AS signal,
                   cr.confidence,
                   cr.conviction,
                   COALESCE(wr.recent_win_rate, 0.5) AS recent_win_rate,
                   ${daysOldExpr}  AS days_old,
                   COALESCE(p.close, 0) AS entry_price
            FROM consensus_results cr
            LEFT JOIN (${winRateSub}) wr ON wr.symbol = cr.symbol
            LEFT JOIN (
                SELECT symbol, close
                FROM prices
                WHERE (symbol, date) IN (
                    SELECT symbol, MAX(date) FROM prices GROUP BY symbol
                )
            ) p ON p.symbol = cr.symbol
            WHERE cr.prediction_date = ${ph1}
              AND cr.symbol LIKE '%.SR'
              AND cr.final_signal IN ('BUY', 'STRONG_BUY', 'UP')
              AND cr.risk_action NOT IN ('BLOCK')
              AND p.close > 0
            ORDER BY cr.confidence DESC,
                     COALESCE(wr.recent_win_rate, 0.5) DESC,
                     ${daysOldExpr} ASC
            LIMIT 50
        `;

        const candidates = await dbAll(candidateSql, [today]);

        if (!candidates || candidates.length === 0) {
            return res.json({
                status:     'no_signals',
                budget_sar: budget,
                positions:  [],
                summary:    { total_invested: 0, total_risk: 0, position_count: 0 },
            });
        }

        // Sector map (inline â€” avoid Python round-trip for performance)
        // KSA Tadawul universe (.SR symbols)
        const SECTOR_MAP = {
            '1180.SR': 'Banking',        '1120.SR': 'Banking',
            '1140.SR': 'Banking',        '1010.SR': 'Banking',
            '1020.SR': 'Banking',        '1030.SR': 'Banking',
            '1050.SR': 'Banking',        '1060.SR': 'Banking',
            '1080.SR': 'Banking',        '1150.SR': 'Banking',
            '1170.SR': 'Banking',        '1160.SR': 'Insurance',
            '2222.SR': 'Energy',         '2100.SR': 'Energy',
            '2010.SR': 'Petrochemicals', '2020.SR': 'Petrochemicals',
            '2030.SR': 'Petrochemicals', '2060.SR': 'Petrochemicals',
            '2080.SR': 'Petrochemicals', '2090.SR': 'Petrochemicals',
            '7010.SR': 'Telecom',        '7020.SR': 'Telecom',
            '7030.SR': 'Telecom',        '4003.SR': 'Retail',
            '4001.SR': 'Retail',         '4190.SR': 'Retail',
            '4240.SR': 'Retail',         '4321.SR': 'Retail',
            '4050.SR': 'Food & Beverages','4061.SR': 'Food & Beverages',
            '4020.SR': 'Real Estate',    '4040.SR': 'Real Estate',
            '4100.SR': 'Real Estate',    '4150.SR': 'Real Estate',
            '2110.SR': 'Materials',      '2120.SR': 'Industrials',
            '2130.SR': 'Building Materials','2140.SR': 'Industrials',
            '2150.SR': 'Industrials',    '3001.SR': 'Building Materials',
            '3002.SR': 'Building Materials','3003.SR': 'Building Materials',
            '4002.SR': 'Healthcare',     '4005.SR': 'Healthcare',
            '4007.SR': 'Healthcare',     '4009.SR': 'Healthcare',
            '8010.SR': 'Insurance',      '8020.SR': 'Insurance',
            '8030.SR': 'Insurance',      '4030.SR': 'Transportation',
            '4031.SR': 'Transportation',
        };

        const sectorCounts = {};
        const selected = [];

        for (const c of candidates) {
            const sector = SECTOR_MAP[c.symbol] || 'Unknown';
            if ((sectorCounts[sector] || 0) >= 3) continue;

            selected.push({ ...c, sector });
            sectorCounts[sector] = (sectorCounts[sector] || 0) + 1;
            if (selected.length >= 7) break;
        }

        if (selected.length === 0) {
            return res.json({
                status:     'no_eligible_signals',
                budget_sar: budget,
                positions:  [],
                summary:    { total_invested: 0, total_risk: 0, position_count: 0 },
            });
        }

        const posWeight = Math.min(1 / selected.length, 0.15);
        const allocPerPos = budget * posWeight;

        const positions = [];
        let totalInvested = 0;
        let totalRisk = 0;

        for (const sig of selected) {
            const entry = parseFloat(sig.entry_price);
            if (!entry || entry <= 0) continue;

            const stopLoss  = parseFloat((entry * 0.94).toFixed(2));
            const target    = parseFloat((entry * 1.05).toFixed(2));
            const riskPerSh = entry - stopLoss;

            let qty = Math.max(1, Math.floor(allocPerPos / entry));
            let entrySAR = parseFloat((qty * entry).toFixed(2));
            let riskSAR  = parseFloat((qty * riskPerSh).toFixed(2));

            // Clamp to remaining budget
            if (totalInvested + entrySAR > budget + BUDGET_TOLERANCE_SAR) {
                const remaining = budget - totalInvested;
                if (remaining < entry) break;
                qty = Math.max(1, Math.floor(remaining / entry));
                entrySAR = parseFloat((qty * entry).toFixed(2));
                riskSAR  = parseFloat((qty * riskPerSh).toFixed(2));
            }

            positions.push({
                symbol:          sig.symbol,
                sector:          sig.sector,
                signal:          sig.signal,
                confidence:      parseFloat(sig.confidence || 0),
                recent_win_rate: parseFloat(sig.recent_win_rate || 0.5),
                qty,
                entry_price:     entry,
                entry_sar:       entrySAR,
                stop_loss:       stopLoss,
                target,
                risk_sar:        riskSAR,
            });

            totalInvested += entrySAR;
            totalRisk     += riskSAR;
        }

        res.json({
            status:               'ok',
            budget_sar:           budget,
            risk_tolerance_pct:   riskPct,
            signal_date:          today,
            positions,
            summary: {
                position_count:        positions.length,
                total_invested:        parseFloat(totalInvested.toFixed(2)),
                cash_remaining:        parseFloat((budget - totalInvested).toFixed(2)),
                total_risk_sar:        parseFloat(totalRisk.toFixed(2)),
                budget_constraint_met: totalInvested <= budget + BUDGET_TOLERANCE_SAR,
                risk_constraint_met:   totalRisk <= maxRisk + BUDGET_TOLERANCE_SAR,
            },
        });

    } catch (err) {
        if (isTableMissing(err)) {
            return res.status(503).json({ error: 'Required tables not yet populated. Run the pipeline first.' });
        }
        console.error('[screening/portfolio-builder]', err.message);
        res.status(500).json({ error: err.message });
    }
});


module.exports = { router, attachDb };
