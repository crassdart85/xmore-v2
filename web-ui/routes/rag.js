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
const { embedReports } = require('../lib/embedReports');

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

        // 2. Load all embedded chunks from market_reports
        const chunks = await dbAll(
            `SELECT rc.source_id, rc.chunk_index, rc.chunk_text, rc.embedding,
                    mr.filename
             FROM rag_chunks rc
             LEFT JOIN market_reports mr ON mr.id = rc.source_id
             WHERE rc.source_type = ${ph(1)} AND rc.embedding IS NOT NULL`,
            ['market_report']
        );

        if (chunks.length === 0) {
            return res.json({
                answer: 'No embedded documents found. Please upload market reports and click "Embed Documents" in the admin panel.',
                sources: []
            });
        }

        // 3. Score and pick top 5
        const scored = chunks.map(c => {
            let emb;
            try { emb = JSON.parse(c.embedding); } catch { emb = null; }
            return { ...c, similarity: cosineSim(qEmbedding, emb) };
        }).sort((a, b) => b.similarity - a.similarity).slice(0, 5);

        // 4. Build RAG prompt
        const contextBlock = scored.map((c, i) =>
            `[Source ${i + 1}: ${c.filename || 'Report ' + c.source_id}]\n${c.chunk_text}`
        ).join('\n\n---\n\n');

        const prompt = `You are an expert financial analyst for the Egyptian Exchange (EGX).
Use ONLY the provided document excerpts to answer the question.
If the answer is not in the excerpts, say "I cannot find this in the uploaded reports."

Document excerpts:
${contextBlock}

Question: ${question}

Answer concisely and cite the source document where relevant.`;

        // 5. Generate answer
        const answer = await geminiGenerate(prompt, 0.1);

        res.json({
            answer,
            sources: scored.map(c => ({
                source_id: c.source_id,
                filename: c.filename || `Report ${c.source_id}`,
                preview: c.chunk_text.slice(0, 120) + (c.chunk_text.length > 120 ? '...' : ''),
                similarity: Math.round(c.similarity * 100) / 100,
            }))
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
`.trim();

// ── POST /api/rag/chat — General EGX research chat ──────────────────────────

router.post('/chat', async (req, res) => {
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

        // 2. Keyword-match news from main DB (keyword = any word ≥ 4 chars in question)
        const words = question.trim().toLowerCase().match(/\b\w{4,}\b/g) || [];
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
            // Keyword search in headlines
            const likeClause = words.slice(0, 3).map((w, i) => `headline LIKE ${ph(i + (symbol ? 2 : 1))}`).join(' OR ');
            const likeParams = words.slice(0, 3).map(w => `%${w}%`);
            const extraRows = await dbAll(
                `SELECT headline, source, date, url FROM news WHERE ${likeClause} ORDER BY date DESC LIMIT 10`,
                likeParams
            );
            // Merge, deduplicate by headline
            const seen = new Set(newsRows.map(r => r.headline));
            for (const r of extraRows) {
                if (!seen.has(r.headline)) { newsRows.push(r); seen.add(r.headline); }
            }
        }
        const newsContext = newsRows.slice(0, 8).map(r =>
            `- [${r.date}] ${r.headline} (${r.source})`
        ).join('\n');

        if (newsRows.length > 0) {
            sources.push(...newsRows.slice(0, 5).map(r => ({
                type: 'news', title: r.headline, source: r.source, date: r.date, url: r.url || null
            })));
        }

        // 3. Try RAG chunks if any exist
        let reportContext = '';
        try {
            const chunkCount = await dbGet(
                `SELECT COUNT(*) as cnt FROM rag_chunks WHERE source_type = ${ph(1)} AND embedding IS NOT NULL`,
                ['market_report']
            );
            if (chunkCount && (chunkCount.cnt > 0 || chunkCount['COUNT(*)'] > 0)) {
                const qEmbedding = await embedText(question.trim());
                const allChunks = await dbAll(
                    `SELECT rc.source_id, rc.chunk_text, rc.embedding, mr.filename
                     FROM rag_chunks rc
                     LEFT JOIN market_reports mr ON mr.id = rc.source_id
                     WHERE rc.source_type = ${ph(1)} AND rc.embedding IS NOT NULL`,
                    ['market_report']
                );
                const topChunks = allChunks.map(c => {
                    let emb; try { emb = JSON.parse(c.embedding); } catch { emb = null; }
                    return { ...c, sim: cosineSim(qEmbedding, emb) };
                }).sort((a, b) => b.sim - a.sim).slice(0, 3);

                if (topChunks.length > 0 && topChunks[0].sim > 0.4) {
                    reportContext = '\n\nRelevant report excerpts:\n' + topChunks.map(c =>
                        `[${c.filename || 'Report'}]: ${c.chunk_text.slice(0, 300)}`
                    ).join('\n\n');
                    sources.push(...topChunks.filter(c => c.sim > 0.4).map(c => ({
                        type: 'report', title: c.filename || `Report ${c.source_id}`,
                        source: 'Market Report', date: null, url: null
                    })));
                }
            }
        } catch (_e) {
            // No chunks available — skip silently
        }

        // 4. Build prompt and generate
        const symbolNote = symbol ? `\nFocus on: ${symbol}` : '';
        const prompt = `You are an expert EGX financial research assistant with full knowledge of the Egyptian stock market.
Use the EGX reference knowledge and stock list below to answer questions about any EGX stock, symbol, or market topic.
Supplement with recent news when available. Keep answers concise (2-4 sentences) and factual.
${symbolNote}

${EGX_MARKET_KNOWLEDGE}
${stockReferenceBlock}

Recent news:
${newsContext || 'No recent news in database.'}
${reportContext}

User question: ${question}`;

        const answer = await geminiGenerate(prompt, 0.3);
        res.json({ answer, sources });

    } catch (err) {
        console.error('RAG /chat error:', err.message);
        res.status(500).json({ error: err.message });
    }
});

// ── GET /api/rag/embed/status — how many chunks are embedded ─────────────────

router.get('/embed/status', async (req, res) => {
    try {
        const row = await dbGet(
            `SELECT COUNT(*) as total,
                    COUNT(DISTINCT source_id) as reports
             FROM rag_chunks WHERE source_type = ${ph(1)}`,
            ['market_report']
        );
        const total = row ? (row.total || row['COUNT(*)'] || 0) : 0;
        const reports = row ? (row.reports || 0) : 0;
        res.json({ ok: true, chunks: total, reports });
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
    res.json({ ok: true, message: 'Embedding started. Check status with GET /api/rag/embed/status' });

    embedReports(_db, _isPostgres, GEMINI_API_KEY, reportId)
        .then(r => console.log(`[RAG embed] complete: ${r.chunksEmbedded} chunks, ${r.reportsProcessed} report(s)`))
        .catch(err => console.error('[RAG embed] error:', err.message));
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
