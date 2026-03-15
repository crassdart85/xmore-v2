const express = require('express');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const multer = require('multer');
const { PDFParse } = require('pdf-parse');
let _tesseract = null;
function getTesseract() {
    if (!_tesseract) {
        try { _tesseract = require('tesseract.js'); } catch(_) { return null; }
    }
    return _tesseract;
}
const { requireAdminSecret } = require('../middleware/admin');
const { embedReports } = require('../lib/embedReports');

const router = express.Router();

let db;
let isPostgres = false;

const uploadDir = path.join(__dirname, '..', 'uploads', 'market_reports');

function attachDb(database, pg) {
    db = database;
    isPostgres = pg;
}

function ph(n) {
    return isPostgres ? `$${n}` : '?';
}

function normalizeSql(query) {
    if (isPostgres) return query;
    return query.replace(/\$\d+\b/g, '?');
}

function dbAll(query, params = []) {
    return new Promise((resolve, reject) => {
        db.all(normalizeSql(query), params, (err, rows) => {
            if (err) reject(err);
            else resolve(rows || []);
        });
    });
}

function dbGet(query, params = []) {
    return new Promise((resolve, reject) => {
        db.get(normalizeSql(query), params, (err, row) => {
            if (err) reject(err);
            else resolve(row || null);
        });
    });
}

function dbRun(query, params = []) {
    return new Promise((resolve, reject) => {
        if (isPostgres) {
            db.run(normalizeSql(query), params, (err, result) => {
                if (err) reject(err);
                else resolve(result || null);
            });
            return;
        }

        db.run(normalizeSql(query), params, function onRun(err) {
            if (err) reject(err);
            else resolve({ lastID: this.lastID, changes: this.changes });
        });
    });
}

function isMissingTableError(err) {
    return !!(err && err.message && (
        err.message.includes('does not exist') ||
        err.message.includes('no such table') ||
        err.message.includes('no such column')
    ));
}

function ensureUploadDir() {
    fs.mkdirSync(uploadDir, { recursive: true });
}

function decodeFilename(raw) {
    if (!raw) return 'report';
    try {
        return Buffer.from(raw, 'latin1').toString('utf8');
    } catch (_e) {
        return raw;
    }
}

const storage = multer.diskStorage({
    destination: (_req, _file, cb) => {
        try {
            ensureUploadDir();
            cb(null, uploadDir);
        } catch (err) {
            cb(err);
        }
    },
    filename: (_req, file, cb) => {
        const ext = path.extname(file.originalname || '').toLowerCase();
        const base = path
            .basename(file.originalname || 'report', ext)
            .replace(/[^a-zA-Z0-9._-]/g, '_');
        cb(null, `${Date.now()}_${base}${ext || '.pdf'}`);
    }
});

const ALLOWED_EXTENSIONS = new Set(['.pdf', '.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff', '.tif']);
const IMAGE_EXTENSIONS = new Set(['.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff', '.tif']);

function allowedFileFilter(_req, file, cb) {
    const ext = path.extname(file.originalname || '').toLowerCase();
    if (ALLOWED_EXTENSIONS.has(ext)) {
        cb(null, true);
        return;
    }
    cb(new Error('Only PDF and image files (PNG, JPG, WEBP, BMP, TIFF) are allowed'));
}

const upload = multer({
    storage,
    fileFilter: allowedFileFilter,
    limits: { fileSize: 25 * 1024 * 1024 }
});

router.use(requireAdminSecret);

const ARABIC_RE = /[\u0600-\u06FF]/g;
const LATIN_RE = /[A-Za-z]/g;
const SENTENCE_SPLIT_RE = /(?<=[.!?\u061f])\s+/;

function detectLanguage(text) {
    if (!text) return 'EN';
    const arCount = (text.match(ARABIC_RE) || []).length;
    const enCount = (text.match(LATIN_RE) || []).length;
    return arCount > enCount ? 'AR' : 'EN';
}

