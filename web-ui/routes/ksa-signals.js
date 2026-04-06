/**
 * KSA Signals API Routes
 * All queries partition by market_id = 'KSA'
 * KSA/Tadawul signal routes with SAR currency and .SR tickers
 */
'use strict';

const express = require('express');
const router  = express.Router();

let db, isPostgres;
function attachDb(_db, _pg) { db = _db; isPostgres = _pg; }

const ph = (n) => isPostgres ? `$${n}` : '?';
const simFilter = () => isPostgres
    ? `(is_simulated = FALSE OR is_simulated IS NULL)`
    : `(is_simulated = 0 OR is_simulated IS NULL)`;

function dbAll(query, params = []) {
    return new Promise((resolve, reject) => {
        db.all(query, params, (err, rows) => err ? reject(err) : resolve(rows || []));
    });
}

function dbGet(query, params = []) {
    return new Promise((resolve, reject) => {
        db.get(query, params, (err, row) => err ? reject(err) : resolve(row || null));
    });
}

function isTableMissing(err) {
    return err && err.message && (
        err.message.includes('does not exist') ||
        err.message.includes('no such table') ||
        err.message.includes('no such column')
    );
}

async function dbGetSafe(query, params = [], fallback = null) {
    try {
        return await dbGet(query, params);
    } catch (err) {
        if (isTableMissing(err)) return fallback;
        throw err;
    }
}

// GET /api/ksa/signals/latest — last 20 KSA signals
router.get('/signals/latest', async (req, res) => {
    try {
        const limit = Math.min(Math.max(parseInt(req.query.limit || '20', 10), 1), 50);
        const rows = await dbAll(`
            SELECT c.symbol, COALESCE(k.name_en, c.symbol) AS name_en,
                   final_signal, conviction, xmore_score, confidence,
                   bull_score, bear_score, agent_agreement, prediction_date AS timestamp,
                   drivers_json, risk_level, expected_move, signal_label, liquidity_score
            FROM consensus_results c
            LEFT JOIN ksa_stocks k ON k.symbol = c.symbol
            WHERE c.market_id = 'KSA'
            ORDER BY prediction_date DESC
            LIMIT ${ph(1)}
        `, [limit]);
        const result = rows.map(r => ({
            ...r,
            ticker: r.symbol,
            signal: r.final_signal,
            company: r.name_en,
            summary: `${r.symbol} ${r.final_signal || 'HOLD'}${r.expected_move ? ` · ${r.expected_move}` : ''}`,
            drivers: (() => { try { return JSON.parse(r.drivers_json || '[]'); } catch { return []; } })(),
            drivers_json: undefined,
        }));
        res.json({ available: true, signals: result });
    } catch (e) {
        console.error('[KSA] /signals/latest error:', e);
        res.status(500).json({ error: 'Failed to load KSA signals' });
    }
});

// GET /api/ksa/signals/today — today's pre-market signals
router.get('/signals/today', async (req, res) => {
    try {
        const latest = await dbGet(`
            SELECT MAX(prediction_date) AS latest_date
            FROM consensus_results
            WHERE market_id = 'KSA'
        `);
        const latestDate = latest?.latest_date || null;
        if (!latestDate) {
            return res.json({ available: true, date: null, signals: [], stale: false });
        }

        const dateClause = isPostgres
            ? `prediction_date = ${ph(1)}::date`
            : `prediction_date = ${ph(1)}`;
        const rows = await dbAll(`
            SELECT c.symbol, COALESCE(k.name_en, c.symbol) AS name_en,
                   final_signal, conviction, xmore_score, confidence,
                   bull_score, bear_score, agent_agreement, prediction_date AS timestamp,
                   drivers_json, risk_level, expected_move,
                   signal_label, liquidity_score
            FROM consensus_results c
            LEFT JOIN ksa_stocks k ON k.symbol = c.symbol
            WHERE c.market_id = 'KSA'
              AND ${dateClause}
            ORDER BY xmore_score DESC
        `, [latestDate]);
        const result = rows.map(r => ({
            ...r,
            ticker: r.symbol,
            signal: r.final_signal,
            company: r.name_en,
            drivers: (() => { try { return JSON.parse(r.drivers_json || '[]'); } catch { return []; } })(),
            drivers_json: undefined,
        }));
        const apiDate = String(latestDate).slice(0, 10);
        const stale = apiDate !== new Date().toISOString().slice(0, 10);
        res.json({ available: true, date: apiDate, signals: result, stale });
    } catch (e) {
        res.status(500).json({ error: 'Failed to load today\'s KSA signals' });
    }
});

