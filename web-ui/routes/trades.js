const express = require('express');
const router = express.Router();
const { authMiddleware } = require('../middleware/auth');

let db;

function attachDb(database) {
    db = database;
}

// Helper to promisify db.all (since server.js db wrapper uses callbacks)
function queryAll(sql, params = []) {
    return new Promise((resolve, reject) => {
        // Adjust params placeholder if SQLite
        if (!db._isPostgres) {
            sql = sql.replace(/\$\d+\b/g, '?');
        }

        db.all(sql, params, (err, rows) => {
            if (err) reject(err);
            else resolve({ rows: rows || [] }); // match pg format
        });
    });
}

function safeJsonArrayParse(value) {
    if (!value) return [];
    if (Array.isArray(value)) return value;
    try {
        const parsed = JSON.parse(value);
        return Array.isArray(parsed) ? parsed : [];
    } catch {
        return [];
    }
}


// ─── GET /api/trades/today ────────────────────────────────────
router.get('/today', authMiddleware, async (req, res) => {
    try {
        const userId = req.userId;

        // Fetch user language preference
        // We do this inside the route to keep auth middleware lightweight
        const userSql = `SELECT preferred_language FROM users WHERE id = $1`;
        // Since we are inside an async route and queryAll returns { rows: [] }
        // We need to be careful with queryAll result structure
        let lang = 'en';
        try {
            const userRes = await queryAll(userSql, [userId]);
            if (userRes.rows.length > 0) {
                lang = userRes.rows[0].preferred_language || 'en';
            }
        } catch (e) {
            console.warn('Failed to fetch user language, defaulting to en', e);
        }

        // PostgreSQL uses LATERAL, SQLite might not support it in older versions, 
        // but Render generic SQLite usually is modern enough or we fallback.
        // For simplicity, we keep the query mostly standard.
        // However, SQLite doesn't use $1, $2. We handle that in queryAll.

        const sql = `
            SELECT
                tr.symbol,
                s.name_en, s.name_ar, s.sector_en, s.sector_ar,
                tr.action, tr.signal, tr.confidence, tr.conviction,
                tr.risk_action, tr.priority,
                tr.close_price, tr.stop_loss_pct, tr.target_pct,
                tr.stop_loss_price, tr.target_price, tr.risk_reward_ratio,
                tr.reasons, tr.reasons_ar,
                tr.bull_score, tr.bear_score,
                tr.agents_agreeing, tr.agents_total,
                tr.risk_flags,
                tr.trend_ar, tr.trend_en, tr.rec_type_ar, tr.rec_type_en,
                tr.buy_guide, tr.pivot, tr.r1, tr.r2, tr.s1, tr.s2,
                CASE WHEN up.id IS NOT NULL THEN 1 ELSE 0 END AS has_position,
                up.entry_date, up.entry_price
            FROM trade_recommendations tr
            JOIN egx30_stocks s ON tr.symbol = s.symbol
            LEFT JOIN user_positions up
                ON up.user_id = tr.user_id
                AND up.symbol = tr.symbol
                AND up.status = 'OPEN'
            WHERE tr.user_id = $1
            AND tr.recommendation_date = $2
            ORDER BY tr.priority DESC
        `;

        const today = new Date().toISOString().split('T')[0];
        let result = await queryAll(sql, [userId, today]);
        let usedDate = today;
        let fallbackUsed = false;

        if (!result.rows.length) {
            const latestDateRes = await queryAll(
                `SELECT MAX(recommendation_date) AS latest_date FROM trade_recommendations WHERE user_id = $1`,
                [userId]
            );
            const latestDateRaw = latestDateRes.rows[0]?.latest_date;
            const latestDate = latestDateRaw
                ? new Date(latestDateRaw).toISOString().split('T')[0]
                : null;

            if (latestDate) {
                result = await queryAll(sql, [userId, latestDate]);
                if (result.rows.length) {
                    usedDate = latestDate;
                    fallbackUsed = true;
                }
            }
        }

        // Summary counts
        const rows = result.rows;
        const summary = {
            buy: rows.filter(r => r.action === 'BUY').length,
            sell: rows.filter(r => r.action === 'SELL').length,
            hold: rows.filter(r => r.action === 'HOLD').length,
            watch: rows.filter(r => r.action === 'WATCH').length,
            total: rows.length,
            date: usedDate,
            fallback_used: fallbackUsed
        };

        return res.json({
            summary,
            recommendations: rows.map(r => ({
                ...r,
                name: lang === 'ar' ? r.name_ar : r.name_en,
                reasons: lang === 'ar' ? safeJsonArrayParse(r.reasons_ar) : safeJsonArrayParse(r.reasons),
                has_position: !!r.has_position
            }))
        });
    } catch (err) {
        console.error('Error fetching today trades:', err);
        res.status(500).json({ error: 'Failed to fetch trades', details: err.message });
    }
});