const TICKER_RE = /\b[A-Z]{2,5}(?:\.CA)?\b/g;
const BULLISH_RE = /\b(buy|long|bullish|upside|outperform|go(?:ing)?\s+up|rise|rally|upgrade|accumulate|overweight|strong|growth|positive|gain|recover)\b/gi;
const BEARISH_RE = /\b(sell|short|bearish|downside|underperform|go(?:ing)?\s+down|fall|decline|downgrade|reduce|underweight|weak|loss|drop|risk|negative|warning)\b/gi;
const TOPIC_RE = /\b(earnings|revenue|profit|dividend|merger|acquisition|IPO|interest\s+rate|inflation|GDP|oil|sector|market|index|EGX|banking|real\s+estate|pharma|tech|telecom|construction|food|chemicals|retail)\b/gi;

function buildInsight(text) {
    if (!text) return '';
    const cleaned = text.replace(/\s+/g, ' ').trim();
    if (!cleaned) return '';

    // Extract stock tickers mentioned
    const tickerMatches = [...new Set((cleaned.match(TICKER_RE) || []).filter(t => t.length >= 2 && t.length <= 7))];
    // Filter out common English words that look like tickers
    const stopWords = new Set(['THE', 'AND', 'FOR', 'ARE', 'BUT', 'NOT', 'YOU', 'ALL', 'CAN', 'HER', 'WAS', 'ONE', 'OUR', 'OUT', 'HAS', 'ITS', 'HIS', 'HOW', 'MAY', 'NEW', 'NOW', 'OLD', 'SEE', 'WAY', 'WHO', 'DID', 'GET', 'LET', 'SAY', 'SHE', 'TOO', 'USE', 'PDF', 'PNG', 'JPG', 'EGP', 'USD', 'EUR', 'GBP', 'SAR', 'AED', 'WITH', 'THIS', 'THAT', 'FROM', 'ALSO', 'BEEN', 'WILL', 'EACH', 'THAN', 'THEM', 'THEN', 'SOME', 'HAVE', 'MORE']);
    const tickers = tickerMatches.filter(t => !stopWords.has(t)).slice(0, 6);

    // Count bullish vs bearish signals
    const bullCount = (cleaned.match(BULLISH_RE) || []).length;
    const bearCount = (cleaned.match(BEARISH_RE) || []).length;

    // Extract topics
    const topicMatches = [...new Set((cleaned.match(TOPIC_RE) || []).map(t => t.toLowerCase()))].slice(0, 4);

    // Build the interpretive summary
    const parts = [];

    // What the document is about
    if (tickers.length && topicMatches.length) {
        parts.push(`Discusses ${tickers.join(', ')} in the context of ${topicMatches.join(', ')}`);
    } else if (tickers.length) {
        parts.push(`Covers stocks: ${tickers.join(', ')}`);
    } else if (topicMatches.length) {
        parts.push(`Covers topics: ${topicMatches.join(', ')}`);
    } else {
        // Fall back to first meaningful sentence
        const sentences = cleaned.split(SENTENCE_SPLIT_RE).map(s => s.trim()).filter(Boolean);
        if (sentences.length) {
            parts.push(sentences[0].slice(0, 200));
        } else {
            return cleaned.slice(0, 300);
        }
    }

    // Overall tone
    if (bullCount > 0 || bearCount > 0) {
        const total = bullCount + bearCount;
        if (bullCount > bearCount * 2) {
            parts.push(`Overall tone is bullish (${bullCount}/${total} signals positive)`);
        } else if (bearCount > bullCount * 2) {
            parts.push(`Overall tone is bearish (${bearCount}/${total} signals negative)`);
        } else {
            parts.push(`Mixed outlook (${bullCount} bullish vs ${bearCount} bearish signals)`);
        }
    }

    // Key takeaway from signal sentences
    const sentences = cleaned.split(SENTENCE_SPLIT_RE).map(s => s.trim()).filter(Boolean);
    const SIGNAL_RE = /\b(buy|sell|bullish|bearish|target|upgrade|downgrade|outperform|underperform)\b/i;
    const keySentence = sentences.find(s => SIGNAL_RE.test(s));
    if (keySentence) {
        parts.push(`Key insight: "${keySentence.slice(0, 150)}"`);
    }

    return parts.join('. ').slice(0, 600);
}

async function extractPdf(filePath) {
    const dataBuffer = fs.readFileSync(filePath);
    const pdf = new PDFParse({ data: dataBuffer });
    const result = await pdf.getText();
    const extractedText = (result.text || '').trim();
    const language = detectLanguage(extractedText);
    const summary = buildInsight(extractedText);
    pdf.destroy();
    return { extracted_text: extractedText, language, summary };
}

