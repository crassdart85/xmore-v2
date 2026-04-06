const express = require('express');
const router = express.Router();
const { authMiddleware, optionalAuth } = require('../middleware/auth');

let db;
let isPostgres = false;

function attachDb(_db, _isPostgres) {
    db = _db;
    isPostgres = _isPostgres;
}

// Promisify db.all
function queryAll(sql, params = []) {
    return new Promise((resolve, reject) => {
        if (!db._isPostgres) {
            sql = sql.replace(/\$\d+\b/g, '?');
        }
        db.all(sql, params, (err, rows) => {
            if (err) reject(err);
            else resolve({ rows: rows || [] });
        });
    });
}

// Promisify db.get
function queryOne(sql, params = []) {
    return new Promise((resolve, reject) => {
        if (!db._isPostgres) {
            sql = sql.replace(/\$\d+\b/g, '?');
        }
        db.get(sql, params, (err, row) => {
            if (err) reject(err);
            else resolve(row || null);
        });
    });
}

function parseJSON(str) {
    if (!str) return null;
    try { return JSON.parse(str); } catch { return null; }
}


// ─── GET /api/briefing/today ──────────────────────────────────
// Returns the most recent briefing + user-specific overlays
router.get('/today', optionalAuth, async (req, res) => {
    try {
        // 1. Fetch most recent briefing (handle stale data gracefully)
        const briefingRow = await queryOne(
            `SELECT * FROM daily_briefings ORDER BY briefing_date DESC LIMIT 1`
        );

        if (!briefingRow) {
            return res.json({ available: false });
        }

        const briefingDate = briefingRow.briefing_date;
        const response = {
            available: true,
            briefing_date: briefingDate,
            stocks_processed: briefingRow.stocks_processed,
            generation_time_seconds: briefingRow.generation_time_seconds,
            market_pulse: (() => {
                const mp = parseJSON(briefingRow.market_pulse_json) || {};
                if (mp.top_gainers) mp.top_gainers = mp.top_gainers.filter(s => s.symbol && s.symbol.endsWith('.SR'));
                if (mp.top_losers)  mp.top_losers  = mp.top_losers.filter(s => s.symbol && s.symbol.endsWith('.SR'));
                return mp;
            })(),
            sector_breakdown: parseJSON(briefingRow.sector_breakdown_json) || [],
            risk_alerts: parseJSON(briefingRow.risk_alerts_json) || [],
            sentiment_snapshot: parseJSON(briefingRow.sentiment_snapshot_json) || {},
            // Per-user sections (null if not logged in)
            actions_today: null,
            portfolio_snapshot: null,
            watchlist_heatmap: null
        };

        // 2. If logged in, overlay user-specific data
        if (req.userId) {
            const userId = req.userId;

            // a. Urgent actions (BUY/SELL only)
            const dateFilter = db._isPostgres
                ? `tr.recommendation_date = CURRENT_DATE`
                : `tr.recommendation_date = date('now')`;

            const actionsResult = await queryAll(`
                SELECT tr.symbol, s.name_en, s.name_ar, s.sector_en, s.sector_ar,
                       tr.action, tr.signal, tr.confidence, tr.conviction,
                       tr.priority, tr.close_price, tr.stop_loss_price,
                       tr.target_price, tr.stop_loss_pct, tr.target_pct,
                       tr.reasons, tr.reasons_ar,
                       tr.bull_score, tr.bear_score
                FROM trade_recommendations tr
                JOIN egx30_stocks s ON tr.symbol = s.symbol
                WHERE tr.user_id = $1
                  AND tr.symbol LIKE '%.SR'
                  AND ${dateFilter}
                ORDER BY tr.priority DESC
            `, [userId]);

            const allRecs = actionsResult.rows.map(r => ({
                ...r,
                reasons: parseJSON(r.reasons) || [],
                reasons_ar: parseJSON(r.reasons_ar) || []
            }));

            response.actions_today = allRecs.filter(r => r.action === 'BUY' || r.action === 'SELL');
            response.all_recommendations = allRecs;

            // b. Portfolio snapshot
            const daysHeldExpr = db._isPostgres
                ? "(CURRENT_DATE - up.entry_date)"
                : "CAST(julianday('now') - julianday(up.entry_date) AS INTEGER)";

            const positionsResult = await queryAll(`
                SELECT up.symbol, s.name_en, s.name_ar,
                       up.entry_date, up.entry_price,
                       ${daysHeldExpr} AS days_held
                FROM user_positions up
                JOIN egx30_stocks s ON up.symbol = s.symbol
                WHERE up.user_id = $1
                  AND up.symbol LIKE '%.SR'
                  AND up.status = 'OPEN'
                ORDER BY up.entry_date ASC
            `, [userId]);

            // Enrich with latest prices
            const positions = [];
            for (const p of positionsResult.rows) {
                const priceRow = await queryOne(
                    `SELECT close FROM prices WHERE symbol = $1 ORDER BY date DESC LIMIT 1`,
                    [p.symbol]
                );
                const currentPrice = priceRow ? priceRow.close : null;
                const unrealizedPct = (currentPrice && p.entry_price > 0)
                    ? parseFloat(((currentPrice - p.entry_price) / p.entry_price * 100).toFixed(2))
                    : 0;

                positions.push({
                    symbol: p.symbol,
                    name_en: p.name_en,
                    name_ar: p.name_ar,
                    entry_date: p.entry_date,
                    entry_price: p.entry_price,
                    current_price: currentPrice,
                    unrealized_pct: unrealizedPct,
                    days_held: p.days_held || 0
                });
            }

            // Sort by unrealized % desc for best/worst
            positions.sort((a, b) => b.unrealized_pct - a.unrealized_pct);

            const totalUnrealized = positions.length > 0
                ? parseFloat((positions.reduce((sum, p) => sum + p.unrealized_pct, 0) / positions.length).toFixed(2))
                : 0;

            response.portfolio_snapshot = {
                open_count: positions.length,
                total_unrealized_pct: totalUnrealized,
                best_position: positions[0] || null,
                worst_position: positions[positions.length - 1] || null,
                positions: positions
            };

            // c. Watchlist heatmap — consensus data for user's watchlist stocks
            const heatmapDateFilter = db._isPostgres
                ? `c.prediction_date = $2::date`
                : `c.prediction_date = $2`;

            const heatmapResult = await queryAll(`
                SELECT c.symbol, s.name_en, s.name_ar, s.sector_en, s.sector_ar,
                       c.final_signal, c.confidence, c.conviction,
                       c.bull_score, c.bear_score, c.risk_action
                FROM consensus_results c
                JOIN egx30_stocks s ON c.symbol = s.symbol
                JOIN user_watchlist w ON w.stock_id = s.id
                WHERE w.user_id = $1
                  AND c.symbol LIKE '%.SR'
                  AND ${heatmapDateFilter}
                ORDER BY c.confidence DESC
            `, [userId, briefingDate]);

            response.watchlist_heatmap = heatmapResult.rows.map(r => ({
                ...r,
                signal_strength: Math.abs((r.bull_score || 0) - (r.bear_score || 0))
            }));
            response.watchlist_heatmap.sort((a, b) => b.signal_strength - a.signal_strength);
        }

        return res.json(response);

    } catch (err) {
        console.error('Error fetching briefing:', err);
        return res.status(500).json({ error: 'Failed to load briefing', details: err.message });
    }
});


module.exports = { router, attachDb };
