'use strict';
/**
 * RAG Routes — Retrieval-Augmented Generation for Xmore
 *
 * POST /api/rag/ask              Q&A against embedded market reports
 * POST /api/rag/chat             General EGX research chat with news context
 * GET  /api/rag/embed/status     How many chunks are embedded
 * POST /api/rag/embed            Trigger Python embedder (admin)
 * GET  /api/sentiment/:symbol/evidence  News articles that drove sentiment score
 */

const express = require('express');
const router = express.Router();
const https = require('https');
const { spawn } = require('child_process');
const path = require('path');

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
        { model: 'models/text-embedding-004', content: { parts: [{ text }] } }
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

        // 1. Keyword-match news from main DB (keyword = any word ≥ 4 chars in question)
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

        // 2. Try RAG chunks if any exist
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

        // 3. Build prompt and generate
        const symbolNote = symbol ? `\nFocus on: ${symbol}` : '';
        const prompt = `You are an expert EGX financial research assistant.
Answer the user's question using the provided news and any report context.
If insufficient data, say so honestly. Keep the answer concise (2-4 sentences).
${symbolNote}

Recent news:
${newsContext || 'No recent news found.'}
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

// ── POST /api/rag/embed — trigger Python embedder ────────────────────────────

router.post('/embed', (req, res) => {
    if (!GEMINI_API_KEY) {
        return res.status(503).json({ error: 'GOOGLE_API_KEY not configured' });
    }

    const projectRoot = path.join(__dirname, '..', '..');
    const reportId = req.body && req.body.report_id ? String(req.body.report_id) : null;
    const args = ['rag/embedder.py'];
    if (reportId) args.push('--report-id', reportId);

    const child = spawn('python', args, { cwd: projectRoot, timeout: 300000 });

    let stdout = '', stderr = '';
    child.stdout.on('data', d => { stdout += d.toString(); });
    child.stderr.on('data', d => { stderr += d.toString(); });

    // Respond immediately — embedding runs async
    res.json({ ok: true, message: 'Embedding started in background. Check server logs for progress.' });

    child.on('close', code => {
        if (code !== 0) {
            console.error(`[RAG embed] exited ${code}: ${stderr.slice(-500)}`);
        } else {
            console.log(`[RAG embed] complete: ${stdout.slice(-300)}`);
        }
    });
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

module.exports = { router, attachDb };