// GET /api/ksa/performance/summary — KSA win rate, Sharpe, profit factor
router.get('/performance/summary', async (req, res) => {
    try {
        const rows = await dbAll(`
            SELECT actual_next_day_return, benchmark_1d_return, was_correct,
                   alpha_1d, recommendation_date
            FROM trade_recommendations
            WHERE market_id = 'KSA'
              AND actual_next_day_return IS NOT NULL
              AND ${simFilter()}
            ORDER BY recommendation_date ASC
        `);

        if (!rows.length) return res.json({ available: false, message: 'No KSA evaluated signals yet.' });

        const toNum = v => Number(v || 0);
        const mean  = arr => arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : 0;
        const stdev = arr => {
            if (arr.length < 2) return 0;
            const m = mean(arr);
            return Math.sqrt(arr.reduce((a, v) => a + (v - m) ** 2, 0) / (arr.length - 1));
        };

        // KSA: SAIBOR 3M 4.89% annual
        const SAIBOR_3M  = 0.0489;
        const TRADING_DAYS = 250;
        const dailyRf    = Math.pow(1 + SAIBOR_3M, 1 / TRADING_DAYS) - 1;

        const returns    = rows.map(r => toNum(r.actual_next_day_return));
        const bench      = rows.map(r => toNum(r.benchmark_1d_return));
        const wins       = rows.filter(r => r.was_correct === true || r.was_correct === 1 || r.was_correct === 't').length;
        const winRate    = rows.length ? (wins / rows.length) * 100 : 0;

        const m = mean(returns), s = stdev(returns);
        const sharpe  = s > 0 ? ((m / 100 - dailyRf) / (s / 100)) * Math.sqrt(TRADING_DAYS) : 0;

        const profits = returns.filter(v => v > 0).reduce((a, b) => a + b, 0);
        const losses  = Math.abs(returns.filter(v => v < 0).reduce((a, b) => a + b, 0));
        const pf      = losses > 0 ? profits / losses : (profits > 0 ? 99 : 0);

        const alpha30rows = rows.slice(-30);
        const alpha30 = mean(alpha30rows.map((r, i) => toNum(r.actual_next_day_return) - toNum(r.benchmark_1d_return)));

        res.json({
            available:     true,
            total_signals: rows.length,
            win_rate:      Number(winRate.toFixed(1)),
            sharpe_ratio:  Number(sharpe.toFixed(2)),
            profit_factor: Number(pf.toFixed(2)),
            alpha_30d:     Number((alpha30 * 100).toFixed(2)),
            risk_free_rate: 'SAIBOR 3M 4.89%',
            currency:      'SAR',
        });
    } catch (e) {
        console.error('[KSA] performance/summary error:', e);
        res.status(500).json({ error: 'Failed to load KSA performance' });
    }
});

// GET /api/ksa/regime — current TASI regime
router.get('/regime', async (req, res) => {
    try {
        const row = await dbGet(`
            SELECT regime_label_en, regime_label_ar, regime_confidence,
                   n_regimes, trading_date
            FROM regime_log
            WHERE market_id = 'KSA'
            ORDER BY trading_date DESC
            LIMIT 1
        `);
        if (!row) return res.json({ available: false, regime: 'calm', label: 'Unknown' });
        const rawLabel = String(row.regime_label_en || '').toLowerCase();
        const regime = rawLabel.includes('crisis')
            ? 'crisis'
            : rawLabel.includes('turb')
                ? 'turbulent'
                : 'calm';
        res.json({
            available: true,
            regime,
            label: row.regime_label_en || 'Unknown',
            label_ar: row.regime_label_ar || null,
            probability: row.regime_confidence != null ? Number(row.regime_confidence) : null,
            n_regimes: row.n_regimes,
            as_of: row.trading_date,
        });
    } catch (e) {
        res.json({ available: false, regime: 'calm', label: 'Unknown' });
    }
});

// GET /api/ksa/freshness
router.get('/freshness', async (_req, res) => {
    try {
        const [pricesRow, signalsRow, dcfRow] = await Promise.all([
            dbGetSafe(
                `SELECT MAX(date) AS latest_value FROM prices WHERE market_id = 'KSA' OR symbol LIKE '%.SR'`,
                [],
                null,
            ).then(row => row || dbGetSafe(
                `SELECT MAX(date) AS latest_value FROM prices WHERE symbol LIKE '%.SR'`,
                [],
                { latest_value: null },
            )),
            dbGetSafe(
                `SELECT MAX(prediction_date) AS latest_value FROM consensus_results WHERE market_id = 'KSA'`,
                [],
                { latest_value: null },
            ),
            dbGetSafe(
                `SELECT MAX(COALESCE(computed_at, valuation_date)) AS latest_value FROM ksa_dcf_valuations`,
                [],
                null,
            ).then(row => row || dbGetSafe(
                `SELECT MAX(valuation_date) AS latest_value FROM ksa_dcf_valuations`,
                [],
                { latest_value: null },
            )),
        ]);

        res.json({
            available: true,
            prices_updated: pricesRow?.latest_value || null,
            signals_updated: signalsRow?.latest_value || null,
            dcf_updated: dcfRow?.latest_value || null,
        });
    } catch (e) {
        console.error('[KSA] /freshness error:', e);
        res.status(500).json({ error: 'Failed to load KSA freshness' });
    }
});

