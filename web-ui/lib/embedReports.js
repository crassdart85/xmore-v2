'use strict';
/**
 * lib/embedReports.js — Pure Node.js market-report chunker + embedder.
 *
 * Works on Render (no Python required).
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
            path: `/v1beta/models/text-embedding-004:embedContent?key=${apiKey}`,
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
    function dbRun(sql, params = []) {
        return new Promise((resolve, reject) =>
            db.run(adapt(sql), params, (err) => err ? reject(err) : resolve()));
    }
    return { dbAll, dbRun };
}

// ── Main export ───────────────────────────────────────────────────────────────

/**
 * Embed market reports into rag_chunks using Node.js + Gemini REST API.
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

    // Fetch target reports
    let reports;
    if (reportId != null) {
        reports = await dbAll(
            `SELECT id, filename, extracted_text FROM market_reports WHERE id = $1`,
            [reportId]
        );
        // Delete existing chunks so re-embed is clean
        if (reports.length) {
            await dbRun(
                `DELETE FROM rag_chunks WHERE source_type = $1 AND source_id = $2`,
                ['market_report', reportId]
            );
        }
    } else {
        reports = await dbAll(`
            SELECT mr.id, mr.filename, mr.extracted_text
            FROM market_reports mr
            WHERE mr.extracted_text IS NOT NULL AND TRIM(mr.extracted_text) != ''
              AND mr.id NOT IN (
                  SELECT DISTINCT source_id FROM rag_chunks WHERE source_type = $1
              )
            ORDER BY mr.upload_date DESC
        `, ['market_report']);
    }

    if (!reports.length) {
        console.log('[embedReports] No reports to embed.');
        return { chunksEmbedded: 0, reportsProcessed: 0 };
    }

    let totalChunks = 0;
    for (const report of reports) {
        const chunks = chunkText(report.extracted_text || '');
        if (!chunks.length) {
            console.log(`[embedReports] ${report.filename}: no text to chunk, skipping.`);
            continue;
        }
        console.log(`[embedReports] ${report.filename}: embedding ${chunks.length} chunks…`);

        for (let idx = 0; idx < chunks.length; idx++) {
            const text = chunks[idx];
            try {
                const embedding = await geminiEmbed(text, apiKey);
                const embJson = JSON.stringify(embedding);

                if (isPostgres) {
                    await dbRun(`
                        INSERT INTO rag_chunks (source_type, source_id, chunk_index, chunk_text, embedding)
                        VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (source_type, source_id, chunk_index)
                        DO UPDATE SET chunk_text = EXCLUDED.chunk_text, embedding = EXCLUDED.embedding
                    `, ['market_report', report.id, idx, text, embJson]);
                } else {
                    await dbRun(`
                        INSERT OR REPLACE INTO rag_chunks
                          (source_type, source_id, chunk_index, chunk_text, embedding)
                        VALUES ($1, $2, $3, $4, $5)
                    `, ['market_report', report.id, idx, text, embJson]);
                }

                totalChunks++;
                // Rate-limit between chunks (skip sleep after last chunk of report)
                if (idx < chunks.length - 1) await sleep(RATE_LIMIT_MS);

            } catch (err) {
                console.error(`[embedReports] chunk ${idx} of "${report.filename}" failed: ${err.message}`);
                // Continue with next chunk rather than aborting the whole report
            }
        }
        console.log(`[embedReports] done: ${report.filename} (${chunks.length} chunks)`);
    }

    console.log(`[embedReports] complete — ${totalChunks} chunks across ${reports.length} report(s).`);
    return { chunksEmbedded: totalChunks, reportsProcessed: reports.length };
}

module.exports = { embedReports };
