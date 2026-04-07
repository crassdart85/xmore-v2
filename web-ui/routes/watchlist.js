/**
 * Xmore — Watchlist Routes
 * GET    /api/watchlist         — user's watchlist with latest predictions
 * POST   /api/watchlist/:stockId — add stock to watchlist
 * DELETE /api/watchlist/:stockId — remove stock from watchlist
 */

const express = require('express');
const { authMiddleware } = require('../middleware/auth');

const ACTIVE_MARKET = String(process.env.MARKET || '').toUpperCase();
const STOCK_TABLE = ACTIVE_MARKET === 'KSA' ? 'ksa_stocks' : 'egx30_stocks';

const router = express.Router();

let db = null;
let isPostgres = false;

function attachDb(_db, _isPostgres) {
    db = _db;
    isPostgres = _isPostgres;
}

// Promisify helpers
function dbGet(query, params) {
    return new Promise((resolve, reject) => {
        db.get(query, params, (err, row) => {
            if (err) reject(err);
            else resolve(row);
        });
    });
}

function dbAll(query, params) {
    return new Promise((resolve, reject) => {
        db.all(query, params, (err, rows) => {
            if (err) reject(err);
            else resolve(rows);
        });
    });
}

function dbRun(query, params) {
    return new Promise((resolve, reject) => {
        if (db.run) {
            db.run(query, params, function (err) {
                if (err) reject(err);
                else resolve({ changes: this ? this.changes : 0 });
            });
        } else {
            db.all(query, params, (err, rows) => {
                if (err) reject(err);
                else resolve({ rows, changes: rows ? rows.length : 0 });
            });
        }
    });
}

function ph(n) {
    return isPostgres ? `$${n}` : '?';
}

// ============================================
// GET /api/watchlist
// ============================================
router.get('/watchlist', authMiddleware, async (req, res) => {
    try {
        let query;

        if (isPostgres) {
            query = `
        SELECT
          s.id, s.symbol, s.name_en, s.name_ar, s.sector_en, s.sector_ar,
          w.added_at,
          p.prediction AS latest_prediction,
          p.confidence AS latest_confidence,
          p.target_date AS prediction_date,
          cr.final_signal AS consensus_signal,
          cr.conviction,
          cr.agent_agreement
        FROM user_watchlist w
        JOIN ${STOCK_TABLE} s ON w.stock_id = s.id
        LEFT JOIN LATERAL (
          SELECT prediction, confidence, target_date
          FROM predictions
          WHERE symbol = s.symbol
          ORDER BY target_date DESC
          LIMIT 1
        ) p ON true
        LEFT JOIN LATERAL (
          SELECT final_signal, conviction, agent_agreement
          FROM consensus_results
          WHERE symbol = s.symbol
            AND symbol LIKE '%.SR'
          ORDER BY prediction_date DESC
          LIMIT 1
        ) cr ON true
        WHERE w.user_id = $1
        ORDER BY w.added_at DESC
      `;
        } else {
            // SQLite doesn't support LATERAL JOIN — use subqueries
            query = `
        SELECT
          s.id, s.symbol, s.name_en, s.name_ar, s.sector_en, s.sector_ar,
          w.added_at,
          (SELECT prediction FROM predictions WHERE symbol = s.symbol ORDER BY target_date DESC LIMIT 1) AS latest_prediction,
          (SELECT confidence FROM predictions WHERE symbol = s.symbol ORDER BY target_date DESC LIMIT 1) AS latest_confidence,
          (SELECT target_date FROM predictions WHERE symbol = s.symbol ORDER BY target_date DESC LIMIT 1) AS prediction_date,
          (SELECT final_signal FROM consensus_results WHERE symbol = s.symbol AND symbol LIKE '%.SR' ORDER BY prediction_date DESC LIMIT 1) AS consensus_signal,
          (SELECT conviction FROM consensus_results WHERE symbol = s.symbol AND symbol LIKE '%.SR' ORDER BY prediction_date DESC LIMIT 1) AS conviction,
          (SELECT agent_agreement FROM consensus_results WHERE symbol = s.symbol AND symbol LIKE '%.SR' ORDER BY prediction_date DESC LIMIT 1) AS agent_agreement
        FROM user_watchlist w
        JOIN ${STOCK_TABLE} s ON w.stock_id = s.id
        WHERE w.user_id = ?
        ORDER BY w.added_at DESC
      `;
        }

        const rows = await dbAll(query, [req.userId]);
        return res.json({ watchlist: rows || [] });
    } catch (err) {
        console.error('Watchlist fetch error:', err);
        // Handle table not existing yet
        if (err.message && (err.message.includes('does not exist') || err.message.includes('no such table'))) {
            return res.json({ watchlist: [] });
        }
        return res.status(500).json({ error: 'Internal server error' });
    }
});

// ============================================
// POST /api/watchlist/:stockId
// ============================================
router.post('/watchlist/:stockId', authMiddleware, async (req, res) => {
    try {
        const stockId = parseInt(req.params.stockId);
        if (isNaN(stockId)) {
            return res.status(400).json({ error: 'Invalid stock ID' });
        }

        // Check stock exists
        const boolTrue = isPostgres ? 'TRUE' : '1';
        const stock = await dbGet(
            `SELECT id FROM ${STOCK_TABLE} WHERE id = ${ph(1)} AND is_active = ${boolTrue}`,
            [stockId]
        );
        if (!stock) {
            return res.status(404).json({ error: 'Stock not found' });
        }

        // Add (ignore duplicate via ON CONFLICT or catch unique violation)
        if (isPostgres) {
            await dbRun(
                `INSERT INTO user_watchlist (user_id, stock_id) VALUES ($1, $2)
         ON CONFLICT (user_id, stock_id) DO NOTHING`,
                [req.userId, stockId]
            );
        } else {
            await dbRun(
                `INSERT OR IGNORE INTO user_watchlist (user_id, stock_id) VALUES (?, ?)`,
                [req.userId, stockId]
            );
        }

        return res.status(201).json({ success: true });
    } catch (err) {
        console.error('Watchlist add error:', err);
        return res.status(500).json({ error: 'Internal server error' });
    }
});

// ============================================
// DELETE /api/watchlist/:stockId
// ============================================
router.delete('/watchlist/:stockId', authMiddleware, async (req, res) => {
    try {
        const stockId = parseInt(req.params.stockId);
        if (isNaN(stockId)) {
            return res.status(400).json({ error: 'Invalid stock ID' });
        }

        if (isPostgres) {
            const result = await dbRun(
                `DELETE FROM user_watchlist WHERE user_id = $1 AND stock_id = $2 RETURNING id`,
                [req.userId, stockId]
            );
            if (!result.rows || result.rows.length === 0) {
                return res.status(404).json({ error: 'Stock not in watchlist' });
            }
        } else {
            const result = await dbRun(
                `DELETE FROM user_watchlist WHERE user_id = ? AND stock_id = ?`,
                [req.userId, stockId]
            );
            if (result.changes === 0) {
                return res.status(404).json({ error: 'Stock not in watchlist' });
            }
        }

        return res.json({ success: true });
    } catch (err) {
        console.error('Watchlist remove error:', err);
        return res.status(500).json({ error: 'Internal server error' });
    }
});

module.exports = { router, attachDb };
