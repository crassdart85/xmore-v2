'use strict';
/**
 * web-ui/routes/etf.js — ETF data API routes.
 *
 * Endpoints:
 *   GET  /api/etf/instruments              — list all instruments with latest price + NAV
 *   GET  /api/etf/prices/:symbol?days=30   — price history for one instrument
 *   GET  /api/etf/nav/:symbol?days=30      — NAV history
 *   GET  /api/etf/premium-discount/:symbol — premium/discount history
 *   GET  /api/etf/fund-volume/:symbol      — latest fund volume row
 *   GET  /api/etf/holdings/:symbol         — latest holdings snapshot + all lines
 *   GET  /api/etf/country-exposure         — Egypt-exposure rows, latest per instrument
 *   GET  /api/etf/documents                — rag_document rows + embedding job status
 */

const express = require('express');
const router  = express.Router();

let db         = null;
let isPostgres = false;
const ACTIVE_MARKET = String(process.env.MARKET || '').toUpperCase();

function attachDb(database, pg) {
    db         = database;
    isPostgres = pg;
}

// ── SQL helpers ───────────────────────────────────────────────────────────────

function ph(n) { return isPostgres ? `$${n}` : '?'; }

function dbAll(sql, params = []) {
    return new Promise((resolve, reject) =>
        db.all(sql, params, (err, rows) => err ? reject(err) : resolve(rows || [])));
}

function dbGet(sql, params = []) {
    return new Promise((resolve, reject) =>
        db.get(sql, params, (err, row) => err ? reject(err) : resolve(row || null)));
}

// Column name for PK differs between PG (instrument_id / snapshot_id / doc_id) and SQLite (id)
const instrIdCol = () => isPostgres ? 'instrument_id' : 'id';
const snapIdCol  = () => isPostgres ? 'snapshot_id'   : 'id';
const docIdCol   = () => isPostgres ? 'doc_id'        : 'id';

// Graceful table-missing handler
function handleMissing(err, res, emptyVal = []) {
    if (err.message && (err.message.includes('does not exist') || err.message.includes('no such table'))) {
        return res.json(emptyVal);
    }
    return res.status(500).json({ error: err.message });
}

function instrumentMarketWhere(alias = 'i') {
    if (ACTIVE_MARKET === 'KSA') {
        return `${alias}.region = 'LOCAL_KSA' OR ${alias}.exchange = 'TADAWUL' OR ${alias}.currency = 'SAR'`;
    }
    return `${alias}.is_active = ${isPostgres ? 'TRUE' : '1'}`;
}

// ── GET /api/etf/instruments ─────────────────────────────────────────────────

