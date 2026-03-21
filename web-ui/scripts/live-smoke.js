const DEFAULT_BASE_URL = process.env.SMOKE_BASE_URL || 'https://xmore-project.onrender.com';

function formatNumber(value, digits = 2) {
  const num = Number(value);
  return Number.isFinite(num) ? num.toFixed(digits) : 'n/a';
}

async function fetchJson(baseUrl, endpoint) {
  const url = `${baseUrl}${endpoint}`;
  const response = await fetch(url, {
    headers: {
      Accept: 'application/json',
      'User-Agent': 'xmore-live-smoke/1.0',
    },
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`${endpoint} -> HTTP ${response.status}: ${body.slice(0, 300)}`);
  }

  return response.json();
}

function summarizeConsensus(consensus) {
  const rows = Array.isArray(consensus) ? consensus : [];
  const latest = rows[0] || null;
  const activeDirectional = rows.filter((row) => ['UP', 'DOWN', 'BUY', 'SELL'].includes(String(row.final_signal || '').toUpperCase()));
  return {
    total: rows.length,
    directional: activeDirectional.length,
    latestDate: latest ? latest.prediction_date : null,
    sample: latest
      ? `${latest.symbol} ${latest.final_signal} raw=${formatNumber(latest.confidence, 1)} cal=${formatNumber(latest.calibrated_confidence, 2)} edge=${formatNumber(latest.expected_edge_pct, 3)} rank=${formatNumber(latest.ranking_score, 3)}`
      : 'none',
  };
}

function summarizeChanges(changes) {
  const signalChanges = Array.isArray(changes?.signal_changes) ? changes.signal_changes : [];
  const first = signalChanges[0] || null;
  return {
    asOf: changes?.as_of || null,
    count: signalChanges.length,
    sample: first
      ? `${first.symbol} ${first.previous_signal || 'n/a'} -> ${first.current_signal} edgeΔ=${formatNumber(first.edge_delta_pct, 3)} confΔ=${formatNumber(first.confidence_delta, 2)}`
      : 'none',
  };
}

function summarizeScored(scored) {
  const rows = Array.isArray(scored?.signals) ? scored.signals : [];
  const top = rows[0] || null;
  return {
    count: Number(scored?.count || 0),
    top: top
      ? `${top.symbol} action=${top.action} composite=${formatNumber((top.composite_score || 0) * 100, 1)} threshold=${Boolean(top.meets_threshold)}`
      : 'none',
  };
}

async function main() {
  const baseUrl = (process.argv[2] || DEFAULT_BASE_URL).replace(/\/$/, '');
  console.log(`[smoke] baseUrl=${baseUrl}`);

  const [consensus, changes, scored, brief] = await Promise.all([
    fetchJson(baseUrl, '/api/consensus'),
    fetchJson(baseUrl, '/api/intelligence/changes'),
    fetchJson(baseUrl, '/api/signals/scored/compare?days=1&action=BUY'),
    fetchJson(baseUrl, '/api/signals/morning-brief?mode=standard_100&top_n=5'),
  ]);

  const consensusSummary = summarizeConsensus(consensus);
  const changesSummary = summarizeChanges(changes);
  const scoredSummary = summarizeScored(scored);
  const briefTop = Array.isArray(brief?.top_buys) ? brief.top_buys.length : 0;

  console.log(`[smoke] consensus total=${consensusSummary.total} directional=${consensusSummary.directional} latest=${consensusSummary.latestDate || 'n/a'}`);
  console.log(`[smoke] consensus sample=${consensusSummary.sample}`);
  console.log(`[smoke] changes asOf=${changesSummary.asOf || 'n/a'} count=${changesSummary.count}`);
  console.log(`[smoke] changes sample=${changesSummary.sample}`);
  console.log(`[smoke] scored buys count=${scoredSummary.count} top=${scoredSummary.top}`);
  console.log(`[smoke] morning brief buys=${briefTop} total=${brief?.summary?.total ?? 'n/a'} aboveThreshold=${brief?.summary?.above_threshold ?? 'n/a'}`);

  if (!Array.isArray(consensus) || consensus.length === 0) {
    throw new Error('Consensus endpoint returned no rows');
  }

  if (!changes || typeof changes !== 'object') {
    throw new Error('Changes endpoint returned invalid payload');
  }

  if (!scored || typeof scored !== 'object' || !Array.isArray(scored.signals)) {
    throw new Error('Scored endpoint returned invalid payload');
  }

  console.log('[smoke] ok');
}

main().catch((error) => {
  console.error('[smoke] failed');
  console.error(error.stack || String(error));
  process.exit(1);
});