async function extractImage(filePath) {
    const tesseract = getTesseract();
    if (!tesseract) throw new Error('tesseract.js not available');
    const lang = 'eng+ara';
    const worker = await tesseract.createWorker(lang);
    try {
        const { data } = await worker.recognize(filePath);
        const extractedText = (data.text || '').trim();
        const language = detectLanguage(extractedText);
        const summary = buildInsight(extractedText);
        return { extracted_text: extractedText, language, summary };
    } finally {
        await worker.terminate();
    }
}

async function extractFile(filePath) {
    const ext = path.extname(filePath).toLowerCase();
    if (IMAGE_EXTENSIONS.has(ext)) {
        return extractImage(filePath);
    }
    return extractPdf(filePath);
}

function buildSummary(text, fallbackSummary) {
    if (fallbackSummary && fallbackSummary.trim()) return fallbackSummary.trim();
    if (!text || !text.trim()) return '';
    const cleaned = text.replace(/\s+/g, ' ').trim();
    return cleaned.slice(0, 600);
}

router.get('/system-health', async (_req, res) => {
    try {
        const latestAudit = await dbGet(`
            SELECT id, table_name, record_id, field_changed, changed_at
            FROM prediction_audit_log
            ORDER BY changed_at DESC
            LIMIT 1
        `);

        const latestAgentDaily = await dbGet(`
            SELECT snapshot_date, agent_name, predictions_30d, win_rate_30d, predictions_90d, win_rate_90d
            FROM agent_performance_daily
            ORDER BY snapshot_date DESC, agent_name ASC
            LIMIT 1
        `);

        return res.json({
            audit_log: latestAudit || null,
            agent_performance_daily: latestAgentDaily || null,
            checked_at: new Date().toISOString()
        });
    } catch (err) {
        if (isMissingTableError(err)) {
            return res.json({
                audit_log: null,
                agent_performance_daily: null,
                checked_at: new Date().toISOString()
            });
        }
        console.error('Admin system-health error:', err);
        return res.status(500).json({ error: 'Failed to load admin system health' });
    }
});

router.get('/reports', async (req, res) => {
    try {
        const limitRaw = parseInt(req.query.limit, 10);
        const limit = Number.isFinite(limitRaw) ? Math.min(Math.max(limitRaw, 1), 200) : 100;

        const rows = await dbAll(`
            SELECT
                id,
                filename,
                upload_date,
                language,
                summary,
                CASE
                    WHEN extracted_text IS NULL OR TRIM(extracted_text) = '' THEN 'Pending'
                    ELSE 'Processed'
                END AS status
            FROM market_reports
            ORDER BY upload_date DESC
            LIMIT ${ph(1)}
        `, [limit]);

        return res.json({ reports: rows });
    } catch (err) {
        if (isMissingTableError(err)) {
            return res.json({ reports: [] });
        }
        console.error('Admin reports list error:', err);
        return res.status(500).json({ error: 'Failed to load reports list' });
    }
});

router.post('/reports/upload', upload.single('report'), async (req, res) => {
    if (!req.file) {
        return res.status(400).json({ error: 'A PDF or image file is required (field name: report)' });
    }

    try {
        const filename = decodeFilename(req.file.originalname);
        const ingest = await extractFile(req.file.path);
        const extractedText = typeof ingest.extracted_text === 'string' ? ingest.extracted_text : '';
        const language = String(ingest.language || 'EN').toUpperCase() === 'AR' ? 'AR' : 'EN';
        const summary = buildSummary(extractedText, ingest.summary || '');

        // Insert report and get its ID for auto-embedding
        let newReportId = null;
        if (isPostgres) {
            const row = await dbGet(`
                INSERT INTO market_reports (filename, upload_date, extracted_text, language, summary)
                VALUES (${ph(1)}, CURRENT_TIMESTAMP, ${ph(2)}, ${ph(3)}, ${ph(4)})
                RETURNING id
            `, [filename, extractedText, language, summary]);
            newReportId = row ? row.id : null;
        } else {
            const result = await dbRun(`
                INSERT INTO market_reports (filename, upload_date, extracted_text, language, summary)
                VALUES (${ph(1)}, CURRENT_TIMESTAMP, ${ph(2)}, ${ph(3)}, ${ph(4)})
            `, [filename, extractedText, language, summary]);
            newReportId = result ? result.lastID : null;
        }

        // Auto-embed in background if Gemini API key is available
        const apiKey = process.env.GOOGLE_API_KEY || '';
        if (apiKey && newReportId && extractedText.trim()) {
            embedReports(db, isPostgres, apiKey, newReportId)
                .then(r => console.log(`[auto-embed] "${filename}": ${r.chunksEmbedded} chunks embedded`))
                .catch(err => console.error(`[auto-embed] "${filename}" failed:`, err.message));
        }

        return res.status(201).json({
            ok: true,
            filename,
            language,
            summary,
            status: extractedText.trim() ? 'Processed' : 'Pending',
            embedding: apiKey ? 'started' : 'skipped (no GOOGLE_API_KEY)'
        });
    } catch (err) {
        console.error('Admin upload error:', err);
        return res.status(500).json({
            error: 'Failed to process uploaded report',
            details: err.message
        });
    }
});