router.get('/instruments', async (req, res) => {
    try {
        const idCol = instrIdCol();
        // Instruments joined with latest price and latest NAV
        const sql = `
            SELECT
                i.${idCol}              AS id,
                i.type, i.region, i.symbol, i.name, i.exchange, i.currency,
                i.country, i.issuer, i.underlying_index, i.is_active,
                p.trade_date AS latest_price_date,
                p.close_price, p.last_price, p.pct_change,
                p.value_traded, p.volume,
                n.nav_date,
                n.nav_value,
                pd.premium_discount,
                pd.asof_date AS pd_date
            FROM instrument i
            LEFT JOIN LATERAL (
                SELECT trade_date, close_price, last_price, pct_change, value_traded, volume
                FROM etf_price_daily
                WHERE instrument_id = i.${idCol}
                ORDER BY trade_date DESC LIMIT 1
            ) p ON TRUE
            LEFT JOIN LATERAL (
                SELECT nav_date, nav_value
                FROM etf_nav
                WHERE instrument_id = i.${idCol}
                ORDER BY nav_date DESC LIMIT 1
            ) n ON TRUE
            LEFT JOIN LATERAL (
                SELECT premium_discount, asof_date
                FROM etf_premium_discount_daily
                WHERE instrument_id = i.${idCol}
                ORDER BY asof_date DESC LIMIT 1
            ) pd ON TRUE
            WHERE i.is_active = ${isPostgres ? 'TRUE' : '1'}
            ORDER BY i.region, i.symbol
        `;
        // SQLite fallback (no LATERAL)
        const sqlSqlite = `
            SELECT
                i.${idCol}  AS id,
                i.type, i.region, i.symbol, i.name, i.exchange, i.currency,
                i.country, i.issuer, i.underlying_index, i.is_active,
                p.trade_date AS latest_price_date,
                p.close_price, p.last_price, p.pct_change, p.value_traded, p.volume,
                n.nav_date, n.nav_value,
                pd.premium_discount, pd.asof_date AS pd_date
            FROM instrument i
            LEFT JOIN etf_price_daily p ON p.instrument_id = i.${idCol}
                AND p.trade_date = (SELECT MAX(trade_date) FROM etf_price_daily WHERE instrument_id = i.${idCol})
            LEFT JOIN etf_nav n ON n.instrument_id = i.${idCol}
                AND n.nav_date = (SELECT MAX(nav_date) FROM etf_nav WHERE instrument_id = i.${idCol})
            LEFT JOIN etf_premium_discount_daily pd ON pd.instrument_id = i.${idCol}
                AND pd.asof_date = (SELECT MAX(asof_date) FROM etf_premium_discount_daily WHERE instrument_id = i.${idCol})
            WHERE i.is_active = 1
            ORDER BY i.region, i.symbol
        `;
        const rows = await dbAll(isPostgres ? sql : sqlSqlite, []);
        const filtered = rows.filter(row => ACTIVE_MARKET !== 'KSA' || row.region === 'LOCAL_KSA' || row.exchange === 'TADAWUL' || row.currency === 'SAR');
        res.json(filtered);
    } catch (err) { handleMissing(err, res); }
});

// ── GET /api/etf/prices/:symbol ───────────────────────────────────────────────

router.get('/prices/:symbol', async (req, res) => {
    try {
        const { symbol } = req.params;
        const days = parseInt(req.query.days || '30', 10);
        const idCol = instrIdCol();

        const instr = await dbGet(
            `SELECT ${idCol} AS id FROM instrument WHERE symbol = ${ph(1)}`,
            [symbol.toUpperCase()]
        );
        if (!instr) return res.json([]);

        const cutoff = isPostgres
            ? `CURRENT_DATE - INTERVAL '${days} days'`
            : `date('now','-${days} days')`;
        const rows = await dbAll(
            `SELECT trade_date, open_price, high_price, low_price, close_price,
                    last_price, pct_change, value_traded, volume, trades, market_cap_mn
             FROM etf_price_daily
             WHERE instrument_id = ${ph(1)} AND trade_date >= ${cutoff}
             ORDER BY trade_date`,
            [instr.id]
        );
        res.json(rows);
    } catch (err) { handleMissing(err, res); }
});

// ── GET /api/etf/nav/:symbol ──────────────────────────────────────────────────

router.get('/nav/:symbol', async (req, res) => {
    try {
        const { symbol } = req.params;
        const days = parseInt(req.query.days || '30', 10);
        const idCol = instrIdCol();

        const instr = await dbGet(
            `SELECT ${idCol} AS id FROM instrument WHERE symbol = ${ph(1)}`,
            [symbol.toUpperCase()]
        );
        if (!instr) return res.json([]);

        const cutoff = isPostgres
            ? `CURRENT_DATE - INTERVAL '${days} days'`
            : `date('now','-${days} days')`;
        const rows = await dbAll(
            `SELECT nav_date, nav_value, last_update_raw
             FROM etf_nav
             WHERE instrument_id = ${ph(1)} AND nav_date >= ${cutoff}
             ORDER BY nav_date`,
            [instr.id]
        );
        res.json(rows);
    } catch (err) { handleMissing(err, res); }
});

// ── GET /api/etf/premium-discount/:symbol ────────────────────────────────────

