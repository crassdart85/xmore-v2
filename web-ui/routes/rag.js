'use strict';
/**
 * RAG Routes — Retrieval-Augmented Generation for Xmore
 *
 * POST /api/rag/ask              Q&A against embedded market reports
 * POST /api/rag/chat             General EGX research chat with news context
 * GET  /api/rag/embed/status     How many chunks are embedded
 * POST /api/rag/embed            Embed un-embedded reports (pure Node.js, no Python)
 * GET  /api/sentiment/:symbol/evidence  News articles that drove sentiment score
 */

const express = require('express');
const router = express.Router();
const https = require('https');
const { embedReports, embedNewsArticles } = require('../lib/embedReports');
const { optionalAuth } = require('../middleware/auth');

let _db = null;
let _isPostgres = false;

function attachDb(db, isPostgres) {
    _db = db;
    _isPostgres = !!isPostgres;
}

// ── DB helpers ───────────────────────────────────────────────────────────────

function ph(n) { return _isPostgres ? `$${n}` : '?'; }

function adaptSql(sql) {
    if (_isPostgres) return sql;
    let i = 0;
    return sql.replace(/\$\d+/g, () => { i++; return '?'; });
}

// The server.js db wrapper always exposes .all()/.get()/.run() regardless of backend.
// PostgreSQL queries use $N placeholders (via ph()), SQLite uses ?.
// The wrapper passes SQL directly to the underlying driver, so ph() ensures correct style.

function dbAll(sql, params = []) {
    return new Promise((resolve, reject) => {
        _db.all(sql, params, (err, rows) => {
            if (err) return reject(err);
            resolve(rows || []);
        });
    });
}

function dbGet(sql, params = []) {
    return new Promise((resolve, reject) => {
        _db.get(sql, params, (err, row) => {
            if (err) return reject(err);
            resolve(row || null);
        });
    });
}

function dbRun(sql, params = []) {
    return new Promise((resolve, reject) => {
        _db.run(sql, params, (err) => {
            if (err) return reject(err);
            resolve();
        });
    });
}

// ── pgvector availability flag (set once on first use) ────────────────────────

let _pgvectorAvailable = null;

async function hasPgvector() {
    if (!_isPostgres) return false;
    if (_pgvectorAvailable !== null) return _pgvectorAvailable;
    try {
        // If embedding_vec column exists, pgvector is available
        await dbGet(
            `SELECT embedding_vec FROM rag_chunks WHERE embedding_vec IS NOT NULL LIMIT 1`
        );
        _pgvectorAvailable = true;
    } catch (_) {
        _pgvectorAvailable = false;
    }
    return _pgvectorAvailable;
}

// ── Unified top-K retrieval (pgvector if available, in-memory cosine fallback) ──

/**
 * Retrieve the top-K most similar chunks to a query embedding.
 *
 * @param {number[]}  qEmbedding   - 768-dim query embedding
 * @param {number}    topK         - how many chunks to return
 * @param {string[]}  sourceTypes  - filter by source_type(s), or null for all
 * @returns {Promise<Array>}
 */
async function retrieveTopChunks(qEmbedding, topK = 5, sourceTypes = null) {
    const useVec = await hasPgvector();

    if (useVec) {
        // pgvector path — O(log n) with IVFFlat index
        const vecStr = '[' + qEmbedding.join(',') + ']';
        let sql, params;
        if (sourceTypes && sourceTypes.length > 0) {
            sql = `
                SELECT source_type, source_id, chunk_index, chunk_text, source_meta,
                       1 - (embedding_vec <=> $1::vector) AS similarity
                FROM rag_chunks
                WHERE embedding_vec IS NOT NULL
                  AND source_type = ANY($2::text[])
                ORDER BY embedding_vec <=> $1::vector
                LIMIT $3
            `;
            params = [vecStr, '{' + sourceTypes.join(',') + '}', topK];
        } else {
            sql = `
                SELECT source_type, source_id, chunk_index, chunk_text, source_meta,
                       1 - (embedding_vec <=> $1::vector) AS similarity
                FROM rag_chunks
                WHERE embedding_vec IS NOT NULL
                ORDER BY embedding_vec <=> $1::vector
                LIMIT $2
            `;
            params = [vecStr, topK];
        }
        const rows = await dbAll(sql, params);
        return rows.map(r => ({
            ...r,
            similarity: Math.round((r.similarity || 0) * 1000) / 1000,
            source_meta: _parseMeta(r.source_meta),
        }));
    }

    // In-memory cosine fallback (SQLite or pgvector unavailable)
    let sql = `SELECT source_type, source_id, chunk_index, chunk_text, source_meta, embedding
               FROM rag_chunks WHERE embedding IS NOT NULL`;
    const params = [];
    if (sourceTypes && sourceTypes.length > 0) {
        const placeholders = sourceTypes.map((_, i) => ph(i + 1)).join(',');
        sql += ` AND source_type IN (${placeholders})`;
        params.push(...sourceTypes);
    }
    const rows = await dbAll(sql, params);

    const scored = rows.map(r => {
        let emb; try { emb = JSON.parse(r.embedding); } catch { emb = null; }
        return { ...r, similarity: cosineSim(qEmbedding, emb), source_meta: _parseMeta(r.source_meta) };
    });
    scored.sort((a, b) => b.similarity - a.similarity);
    return scored.slice(0, topK);
}

function _parseMeta(metaStr) {
    if (!metaStr) return {};
    try { return JSON.parse(metaStr); } catch { return {}; }
}

// ── Gemini API helpers ───────────────────────────────────────────────────────

const GEMINI_API_KEY = process.env.GOOGLE_API_KEY || '';

function geminiRequest(path, body) {
    return new Promise((resolve, reject) => {
        if (!GEMINI_API_KEY) return reject(new Error('GOOGLE_API_KEY not set'));
        const bodyStr = JSON.stringify(body);
        const options = {
            hostname: 'generativelanguage.googleapis.com',
            path: `${path}?key=${GEMINI_API_KEY}`,
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(bodyStr) },
        };
        const req = https.request(options, (res) => {
            let data = '';
            res.on('data', chunk => { data += chunk; });
            res.on('end', () => {
                try { resolve(JSON.parse(data)); }
                catch (e) { reject(new Error(`Parse error: ${data.slice(0, 200)}`)); }
            });
        });
        req.on('error', reject);
        req.write(bodyStr);
        req.end();
    });
}

async function embedText(text) {
    const result = await geminiRequest(
        '/v1beta/models/text-embedding-004:embedContent',
        { content: { parts: [{ text }] } }
    );
    if (!result.embedding || !result.embedding.values) {
        throw new Error(`Embed API error: ${JSON.stringify(result).slice(0, 300)}`);
    }
    return result.embedding.values;
}