// ============================================================
// CUSTOM NEWS SOURCES — CRUD + Fetch Now + WhatsApp ingest
// ============================================================

const VALID_SOURCE_TYPES = new Set(['url', 'rss', 'telegram_public', 'telegram_bot', 'manual']);
const VALID_LANGUAGES = new Set(['auto', 'en', 'ar']);

// GET /api/admin/sources
router.get('/sources', async (_req, res) => {
    try {
        const rows = await dbAll(`
            SELECT
                s.id, s.name, s.source_type, s.source_url,
                s.chat_id, s.language, s.is_active,
                s.fetch_interval_hours, s.last_fetched_at, s.created_at,
                (SELECT COUNT(*) FROM custom_source_articles a WHERE a.source_id = s.id) AS article_count
            FROM custom_news_sources s
            ORDER BY s.created_at DESC
        `);
        return res.json({ sources: rows });
    } catch (err) {
        if (isMissingTableError(err)) return res.json({ sources: [] });
        console.error('Admin sources list error:', err);
        return res.status(500).json({ error: 'Failed to load sources' });
    }
});

// POST /api/admin/sources
router.post('/sources', express.json(), async (req, res) => {
    const { name, source_type, source_url, bot_token, chat_id, language, fetch_interval_hours } = req.body || {};

    if (!name || !source_type) {
        return res.status(400).json({ error: 'name and source_type are required' });
    }
    if (!VALID_SOURCE_TYPES.has(source_type)) {
        return res.status(400).json({ error: `source_type must be one of: ${[...VALID_SOURCE_TYPES].join(', ')}` });
    }
    const lang = VALID_LANGUAGES.has(language) ? language : 'auto';
    const interval = Math.min(Math.max(parseInt(fetch_interval_hours, 10) || 6, 1), 168);

    if (['url', 'rss', 'telegram_public'].includes(source_type) && !source_url) {
        return res.status(400).json({ error: `source_url is required for source_type=${source_type}` });
    }
    if (source_type === 'telegram_bot' && (!bot_token || !chat_id)) {
        return res.status(400).json({ error: 'bot_token and chat_id are required for telegram_bot sources' });
    }

    try {
        const row = await dbGet(`
            INSERT INTO custom_news_sources (name, source_type, source_url, bot_token, chat_id, language, fetch_interval_hours)
            VALUES (${ph(1)},${ph(2)},${ph(3)},${ph(4)},${ph(5)},${ph(6)},${ph(7)})
            RETURNING id
        `, [name, source_type, source_url || null, bot_token || null, chat_id || null, lang, interval]);

        const id = row ? row.id : null;
        return res.status(201).json({ ok: true, id });
    } catch (err) {
        console.error('Admin create source error:', err);
        return res.status(500).json({ error: 'Failed to create source' });
    }
});

