'use strict';
/**
 * lib/embedReports.js — Pure Node.js multi-source embedder.
 *
 * Works on Render (no Python required). Embeds:
 *   - market_reports  (PDFs/images uploaded via admin)
 *   - news_article    (recent headlines from main `news` table)
 *
 * Used by:
 *   - routes/rag.js   POST /api/rag/embed
 *   - routes/admin.js auto-embed after upload
 */

const https = require('https');

const CHUNK_SIZE    = 500;   // characters per chunk
const CHUNK_OVERLAP = 50;    // overlap between adjacent chunks
const RATE_LIMIT_MS = 130;   // ~7.5 req/s, under Gemini free-tier 10/s limit

// ── helpers ──────────────────────────────────────────────────────────────────

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function chunkText(text, size = CHUNK_SIZE, overlap = CHUNK_OVERLAP) {
    if (!text || !text.trim()) return [];
    const chunks = [];
    let start = 0;
    while (start < text.length) {
        chunks.push(text.slice(start, start + size));
        start += size - overlap;
    }
    return chunks;
}

function geminiEmbed(text, apiKey) {
    return new Promise((resolve, reject) => {
        const bodyStr = JSON.stringify({ content: { parts: [{ text }] } });
        const options = {
            hostname: 'generativelanguage.googleapis.com',
            path: `/v1beta/models/text-embedding-005:embedContent?key=${apiKey}`,
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Content-Length': Buffer.byteLength(bodyStr),
            },
        };
        const req = https.request(options, (res) => {
            let data = '';
            res.on('data', c => { data += c; });
            res.on('end', () => {
                try {
                    const result = JSON.parse(data);
                    if (!result.embedding || !result.embedding.values) {
                        return reject(new Error(`Embed API error: ${data.slice(0, 200)}`));
                    }
                    resolve(result.embedding.values);
                } catch (e) {
                    reject(new Error(`Embed parse error: ${data.slice(0, 200)}`));
                }
            });
        });
        req.on('error', reject);
        req.write(bodyStr);
        req.end();
    });
}

// ── DB helpers (work with the server.js unified db wrapper) ──────────────────

function makeHelpers(db, isPostgres) {
    function adapt(sql) {
        if (isPostgres) return sql;
        let i = 0;
        return sql.replace(/\$\d+/g, () => { i++; return '?'; });
    }
    function dbAll(sql, params = []) {
        return new Promise((resolve, reject) =>
            db.all(adapt(sql), params, (err, rows) => err ? reject(err) : resolve(rows || [])));
    }
    function dbGet(sql, params = []) {
        return new Promise((resolve, reject) =>
            db.get(adapt(sql), params, (err, row) => err ? reject(err) : resolve(row || null)));
    }
    function dbRun(sql, params = []) {
        return new Promise((resolve, reject) =>
            db.run(adapt(sql), params, (err) => err ? reject(err) : resolve()));
    }
    return { dbAll, dbGet, dbRun };
}

// ── Upsert one chunk (with source_meta + pgvector fallback) ──────────────────

async function upsertChunk(db, isPostgres, sourceType, sourceId, chunkIndex, chunkText, embedding, sourceMeta) {
    const { dbRun } = makeHelpers(db, isPostgres);
    const embJson  = JSON.stringify(embedding);
    const metaJson = JSON.stringify(sourceMeta || {});

    if (isPostgres) {
        const vecStr = '[' + embedding.join(',') + ']';
        try {
            await dbRun(`
                INSERT INTO rag_chunks
                  (source_type, source_id, chunk_index, chunk_text, embedding, source_meta, embedding_vec)
                VALUES ($1, $2, $3, $4, $5, $6, $7::vector)
                ON CONFLICT (source_type, source_id, chunk_index)
                DO UPDATE SET chunk_text    = EXCLUDED.chunk_text,
                              embedding     = EXCLUDED.embedding,
                              source_meta   = EXCLUDED.source_meta,
                              embedding_vec = EXCLUDED.embedding_vec
            `, [sourceType, sourceId, chunkIndex, chunkText, embJson, metaJson, vecStr]);
        } catch (_) {
            // pgvector column may not exist on this instance — fall back without it
            await dbRun(`
                INSERT INTO rag_chunks
                  (source_type, source_id, chunk_index, chunk_text, embedding, source_meta)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (source_type, source_id, chunk_index)
                DO UPDATE SET chunk_text  = EXCLUDED.chunk_text,
                              embedding   = EXCLUDED.embedding,
                              source_meta = EXCLUDED.source_meta
            `, [sourceType, sourceId, chunkIndex, chunkText, embJson, metaJson]);
        }
    } else {
        await dbRun(`
            INSERT OR REPLACE INTO rag_chunks
              (source_type, source_id, chunk_index, chunk_text, embedding, source_meta)
            VALUES ($1, $2, $3, $4, $5, $6)
        `, [sourceType, sourceId, chunkIndex, chunkText, embJson, metaJson]);
    }
}

// ── embedReports — market_reports ─────────────────────────────────────────────

