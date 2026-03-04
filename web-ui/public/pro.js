/* ─── Xmore Pro — Market Overview ────────────────────────────────────────── */

// ── Date header ──────────────────────────────────────────────────────────────
(function renderDate() {
  const el = document.getElementById('proDate');
  if (!el) return;
  const now = new Date();
  el.textContent = now.toLocaleDateString('en-GB', {
    weekday: 'long', day: 'numeric', month: 'short', year: 'numeric'
  });
})();

// ── TradingView ticker ────────────────────────────────────────────────────────
(function loadTicker() {
  const container = document.getElementById('proTicker');
  if (!container) return;

  const wrapper = document.createElement('div');
  wrapper.className = 'tradingview-widget-container';

  const inner = document.createElement('div');
  inner.className = 'tradingview-widget-container__widget';
  wrapper.appendChild(inner);

  const script = document.createElement('script');
  script.type = 'text/javascript';
  script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js';
  script.async = true;
  script.innerHTML = JSON.stringify({
    symbols: [
      { proName: 'EGX:EGX30',  title: 'EGX 30'  },
      { proName: 'EGX:COMI',   title: 'CIB'      },
      { proName: 'EGX:HRHO',   title: 'EFG'      },
      { proName: 'EGX:ETEL',   title: 'Telecom'  },
      { proName: 'EGX:EFIH',   title: 'EFG Fin'  },
      { proName: 'EGX:CLHO',   title: 'Cleopatra'},
      { proName: 'EGX:SWDY',   title: 'Edita'    },
      { proName: 'EGX:AMOC',   title: 'AMOC'     },
      { proName: 'EGX:ABUK',   title: 'AbuQir'   },
    ],
    showSymbolLogo: false,
    colorTheme: 'dark',
    isTransparent: true,
    displayMode: 'adaptive',
    locale: 'en',
  });
  wrapper.appendChild(script);
  container.appendChild(wrapper);
})();

// ── EGX 30 Intraday Chart ────────────────────────────────────────────────────
(function loadEGX30Chart() {
  const container = document.getElementById('egx30ChartWidget');
  if (!container) return;

  const wrapper = document.createElement('div');
  wrapper.className = 'tradingview-widget-container';
  wrapper.style.cssText = 'height:100%;width:100%';

  const inner = document.createElement('div');
  inner.className = 'tradingview-widget-container__widget';
  inner.style.cssText = 'height:calc(100% - 32px);width:100%';
  wrapper.appendChild(inner);

  const script = document.createElement('script');
  script.type = 'text/javascript';
  script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js';
  script.async = true;
  script.innerHTML = JSON.stringify({
    autosize: true,
    symbol: 'EGX:EGX30',
    interval: '5',
    timezone: 'Africa/Cairo',
    theme: 'dark',
    style: '2',        // area chart
    locale: 'en',
    backgroundColor: '#141414',
    gridColor: 'rgba(42,42,42,0.4)',
    hide_top_toolbar: false,
    hide_legend: true,
    save_image: false,
    hide_volume: false,
    support_host: 'https://www.tradingview.com',
  });
  wrapper.appendChild(script);
  container.appendChild(wrapper);
})();