// PATCH /api/admin/sources/:id
router.patch('/sources/:id', express.json(), async (req, res) => {
    const sourceId = parseInt(req.params.id, 10);
    if (!sourceId) return res.status(400).json({ error: 'Invalid id' });

    const { name, is_active, fetch_interval_hours, language, bot_token, chat_id, source_url } = req.body || {};
    const updates = [];
    const params = [];
    let i = 1;

    if (name !== undefined)               { updates.push(`name = ${ph(i++)}`);                   params.push(name); }
    if (is_active !== undefined)          { updates.push(`is_active = ${ph(i++)}`);               params.push(!!is_active); }
    if (fetch_interval_hours !== undefined) { updates.push(`fetch_interval_hours = ${ph(i++)}`); params.push(parseInt(fetch_interval_hours, 10) || 6); }
    if (language !== undefined && VALID_LANGUAGES.has(language)) { updates.push(`language = ${ph(i++)}`); params.push(language); }
    if (bot_token !== undefined)          { updates.push(`bot_token = ${ph(i++)}`);               params.push(bot_token || null); }
    if (chat_id !== undefined)            { updates.push(`chat_id = ${ph(i++)}`);                 params.push(chat_id || null); }
    if (source_url !== undefined)         { updates.push(`source_url = ${ph(i++)}`);              params.push(source_url || null); }

    if (updates.length === 0) return res.status(400).json({ error: 'No valid fields to update' });

    params.push(sourceId);
    try {
        await dbRun(`UPDATE custom_news_sources SET ${updates.join(', ')} WHERE id = ${ph(i)}`, params);
        return res.json({ ok: true });
    } catch (err) {
        if (isMissingTableError(err)) return res.status(404).json({ error: 'Table not found — run migration 011' });
        console.error('Admin update source error:', err);
        return res.status(500).json({ error: 'Failed to update source' });
    }
});

// DELETE /api/admin/sources/:id
router.delete('/sources/:id', async (req, res) => {
    const sourceId = parseInt(req.params.id, 10);
    if (!sourceId) return res.status(400).json({ error: 'Invalid id' });
    try {
        await dbRun(`DELETE FROM custom_news_sources WHERE id = ${ph(1)}`, [sourceId]);
        return res.json({ ok: true });
    } catch (err) {
        console.error('Admin delete source error:', err);
        return res.status(500).json({ error: 'Failed to delete source' });
    }
});

// POST /api/admin/sources/:id/fetch — trigger Python fetcher for one source
router.post('/sources/:id/fetch', async (req, res) => {
    const sourceId = parseInt(req.params.id, 10);
    if (!sourceId) return res.status(400).json({ error: 'Invalid id' });

    const projectRoot = path.join(__dirname, '..', '..');
    const scriptPath = path.join(projectRoot, 'engines', 'custom_source_fetcher.py');

    let stdout = '';
    let stderr = '';
    let timedOut = false;

    const child = spawn('python', [scriptPath, '--source-id', String(sourceId)], {
        cwd: projectRoot,
        env: { ...process.env },
    });

    const timeout = setTimeout(() => {
        timedOut = true;
        child.kill();
    }, 60000);

    child.stdout.on('data', d => { stdout += d.toString(); });
    child.stderr.on('data', d => { stderr += d.toString(); });

    child.on('close', (code) => {
        clearTimeout(timeout);
        if (timedOut) {
            return res.status(504).json({ ok: false, error: 'Fetch timed out after 60s' });
        }
        try {
            const result = JSON.parse(stdout.trim() || '{}');
            return res.json(result);
        } catch (_e) {
            return res.status(500).json({
                ok: false,
                error: `Fetcher exited with code ${code}`,
                stderr: stderr.slice(0, 500),
            });
        }
    });
});

// POST /api/admin/sources/manual — manual paste or file upload (private channels, etc.)
const waUpload = multer({
    storage,
    fileFilter: allowedFileFilter,
    limits: { fileSize: 25 * 1024 * 1024 },
});