/**
 * Embed market reports into rag_chunks.
 *
 * @param {object}      db          - server.js db wrapper (.all/.get/.run)
 * @param {boolean}     isPostgres  - true for Render/PostgreSQL
 * @param {string}      apiKey      - GOOGLE_API_KEY
 * @param {number|null} reportId    - specific report to (re-)embed, or null for all un-embedded
 * @returns {Promise<{chunksEmbedded: number, reportsProcessed: number}>}
 */
async function embedReports(db, isPostgres, apiKey, reportId = null) {
    if (!apiKey) throw new Error('GOOGLE_API_KEY not set');

    const { dbAll, dbRun } = makeHelpers(db, isPostgres);

    let reports;
    if (reportId != null) {
        reports = await dbAll(
            `SELECT id, filename, extracted_text, upload_date FROM market_reports WHERE id = $1`,
            [reportId]
        );
        if (reports.length) {
            await dbRun(
                `DELETE FROM rag_chunks WHERE source_type = $1 AND source_id = $2`,
                ['market_report', reportId]
            );
        }
    } else {
        reports = await dbAll(`
            SELECT mr.id, mr.filename, mr.extracted_text, mr.upload_date
            FROM market_reports mr
            WHERE mr.extracted_text IS NOT NULL AND TRIM(mr.extracted_text) != ''
              AND mr.id NOT IN (
                  SELECT DISTINCT source_id FROM rag_chunks WHERE source_type = $1
              )
            ORDER BY mr.upload_date DESC
        `, ['market_report']);
    }

    if (!reports.length) {
        console.log('[embedReports] No market reports to embed.');
        return { chunksEmbedded: 0, reportsProcessed: 0 };
    }

    let totalChunks = 0;
    for (const report of reports) {
        const chunks = chunkText(report.extracted_text || '');
        if (!chunks.length) continue;
        console.log(`[embedReports] ${report.filename}: embedding ${chunks.length} chunks…`);

        const sourceMeta = {
            filename:    report.filename,
            upload_date: report.upload_date ? String(report.upload_date).slice(0, 10) : '',
        };

        for (let idx = 0; idx < chunks.length; idx++) {
            try {
                const embedding = await geminiEmbed(chunks[idx], apiKey);
                await upsertChunk(db, isPostgres, 'market_report', report.id, idx, chunks[idx], embedding, sourceMeta);
                totalChunks++;
                if (idx < chunks.length - 1) await sleep(RATE_LIMIT_MS);
            } catch (err) {
                console.error(`[embedReports] chunk ${idx} of "${report.filename}" failed: ${err.message}`);
            }
        }
        console.log(`[embedReports] done: ${report.filename}`);
    }

    console.log(`[embedReports] complete — ${totalChunks} chunks across ${reports.length} report(s).`);
    return { chunksEmbedded: totalChunks, reportsProcessed: reports.length };
}

// ── embedNewsArticles — news headlines ────────────────────────────────────────

/**
 * Embed recent news headlines from the main `news` table into rag_chunks.
 *
 * @param {object}  db          - server.js db wrapper
 * @param {boolean} isPostgres  - true for Render/PostgreSQL
 * @param {string}  apiKey      - GOOGLE_API_KEY
 * @param {object}  [opts]      - { days: number (default 30), limit: number (default 300) }
 * @returns {Promise<{chunksEmbedded: number}>}
 */
async function embedNewsArticles(db, isPostgres, apiKey, opts = {}) {
    if (!apiKey) throw new Error('GOOGLE_API_KEY not set');

    const days  = opts.days  || 30;
    const limit = opts.limit || 300;
    const { dbAll } = makeHelpers(db, isPostgres);

    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - days);
    const cutoffStr = cutoff.toISOString().slice(0, 10);

    const articles = await dbAll(`
        SELECT n.id, n.symbol, n.date, n.headline, n.source, n.sentiment_label
        FROM news n
        WHERE n.headline IS NOT NULL
          AND n.date >= $1
          AND n.id NOT IN (
              SELECT DISTINCT source_id FROM rag_chunks WHERE source_type = $2
          )
        ORDER BY n.date DESC
        LIMIT $3
    `, [cutoffStr, 'news_article', limit]);

    if (!articles.length) {
        console.log('[embedNews] No new headlines to embed.');
        return { chunksEmbedded: 0 };
    }

    console.log(`[embedNews] Embedding ${articles.length} headlines…`);
    let total = 0;

    for (const article of articles) {
        const text = (
            `[${article.date}] ${article.headline}\n` +
            `Symbol: ${article.symbol} | Source: ${article.source || '?'} | ` +
            `Sentiment: ${article.sentiment_label || '?'}`
        );
        const sourceMeta = {
            symbol:          article.symbol,
            headline:        article.headline,
            source:          article.source  || '',
            date:            String(article.date || ''),
            sentiment_label: article.sentiment_label || '',
        };
        try {
            const embedding = await geminiEmbed(text, apiKey);
            await upsertChunk(db, isPostgres, 'news_article', article.id, 0, text, embedding, sourceMeta);
            total++;
            await sleep(RATE_LIMIT_MS);
        } catch (err) {
            console.error(`[embedNews] article ${article.id} failed: ${err.message}`);
        }
    }

    console.log(`[embedNews] complete — ${total} headlines embedded.`);
    return { chunksEmbedded: total };
}

module.exports = { embedReports, embedNewsArticles };
