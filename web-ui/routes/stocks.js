/**
 * Xmore — Stocks Route
 * GET /api/stocks — returns the active Tadawul universe when available.
 */

const express = require('express');
const router = express.Router();

let db = null;

function attachDb(_db) {
    db = _db;
}

// GET /api/stocks — public, prefers Saudi rows and falls back to legacy rows.
router.get('/stocks', (req, res) => {
    const isPostgres = db && db._isPostgres;
        console.log('DEBUG: /api/stocks hit. isPostgres:', isPostgres, 'Querying DB...');
        const ksaQuery = `
    SELECT id, symbol, name_en, name_ar, sector_en, sector_ar
    FROM egx30_stocks
    WHERE is_active = ${isPostgres ? 'TRUE' : '1'}
            AND UPPER(symbol) LIKE '%.SR'
    ORDER BY symbol
  `;
        const fallbackQuery = `
        SELECT id, symbol, name_en, name_ar, sector_en, sector_ar
        FROM egx30_stocks
        WHERE is_active = ${isPostgres ? 'TRUE' : '1'}
        ORDER BY CASE WHEN UPPER(symbol) LIKE '%.SR' THEN 0 ELSE 1 END, symbol
    `;

    if (!db || !db.all) {
        console.error('DEBUG: DB object missing or invalid');
        return res.status(500).json({ error: 'Database not initialized' });
    }

    db.all(ksaQuery, [], (err, rows) => {
        if (err) {
            if (err.message && (err.message.includes('does not exist') || err.message.includes('no such table'))) {
                return res.json({ stocks: [] });
            }
            return res.status(500).json({ error: err.message });
        }

        if (rows && rows.length > 0) {
            return res.json({ stocks: rows });
        }

        db.all(fallbackQuery, [], (fallbackErr, fallbackRows) => {
            if (fallbackErr) {
                if (fallbackErr.message && (fallbackErr.message.includes('does not exist') || fallbackErr.message.includes('no such table'))) {
                    return res.json({ stocks: [] });
                }
                return res.status(500).json({ error: fallbackErr.message });
            }
            res.json({ stocks: fallbackRows || [] });
        });
    });
});

module.exports = { router, attachDb };