// ─── GET /api/trades/history ──────────────────────────────────
router.get('/history', authMiddleware, async (req, res) => {
    try {
        const userId = req.userId;
        const page = parseInt(req.query.page) || 1;
        const limit = Math.min(parseInt(req.query.limit) || 20, 50);
        const offset = (page - 1) * limit;
        const action = req.query.action;
        const symbol = req.query.symbol;

        let whereClause = 'WHERE tr.user_id = $1';
        const params = [userId];
        let paramIdx = 2;

        if (action) {
            whereClause += ` AND tr.action = $${paramIdx++}`;
            params.push(action.toUpperCase());
        }
        if (symbol) {
            whereClause += ` AND tr.symbol = $${paramIdx++}`;
            params.push(symbol.toUpperCase());
        }

        const sql = `
            SELECT 
                tr.*, s.name_en, s.name_ar,
                tr.actual_next_day_return, tr.actual_5day_return, tr.was_correct
            FROM trade_recommendations tr
            JOIN egx30_stocks s ON tr.symbol = s.symbol
            ${whereClause}
            ORDER BY tr.recommendation_date DESC, tr.priority DESC
            LIMIT $${paramIdx++} OFFSET $${paramIdx++}
        `;

        const result = await queryAll(sql, [...params, limit, offset]);

        // Count query
        const countSql = `SELECT COUNT(*) as count FROM trade_recommendations tr ${whereClause}`;
        // params only up to filters, excluding limit/offset
        const countParams = params;

        const countResult = await queryAll(countSql, countParams);
        const total = parseInt(countResult.rows[0].count);

        return res.json({
            trades: result.rows,
            pagination: {
                page,
                limit,
                total: total,
                pages: Math.ceil(total / limit)
            }
        });
    } catch (err) {
        console.error('Error fetching trade history:', err);
        res.status(500).json({ error: 'Server error' });
    }
});