async function geminiGenerate(prompt, temperature = 0.2) {
    const result = await geminiRequest(
        '/v1beta/models/gemini-2.5-flash:generateContent',
        {
            contents: [{ parts: [{ text: prompt }] }],
            generationConfig: { temperature }
        }
    );
    const candidate = result.candidates && result.candidates[0];
    if (!candidate) throw new Error(`Generate API error: ${JSON.stringify(result).slice(0, 300)}`);
    return candidate.content.parts[0].text.trim();
}

async function geminiGenerateGrounded(prompt, temperature = 0.3) {
    const result = await geminiRequest(
        '/v1beta/models/gemini-2.5-flash:generateContent',
        {
            contents: [{ parts: [{ text: prompt }] }],
            tools: [{ google_search: {} }],
            generationConfig: { temperature }
        }
    );
    const candidate = result.candidates && result.candidates[0];
    if (!candidate) throw new Error(`Grounded generate error: ${JSON.stringify(result).slice(0, 300)}`);
    const text = (candidate.content.parts || []).map(p => p.text || '').join('').trim();
    const sources = [];
    const chunks = (candidate.groundingMetadata || {}).groundingChunks || [];
    for (const chunk of chunks) {
        if (chunk.web) sources.push({ type: 'web', title: chunk.web.title || chunk.web.uri, url: chunk.web.uri });
    }
    return { text, sources };
}

// ── Cosine similarity (pure JS) ──────────────────────────────────────────────

function cosineSim(a, b) {
    if (!a || !b || a.length !== b.length) return 0;
    let dot = 0, na = 0, nb = 0;
    for (let i = 0; i < a.length; i++) {
        dot += a[i] * b[i];
        na += a[i] * a[i];
        nb += b[i] * b[i];
    }
    if (na === 0 || nb === 0) return 0;
    return dot / (Math.sqrt(na) * Math.sqrt(nb));
}

// ── POST /api/rag/ask — Q&A against market reports ──────────────────────────

router.post('/ask', async (req, res) => {
    const { question } = req.body || {};
    if (!question || !question.trim()) {
        return res.status(400).json({ error: 'question is required' });
    }
    if (!GEMINI_API_KEY) {
        return res.status(503).json({ error: 'GOOGLE_API_KEY not configured' });
    }

    try {
        // 1. Embed the question
        const qEmbedding = await embedText(question.trim());

        // 2. Retrieve top chunks across all embedded source types
        const scored = await retrieveTopChunks(qEmbedding, 5, null);

        if (scored.length === 0) {
            return res.json({
                answer: 'No embedded documents found. Please upload market reports and click "Embed Documents" in the admin panel.',
                sources: []
            });
        }

        // 3. Build RAG prompt
        const contextBlock = scored.map((c, i) => {
            const meta = c.source_meta || {};
            const label = meta.filename || meta.headline || meta.title || `${c.source_type} ${c.source_id}`;
            return `[Source ${i + 1}: ${label}]\n${c.chunk_text}`;
        }).join('\n\n---\n\n');

        const prompt = `You are an expert financial analyst for the Egyptian Exchange (EGX).
Use ONLY the provided document and news excerpts to answer the question.
If the answer is not in the excerpts, say "I cannot find this in the available sources."

Excerpts:
${contextBlock}

Question: ${question}

Answer concisely and cite the source where relevant.`;

        // 4. Generate answer
        const answer = await geminiGenerate(prompt, 0.1);

        res.json({
            answer,
            sources: scored.map(c => {
                const meta = c.source_meta || {};
                return {
                    source_type: c.source_type,
                    source_id:   c.source_id,
                    label:       meta.filename || meta.headline || meta.title || `${c.source_type} ${c.source_id}`,
                    preview:     c.chunk_text.slice(0, 120) + (c.chunk_text.length > 120 ? '...' : ''),
                    similarity:  Math.round(c.similarity * 100) / 100,
                };
            })
        });

    } catch (err) {
        console.error('RAG /ask error:', err.message);
        res.status(500).json({ error: err.message });
    }
});

// ── Static EGX market knowledge (injected into every /chat prompt) ───────────

const EGX_MARKET_KNOWLEDGE = `
EGYPTIAN EXCHANGE (EGX) — REFERENCE KNOWLEDGE
==============================================
The Egyptian Exchange (EGX) is the stock exchange of Egypt, one of the oldest in the region,
established in 1883. It is headquartered in Cairo with a branch in Alexandria.

Key Facts:
- Full name: Egyptian Exchange (البورصة المصرية)
- Website: https://www.egx.com.eg
- Currency: Egyptian Pound (EGP / جنيه مصري)
- Trading days: Sunday – Thursday (Friday/Saturday are weekends in Egypt)
- Trading hours: 10:00 – 14:30 Cairo time (UTC+2)
- Pre-open session: 09:30 – 10:00
- Settlement: T+2
- Main indices: EGX30 (top 30 by liquidity/activity), EGX70 (mid-cap), EGX100 (combined), EGX20 Capped
- Symbol format: TICKER.CA  (e.g., COMI.CA for CIB, SWDY.CA for El-Sewedy Electric)
- Regulator: Financial Regulatory Authority (FRA — الهيئة العامة للرقابة المالية)
- ~250+ companies listed across 15+ sectors

Major Sectors on EGX:
Banking, Real Estate & Construction, Telecommunications, Food & Beverage,
Chemicals & Petrochemicals, Steel & Industrial, Ports & Logistics,
Healthcare, Fintech, Textiles, Energy, Cement, Tourism & Hospitality

XMORE PLATFORM — METHODOLOGY & DATA SOURCES:
- Multi-agent AI stack: ML (LightGBM per-symbol), RSI (adaptive periods), MA (adaptive periods), Sentiment (Gemini + recency decay), Volume, Risk agents
- Consensus engine: 4-layer pipeline — Layer 1 (agent vote), Layer 2 (weighted average), Layer 3 (risk filter), Layer 4 (regime gate: Crisis blocks UP signals; Turbulent downgrades conviction)
- Market regime detection: Gaussian HMM on EGX30 price history — states: Calm, Turbulent, Crisis
- Walk-forward validation: 90-day train / 20-day test / 10-day step rolling windows across all 6 agents, validated weekly
- Confidence gating: signals with max(probability) < 60% are converted to HOLD before publication
- Live knowledge sources injected into this assistant:
  * Latest prices, top gainers/losers, most active volume
  * Consensus signals + per-stock sentiment snapshots
  * Current market regime (Calm/Turbulent/Crisis) + 30-day signal distribution
  * Walk-forward backtest accuracy summary (latest weekly run)
  * Agent performance leaderboard (accuracy per agent)
  * Admin-uploaded market reports (RAG chunks, vector search)
  * ETF factsheets & prospectuses (RAG chunks)
  * News RAG chunks with recency-weighted semantic search
  * Custom news sources + manual feeds
  * Portfolio forecasts + actual vs forecast performance (user-specific, when logged in)
`.trim();