// ── EGX Market Indices ────────────────────────────────────────────────────────
(function loadEGXIndices() {
  const container = document.getElementById('egxIndicesWidget');
  if (!container) return;

  const wrapper = document.createElement('div');
  wrapper.className = 'tradingview-widget-container';
  wrapper.style.cssText = 'height:100%;width:100%';

  const inner = document.createElement('div');
  inner.className = 'tradingview-widget-container__widget';
  inner.style.cssText = 'height:100%;width:100%';
  wrapper.appendChild(inner);

  const script = document.createElement('script');
  script.type = 'text/javascript';
  script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-market-overview.js';
  script.async = true;
  script.innerHTML = JSON.stringify({
    colorTheme: 'dark',
    dateRange: '1D',
    showChart: true,
    locale: 'en',
    isTransparent: true,
    showSymbolLogo: false,
    showFloatingTooltip: false,
    width: '100%',
    height: '100%',
    tabs: [
      {
        title: 'EGX Blue Chips',
        symbols: [
          { s: 'EGX:COMI',  d: 'CIB'        },
          { s: 'EGX:HRHO',  d: 'EFG Hermes' },
          { s: 'EGX:ETEL',  d: 'Telecom EG' },
          { s: 'EGX:CLHO',  d: 'Cleopatra'  },
          { s: 'EGX:SWDY',  d: 'Edita'      },
          { s: 'EGX:AMOC',  d: 'AMOC'       },
          { s: 'EGX:ABUK',  d: 'AbuQir'     },
          { s: 'EGX:EFIH',  d: 'EFG Fin'    },
        ],
        originalTitle: 'EGX Blue Chips',
      },
    ],
  });
  wrapper.appendChild(script);
  container.appendChild(wrapper);
})();

// ── Helpers ───────────────────────────────────────────────────────────────────
function fmtChg(val) {
  if (val === null || val === undefined || isNaN(val)) return '—';
  const n = parseFloat(val);
  return (n >= 0 ? '+' : '') + n.toFixed(2) + '%';
}

function fmtClose(val) {
  if (!val) return '—';
  return parseFloat(val).toFixed(2);
}