// ─── GET /api/portfolio ───────────────────────────────────────
router.get('/portfolio', authMiddleware, async (req, res) => {
    try {
        // Since we are mocking 'user_positions' which might not exist if running fresh without migration locally (though I added sql),
        // we should be careful. 
        // Also LATERAL might flag on SQLite.

        const userId = req.userId;

        // Open positions
        // Re-write query to avoid LATERAL for better SQLite compat if needed, 
        // but for now let's stick to the prompt's SQL and assume Postgres (Production) or decent SQLite.
        // Actually, let's use a subquery in SELECT join which is safer.
        const daysHeldExpr = db._isPostgres
            ? "(CURRENT_DATE - up.entry_date)"
            : "CAST(julianday('now') - julianday(up.entry_date) AS INTEGER)";

        const openSql = `
            SELECT
                up.id, up.symbol, s.name_en, s.name_ar, s.sector_en, s.sector_ar,
                up.entry_date, up.entry_price,
                COALESCE(up.quantity, 1) AS quantity,
                (SELECT close FROM prices WHERE symbol = up.symbol ORDER BY date DESC LIMIT 1) AS current_price,
                ${daysHeldExpr} AS days_held
            FROM user_positions up
            LEFT JOIN egx30_stocks s ON up.symbol = s.symbol
            WHERE up.user_id = $1 AND up.status = 'OPEN'
            ORDER BY up.entry_date DESC
        `;

        const openResult = await queryAll(openSql, [userId]);
        const openPositions = openResult.rows.map(p => {
            const qty = parseInt(p.quantity) || 1;
            const entry = parseFloat(p.entry_price) || 0;
            const current = parseFloat(p.current_price) || 0;
            const ret = entry > 0 && current > 0
                ? ((current - entry) / entry * 100).toFixed(2)
                : 0;
            const cost_sar = +(entry * qty).toFixed(2);
            const value_sar = current > 0 ? +(current * qty).toFixed(2) : null;
            const pnl_sar = value_sar != null ? +(value_sar - cost_sar).toFixed(2) : null;
            return { ...p, quantity: qty, unrealized_return_pct: ret, cost_sar, value_sar, pnl_sar };
        });

        // Closed positions
        const closedDaysExpr = db._isPostgres
            ? "(up.exit_date - up.entry_date)"
            : "CAST(julianday(up.exit_date) - julianday(up.entry_date) AS INTEGER)";

        const closedSql = `
            SELECT
                up.symbol, s.name_en, s.name_ar,
                up.entry_date, up.entry_price,
                up.exit_date, up.exit_price,
                up.return_pct,
                ${closedDaysExpr} AS days_held
            FROM user_positions up
            JOIN egx30_stocks s ON up.symbol = s.symbol
            WHERE up.user_id = $1 AND up.status = 'CLOSED'
            ORDER BY up.exit_date DESC
            LIMIT 30
        `;
        const closedResult = await queryAll(closedSql, [userId]);

        // Stats
        const statsSql = `
            SELECT 
                COUNT(*) as count,
                status,
                return_pct
            FROM user_positions
            WHERE user_id = $1
        `;
        // Aggregate in JS to avoid complex FILTER which SQLite hates
        const allPositionsSql = `SELECT status, return_pct FROM user_positions WHERE user_id = $1`;
        const allPosResult = await queryAll(allPositionsSql, [userId]);

        const allPos = allPosResult.rows;
        const closed = allPos.filter(p => p.status === 'CLOSED');
        const open = allPos.filter(p => p.status === 'OPEN');

        const total_trades = closed.length;
        const winning = closed.filter(p => p.return_pct > 0);
        const losing = closed.filter(p => p.return_pct <= 0);

        const avg_ret = total_trades > 0 ? closed.reduce((sum, p) => sum + (p.return_pct || 0), 0) / total_trades : 0;
        const avg_win = winning.length > 0 ? winning.reduce((sum, p) => sum + (p.return_pct || 0), 0) / winning.length : 0;
        const avg_loss = losing.length > 0 ? losing.reduce((sum, p) => sum + (p.return_pct || 0), 0) / losing.length : 0;

        // Portfolio totals
        const totalCostSar = openPositions.reduce((s, p) => s + (p.cost_sar || 0), 0);
        const totalValueSar = openPositions.reduce((s, p) => s + (p.value_sar || p.cost_sar || 0), 0);
        const totalPnlSar = totalValueSar - totalCostSar;
        const totalReturnPct = totalCostSar > 0 ? +((totalPnlSar / totalCostSar) * 100).toFixed(2) : 0;

        // Sector breakdown (by cost_sar)
        const sectorMap = {};
        for (const p of openPositions) {
            const sec = p.sector_en || 'Other';
            sectorMap[sec] = (sectorMap[sec] || 0) + (p.cost_sar || 0);
        }
        const sector_breakdown = Object.entries(sectorMap)
            .map(([sector, cost]) => ({
                sector,
                weight_pct: totalCostSar > 0 ? +((cost / totalCostSar) * 100).toFixed(1) : 0
            }))
            .sort((a, b) => b.weight_pct - a.weight_pct);

        return res.json({
            open_positions: openPositions,
            closed_positions: closedResult.rows,
            totals: {
                total_cost_sar: +totalCostSar.toFixed(2),
                total_value_sar: +totalValueSar.toFixed(2),
                total_pnl_sar: +totalPnlSar.toFixed(2),
                total_return_pct: totalReturnPct,
            },
            sector_breakdown,
            stats: {
                total_trades,
                winning_trades: winning.length,
                losing_trades: losing.length,
                win_rate: total_trades > 0 ? Math.round((winning.length / total_trades) * 100) : 0,
                avg_return: parseFloat(avg_ret.toFixed(2)),
                avg_win: parseFloat(avg_win.toFixed(2)),
                avg_loss: parseFloat(avg_loss.toFixed(2)),
                open_positions: open.length
            }
        });

    } catch (err) {
        console.error('Error fetching portfolio:', err);
        res.status(500).json({ error: 'Server error' });
    }
});