// ── POST /api/rag/chat — General EGX research chat ──────────────────────────

router.post('/chat', optionalAuth, async (req, res) => {
    const { question, symbol } = req.body || {};
    if (!question || !question.trim()) {
        return res.status(400).json({ error: 'question is required' });
    }
    if (!GEMINI_API_KEY) {
        return res.status(503).json({ error: 'GOOGLE_API_KEY not configured' });
    }

    try {
        const sources = [];

        // 1. Load EGX stock reference from DB
        let stockReferenceBlock = '';
        try {
            const stocks = await dbAll(
                `SELECT symbol, name_en, name_ar, sector_en FROM egx30_stocks ORDER BY symbol ASC`,
                []
            );
            if (stocks.length > 0) {
                const lines = stocks.map(s =>
                    `  ${s.symbol.padEnd(12)} ${s.name_en} (${s.name_ar}) — ${s.sector_en || 'N/A'}`
                ).join('\n');
                stockReferenceBlock = `\nLISTED EGX STOCKS (${stocks.length} companies):\n${lines}`;
            }
        } catch (_e) {
            // Table may not exist in older schema — skip silently
        }

        // 2. Keyword-match news from main DB
        // Use Unicode-aware word extraction (handles Arabic + Latin)
        const words = question.trim().toLowerCase().match(/[\w\u0600-\u06FF]{4,}/g) || [];
        let newsRows = [];
        if (symbol) {
            // Symbol-specific first
            newsRows = await dbAll(
                `SELECT headline, source, date, url FROM news
                 WHERE symbol = ${ph(1)} ORDER BY date DESC LIMIT 10`,
                [symbol.toUpperCase()]
            );
        }
        if (newsRows.length < 5 && words.length > 0) {
            // Keyword search in headlines (Latin keywords only — SQL LIKE is ASCII-safe)
            const latinWords = words.filter(w => /[a-z]/.test(w)).slice(0, 3);
            if (latinWords.length > 0) {
                const likeClause = latinWords.map((w, i) => `headline LIKE ${ph(i + (symbol ? 2 : 1))}`).join(' OR ');
                const likeParams = latinWords.map(w => `%${w}%`);
                const extraRows = await dbAll(
                    `SELECT headline, source, date, url FROM news WHERE ${likeClause} ORDER BY date DESC LIMIT 10`,
                    likeParams
                );
                const seen = new Set(newsRows.map(r => r.headline));
                for (const r of extraRows) {
                    if (!seen.has(r.headline)) { newsRows.push(r); seen.add(r.headline); }
                }
            }
        }
        // Fallback: for general news questions (no symbol, nothing matched), return latest headlines
        if (newsRows.length === 0 && !symbol) {
            newsRows = await dbAll(
                `SELECT headline, source, date, url FROM news ORDER BY date DESC LIMIT 10`,
                []
            );
        }
        const newsContext = newsRows.slice(0, 8).map(r =>
            `- [${r.date}] ${r.headline} (${r.source})`
        ).join('\n');

        if (newsRows.length > 0) {
            sources.push(...newsRows.slice(0, 5).map(r => ({
                type: 'news', title: r.headline, source: r.source, date: r.date, url: r.url || null
            })));
        }

        // 3. RAG knowledge base (reports + ETFs + embedded news/event intel)
        let ragContext = '';
        let qEmbedding = null;
        try {
            qEmbedding = await embedText(question.trim());
            const chunks = await retrieveTopChunks(qEmbedding, 6, null);
            const topChunks = chunks
                .map(c => ({ ...c, sim: c.similarity ?? 0 }))
                .filter(c => c.sim > 0.4)
                .slice(0, 4);

            if (topChunks.length > 0) {
                ragContext = '\n\nKnowledge base excerpts:\n' + topChunks.map(c => {
                    const meta  = c.source_meta || {};
                    const label = meta.filename || meta.title || meta.headline || `${c.source_type} ${c.source_id}`;
                    return `[${label}]: ${c.chunk_text.slice(0, 320)}`;
                }).join('\n\n');
                sources.push(...topChunks.map(c => {
                    const meta = c.source_meta || {};
                    return {
                        type: c.source_type,
                        title: meta.filename || meta.title || meta.headline || `${c.source_type} ${c.source_id}`,
                        source: meta.publisher || meta.source || meta.outlet || c.source_type,
                        date: meta.date || meta.upload_date || meta.published_at || null,
                        url: meta.url || null
                    };
                }));
            }
        } catch (_e) {
            // No rag_chunks available — skip silently
        }

        // 3b. News RAG chunks (recency-weighted semantic matches)
        let newsRagContext = '';
        try {
            if (!qEmbedding) qEmbedding = await embedText(question.trim());
            const newsChunks = await dbAll(
                `SELECT id, title, source_name, published_at, article_url, content, embedding
                 FROM news_rag_chunks
                 ORDER BY published_at DESC
                 LIMIT 200`,
                []
            );
            const scored = newsChunks.map(r => {
                let emb; try { emb = JSON.parse(r.embedding); } catch { emb = null; }
                return { ...r, sim: cosineSim(qEmbedding, emb) };
            }).sort((a, b) => b.sim - a.sim).slice(0, 3);

            const topNews = scored.filter(s => s.sim > 0.4);
            if (topNews.length > 0) {
                newsRagContext = '\n\nRelevant news RAG excerpts:\n' + topNews.map(n =>
                    `[${n.source_name || 'News'} | ${n.published_at || 'date'}] ${n.title}: ${String(n.content || '').slice(0, 260)}`
                ).join('\n\n');
                sources.push(...topNews.map(n => ({
                    type: 'news_rag',
                    title: n.title,
                    source: n.source_name || 'News',
                    date: n.published_at || null,
                    url: n.article_url || null
                })));
            }
        } catch (_e) {
            // news_rag_chunks missing — skip silently
        }

        // 4. Live market data context
        let marketDataBlock = '';
        try {
            // 4a. Latest prices — top gainers / losers / most active
            const priceRows = await dbAll(
                _isPostgres
                ? `SELECT DISTINCT ON (p.symbol) p.symbol, p.date, p.close, p.open,
                     ROUND(((p.close - p.open) / NULLIF(p.open, 0) * 100)::numeric, 2) AS change_pct,
                     p.volume
                   FROM prices p ORDER BY p.symbol, p.date DESC`
                : `SELECT p.symbol, p.date, p.close, p.open,
                     ROUND((p.close - p.open) / NULLIF(p.open, 0) * 100, 2) AS change_pct,
                     p.volume
                   FROM prices p
                   INNER JOIN (SELECT symbol, MAX(date) AS md FROM prices GROUP BY symbol) l
                     ON p.symbol = l.symbol AND p.date = l.md`,
                []
            );
            if (priceRows.length > 0) {
                const latestDate = priceRows[0]?.date || 'N/A';
                const sorted  = [...priceRows].sort((a, b) => (b.change_pct || 0) - (a.change_pct || 0));
                const gainers = sorted.slice(0, 5).filter(p => (p.change_pct || 0) > 0);
                const losers  = [...sorted].reverse().slice(0, 5).filter(p => (p.change_pct || 0) < 0);
                const byVol   = [...priceRows].sort((a, b) => (b.volume || 0) - (a.volume || 0)).slice(0, 5);
                const lines   = [`LIVE EGX MARKET DATA (${latestDate}, ${priceRows.length} stocks):`];
                if (gainers.length) lines.push(`  Top Gainers: ${gainers.map(p => `${p.symbol} +${p.change_pct}%`).join(', ')}`);
                if (losers.length)  lines.push(`  Top Losers:  ${losers.map(p => `${p.symbol} ${p.change_pct}%`).join(', ')}`);
                if (byVol.length)   lines.push(`  Most Active: ${byVol.map(p => p.symbol).join(', ')}`);
                if (symbol) {
                    const sp = priceRows.find(p => p.symbol === symbol.toUpperCase());
                    if (sp) lines.push(`  ${symbol}: Close=${sp.close}, Change=${sp.change_pct}%, Vol=${sp.volume}`);
                }
                marketDataBlock += lines.join('\n');
            }

            // 4b. Sentiment summary
            const sentRows = await dbAll(
                _isPostgres
                ? `SELECT DISTINCT ON (symbol) symbol, sentiment_label
                   FROM sentiment_scores ORDER BY symbol, date DESC`
                : `SELECT s.symbol, s.sentiment_label
                   FROM sentiment_scores s
                   INNER JOIN (SELECT symbol, MAX(date) AS md FROM sentiment_scores GROUP BY symbol) l
                     ON s.symbol = l.symbol AND s.date = l.md`,
                []
            );
            if (sentRows.length > 0) {
                const bullish = sentRows.filter(s => s.sentiment_label === 'positive').map(s => s.symbol).slice(0, 8);
                const bearish = sentRows.filter(s => s.sentiment_label === 'negative').map(s => s.symbol).slice(0, 8);
                if (bullish.length) marketDataBlock += `\n  Bullish Sentiment: ${bullish.join(', ')}`;
                if (bearish.length) marketDataBlock += `\n  Bearish Sentiment: ${bearish.join(', ')}`;
            }

            // 4c. Consensus signals
            const consensusRows = await dbAll(
                _isPostgres
                ? `SELECT DISTINCT ON (symbol) symbol, final_signal
                   FROM consensus_results ORDER BY symbol, prediction_date DESC`
                : `SELECT c.symbol, c.final_signal
                   FROM consensus_results c
                   INNER JOIN (SELECT symbol, MAX(prediction_date) AS md FROM consensus_results GROUP BY symbol) l
                     ON c.symbol = l.symbol AND c.prediction_date = l.md`,
                []
            );
            if (consensusRows.length > 0) {
                const strongBuy  = consensusRows.filter(c => c.final_signal === 'STRONG_BUY').map(c => c.symbol).slice(0, 6);
                const buy        = consensusRows.filter(c => c.final_signal === 'BUY').map(c => c.symbol).slice(0, 6);
                const strongSell = consensusRows.filter(c => c.final_signal === 'STRONG_SELL').map(c => c.symbol).slice(0, 6);
                const sell       = consensusRows.filter(c => c.final_signal === 'SELL').map(c => c.symbol).slice(0, 6);
                if (strongBuy.length)  marketDataBlock += `\n  STRONG BUY signals: ${strongBuy.join(', ')}`;
                if (buy.length)        marketDataBlock += `\n  BUY signals: ${buy.join(', ')}`;
                if (strongSell.length) marketDataBlock += `\n  STRONG SELL signals: ${strongSell.join(', ')}`;
                if (sell.length)       marketDataBlock += `\n  SELL signals: ${sell.join(', ')}`;
            }

            // 4d. ETF prices
            const etfRows = await dbAll(
                _isPostgres
                ? `SELECT DISTINCT ON (i.symbol) i.symbol, p.close_price, p.pct_change, p.trade_date
                   FROM instrument i
                   JOIN etf_price_daily p ON p.instrument_id = i.instrument_id
                   WHERE i.is_active = TRUE ORDER BY i.symbol, p.trade_date DESC`
                : `SELECT i.symbol, p.close_price, p.pct_change, p.trade_date
                   FROM instrument i
                   JOIN etf_price_daily p ON p.instrument_id = i.id
                     AND p.trade_date = (SELECT MAX(trade_date) FROM etf_price_daily WHERE instrument_id = i.id)
                   WHERE i.is_active = 1 ORDER BY i.symbol`,
                []
            );
            if (etfRows.length > 0) {
                const etfLine = etfRows.map(e => {
                    const chg = e.pct_change != null
                        ? ` (${e.pct_change >= 0 ? '+' : ''}${parseFloat(e.pct_change).toFixed(2)}%)`
                        : '';
                    return `${e.symbol} ${e.close_price}${chg}`;
                }).join(', ');
                marketDataBlock += `\n  ETF Prices: ${etfLine}`;
            }

            // 4e. Current market regime
            try {
                const regimeRow = await dbAll(
                    `SELECT regime, date FROM regime_log ORDER BY date DESC LIMIT 5`,
                    []
                );
                if (regimeRow.length > 0) {
                    const current = regimeRow[0];
                    const history = regimeRow.map(r => `${r.date}:${r.regime}`).join(', ');
                    marketDataBlock += `\n  Market Regime: ${current.regime} (as of ${current.date}) — recent: ${history}`;
                }
            } catch (_e) { /* regime_log missing */ }

            // 4f. 30-day signal distribution
            try {
                const cutoff = new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10);
                const sigDist = await dbAll(
                    `SELECT prediction, COUNT(*) AS cnt
                     FROM trade_recommendations
                     WHERE recommendation_date >= ${ph(1)}
                     GROUP BY prediction`,
                    [cutoff]
                );
                if (sigDist.length > 0) {
                    const total = sigDist.reduce((s, r) => s + Number(r.cnt), 0);
                    const parts = sigDist.map(r => `${r.prediction}: ${r.cnt} (${Math.round(Number(r.cnt)/total*100)}%)`).join(', ');
                    marketDataBlock += `\n  30-day Signal Distribution: ${parts} — total ${total} signals`;
                }
            } catch (_e) { /* trade_recommendations missing */ }

            // 4g. Walk-forward backtest summary (latest run)
            try {
                const btLog = await dbAll(
                    `SELECT run_date, symbols_tested, windows_run, overall_accuracy, agent_summaries_json
                     FROM backtest_run_log ORDER BY run_date DESC LIMIT 1`,
                    []
                );
                if (btLog.length > 0) {
                    const bt = btLog[0];
                    let agentSummary = '';
                    try {
                        const agents = JSON.parse(bt.agent_summaries_json || '[]');
                        agentSummary = agents.map(a => `${a.agent}: ${(a.accuracy*100).toFixed(1)}%`).join(', ');
                    } catch (_) {}
                    marketDataBlock += `\n  Walk-Forward Backtest (${bt.run_date}): ${bt.symbols_tested} stocks, ${bt.windows_run} windows — accuracy: ${(bt.overall_accuracy*100).toFixed(1)}%${agentSummary ? ` | by agent: ${agentSummary}` : ''}`;
                }
            } catch (_e) { /* backtest_run_log missing */ }

            // 4h. Agent performance leaderboard
            try {
                const agentPerf = await dbAll(
                    _isPostgres
                    ? `SELECT DISTINCT ON (agent_name) agent_name, accuracy, total_evaluated, date
                       FROM agent_performance_daily ORDER BY agent_name, date DESC`
                    : `SELECT ap.agent_name, ap.accuracy, ap.total_evaluated, ap.date
                       FROM agent_performance_daily ap
                       INNER JOIN (SELECT agent_name, MAX(date) AS md FROM agent_performance_daily GROUP BY agent_name) l
                         ON ap.agent_name = l.agent_name AND ap.date = l.md`,
                    []
                );
                if (agentPerf.length > 0) {
                    const sorted = [...agentPerf].sort((a, b) => (b.accuracy || 0) - (a.accuracy || 0));
                    const perfLine = sorted.map(a => `${a.agent_name}: ${(parseFloat(a.accuracy||0)*100).toFixed(1)}%`).join(', ');
                    marketDataBlock += `\n  Agent Accuracy (live): ${perfLine}`;
                }
            } catch (_e) { /* agent_performance_daily missing */ }

        } catch (_e) { /* silently skip if tables missing */ }

        // 5. Portfolio context for logged-in user
        let portfolioBlock = '';
        if (req.userId) {
            try {
                const pfRows = await dbAll(
                    `SELECT fp.id, fp.name, fp.symbols_json, fp.horizon_days, fp.scenario, fp.investment_amount,
                            fp.updated_at
                     FROM forecast_portfolios fp
                     WHERE fp.user_id = ${ph(1)}
                     ORDER BY fp.updated_at DESC LIMIT 10`,
                    [req.userId]
                );
                if (pfRows.length > 0) {
                    const pfDetails = [];
                    for (const pf of pfRows) {
                        const symbols = (() => { try { return JSON.parse(pf.symbols_json) || []; } catch { return []; } })();
                        // Latest forecast results for this portfolio
                        const results = await dbAll(
                            `SELECT r.symbol, r.expected_return_pct, r.probability_positive,
                                    r.worst_case_pct, r.median_pct, r.best_case_pct,
                                    r.run_date, r.target_date,
                                    da.return_pct_from_start as actual_so_far, da.date as actual_date
                             FROM portfolio_forecast_results r
                             LEFT JOIN portfolio_daily_actuals da ON da.portfolio_id = r.portfolio_id
                               AND da.symbol = r.symbol
                               AND da.date = (SELECT MAX(d2.date) FROM portfolio_daily_actuals d2
                                              WHERE d2.portfolio_id = r.portfolio_id AND d2.symbol = r.symbol)
                             WHERE r.portfolio_id = ${ph(1)}
                               AND r.run_date = (SELECT MAX(run_date) FROM portfolio_forecast_results WHERE portfolio_id = ${ph(2)})
                             ORDER BY r.expected_return_pct DESC NULLS LAST`,
                            [pf.id, pf.id]
                        );
                        const today = new Date().toISOString().split('T')[0];
                        const startDate = results[0]?.run_date;
                        const daysElapsed = startDate
                            ? Math.max(0, Math.round((new Date(today) - new Date(startDate)) / 86400000))
                            : null;
                        const stockLines = results.map(r => {
                            const forecast = `forecast +${(r.expected_return_pct || 0).toFixed(1)}%`;
                            const actual   = r.actual_so_far != null
                                ? `, actual so far ${r.actual_so_far >= 0 ? '+' : ''}${parseFloat(r.actual_so_far).toFixed(1)}% (day ${daysElapsed}/${pf.horizon_days})`
                                : '';
                            const prob = r.probability_positive != null ? `, ${Math.round(r.probability_positive * 100)}% prob positive` : '';
                            return `    ${r.symbol}: ${forecast}${prob}${actual}`;
                        }).join('\n') || '    (no forecast results yet)';
                        pfDetails.push(
                            `  Portfolio "${pf.name}" — ${symbols.length} stock(s), ${pf.horizon_days}d ${pf.scenario} horizon, ${pf.investment_amount} EGP\n${stockLines}`
                        );
                    }
                    portfolioBlock = `\nUSER'S FORECAST PORTFOLIOS:\n${pfDetails.join('\n')}`;
                }
            } catch (_e) { /* silently skip if tables missing */ }
        }

        // 5b. Custom news sources (if available)
        try {
            const customRows = await dbAll(
                `SELECT a.title, a.published_at, a.url, s.name AS source
                 FROM custom_source_articles a
                 JOIN custom_news_sources s ON s.id = a.source_id
                 ORDER BY a.published_at DESC
                 LIMIT 8`,
                []
            );
            if (customRows.length > 0) {
                const extra = customRows.map(r =>
                    `- [${r.published_at || 'date'}] ${r.title} (${r.source || 'Custom'})`
                ).join('\n');
                if (extra) {
                    newsContext += `\n\nCustom sources:\n${extra}`;
                }
            }
        } catch (_e) { /* tables optional */ }

        // 6. Build prompt and generate
        const symbolNote = symbol ? `\nFocus on: ${symbol}` : '';
        const prompt = `You are an expert EGX financial research assistant with access to live market data.
Use the live market data, stock reference, EGX knowledge, and knowledge base excerpts to answer questions.
When discussing the user's portfolios, use the portfolio data provided — show actual vs forecast performance.
Keep answers concise (2-4 sentences) and factual. Use live data when asked about today's market.
${symbolNote}

${EGX_MARKET_KNOWLEDGE}
${stockReferenceBlock}
${marketDataBlock ? '\n' + marketDataBlock : ''}
${portfolioBlock}

Recent news:
${newsContext || 'No recent news in database.'}
${ragContext}
${newsRagContext}

User question: ${question}`;

        const answer = await geminiGenerate(prompt, 0.3);
        res.json({ answer, sources });

    } catch (err) {
        console.error('RAG /chat error:', err.message);
        res.status(500).json({ error: err.message });
    }
});