function fmtDate(dateStr) {
  if (!dateStr) return '—';
  // Slice to YYYY-MM-DD to handle both "2026-03-03" and "2026-03-03T00:00:00.000Z"
  const d = new Date(String(dateStr).slice(0, 10) + 'T00:00:00');
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

function signalBadge(prediction, confidence) {
  if (!prediction) return '<span class="sig-none">—</span>';
  const p = prediction.toUpperCase();
  if (p === 'UP')   return `<span class="sig-buy">↑ BUY</span>`;
  if (p === 'DOWN') return `<span class="sig-sell">↓ SELL</span>`;
  if (p === 'HOLD') return `<span class="sig-hold">→ HOLD</span>`;
  return `<span class="sig-none">${p}</span>`;
}

function escHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ── Main data load ────────────────────────────────────────────────────────────
Promise.all([
  fetch('/api/prices').then(r => r.json()).catch(() => []),
  fetch('/api/stocks').then(r => r.json()).catch(() => ({ stocks: [] })),
  fetch('/api/consensus').then(r => r.json()).catch(() => []),
  fetch('/api/stats').then(r => r.json()).catch(() => ({})),
  fetch('/api/performance').then(r => r.json()).catch(() => []),
]).then(([prices, stocksData, consensus, stats, perf]) => {
  const stocks = Array.isArray(stocksData) ? stocksData : (stocksData.stocks || []);
  const pricesArr = Array.isArray(prices) ? prices : [];
  const consensusArr = Array.isArray(consensus) ? consensus : [];
  const perfArr = Array.isArray(perf) ? perf : [];

  renderStats(pricesArr, stats, perfArr);
  renderMovers(pricesArr, stocks, consensusArr);
  renderSectors(pricesArr, stocks);
});

// ── renderStats ───────────────────────────────────────────────────────────────
function renderStats(prices, stats, perf) {
  const total = prices.length;
  const upCount   = prices.filter(p => parseFloat(p.change_pct) > 0).length;
  const downCount = prices.filter(p => parseFloat(p.change_pct) < 0).length;
  const upPct     = total ? Math.round(upCount / total * 100) : 0;
  const downPct   = total ? Math.round(downCount / total * 100) : 0;

  document.getElementById('statTracked').textContent  = total || stats.stocksTracked || '—';
  document.getElementById('statUp').textContent       = upCount || '—';
  document.getElementById('statUpPct').textContent    = total ? `${upPct}% of market` : '';
  document.getElementById('statDown').textContent     = downCount || '—';
  document.getElementById('statDownPct').textContent  = total ? `${downPct}% of market` : '';
  document.getElementById('statLastData').textContent = stats.latestDate ? fmtDate(stats.latestDate) : '—';

  // Best non-Consensus agent accuracy
  const agents = perf.filter(p => p.agent_name !== 'Consensus' && parseFloat(p.accuracy) > 0);
  if (agents.length) {
    agents.sort((a, b) => parseFloat(b.accuracy) - parseFloat(a.accuracy));
    const best = agents[0];
    document.getElementById('statWinRate').textContent  = parseFloat(best.accuracy).toFixed(1) + '%';
    document.getElementById('statWinAgent').textContent = best.agent_name.replace('_Agent', '').replace('_', ' ');
  }
}

// ── renderMovers ──────────────────────────────────────────────────────────────
function renderMovers(prices, stocks, consensus) {
  // Build consensus map: symbol → {prediction, confidence}
  const csMap = {};
  consensus.forEach(c => {
    csMap[c.symbol] = {
      prediction: c.final_signal || c.consensus_prediction || c.prediction,
      confidence: c.confidence,
    };
  });

  // Sort by change_pct
  const sorted = [...prices]
    .filter(p => p.change_pct !== null && p.change_pct !== undefined)
    .sort((a, b) => parseFloat(b.change_pct) - parseFloat(a.change_pct));

  const gainers = sorted.filter(p => parseFloat(p.change_pct) > 0).slice(0, 8);
  const losers  = sorted.filter(p => parseFloat(p.change_pct) < 0).reverse().slice(0, 8);

  fillMoversTable('gainersTable', gainers, csMap);
  fillMoversTable('losersTable',  losers,  csMap);
}

function fillMoversTable(tableId, rows, csMap) {
  const tbody = document.querySelector(`#${tableId} tbody`);
  if (!tbody) return;

  if (!rows.length) {
    tbody.innerHTML = '<tr><td colspan="5" style="color:#555;padding:12px 14px;">No data</td></tr>';
    return;
  }

  tbody.innerHTML = rows.map(p => {
    const sym    = p.symbol || '';
    const label  = sym.replace('.CA', '');
    const chg    = parseFloat(p.change_pct);
    const chgCls = chg > 0 ? 'green' : (chg < 0 ? 'red' : '');
    const cs     = csMap[sym] || {};
    const conf   = cs.confidence ? parseFloat(cs.confidence).toFixed(0) + '%' : '—';

    return `<tr>
      <td class="sym-cell">${escHtml(label)}</td>
      <td class="chg-cell">${escHtml(fmtClose(p.close))}</td>
      <td class="chg-cell ${chgCls}">${escHtml(fmtChg(p.change_pct))}</td>
      <td class="sig-cell">${signalBadge(cs.prediction)}</td>
      <td class="conf-cell">${escHtml(conf)}</td>
    </tr>`;
  }).join('');
}

// ── renderSectors ─────────────────────────────────────────────────────────────
function renderSectors(prices, stocks) {
  const grid = document.getElementById('sectorGrid');
  if (!grid) return;

  // Build symbol→sector map
  const sectorMap = {};
  stocks.forEach(s => { if (s.symbol && s.sector_en) sectorMap[s.symbol] = s.sector_en; });

  // Group prices by sector
  const sectorData = {};
  prices.forEach(p => {
    const sector = sectorMap[p.symbol];
    if (!sector) return;
    const chg = parseFloat(p.change_pct);
    if (isNaN(chg)) return;
    if (!sectorData[sector]) sectorData[sector] = { sum: 0, count: 0 };
    sectorData[sector].sum += chg;
    sectorData[sector].count++;
  });

  const sectors = Object.entries(sectorData)
    .map(([name, d]) => ({ name, avg: d.sum / d.count }))
    .sort((a, b) => b.avg - a.avg);

  if (!sectors.length) {
    grid.innerHTML = '<div style="color:#555;font-size:12px;padding:8px 0;">No sector data available</div>';
    return;
  }

  const maxAbs = Math.max(...sectors.map(s => Math.abs(s.avg)), 0.1);

  grid.innerHTML = sectors.map(s => {
    const pct     = (Math.abs(s.avg) / maxAbs * 100).toFixed(1);
    const colour  = s.avg >= 0 ? 'var(--pro-green)' : 'var(--pro-red)';
    const valCls  = s.avg >= 0 ? 'green' : 'red';
    const label   = s.name.length > 16 ? s.name.slice(0, 15) + '…' : s.name;

    return `<div class="pro-sector-row">
      <span class="pro-sector-name" title="${escHtml(s.name)}">${escHtml(label)}</span>
      <div class="pro-sector-track">
        <div class="pro-sector-fill" style="width:${pct}%;background:${colour}"></div>
      </div>
      <span class="pro-sector-val ${valCls}">${fmtChg(s.avg)}</span>
    </div>`;
  }).join('');
}

// ── Macro brief ───────────────────────────────────────────────────────────────
function simpleMarkdown(text) {
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/^## (.+)$/gm, '<h3>$1</h3>')
    .replace(/^# (.+)$/gm,  '<h3>$1</h3>')
    .replace(/^### (.+)$/gm,'<h3>$1</h3>')
    .replace(/\n{2,}/g, '</p><p>')
    .replace(/\n/g, '<br>');
}

async function loadMacroBrief() {
  const btn     = document.getElementById('macroBtn');
  const content = document.getElementById('macroContent');
  if (!btn || !content) return;

  btn.disabled  = true;
  btn.textContent = 'Loading…';
  content.innerHTML = '<div class="pro-macro-loading">Searching live macro data via Google…</div>';

  try {
    const res  = await fetch('/api/rag/macro', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    });
    const data = await res.json();

    if (data.error) throw new Error(data.error);

    const html = `<p>${simpleMarkdown(data.answer || '')}</p>`;

    let sourcesHtml = '';
    if (data.sources && data.sources.length) {
      const pills = data.sources.slice(0, 8).map(s => {
        const title = escHtml(s.title || s.url || 'Source');
        return s.url
          ? `<a class="pro-source-pill" href="${escHtml(s.url)}" target="_blank" rel="noopener">${title}</a>`
          : `<span class="pro-source-pill">${title}</span>`;
      }).join('');
      sourcesHtml = `<div class="pro-source-pills">${pills}</div>`;
    }

    content.innerHTML = html + sourcesHtml;
    btn.textContent = '↺ Refresh';
    btn.disabled = false;

  } catch (err) {
    content.innerHTML = `<div style="color:var(--pro-red)">Error: ${escHtml(err.message)}</div>`;
    btn.textContent = "📊 Load Today's Read";
    btn.disabled = false;
  }
}

// Auto-load on page open, then refresh every hour
loadMacroBrief();
setInterval(loadMacroBrief, 60 * 60 * 1000);

// ── Portfolio Performance ─────────────────────────────────────────────────────

let _portfolios = [];
let _portfolioChart = null;

// Check if user is logged in; if yes, load portfolios
(async function initPortfolios() {
  try {
    const me = await fetch('/api/auth/me', { credentials: 'include' });
    if (!me.ok) return; // not logged in — panel stays hidden

    const pfRes = await fetch('/api/portfolio-forecasts', { credentials: 'include' });
    if (!pfRes.ok) return;
    const data = await pfRes.json();
    _portfolios = data.portfolios || [];
    if (!_portfolios.length) return;

    // Show panel and populate selector
    const panel = document.getElementById('portfolioPanel');
    const sel   = document.getElementById('portfolioSelect');
    if (panel) panel.style.display = '';
    if (sel) {
      sel.innerHTML = _portfolios.map(p =>
        `<option value="${p.id}">${escHtml(p.name)} (${p.horizon_days}d)</option>`
      ).join('');
    }

    // Load first portfolio
    await loadPortfolioChart(_portfolios[0].id);
  } catch (_) { /* silent — unauthenticated or no portfolios */ }
})();

async function onPortfolioChange() {
  const sel = document.getElementById('portfolioSelect');
  if (sel) await loadPortfolioChart(parseInt(sel.value));
}

async function loadPortfolioChart(portfolioId) {
  try {
    const res  = await fetch(`/api/portfolio-forecasts/${portfolioId}/results`, { credentials: 'include' });
    const data = await res.json();
    if (!data.results || !data.results.length) return;

    renderPortfolioChart(data.portfolio, data.results, data.run_date);
  } catch (_) { /* silent */ }
}

function renderPortfolioChart(portfolio, results, runDate) {
  // Filter to rows with at least an expected return
  const rows = results.filter(r => r.expected_return_pct != null);
  if (!rows.length) return;

  const labels    = rows.map(r => r.symbol.replace('.CA', ''));
  const expected  = rows.map(r => parseFloat(r.expected_return_pct).toFixed(2));
  const actual    = rows.map(r => {
    // Use final actual if evaluated, otherwise daily actual so far
    const v = r.actual_return_pct != null ? r.actual_return_pct : r.daily_return_pct;
    return v != null ? parseFloat(v).toFixed(2) : null;
  });

  // Colour each actual bar green/red based on sign
  const actualColors = actual.map(v => v === null ? 'transparent' :
    parseFloat(v) >= 0 ? 'rgba(0,200,83,0.75)' : 'rgba(255,23,68,0.75)');

  // Render portfolio meta info
  const meta = document.getElementById('portfolioMeta');
  if (meta) {
    const rd     = runDate ? String(runDate).slice(0, 10) : '—';
    const target = results[0] ? String(results[0].target_date || '').slice(0, 10) : '—';
    const daysEl = results[0] ? results[0].days_elapsed : '—';
    const horiz  = portfolio.horizon_days || '—';
    const invest = portfolio.investment_amount
      ? 'EGP ' + parseInt(portfolio.investment_amount).toLocaleString()
      : '—';
    meta.innerHTML = `
      <span>Scenario: <strong>${escHtml(portfolio.scenario || 'base')}</strong></span>
      <span>Run: <strong>${rd}</strong></span>
      <span>Target: <strong>${target}</strong></span>
      <span>Progress: <strong>${daysEl} / ${horiz} days</strong></span>
      <span>Investment: <strong>${invest}</strong></span>
    `;
  }

  // Destroy previous chart instance if exists
  if (_portfolioChart) { _portfolioChart.destroy(); _portfolioChart = null; }

  const ctx = document.getElementById('portfolioChart');
  if (!ctx) return;

  // Dynamic height based on number of stocks
  ctx.style.height = Math.max(200, rows.length * 36) + 'px';

  _portfolioChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: 'Forecast %',
          data: expected,
          backgroundColor: 'rgba(102,126,234,0.6)',
          borderColor: 'rgba(102,126,234,1)',
          borderWidth: 1,
          borderRadius: 2,
        },
        {
          label: 'Actual so far %',
          data: actual,
          backgroundColor: actualColors,
          borderColor: actualColors.map(c => c.replace('0.75', '1')),
          borderWidth: 1,
          borderRadius: 2,
        },
      ],
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: ctx => {
              const v = ctx.parsed.x;
              return v === null ? ' No data' : ` ${ctx.dataset.label}: ${v >= 0 ? '+' : ''}${v}%`;
            },
          },
        },
      },
      scales: {
        x: {
          ticks: { color: '#555', font: { family: 'Courier New', size: 11 },
            callback: v => (v >= 0 ? '+' : '') + v + '%' },
          grid: { color: '#1e1e1e' },
          border: { color: '#2a2a2a' },
        },
        y: {
          ticks: { color: '#aaa', font: { family: 'Courier New', size: 12 } },
          grid: { display: false },
          border: { color: '#2a2a2a' },
        },
      },
    },
  });
}