// ─── GET /api/trades/performance ──────────────────────────────
router.get('/performance', authMiddleware, async (req, res) => {
    try {
        const userId = req.userId;
        const days = parseInt(req.query.days) || 30;

        // SQLite doesn't support FILTER (WHERE...) in aggregates easily or INTERVAL syntax
        // We'll fetch rows and aggregate in JS for compatibility

        const dateLimit = new Date();
        dateLimit.setDate(dateLimit.getDate() - days);
        const dateStr = dateLimit.toISOString().split('T')[0];

        const sql = `
            SELECT action, was_correct, actual_next_day_return, actual_5day_return
            FROM trade_recommendations
            WHERE user_id = $1
            AND recommendation_date >= $2
            AND was_correct IS NOT NULL
        `;

        const result = await queryAll(sql, [userId, dateStr]);

        // Group by action
        const stats = { BUY: [], SELL: [], HOLD: [], WATCH: [] };
        result.rows.forEach(r => {
            if (stats[r.action]) stats[r.action].push(r);
        });

        const by_action = Object.keys(stats).map(action => {
            const items = stats[action];
            if (items.length === 0) return null;

            const total = items.length;
            const correct = items.filter(i => i.was_correct).length; // 1 or true
            const avg1d = items.reduce((sum, i) => sum + (i.actual_next_day_return || 0), 0) / total;
            const avg5d = items.reduce((sum, i) => sum + (i.actual_5day_return || 0), 0) / total;

            return {
                action,
                total,
                correct,
                avg_1d_return: parseFloat(avg1d.toFixed(2)),
                avg_5d_return: parseFloat(avg5d.toFixed(2))
            };
        }).filter(x => x);

        return res.json({
            period_days: days,
            by_action
        });
    } catch (err) {
        console.error('Error fetching performance:', err);
        res.status(500).json({ error: 'Server error' });
    }
});

// ─── POST /api/trades/positions — Open a virtual position ────────────────────
router.post('/positions', authMiddleware, async (req, res) => {
    try {
        const userId = req.user?.userId || req.userId;
        const { symbol, entry_price, entry_date, quantity } = req.body;
        if (!symbol || !entry_price) {
            return res.status(400).json({ error: 'symbol and entry_price are required' });
        }
        const date = entry_date || new Date().toISOString().split('T')[0];
        const price = parseFloat(entry_price);
        const qty = Math.max(1, parseInt(quantity) || 1);
        if (isNaN(price) || price <= 0) return res.status(400).json({ error: 'Invalid entry_price' });

        const sql = db._isPostgres
            ? `INSERT INTO user_positions (user_id, symbol, status, entry_date, entry_price, quantity)
               VALUES ($1, $2, 'OPEN', $3, $4, $5)
               ON CONFLICT ON CONSTRAINT idx_unique_open_position DO NOTHING
               RETURNING id`
            : `INSERT OR IGNORE INTO user_positions (user_id, symbol, status, entry_date, entry_price, quantity)
               VALUES (?, ?, 'OPEN', ?, ?, ?)`;

        const result = await queryAll(sql, [userId, symbol, date, price, qty]);
        if (db._isPostgres && result.rows.length === 0) {
            return res.status(409).json({ error: 'An open position for this symbol already exists' });
        }
        return res.json({ ok: true, message: `Position opened for ${symbol} at ${price} × ${qty}` });
    } catch (err) {
        console.error('Error opening position:', err);
        res.status(500).json({ error: 'Server error' });
    }
});