// GET /api/ksa/ticker
router.get('/ticker', async (_req, res) => {
    try {
        const rows = await dbAll(`
            WITH latest_prices AS (
                SELECT p.symbol, p.close, p.open, p.volume, p.date,
                       ROW_NUMBER() OVER (PARTITION BY p.symbol ORDER BY p.date DESC) AS rn
                FROM prices p
                WHERE p.symbol LIKE '%.SR'
            )
            SELECT lp.symbol,
                   COALESCE(k.name_en, lp.symbol) AS name_en,
                   lp.close AS price,
                   lp.date,
                   lp.volume,
                   CASE
                     WHEN lp.open IS NOT NULL AND lp.open <> 0
                     THEN ROUND(((lp.close - lp.open) / lp.open * 100)::numeric, 2)
                     ELSE NULL
                   END AS change_pct
            FROM latest_prices lp
            LEFT JOIN ksa_stocks k ON k.symbol = lp.symbol
            WHERE lp.rn = 1
            ORDER BY COALESCE(lp.volume, 0) DESC, lp.symbol ASC
            LIMIT 12
        `);

        res.json({
            available: true,
            tickers: rows.map(row => ({
                symbol: row.symbol,
                name_en: row.name_en,
                price: row.price != null ? Number(row.price) : null,
                change_pct: row.change_pct != null ? Number(row.change_pct) : 0,
                date: row.date || null,
            })),
        });
    } catch (e) {
        console.error('[KSA] /ticker error:', e);
        res.status(500).json({ error: 'Failed to load KSA ticker' });
    }
});

// GET /api/ksa/signals/:ticker/history
router.get('/signals/:ticker/history', async (req, res) => {
    const ticker = req.params.ticker.toUpperCase();
    try {
        const rows = await dbAll(`
            SELECT symbol, final_signal, conviction, xmore_score,
                   prediction_date AS timestamp,
                   bull_score, bear_score, agent_agreement
            FROM consensus_results
            WHERE market_id = 'KSA'
              AND symbol = ${ph(1)}
            ORDER BY prediction_date DESC
            LIMIT 60
        `, [ticker]);
        res.json({ available: true, ticker, history: rows });
    } catch (e) {
        res.status(500).json({ error: 'Failed to load ticker history' });
    }
});

// GET /api/ksa/execution/:ticker — stop loss, target, pivot levels for sim UI
router.get('/execution/:ticker', async (req, res) => {
    const ticker = req.params.ticker.toUpperCase();
    try {
        // Latest evaluated trade rec with price levels
        const rec = await dbGet(`
            SELECT symbol, recommendation_date,
                   close_price, stop_loss_price, stop_loss_pct,
                   target_price, target_pct, risk_reward_ratio,
                   buy_guide, pivot, r1, r2, s1, s2, patterns,
                   signal_type, confidence, conviction, xmore_score
            FROM trade_recommendations
            WHERE symbol = ${ph(1)}
              AND market_id = 'KSA'
              AND close_price IS NOT NULL
            ORDER BY recommendation_date DESC
            LIMIT 1
        `, [ticker]);

        // Latest price (may be fresher than trade rec)
        const latestPrice = await dbGet(`
            SELECT close, date
            FROM prices
            WHERE symbol = ${ph(1)}
            ORDER BY date DESC
            LIMIT 1
        `, [ticker]);

        if (!rec && !latestPrice) {
            return res.json({ available: false, ticker });
        }

        const entry = parseFloat(latestPrice?.close || rec?.close_price || 0);
        const stopLossPrice = parseFloat(rec?.stop_loss_price || 0) || (entry > 0 ? parseFloat((entry * 0.97).toFixed(2)) : null);
        const targetPrice   = parseFloat(rec?.target_price || 0) || (entry > 0 ? parseFloat((entry * 1.06).toFixed(2)) : null);
        const stopPct       = parseFloat(rec?.stop_loss_pct || 0) || (stopLossPrice && entry ? ((stopLossPrice - entry) / entry * 100) : -3);
        const targetPct     = parseFloat(rec?.target_pct || 0) || (targetPrice && entry ? ((targetPrice - entry) / entry * 100) : 6);
        const rr            = parseFloat(rec?.risk_reward_ratio || 0) || (stopPct && targetPct ? Math.abs(targetPct / stopPct).toFixed(2) : null);

        return res.json({
            available:     true,
            ticker,
            signal:        rec?.signal_type || null,
            conviction:    rec?.conviction || null,
            confidence:    parseFloat(rec?.confidence || 0),
            xmore_score:   parseFloat(rec?.xmore_score || 0),
            buy_guide:     rec?.buy_guide || null,
            // Price levels
            entry_price:   entry,
            stop_loss:     stopLossPrice,
            stop_loss_pct: parseFloat(stopPct.toFixed(2)),
            target_price:  targetPrice,
            target_pct:    parseFloat(targetPct.toFixed(2)),
            risk_reward:   rr ? parseFloat(Number(rr).toFixed(2)) : null,
            // Pivots
            pivot: parseFloat(rec?.pivot || 0) || null,
            r1:    parseFloat(rec?.r1 || 0) || null,
            r2:    parseFloat(rec?.r2 || 0) || null,
            s1:    parseFloat(rec?.s1 || 0) || null,
            s2:    parseFloat(rec?.s2 || 0) || null,
            patterns:      rec?.patterns || null,
            as_of:         latestPrice?.date || rec?.recommendation_date || null,
            currency:      'SAR',
        });
    } catch (e) {
        console.error('[KSA] /execution/:ticker error:', e);
        res.status(500).json({ error: 'Failed to load execution data' });
    }
});


