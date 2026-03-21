/**
 * KSA DCF Valuation API Routes
 */
'use strict';

const express = require('express');
const router  = express.Router();

let db, isPostgres;
function attachDb(_db, _pg) { db = _db; isPostgres = _pg; }

const ph = (n) => isPostgres ? `$${n}` : '?';

// GET /api/ksa/dcf/summary — top DEEP_VALUE and SPECULATIVE
router.get('/dcf/summary', async (req, res) => {
    try {
        const deepValue = await db.all(`
            SELECT ticker, scenario, intrinsic_per_share, current_price,
                   margin_of_safety, valuation_label, dcf_confidence, computed_at
            FROM ksa_dcf_valuations
            WHERE valuation_label = 'DEEP_VALUE'
              AND scenario = 'base'
            ORDER BY margin_of_safety DESC
            LIMIT 5
        `);
        const speculative = await db.all(`
            SELECT ticker, scenario, intrinsic_per_share, current_price,
                   margin_of_safety, valuation_label, dcf_confidence, computed_at
            FROM ksa_dcf_valuations
            WHERE valuation_label = 'SPECULATIVE'
              AND scenario = 'base'
            ORDER BY margin_of_safety ASC
            LIMIT 5
        `);
        res.json({ available: true, deep_value: deepValue, speculative });
    } catch (e) {
        // Table may not exist yet
        res.json({ available: false, message: 'DCF data not yet available.' });
    }
});

// GET /api/ksa/dcf/:ticker
router.get('/dcf/:ticker', async (req, res) => {
    const ticker = req.params.ticker.toUpperCase();
    try {
        const rows = await db.all(`
            SELECT *
            FROM ksa_dcf_valuations
            WHERE ticker = ${ph(1)}
            ORDER BY computed_at DESC
            LIMIT 3
        `, [ticker]);
        if (!rows.length) return res.json({ available: false, ticker });
        res.json({ available: true, ticker, valuations: rows });
    } catch (e) {
        res.json({ available: false, message: 'DCF data not available.' });
    }
});

// GET /api/ksa/dcf/screener?label=DEEP_VALUE&confidence=HIGH
router.get('/dcf/screener', async (req, res) => {
    const label      = req.query.label || '';
    const confidence = req.query.confidence || '';

    let where = 'scenario = \'base\'';
    const params = [];
    if (label) {
        params.push(label);
        where += ` AND valuation_label = ${ph(params.length)}`;
    }
    if (confidence) {
        params.push(confidence);
        where += ` AND dcf_confidence = ${ph(params.length)}`;
    }

    try {
        const rows = await db.all(`
            SELECT ticker, valuation_label, margin_of_safety, upside_pct,
                   dcf_confidence, terminal_value_warning, computed_at
            FROM ksa_dcf_valuations
            WHERE ${where}
            ORDER BY margin_of_safety DESC
            LIMIT 20
        `, params);
        res.json({ available: true, results: rows });
    } catch (e) {
        res.json({ available: false, results: [] });
    }
});

// GET /api/ksa/dcf/history/:ticker
router.get('/dcf/history/:ticker', async (req, res) => {
    const ticker = req.params.ticker.toUpperCase();
    try {
        const rows = await db.all(`
            SELECT scenario, intrinsic_per_share, current_price,
                   margin_of_safety, valuation_label, computed_at
            FROM ksa_dcf_valuations
            WHERE ticker = ${ph(1)}
            ORDER BY computed_at DESC
            LIMIT 30
        `, [ticker]);
        res.json({ available: rows.length > 0, ticker, history: rows });
    } catch (e) {
        res.json({ available: false, history: [] });
    }
});

module.exports = { router, attachDb };