// ─── PATCH /api/trades/positions/:id — Close a virtual position ───────────────
router.patch('/positions/:id', authMiddleware, async (req, res) => {
    try {
        const userId = req.user?.userId || req.userId;
        const posId = parseInt(req.params.id);
        const { exit_price, exit_date } = req.body;
        if (!exit_price) return res.status(400).json({ error: 'exit_price is required' });

        const price = parseFloat(exit_price);
        if (isNaN(price) || price <= 0) return res.status(400).json({ error: 'Invalid exit_price' });
        const date = exit_date || new Date().toISOString().split('T')[0];

        // Fetch position to compute return_pct
        const fetchSql = `SELECT id, entry_price FROM user_positions WHERE id = $1 AND user_id = $2 AND status = 'OPEN'`;
        const fetchRes = await queryAll(fetchSql, [posId, userId]);
        if (fetchRes.rows.length === 0) {
            return res.status(404).json({ error: 'Open position not found' });
        }
        const entryPrice = parseFloat(fetchRes.rows[0].entry_price);
        const returnPct = entryPrice > 0 ? parseFloat(((price - entryPrice) / entryPrice * 100).toFixed(4)) : 0;

        const updateSql = `
            UPDATE user_positions
            SET status = 'CLOSED', exit_price = $1, exit_date = $2, return_pct = $3, updated_at = CURRENT_TIMESTAMP
            WHERE id = $4 AND user_id = $5 AND status = 'OPEN'
        `;
        await queryAll(updateSql, [price, date, returnPct, posId, userId]);
        return res.json({ ok: true, return_pct: returnPct, message: `Position closed at ${price} (${returnPct > 0 ? '+' : ''}${returnPct}%)` });
    } catch (err) {
        console.error('Error closing position:', err);
        res.status(500).json({ error: 'Server error' });
    }
});

// ─── Session Sheet (/api/trades/session-sheet) ───────────────────────────────
// Returns the latest Tadawul session signals enriched with pivot levels, trend,
// and execution guidance.
router.get('/session-sheet', authMiddleware, async (req, res) => {
    try {
        const userId = req.userId;

        // Resolve latest date for this user
        const latestRes = await queryAll(
            `SELECT MAX(recommendation_date) AS d FROM trade_recommendations WHERE user_id = $1`,
            [userId]
        );
        const sessionDate = latestRes.rows[0]?.d
            ? new Date(latestRes.rows[0].d).toISOString().split('T')[0]
            : new Date().toISOString().split('T')[0];

        // Stock signals
        const stocksSql = `
            SELECT
                tr.symbol,
                COALESCE(s.name_en, REPLACE(REPLACE(tr.symbol, '.SR', ''), '.CA', '')) AS name_en,
                COALESCE(s.name_ar, REPLACE(REPLACE(tr.symbol, '.SR', ''), '.CA', '')) AS name_ar,
                s.sector_en, s.sector_ar,
                tr.action, tr.signal, tr.confidence, tr.conviction,
                tr.close_price, tr.stop_loss_price, tr.stop_loss_pct,
                tr.target_price, tr.target_pct, tr.risk_reward_ratio,
                tr.trend_ar, tr.trend_en, tr.rec_type_ar, tr.rec_type_en,
                tr.buy_guide, tr.pivot, tr.r1, tr.r2, tr.s1, tr.s2, tr.patterns
            FROM trade_recommendations tr
            LEFT JOIN egx30_stocks s ON tr.symbol = s.symbol
            WHERE tr.user_id = $1
              AND tr.recommendation_date = $2
              AND tr.signal IN ('UP', 'DOWN')
              AND (UPPER(tr.symbol) LIKE '%.SR' OR UPPER(tr.symbol) IN ('TASI', 'TASI.SR', 'MT30', 'MT30.SR'))
            ORDER BY tr.confidence DESC, tr.priority DESC
        `;
        const stocksRes = await queryAll(stocksSql, [userId, sessionDate]);

        // Index pivot levels (TASI, MT30 when available in the price store)
        const indexSymbols = [
            { candidates: ['TASI.SR', 'TASI', '^TASI'], name_en: 'TASI Index', name_ar: 'مؤشر تاسي' },
            { candidates: ['MT30.SR', 'MT30'], name_en: 'Tadawul MT30', name_ar: 'مؤشر إم تي 30' },
        ];
        const indexData = [];
        for (const meta of indexSymbols) {
            let selectedSymbol = null;
            let idxRes = { rows: [] };
            for (const candidate of meta.candidates) {
                const ph = db._isPostgres ? '$1' : '?';
                idxRes = await queryAll(
                    `SELECT open, high, low, close FROM prices WHERE symbol = ${ph} ORDER BY date DESC LIMIT 2`,
                    [candidate]
                );
                if (idxRes.rows.length >= 2) {
                    selectedSymbol = candidate;
                    break;
                }
            }
            if (idxRes.rows.length >= 2) {
                const prev = idxRes.rows[1];
                const H = parseFloat(prev.high), L = parseFloat(prev.low), C = parseFloat(prev.close);
                const P  = (H + L + C) / 3;
                const R1 = 2*P - L, R2 = P + (H - L);
                const S1 = 2*P - H, S2 = P - (H - L);
                const close = parseFloat(idxRes.rows[0].close);
                indexData.push({
                    symbol: selectedSymbol,
                    name_en: meta.name_en,
                    name_ar: meta.name_ar,
                    close_price:    parseFloat(close.toFixed(2)),
                    stop_loss_price: parseFloat((close * 0.97).toFixed(2)),
                    pivot: parseFloat(P.toFixed(2)),
                    r1:    parseFloat(R1.toFixed(2)),
                    r2:    parseFloat(R2.toFixed(2)),
                    s1:    parseFloat(S1.toFixed(2)),
                    s2:    parseFloat(S2.toFixed(2)),
                });
            }
        }

        res.json({
            session_date: sessionDate,
            stocks:  stocksRes.rows,
            indices: indexData,
        });
    } catch (err) {
        console.error('Error fetching session sheet:', err);
        res.status(500).json({ error: 'Server error' });
    }
});

