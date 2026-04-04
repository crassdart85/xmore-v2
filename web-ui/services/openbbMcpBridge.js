/**
 * OpenBB MCP Bridge (KSA / Tadawul)
 *
 * Connects the Xmore AI Research Assistant to live market data
 * when available (OpenBB API server or local DB cache).
 *
 * Falls back gracefully to static KSA_MARKET_KNOWLEDGE if unavailable.
 * The MCP server is OPTIONAL - the chat feature must work without it.
 */

'use strict';

const OPENBB_API_BASE = process.env.OPENBB_API_URL || '';
const MCP_TIMEOUT_MS = 3000;

// Known Tadawul ticker patterns
const TICKER_REGEX = /\b(\d{4})\.SR\b/gi;
const BARE_TICKER_REGEX = /\b(2222|1120|1180|2010|1010|2350|2380|4030|2020|1150|4200|3010|2290|2170|4190)\b/gi;

/**
 * Extract Tadawul symbols mentioned in a user query.
 */
function extractSymbols(query, knownSymbols) {
  const symbols = new Set();

  // Direct .SR mentions
  let match;
  while ((match = TICKER_REGEX.exec(query)) !== null) {
    symbols.add(match[1] + '.SR');
  }

  // Bare ticker mentions (common Tadawul tickers)
  while ((match = BARE_TICKER_REGEX.exec(query)) !== null) {
    symbols.add(match[1] + '.SR');
  }

  // Match against known symbol list from DB
  if (knownSymbols && knownSymbols.length > 0) {
    const queryUpper = query.toUpperCase();
    for (const sym of knownSymbols) {
      const base = sym.replace('.SR', '');
      if (base.length >= 3 && queryUpper.includes(base)) {
        symbols.add(sym);
      }
    }
  }

  return Array.from(symbols).slice(0, 10);
}

/**
 * Fetch a live quote from the OpenBB API server (if running).
 * Returns null on timeout/error.
 */
async function fetchLiveQuote(symbol) {
  if (!OPENBB_API_BASE) return null;

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), MCP_TIMEOUT_MS);

    const url = `${OPENBB_API_BASE}/api/v1/equity/price/quote?symbol=${encodeURIComponent(symbol)}&provider=ksa`;
    const resp = await fetch(url, { signal: controller.signal });
    clearTimeout(timeout);

    if (!resp.ok) return null;
    const data = await resp.json();
    return data?.results?.[0] || data;
  } catch (_) {
    return null;
  }
}

/**
 * Fetch macro context from local DB (already cached by daily pipeline).
 * Returns macro summary dict or null.
 */
async function fetchMacroContext(db) {
  if (!db) return null;

  try {
    const indicators = ['sama_rate', 'usd_sar', 'cpi_yoy', 'gdp_growth'];
    const macro = {};

    for (const ind of indicators) {
      const sql = db._isPostgres
        ? `SELECT value, period, source FROM macro_indicators WHERE indicator = $1 ORDER BY fetched_at DESC LIMIT 1`
        : `SELECT value, period, source FROM macro_indicators WHERE indicator = ? ORDER BY fetched_at DESC LIMIT 1`;

      try {
        const row = await new Promise((resolve, reject) => {
          if (db._isPostgres) {
            db.query(sql, [ind]).then(r => resolve(r.rows?.[0])).catch(reject);
          } else {
            db.get(sql, [ind], (err, row) => err ? reject(err) : resolve(row));
          }
        });
        if (row) macro[ind] = { value: row.value, period: row.period };
      } catch (_) {}
    }

    if (Object.keys(macro).length === 0) return null;

    // Compute regime context (KSA: SAMA repo rate, SAR pegged to USD)
    const rate = macro.sama_rate?.value || 5.5;
    const rateEnv = rate > 5.5 ? 'HIGH' : rate > 3.0 ? 'NORMAL' : 'LOW';
    const inflation = macro.cpi_yoy?.value || 1.6;
    const inflationRegime = inflation > 5 ? 'HIGH' : inflation > 2.5 ? 'MODERATE' : 'LOW';

    return {
      sama_rate: macro.sama_rate?.value,
      usd_sar: macro.usd_sar?.value,
      cpi_yoy: macro.cpi_yoy?.value,
      gdp_growth: macro.gdp_growth?.value,
      rate_environment: rateEnv,
      inflation_regime: inflationRegime,
    };
  } catch (_) {
    return null;
  }
}

/**
 * Build an enriched system prompt for /api/rag/chat.
 *
 * 1. Extract Tadawul symbols from user query
 * 2. Fetch live quotes for mentioned symbols (3s timeout)
 * 3. Fetch macro context from local DB cache
 * 4. Compose enriched prompt section
 * 5. If all fetches fail: return null (caller uses static knowledge)
 *
 * Must complete in < 3.5 seconds total.
 */
async function buildEnrichedSystemPrompt(db, userQuery, knownSymbols) {
  const enrichments = [];
  let enriched = false;

  try {
    // Extract symbols mentioned in query
    const symbols = extractSymbols(userQuery, knownSymbols);

    // Parallel fetches with timeouts
    const promises = [];

    // Fetch live quotes for mentioned symbols
    for (const sym of symbols.slice(0, 5)) {
      promises.push(
        fetchLiveQuote(sym)
          .then(q => q ? { type: 'quote', symbol: sym, data: q } : null)
          .catch(() => null)
      );
    }

    // Fetch macro context from local DB
    promises.push(
      fetchMacroContext(db)
        .then(m => m ? { type: 'macro', data: m } : null)
        .catch(() => null)
    );

    // Wait for all with global timeout
    const deadline = new Promise(resolve => setTimeout(() => resolve([]), 3500));
    const results = await Promise.race([
      Promise.all(promises),
      deadline,
    ]);

    // Process results
    for (const r of (results || [])) {
      if (!r) continue;

      if (r.type === 'quote') {
        const q = r.data;
        const price = q.last_price || q.close || q.lastPrice;
        const change = q.change_pct || q.changePct;
        if (price) {
          enrichments.push(
            `LIVE QUOTE: ${r.symbol} = SAR ${price}` +
            (change != null ? ` (${change >= 0 ? '+' : ''}${Number(change).toFixed(2)}%)` : '')
          );
          enriched = true;
        }
      }

      if (r.type === 'macro') {
        const m = r.data;
        const parts = [];
        if (m.sama_rate != null) parts.push(`SAMA rate: ${m.sama_rate}%`);
        if (m.usd_sar != null) parts.push(`USD/SAR: ${m.usd_sar}`);
        if (m.cpi_yoy != null) parts.push(`CPI YoY: ${m.cpi_yoy}%`);
        if (m.gdp_growth != null) parts.push(`GDP growth: ${m.gdp_growth}%`);
        if (m.rate_environment) parts.push(`Rate env: ${m.rate_environment}`);
        if (parts.length > 0) {
          enrichments.push(`MACRO CONTEXT: ${parts.join(' | ')}`);
          enriched = true;
        }
      }
    }
  } catch (_) {
    // Fail silently — enrichment is best-effort
  }

  if (!enriched || enrichments.length === 0) {
    return { prompt: null, enriched: false };
  }

  const prompt = [
    '\n--- LIVE DATA (prioritize over training knowledge when available) ---',
    ...enrichments,
    '--- END LIVE DATA ---\n',
  ].join('\n');

  return { prompt, enriched: true };
}

module.exports = { buildEnrichedSystemPrompt, fetchLiveQuote, fetchMacroContext, extractSymbols };