// ── POST /api/rag/macro — EGX Macro Driver Read with Google Search grounding ──

router.post('/macro', async (req, res) => {
    if (!GEMINI_API_KEY) return res.status(503).json({ error: 'GOOGLE_API_KEY not configured' });

    // Today's date in Cairo time (UTC+2)
    const cairoNow = new Date(Date.now() + 2 * 60 * 60 * 1000);
    const today    = cairoNow.toISOString().slice(0, 10);
    const dayName  = cairoNow.toLocaleDateString('en-US', { weekday: 'long', timeZone: 'Africa/Cairo' });

    // Lightweight DB snapshot to anchor the analysis
    let dbSnapshot = '';
    try {
        const priceRows = await dbAll(
            _isPostgres
            ? `SELECT DISTINCT ON (p.symbol) p.symbol, p.close,
                 ROUND(((p.close - p.open) / NULLIF(p.open, 0) * 100)::numeric, 2) AS chg
               FROM prices p ORDER BY p.symbol, p.date DESC`
            : `SELECT p.symbol, p.close,
                 ROUND((p.close - p.open) / NULLIF(p.open, 0) * 100, 2) AS chg
               FROM prices p
               INNER JOIN (SELECT symbol, MAX(date) AS md FROM prices GROUP BY symbol) l
                 ON p.symbol = l.symbol AND p.date = l.md`,
            []
        );
        if (priceRows.length > 0) {
            const sorted  = [...priceRows].sort((a, b) => (b.chg || 0) - (a.chg || 0));
            const gainers = sorted.slice(0, 3).filter(p => (p.chg || 0) > 0).map(p => `${p.symbol}(+${p.chg}%)`);
            const losers  = [...sorted].reverse().slice(0, 3).filter(p => (p.chg || 0) < 0).map(p => `${p.symbol}(${p.chg}%)`);
            if (gainers.length || losers.length) {
                dbSnapshot += `\nDB Market Snapshot (${today}):`;
                if (gainers.length) dbSnapshot += ` Gainers: ${gainers.join(', ')}`;
                if (losers.length)  dbSnapshot += ` | Losers: ${losers.join(', ')}`;
            }
        }
        const etfRows = await dbAll(
            _isPostgres
            ? `SELECT DISTINCT ON (i.symbol) i.symbol, p.close_price, p.pct_change
               FROM instrument i JOIN etf_price_daily p ON p.instrument_id = i.instrument_id
               WHERE i.is_active = TRUE ORDER BY i.symbol, p.trade_date DESC`
            : `SELECT i.symbol, p.close_price, p.pct_change
               FROM instrument i JOIN etf_price_daily p ON p.instrument_id = i.id
                 AND p.trade_date = (SELECT MAX(trade_date) FROM etf_price_daily WHERE instrument_id = i.id)
               WHERE i.is_active = 1 ORDER BY i.symbol`,
            []
        );
        if (etfRows.length > 0) {
            dbSnapshot += `\n  ETFs: ` + etfRows.map(e => {
                const chg = e.pct_change != null ? `(${e.pct_change >= 0 ? '+' : ''}${parseFloat(e.pct_change).toFixed(2)}%)` : '';
                return `${e.symbol} ${e.close_price}${chg}`;
            }).join(', ');
        }
    } catch (_e) { /* silently skip */ }

    const prompt = `You are an EGX macro analyst. Today is ${dayName}, ${today} (Africa/Cairo, UTC+2).

Use Google Search to find CURRENT data. Search for:
- "Central Bank of Egypt MPC decision 2026" (latest policy rate)
- "IMF Egypt 2026 disbursement" (latest review/tranche)
- "USD EGP exchange rate ${today}" (FX level)
- "oil price ${today}" and "Egypt EGX market ${today}" (global shocks)

Provide a concise EGX Macro Driver Read:

## 1. Rates (CBE)
Latest MPC decision: rate levels, direction, implication for EGX valuations (rate-sensitive sectors).

## 2. IMF / External Financing
Latest IMF program status, any recent disbursement, implication for FX confidence and bank funding.

## 3. FX (USD/EGP)
Current approximate exchange rate. Signal: stability or pressure?

## 4. Global Shocks (last 48h)
Dominant global macro shock (oil, EM risk-off, regional events) and Egypt-specific impact (Suez, imported inflation, foreign flows).

## 5. Sector Lens
Given the macro mix: which EGX sectors have a tailwind vs headwind today?
(Banks / Real Estate / Energy-exporters / Consumer-import-heavy / Industrials)

## 6. Net Tone
One sentence: overall macro tone for EGX today — supportive / neutral / cautious — and why.
${dbSnapshot ? '\n' + dbSnapshot : ''}

Keep each section 2-3 sentences. Cite the source searched. Flag any data that is delayed or unavailable.`;

    try {
        const { text, sources } = await geminiGenerateGrounded(prompt, 0.2);
        res.json({ answer: text, sources });
    } catch (err) {
        // Fallback: grounding may not be available for all API keys
        try {
            const text = await geminiGenerate(prompt, 0.2);
            res.json({ answer: text, sources: [], note: 'grounding_unavailable' });
        } catch (err2) {
            console.error('RAG /macro error:', err2.message);
            res.status(500).json({ error: err2.message });
        }
    }
});