// ─── Price Alerts ──────────────────────────────────────────────

// GET /api/trades/alerts — list user's alerts + trigger check vs latest price
router.get('/alerts', authMiddleware, async (req, res) => {
    try {
        const userId = req.user?.userId || req.userId;
        const sql = `
            SELECT a.id, a.symbol, a.condition, a.target_price, a.active, a.triggered_at, a.created_at,
                   (SELECT close FROM prices WHERE symbol = a.symbol ORDER BY date DESC LIMIT 1) AS current_price
            FROM price_alerts a
            WHERE a.user_id = $1
            ORDER BY a.created_at DESC
            LIMIT 50
        `;
        const result = await queryAll(sql, [userId]);
        // Auto-trigger active alerts
        for (const alert of result.rows) {
            if (!alert.active) continue;
            const cur = parseFloat(alert.current_price);
            const tgt = parseFloat(alert.target_price);
            if (isNaN(cur) || isNaN(tgt)) continue;
            const hit = (alert.condition === 'above' && cur >= tgt) || (alert.condition === 'below' && cur <= tgt);
            if (hit) {
                const now = new Date().toISOString();
                await queryAll(
                    `UPDATE price_alerts SET active = $1, triggered_at = $2 WHERE id = $3`,
                    [false, now, alert.id]
                ).catch(() => {});
                alert.active = false;
                alert.triggered_at = now;
            }
        }
        res.json({ alerts: result.rows });
    } catch (err) {
        res.status(500).json({ error: 'Server error' });
    }
});

// POST /api/trades/alerts — create alert
router.post('/alerts', authMiddleware, async (req, res) => {
    try {
        const userId = req.user?.userId || req.userId;
        const { symbol, condition, target_price } = req.body;
        if (!symbol || !target_price || !['above', 'below'].includes(condition)) {
            return res.status(400).json({ error: 'symbol, condition (above/below), target_price required' });
        }
        const price = parseFloat(target_price);
        if (isNaN(price) || price <= 0) return res.status(400).json({ error: 'Invalid target_price' });
        // Limit 20 active alerts per user
        const countRes = await queryAll(
            `SELECT COUNT(*) AS cnt FROM price_alerts WHERE user_id = $1 AND active = $2`,
            [userId, true]
        );
        const cnt = parseInt(countRes.rows[0]?.cnt) || 0;
        if (cnt >= 20) return res.status(400).json({ error: 'Maximum 20 active alerts allowed' });

        await queryAll(
            `INSERT INTO price_alerts (user_id, symbol, condition, target_price, active) VALUES ($1, $2, $3, $4, $5)`,
            [userId, symbol.toUpperCase(), condition, price, true]
        );
        res.json({ ok: true });
    } catch (err) {
        res.status(500).json({ error: 'Server error' });
    }
});

// DELETE /api/trades/alerts/:id
router.delete('/alerts/:id', authMiddleware, async (req, res) => {
    try {
        const userId = req.user?.userId || req.userId;
        await queryAll(
            `DELETE FROM price_alerts WHERE id = $1 AND user_id = $2`,
            [parseInt(req.params.id), userId]
        );
        res.json({ ok: true });
    } catch (err) {
        res.status(500).json({ error: 'Server error' });
    }
});

module.exports = { router, attachDb };