router.post('/sources/manual', waUpload.single('file'), async (req, res) => {
    const rawText = (req.body && req.body.text) ? String(req.body.text).trim() : '';
    const sourceName = (req.body && req.body.source_name) ? String(req.body.source_name).trim() : 'Manual Feed';

    if (!rawText && !req.file) {
        return res.status(400).json({ error: 'Provide text or a file' });
    }

    try {
        // Ensure a "manual" source exists for this label
        let manualSource = await dbGet(
            `SELECT id FROM custom_news_sources WHERE source_type = ${ph(1)} AND name = ${ph(2)}`,
            ['manual', sourceName]
        );
        if (!manualSource) {
            manualSource = await dbGet(
                `INSERT INTO custom_news_sources (name, source_type, language) VALUES (${ph(1)},'manual','auto') RETURNING id`,
                [sourceName]
            );
        }
        const sourceId = manualSource.id;

        // Extract content
        let content = rawText;
        let contentType = 'text';
        if (req.file) {
            try {
                const ingest = await extractFile(req.file.path);
                const fileText = (typeof ingest.extracted_text === 'string' ? ingest.extracted_text : '').trim();
                content = rawText ? `${rawText}\n\n${fileText}` : fileText;
                contentType = path.extname(req.file.path).toLowerCase() === '.pdf' ? 'pdf' : 'image';
            } catch (e) {
                console.error('Manual ingest file extraction error:', e);
                if (!rawText) return res.status(500).json({ error: 'Failed to extract file content' });
            }
        }

        if (!content) return res.status(400).json({ error: 'No text content could be extracted' });

        // Spawn Python to ingest and match to symbols
        const projectRoot = path.join(__dirname, '..', '..');
        const scriptPath = path.join(projectRoot, 'engines', 'custom_source_fetcher.py');
        const payload = JSON.stringify({ source_id: sourceId, content, content_type: contentType });

        let stdout = '';
        const child = spawn('python', [scriptPath, '--ingest-text', payload], {
            cwd: projectRoot,
            env: { ...process.env },
        });

        let timedOut = false;
        const timeout = setTimeout(() => { timedOut = true; child.kill(); }, 30000);

        child.stdout.on('data', d => { stdout += d.toString(); });

        child.on('close', () => {
            clearTimeout(timeout);
            if (timedOut) return res.status(504).json({ ok: false, error: 'Processing timed out' });
            try {
                const result = JSON.parse(stdout.trim() || '{}');
                return res.status(result.ok === false ? 500 : 201).json(result);
            } catch (_e) {
                return res.status(500).json({ ok: false, error: 'Failed to parse ingest result' });
            }
        });

    } catch (err) {
        console.error('Admin manual ingest error:', err);
        return res.status(500).json({ error: 'Failed to process content' });
    }
});

// ─── GET /api/admin/forecast-accuracy ────────────────────────
router.get('/forecast-accuracy', async (_req, res) => {
    try {
        // Overall summary
        const summary = await dbGet(`
            SELECT
                COUNT(*)                                         AS total_forecasts,
                SUM(CASE WHEN e.id IS NOT NULL THEN 1 ELSE 0 END) AS total_evaluated,
                AVG(CASE WHEN e.id IS NOT NULL THEN e.error_pct END) AS avg_error_pct,
                AVG(CASE WHEN e.id IS NOT NULL THEN CAST(e.within_10pct AS REAL) END) AS within_10pct_rate
            FROM portfolio_forecast_results r
            LEFT JOIN portfolio_forecast_evaluations e ON e.forecast_result_id = r.id
            WHERE r.ok = 1
        `);

        // Per-stock breakdown
        const byStock = await dbAll(`
            SELECT
                r.symbol,
                COUNT(r.id)                                            AS total_forecasts,
                AVG(r.expected_return_pct)                             AS avg_expected_pct,
                AVG(e.actual_return_pct)                               AS avg_actual_pct,
                AVG(e.error_pct)                                       AS avg_error_pct,
                AVG(CAST(e.within_10pct AS REAL))                      AS within_10pct_rate
            FROM portfolio_forecast_results r
            LEFT JOIN portfolio_forecast_evaluations e ON e.forecast_result_id = r.id
            WHERE r.ok = 1
            GROUP BY r.symbol
            ORDER BY COUNT(r.id) DESC
        `);

        // Recent evaluations (last 30)
        const recentEvaluations = await dbAll(`
            SELECT
                e.run_date, e.symbol, e.target_date,
                e.expected_return_pct, e.actual_return_pct, e.error_pct, e.within_10pct,
                e.evaluated_at
            FROM portfolio_forecast_evaluations e
            ORDER BY e.evaluated_at DESC
            LIMIT 30
        `);

        res.json({ summary, by_stock: byStock, recent_evaluations: recentEvaluations });
    } catch (err) {
        console.error('Forecast accuracy error:', err);
        res.status(500).json({ error: err.message });
    }
});

module.exports = { router, attachDb };