router.get('/premium-discount/:symbol', async (req, res) => {
    try {
        const { symbol } = req.params;
        const days = parseInt(req.query.days || '90', 10);
        const idCol = instrIdCol();

        const instr = await dbGet(
            `SELECT ${idCol} AS id FROM instrument WHERE symbol = ${ph(1)}`,
            [symbol.toUpperCase()]
        );
        if (!instr) return res.json([]);

        const cutoff = isPostgres
            ? `CURRENT_DATE - INTERVAL '${days} days'`
            : `date('now','-${days} days')`;
        const rows = await dbAll(
            `SELECT asof_date, market_price, nav_value, premium_discount, nav_date_used, calc_notes
             FROM etf_premium_discount_daily
             WHERE instrument_id = ${ph(1)} AND asof_date >= ${cutoff}
             ORDER BY asof_date`,
            [instr.id]
        );
        res.json(rows);
    } catch (err) { handleMissing(err, res); }
});

// ── GET /api/etf/fund-volume/:symbol ─────────────────────────────────────────

router.get('/fund-volume/:symbol', async (req, res) => {
    try {
        const { symbol } = req.params;
        const idCol = instrIdCol();

        const instr = await dbGet(
            `SELECT ${idCol} AS id FROM instrument WHERE symbol = ${ph(1)}`,
            [symbol.toUpperCase()]
        );
        if (!instr) return res.json(null);

        const row = await dbGet(
            `SELECT asof_date, fund_size, net_subs, no_units, last_update_raw
             FROM etf_fund_volume
             WHERE instrument_id = ${ph(1)}
             ORDER BY asof_date DESC LIMIT 1`,
            [instr.id]
        );
        res.json(row);
    } catch (err) { handleMissing(err, res, null); }
});

// ── GET /api/etf/holdings/:symbol ────────────────────────────────────────────

router.get('/holdings/:symbol', async (req, res) => {
    try {
        const { symbol } = req.params;
        const idCol   = instrIdCol();
        const snapCol = snapIdCol();

        const instr = await dbGet(
            `SELECT ${idCol} AS id FROM instrument WHERE symbol = ${ph(1)}`,
            [symbol.toUpperCase()]
        );
        if (!instr) return res.json({ snapshot: null, lines: [] });

        const snapshot = await dbGet(
            `SELECT ${snapCol} AS id, snapshot_date, source, source_url, currency, total_weight
             FROM etf_holdings_snapshot
             WHERE instrument_id = ${ph(1)}
             ORDER BY snapshot_date DESC LIMIT 1`,
            [instr.id]
        );
        if (!snapshot) return res.json({ snapshot: null, lines: [] });

        const lines = await dbAll(
            `SELECT line_no, holding_symbol, holding_name, holding_isin,
                    weight_pct, country, sector, asset_type
             FROM etf_holding_line
             WHERE snapshot_id = ${ph(1)}
             ORDER BY line_no`,
            [snapshot.id]
        );
        res.json({ snapshot, lines });
    } catch (err) { handleMissing(err, res, { snapshot: null, lines: [] }); }
});

// ── GET /api/etf/country-exposure ────────────────────────────────────────────

router.get('/country-exposure', async (req, res) => {
    try {
        if (ACTIVE_MARKET === 'KSA') return res.json([]);
        const idCol = instrIdCol();
        // Latest Egypt exposure per global instrument
        const sqlPg = `
            SELECT DISTINCT ON (ce.instrument_id)
                i.symbol, i.name, i.exchange, i.issuer,
                ce.country, ce.weight_pct, ce.asof_date, ce.source_url
            FROM etf_country_exposure ce
            JOIN instrument i ON i.instrument_id = ce.instrument_id
            WHERE ce.country = 'Egypt'
            ORDER BY ce.instrument_id, ce.asof_date DESC
        `;
        const sqlSqlite = `
            SELECT i.symbol, i.name, i.exchange, i.issuer,
                   ce.country, ce.weight_pct, ce.asof_date, ce.source_url
            FROM etf_country_exposure ce
            JOIN instrument i ON i.id = ce.instrument_id
            WHERE ce.country = 'Egypt'
              AND ce.asof_date = (
                  SELECT MAX(asof_date) FROM etf_country_exposure
                  WHERE instrument_id = ce.instrument_id AND country = 'Egypt'
              )
            ORDER BY ce.weight_pct DESC
        `;
        const rows = await dbAll(isPostgres ? sqlPg : sqlSqlite, []);
        res.json(rows);
    } catch (err) { handleMissing(err, res); }
});