// GET /api/ksa/context/:ticker — sentiment × signal context flag
router.get('/context/:ticker', async (req, res) => {
    const ticker = req.params.ticker.toUpperCase();
    try {
        // Latest consensus signal
        const cs = await dbGet(`
            SELECT final_signal, confidence, xmore_score, signal_label,
                   drivers_json, risk_level, expected_move
            FROM consensus_results
            WHERE market_id = 'KSA'
              AND symbol = ${ph(1)}
            ORDER BY prediction_date DESC
            LIMIT 1
        `, [ticker]);

        // Latest sentiment score
        const sent = await dbGet(`
            SELECT avg_sentiment, sentiment_label, article_count, date
            FROM sentiment_scores
            WHERE symbol = ${ph(1)}
            ORDER BY date DESC
            LIMIT 1
        `, [ticker]);

        const signal = (cs?.final_signal || 'HOLD').toUpperCase();
        const sentVal = parseFloat(sent?.avg_sentiment || 0);
        const sentLabel = sent?.sentiment_label || 'neutral';

        // Compute context flag: signal direction × sentiment alignment
        let contextFlag = null;
        let contextClass = 'neutral';
        if (signal === 'BUY') {
            if (sentVal > 0.2)        { contextFlag = 'Sentiment Confirms ↑'; contextClass = 'bullish'; }
            else if (sentVal < -0.2)  { contextFlag = 'Sentiment Headwind ⚠';  contextClass = 'warning'; }
            else                       { contextFlag = 'Neutral News';           contextClass = 'neutral'; }
        } else if (signal === 'SELL') {
            if (sentVal < -0.2)       { contextFlag = 'Sentiment Confirms ↓'; contextClass = 'bearish'; }
            else if (sentVal > 0.2)   { contextFlag = 'Contrarian Signal ⚠';   contextClass = 'warning'; }
            else                       { contextFlag = 'Neutral News';           contextClass = 'neutral'; }
        } else {
            contextFlag  = 'Monitoring';
            contextClass = 'neutral';
        }

        // Recent news events (last 3 articles for event overlay)
        let recentNews = [];
        try {
            recentNews = await dbAll(`
                SELECT title, published_at, source, url
                FROM news_items
                WHERE symbol = ${ph(1)}
                ORDER BY published_at DESC
                LIMIT 3
            `, [ticker]);
        } catch (_) { /* table may not exist */ }

        return res.json({
            available:     true,
            ticker,
            signal,
            context_flag:  contextFlag,
            context_class: contextClass,
            sentiment: {
                score:   sentVal,
                label:   sentLabel,
                articles: parseInt(sent?.article_count || 0),
                as_of:   sent?.date || null,
            },
            recent_news: recentNews,
            drivers: (() => { try { return JSON.parse(cs?.drivers_json || '[]'); } catch { return []; } })(),
        });
    } catch (e) {
        console.error('[KSA] /context/:ticker error:', e);
        res.status(500).json({ error: 'Failed to load context data' });
    }
});


// GET /api/ksa/health
router.get('/health', async (req, res) => {
    try {
        const row = await dbGet(`SELECT COUNT(*) AS cnt FROM consensus_results WHERE market_id = 'KSA'`);
        res.json({ status: 'ok', market: 'KSA', total_signals: Number(row?.cnt || 0) });
    } catch (e) {
        res.status(500).json({ status: 'error', error: e.message });
    }
});

module.exports = { router, attachDb };