// ── GET /api/rag/embed/status — how many chunks are embedded ─────────────────

router.get('/embed/status', async (req, res) => {
    try {
        const rows = await dbAll(
            `SELECT source_type,
                    COUNT(*)                    AS chunks,
                    COUNT(DISTINCT source_id)   AS sources
             FROM rag_chunks
             GROUP BY source_type`
        );
        const breakdown = {};
        let totalChunks = 0;
        for (const r of rows) {
            breakdown[r.source_type] = { chunks: Number(r.chunks || 0), sources: Number(r.sources || 0) };
            totalChunks += Number(r.chunks || 0);
        }
        // Backwards-compatible top-level fields
        const rp = breakdown['market_report'] || { chunks: 0, sources: 0 };
        res.json({ ok: true, chunks: rp.chunks, reports: rp.sources, total_chunks: totalChunks, breakdown });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

// ── GET /api/rag/documents — document index / audit trail ────────────────────

router.get('/documents', async (req, res) => {
    try {
        const docs = await dbAll(`
            SELECT
                mr.id,
                mr.filename,
                mr.upload_date,
                mr.language,
                COUNT(rc.id)                                               AS total_chunks,
                COUNT(CASE WHEN rc.embedding IS NOT NULL THEN 1 END)       AS embedded_chunks
            FROM market_reports mr
            LEFT JOIN rag_chunks rc
                   ON rc.source_id = mr.id AND rc.source_type = ${ph(1)}
            GROUP BY mr.id, mr.filename, mr.upload_date, mr.language
            ORDER BY mr.upload_date DESC
        `, ['market_report']);
        res.json({ documents: docs });
    } catch (err) {
        console.error('RAG /documents error:', err.message);
        res.status(500).json({ error: err.message });
    }
});

// ── POST /api/rag/embed — embed reports in Node.js (no Python needed) ────────

router.post('/embed', (req, res) => {
    if (!GEMINI_API_KEY) {
        return res.status(503).json({ error: 'GOOGLE_API_KEY not configured' });
    }

    const reportId = req.body && req.body.report_id
        ? parseInt(req.body.report_id, 10) || null
        : null;

    // Respond immediately — embedding runs in background
    res.json({ ok: true, message: 'Embedding started (reports + recent news). Check status with GET /api/rag/embed/status' });

    // Reset pgvector availability cache so it re-checks after potentially adding the column
    _pgvectorAvailable = null;

    embedReports(_db, _isPostgres, GEMINI_API_KEY, reportId)
        .then(r => {
            console.log(`[RAG embed] reports: ${r.chunksEmbedded} chunks, ${r.reportsProcessed} report(s)`);
            // After reports, embed recent news headlines too (unless specific reportId requested)
            if (!reportId) {
                return embedNewsArticles(_db, _isPostgres, GEMINI_API_KEY, { days: 30, limit: 200 });
            }
        })
        .then(r => { if (r) console.log(`[RAG embed] news: ${r.chunksEmbedded} headlines`); })
        .catch(err => console.error('[RAG embed] error:', err.message));
});

// ── POST /api/rag/why-signal — "Why This Signal?" explanation ────────────────
//
// Body: { symbol, signal, agent_name? }
// Returns: { explanation, sources }

router.post('/why-signal', async (req, res) => {
    const { symbol, signal, agent_name } = req.body || {};
    if (!symbol || !signal) {
        return res.status(400).json({ error: 'symbol and signal are required' });
    }
    if (!GEMINI_API_KEY) {
        return res.status(503).json({ error: 'GOOGLE_API_KEY not configured' });
    }

    try {
        const sym    = symbol.toUpperCase();
        const sig    = signal.toUpperCase();
        const agent  = agent_name || '';
        const sigWord = sig === 'UP' ? 'bullish' : sig === 'DOWN' ? 'bearish' : 'neutral';

        // Semantically rich query covering the stock + signal direction
        const query  = `${sym} stock ${sigWord} signal Egypt EGX ${agent}`.trim();
        const qEmbedding = await embedText(query);

        // Top chunks across ALL source types (reports + news_article + event_intel)
        const chunks = await retrieveTopChunks(qEmbedding, 6, null);

        // Recent news headlines for extra recency context (keyword, not semantic)
        const recentNews = await dbAll(
            `SELECT headline, source, date FROM news
             WHERE symbol = ${ph(1)} ORDER BY date DESC LIMIT 5`,
            [sym]
        );

        const chunksBlock = chunks.length > 0
            ? chunks.map((c, i) => {
                const meta  = c.source_meta || {};
                const label = meta.filename || meta.headline || meta.title || `${c.source_type} ${c.source_id}`;
                return `[Evidence ${i + 1}: ${label}]\n${c.chunk_text.slice(0, 400)}`;
              }).join('\n\n---\n\n')
            : 'No embedded knowledge base articles available.';

        const newsBlock = recentNews.length > 0
            ? recentNews.map(n => `- [${n.date}] ${n.headline} (${n.source || '?'})`).join('\n')
            : 'No recent news found for this stock.';

        const prompt =
`You are a concise EGX financial analyst. Explain in 3-4 bullet points why ${sym} has a ${sig} signal today.
Draw on the evidence below. Be specific — mention concrete facts where present.
If evidence is insufficient, say so honestly.

Knowledge base evidence:
${chunksBlock}

Recent news for ${sym}:
${newsBlock}
${agent ? `\nSignal generated by: ${agent}.` : ''}

Explain the ${sig} signal for ${sym}:`;

        const explanation = await geminiGenerate(prompt, 0.2);

        res.json({
            symbol: sym,
            signal: sig,
            explanation,
            sources: chunks.map(c => {
                const meta = c.source_meta || {};
                return {
                    source_type: c.source_type,
                    label:       meta.filename || meta.headline || meta.title || `${c.source_type} ${c.source_id}`,
                    date:        meta.date || meta.upload_date || meta.published_at || null,
                    similarity:  Math.round(c.similarity * 1000) / 1000,
                };
            }),
        });

    } catch (err) {
        console.error('RAG /why-signal error:', err.message);
        res.status(500).json({ error: err.message });
    }
});

// ── GET /api/sentiment/:symbol/evidence — articles that drove the badge ──────

router.get('/sentiment/:symbol/evidence', async (req, res) => {
    const symbol = req.params.symbol.toUpperCase();
    try {
        // Latest sentiment score for the symbol
        const sentiment = await dbGet(
            `SELECT symbol, date, avg_sentiment, sentiment_label, article_count,
                    positive_count, negative_count, neutral_count
             FROM sentiment_scores
             WHERE symbol = ${ph(1)}
             ORDER BY date DESC LIMIT 1`,
            [symbol]
        );

        if (!sentiment) {
            return res.json({ symbol, sentiment_label: 'N/A', avg_sentiment: 0, articles: [] });
        }

        // News articles for that symbol on or near that date
        const articles = await dbAll(
            `SELECT headline, source, url, sentiment_label, sentiment_score, date
             FROM news
             WHERE symbol = ${ph(1)} AND date = ${ph(2)}
             ORDER BY ABS(COALESCE(sentiment_score, 0)) DESC
             LIMIT 15`,
            [symbol, sentiment.date]
        );

        // Fallback: last 7 days if no articles on exact date
        let articleList = articles;
        if (articles.length === 0) {
            articleList = await dbAll(
                `SELECT headline, source, url, sentiment_label, sentiment_score, date
                 FROM news
                 WHERE symbol = ${ph(1)}
                 ORDER BY date DESC LIMIT 10`,
                [symbol]
            );
        }

        res.json({
            symbol,
            date: sentiment.date,
            avg_sentiment: sentiment.avg_sentiment,
            sentiment_label: sentiment.sentiment_label,
            article_count: sentiment.article_count,
            positive_count: sentiment.positive_count,
            negative_count: sentiment.negative_count,
            neutral_count: sentiment.neutral_count,
            articles: articleList.map(a => ({
                headline: a.headline,
                source: a.source,
                url: a.url || null,
                sentiment_label: a.sentiment_label || 'Neutral',
                sentiment_score: a.sentiment_score != null ? Math.round(a.sentiment_score * 100) / 100 : null,
                date: a.date,
            }))
        });

    } catch (err) {
        console.error('RAG /sentiment/evidence error:', err.message);
        res.status(500).json({ error: err.message });
    }
});

// ── News Q&A and drift adjustment endpoints ───────────────────────────────────
// These call the Python news/ package via child_process.spawn, following
// the same pattern used by timemachine.js (JSON stdout from Python CLI).

const { spawn } = require('child_process');
const path = require('path');

const NEWS_PROJECT_ROOT = path.resolve(__dirname, '..', '..');
const PYTHON_BIN = process.platform === 'win32' ? 'python' : 'python3';

function spawnPythonCli(scriptRelPath, argObj, timeoutMs = 30000) {
    return new Promise((resolve, reject) => {
        const scriptAbs = path.join(NEWS_PROJECT_ROOT, scriptRelPath);
        const argStr = JSON.stringify(argObj);
        const child = spawn(PYTHON_BIN, [scriptAbs, argStr], {
            cwd: NEWS_PROJECT_ROOT,
            env: { ...process.env },
        });

        let stdout = '';
        let stderr = '';
        child.stdout.on('data', d => { stdout += d; });
        child.stderr.on('data', d => { stderr += d; });

        const timer = setTimeout(() => {
            child.kill();
            reject(new Error('Python CLI timeout'));
        }, timeoutMs);

        child.on('close', code => {
            clearTimeout(timer);
            if (!stdout.trim()) {
                return reject(new Error(`No output from Python (exit ${code}): ${stderr.slice(0, 300)}`));
            }
            try {
                resolve(JSON.parse(stdout.trim()));
            } catch (e) {
                reject(new Error(`JSON parse error: ${stdout.slice(0, 200)}`));
            }
        });
    });
}

// ── POST /api/rag/news/ask — recency-weighted news Q&A ───────────────────────
// Body: { question, market?, portfolio?, language?, source_mode?, max_age_hours? }
router.post('/news/ask', async (req, res) => {
    const { question, market, portfolio, language, source_mode, max_age_hours } = req.body || {};
    if (!question || !question.trim()) {
        return res.status(400).json({ error: 'question is required' });
    }
    if (!GEMINI_API_KEY) {
        return res.status(503).json({ error: 'GOOGLE_API_KEY not configured' });
    }

    try {
        const result = await spawnPythonCli('news/ask_cli.py', {
            question: question.trim(),
            market: market || null,
            portfolio: Array.isArray(portfolio) ? portfolio : [],
            language: language || 'en',
            source_mode: source_mode || 'news',
            max_age_hours: max_age_hours || 168,
            top_k: 8,
        }, 45000);

        if (!result.ok) {
            return res.status(500).json({ error: result.error || 'News Q&A failed' });
        }
        res.json(result);
    } catch (err) {
        console.error('RAG /news/ask error:', err.stack || err.message);
        res.status(500).json({ error: err.message });
    }
});

// ── GET /api/rag/news/chunks — recent ingested chunks (for audit / debug) ────
// Query params: market, event_type, limit (default 20)
router.get('/news/chunks', async (req, res) => {
    const { market, event_type, limit = 20 } = req.query;
    try {
        let conditions = [];
        let params = [];
        let p = 1;

        if (market) {
            conditions.push(`market_tag = ${ph(p++)}`);
            params.push(market.toUpperCase());
        }
        if (event_type) {
            conditions.push(`event_type = ${ph(p++)}`);
            params.push(event_type.toUpperCase());
        }

        const where = conditions.length ? 'WHERE ' + conditions.join(' AND ') : '';
        const rows = await dbAll(
            `SELECT id, title, source_name, published_at, market_tag, event_type,
                    drift_direction, affected_assets, chunk_index
             FROM news_rag_chunks
             ${where}
             ORDER BY published_at DESC
             LIMIT ${ph(p)}`,
            [...params, parseInt(limit, 10) || 20]
        );
        res.json({ ok: true, count: rows.length, chunks: rows });
    } catch (err) {
        console.error('RAG /news/chunks error:', err.message);
        res.status(500).json({ error: err.message });
    }
});

// ── GET /api/rag/news/ingest — trigger manual ingestion cycle ─────────────────
// Returns immediately; ingestion runs in background.
router.post('/news/ingest', (req, res) => {
    if (!GEMINI_API_KEY) {
        return res.status(503).json({ error: 'GOOGLE_API_KEY not configured' });
    }
    res.json({ ok: true, message: 'Ingestion started in background. Check /news/chunks for results.' });

    spawnPythonCli('news/ingest_cli.py', {}, 300000)
        .then(r => console.log('[news/ingest] complete:', JSON.stringify(r).slice(0, 200)))
        .catch(err => console.error('[news/ingest] error:', err.message));
});

// ── GET /api/rag/drift/:ticker — current drift adjustments for a ticker ───────
router.get('/drift/:ticker', async (req, res) => {
    const ticker = req.params.ticker.toUpperCase();
    try {
        const result = await spawnPythonCli('news/drift_cli.py', { ticker }, 20000);
        if (!result.ok) return res.status(500).json({ error: result.error });
        res.json(result);
    } catch (err) {
        console.error('RAG /drift error:', err.message);
        res.status(500).json({ error: err.message });
    }
});

// ── GET /api/rag/drift — recent drift adjustments (all tickers) ───────────────
router.get('/drift', async (req, res) => {
    const limit = parseInt(req.query.limit, 10) || 50;
    try {
        const result = await spawnPythonCli('news/drift_cli.py', { recent: true, limit }, 20000);
        if (!result.ok) return res.status(500).json({ error: result.error });
        res.json(result);
    } catch (err) {
        console.error('RAG /drift list error:', err.message);
        res.status(500).json({ error: err.message });
    }
});

// ── GET /api/rag/drift/verify/:id — audit hash integrity check ────────────────
router.get('/drift/verify/:id', async (req, res) => {
    try {
        const result = await spawnPythonCli('news/drift_cli.py', { verify: req.params.id }, 15000);
        res.json(result);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

module.exports = { router, attachDb };