// ── GET /api/etf/documents ───────────────────────────────────────────────────

router.get('/documents', async (req, res) => {
    try {
        const instrId = req.query.instrument_id;
        const idCol   = instrIdCol();
        const docCol  = docIdCol();

        let sql, params;
        if (isPostgres) {
            sql = `
                SELECT d.doc_id AS id, d.title, d.doc_type, d.publisher, d.language,
                       d.url, d.fetched_at, d.ingested_at,
                       i.symbol AS instrument_symbol,
                       j.status AS embed_status, j.error_message AS embed_error
                FROM rag_document d
                LEFT JOIN instrument i ON i.instrument_id = d.instrument_id
                LEFT JOIN LATERAL (
                    SELECT status, error_message FROM rag_embedding_job
                    WHERE doc_id = d.doc_id ORDER BY job_id DESC LIMIT 1
                ) j ON TRUE
                ${instrId ? `WHERE d.instrument_id = ${ph(1)}` : ''}
                ORDER BY d.ingested_at DESC
            `;
            params = instrId ? [instrId] : [];
        } else {
            sql = `
                SELECT d.id, d.title, d.doc_type, d.publisher, d.language,
                       d.url, d.fetched_at, d.ingested_at,
                       i.symbol AS instrument_symbol,
                       j.status AS embed_status, j.error_message AS embed_error
                FROM rag_document d
                LEFT JOIN instrument i ON i.id = d.instrument_id
                LEFT JOIN rag_embedding_job j ON j.doc_id = d.id
                    AND j.id = (SELECT MAX(id) FROM rag_embedding_job WHERE doc_id = d.id)
                ${instrId ? `WHERE d.instrument_id = ${ph(1)}` : ''}
                ORDER BY d.ingested_at DESC
            `;
            params = instrId ? [instrId] : [];
        }
        const rows = await dbAll(sql, params);
        res.json(rows);
    } catch (err) { handleMissing(err, res); }
});

// ── GET /api/etf/signals — ETF technical signals ─────────────────────────────

router.get('/signals', async (req, res) => {
    try {
        const iid = instrIdCol();
        const sql = `SELECT s.instrument_id, s.symbol, s.signal_date, s.signal,
                    s.confidence, s.ma_signal, s.rsi_signal, s.nav_signal,
                    s.momentum_signal, s.rsi_value, s.nav_premium_pct,
                    s.close_price, s.notes,
                    i.name, i.type, i.region, i.exchange, i.currency
             FROM etf_signals s
             JOIN instrument i ON i.${iid} = s.instrument_id
             WHERE s.signal_date = (
                 SELECT MAX(signal_date) FROM etf_signals s2
                 WHERE s2.instrument_id = s.instrument_id
             )
             ORDER BY s.confidence DESC, s.symbol ASC`;
        const rows = await dbAll(sql, []);
        const filtered = rows.filter(row => ACTIVE_MARKET !== 'KSA' || row.region === 'LOCAL_KSA' || row.exchange === 'TADAWUL' || row.currency === 'SAR');
        res.json(filtered);
    } catch (err) {
        if (err.message && (err.message.includes('does not exist') || err.message.includes('no such table'))) {
            return res.json([]);
        }
        console.error('[etf] /signals error:', err.message);
        res.status(500).json({ error: err.message });
    }
});

// ── exports ───────────────────────────────────────────────────────────────────

module.exports = { router, attachDb };
