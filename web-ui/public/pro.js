/* ─── Xmore Pro — Market Overview ────────────────────────────────────────── */

// ── Bilingual i18n ────────────────────────────────────────────────────────────
let _PRO_LANG = 'en';

const _PRO_I18N = {
  en: {
    back: '← Dashboard', signIn: 'Sign In', signOut: 'Sign Out',
    modalTitle: 'Sign in to Xmore', login: 'Login', signUp: 'Sign Up',
    email: 'Email', password: 'Password',
    tracked: 'TRACKED', upToday: 'UP TODAY', downToday: 'DOWN TODAY',
    bestWinRate: 'BEST AGENT WIN RATE', lastData: 'LAST DATA',
    egx30Title: 'EGX 30 — Intraday', egxBlueChips: 'EGX Blue Chips',
    topGainers: 'Top Gainers', topLosers: 'Top Losers',
    colSymbol: 'Symbol', colClose: 'Close', colChg: 'Chg%',
    colSignal: 'Signal', colConf: 'Conf',
    colForecast: 'Forecast', colActual: 'Actual', colGap: 'Gap',
    colProgress: 'Progress', colTarget: 'Target Date',
    sectorPerf: 'Sector Performance',
    myPortfolio: 'My Forecast Portfolio',
    pfLoginTitle: 'Track Your Forecast Performance',
    pfLoginDesc: 'Sign in to see how your AI-generated stock portfolios are performing in real time — forecast vs actual return per stock, progress to target date, and agent signals.',
    signInArrow: 'Sign In ↗',
    pfEmptyTitle: 'No Forecast Portfolios Yet',
    pfEmptyDesc: 'Create a forecast portfolio on the main dashboard to start tracking AI prediction accuracy against live EGX price movements.',
    createPortfolio: 'Create Portfolio ↗',
    legendForecast: 'Forecast', legendActualPos: 'Actual (positive)', legendActualNeg: 'Actual (negative)',
    derivTitle: 'Derivatives Brief', derivBtn: 'Price ▶', pricing: 'Pricing…',
    macroTitle: 'Macro Brief', macroRefresh: '↺ Refresh',
    backtestTitle: 'Walk-Forward Backtest Results', backtestNote: 'Updated weekly · ML agent only',
    colScore: 'Score', btSymbol: 'Symbol', btAcc: 'Accuracy', btDir: 'Directional', btPnl: 'Signal P&L', btRows: 'Rows',
    loading: 'Loading…',
  },
  ar: {
    back: '← الرئيسية', signIn: 'دخول', signOut: 'خروج',
    modalTitle: 'تسجيل الدخول إلى Xmore', login: 'دخول', signUp: 'تسجيل',
    email: 'البريد الإلكتروني', password: 'كلمة المرور',
    tracked: 'متتبع', upToday: 'صاعد اليوم', downToday: 'هابط اليوم',
    bestWinRate: 'أفضل معدل نجاح', lastData: 'آخر بيانات',
    egx30Title: 'EGX 30 — خلال اليوم', egxBlueChips: 'أسهم EGX الكبرى',
    topGainers: 'أعلى الرابحين', topLosers: 'أعلى الخاسرين',
    colSymbol: 'الرمز', colClose: 'الإغلاق', colChg: 'التغير%',
    colSignal: 'الإشارة', colConf: 'الثقة',
    colForecast: 'التوقع', colActual: 'الفعلي', colGap: 'الفجوة',
    colProgress: 'التقدم', colTarget: 'التاريخ المستهدف',
    sectorPerf: 'أداء القطاعات',
    myPortfolio: 'محفظة التوقعات',
    pfLoginTitle: 'تابع أداء توقعاتك',
    pfLoginDesc: 'سجّل دخولك لمتابعة أداء محافظ الأسهم المولّدة بالذكاء الاصطناعي — المقارنة بين التوقع والعائد الفعلي لكل سهم.',
    signInArrow: 'تسجيل الدخول ↗',
    pfEmptyTitle: 'لا توجد محافظ بعد',
    pfEmptyDesc: 'أنشئ محفظة توقعات من اللوحة الرئيسية لبدء تتبع دقة الذكاء الاصطناعي مقارنةً بتحركات سوق البورصة.',
    createPortfolio: 'إنشاء محفظة ↗',
    legendForecast: 'التوقع', legendActualPos: 'الفعلي (موجب)', legendActualNeg: 'الفعلي (سالب)',
    derivTitle: 'موجز المشتقات', derivBtn: 'تسعير ▶', pricing: 'جارٍ التسعير…',
    macroTitle: 'موجز الاقتصاد الكلي', macroRefresh: '↺ تحديث',
    backtestTitle: 'نتائج الاختبار الزمني', backtestNote: 'تحديث أسبوعي · نموذج ML فقط',
    colScore: 'نقاط', btSymbol: 'الرمز', btAcc: 'الدقة', btDir: 'الاتجاه', btPnl: 'ر/خ الإشارة', btRows: 'الصفوف',
    loading: 'جارٍ التحميل…',
  },
};

function proApplyLang() {
  const dict = _PRO_I18N[_PRO_LANG];
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    if (dict[key] !== undefined) el.textContent = dict[key];
  });
  // RTL / LTR
  document.documentElement.setAttribute('lang', _PRO_LANG);
  document.documentElement.setAttribute('dir', _PRO_LANG === 'ar' ? 'rtl' : 'ltr');
  // Toggle button label
  const btn = document.getElementById('proLangBtn');
  if (btn) btn.textContent = _PRO_LANG === 'ar' ? 'EN' : 'عر';
}

function proToggleLang() {
  _PRO_LANG = _PRO_LANG === 'en' ? 'ar' : 'en';
  proApplyLang();
}

// ── FX rates ──────────────────────────────────────────────────────────────────
async function loadFxRates() {
  const strip = document.getElementById('proFxStrip');
  if (!strip) return;
  try {
    const res  = await fetch('/api/fx-rates');
    const data = await res.json();
    if (!data || data.error) throw new Error(data.error || 'no data');

    const fxItems = [
      { label: 'USD/EGP', val: data.USD_EGP?.toFixed(2)  ?? '—' },
      { label: 'USD/SAR', val: data.USD_SAR?.toFixed(4)  ?? '—' },
      { label: 'SAR/EGP', val: data.SAR_EGP?.toFixed(4)  ?? '—' },
    ];
    const goldItems = data.GOLD_24K_EGP_G ? [
      { label: '🥇 24K/g',   val: data.GOLD_24K_EGP_G?.toFixed(0) + ' EGP' },
      { label: '21K/g',      val: data.GOLD_21K_EGP_G?.toFixed(0) + ' EGP' },
      { label: '18K/g',      val: data.GOLD_18K_EGP_G?.toFixed(0) + ' EGP' },
      { label: 'جنيه ذهب',  val: data.GOLD_POUND_EGP?.toFixed(0)  + ' EGP' },
    ] : [];

    const allItems = [...fxItems, ...goldItems];
    strip.innerHTML = allItems.map((item, i) =>
      `${i > 0 ? '<span class="pro-fx-sep">·</span>' : ''}
       <div class="pro-fx-item">
         <span class="pro-fx-pair">${item.label}</span>
         <span class="pro-fx-val">${item.val}</span>
       </div>`
    ).join('');
  } catch (_) {
    strip.innerHTML = '<span class="pro-fx-loading">FX unavailable</span>';
  }
}

loadFxRates();
setInterval(loadFxRates, 60 * 60 * 1000);  // refresh hourly

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

// ── Shared state (available to portfolio renderer) ────────────────────────────
let _csMap = {};  // symbol → {prediction, confidence}

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

  // Populate shared consensus map for portfolio renderer
  consensusArr.forEach(c => {
    _csMap[c.symbol] = {
      prediction:  c.final_signal || c.consensus_prediction || c.prediction,
      confidence:  c.confidence,
      xmore_score: c.xmore_score,
    };
  });

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
  // Build consensus map: symbol → {prediction, confidence, xmore_score}
  const csMap = {};
  consensus.forEach(c => {
    csMap[c.symbol] = {
      prediction:  c.final_signal || c.consensus_prediction || c.prediction,
      confidence:  c.confidence,
      xmore_score: c.xmore_score,
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
    tbody.innerHTML = '<tr><td colspan="6" style="color:#555;padding:12px 14px;">No data</td></tr>';
    return;
  }

  tbody.innerHTML = rows.map(p => {
    const sym    = p.symbol || '';
    const label  = sym.replace('.CA', '');
    const chg    = parseFloat(p.change_pct);
    const chgCls = chg > 0 ? 'green' : (chg < 0 ? 'red' : '');
    const cs     = csMap[sym] || {};
    const conf   = cs.confidence ? parseFloat(cs.confidence).toFixed(0) + '%' : '—';
    const score  = cs.xmore_score != null ? parseFloat(cs.xmore_score).toFixed(0) : '—';
    const scoreCls = cs.xmore_score >= 70 ? 'green' : cs.xmore_score >= 45 ? '' : 'red';

    return `<tr>
      <td class="sym-cell">${escHtml(label)}</td>
      <td class="chg-cell">${escHtml(fmtClose(p.close))}</td>
      <td class="chg-cell ${chgCls}">${escHtml(fmtChg(p.change_pct))}</td>
      <td class="sig-cell">${signalBadge(cs.prediction)}</td>
      <td class="conf-cell">${escHtml(conf)}</td>
      <td class="score-cell ${scoreCls}" title="Xmore Score">${escHtml(score)}</td>
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

// ── Backtest Results ─────────────────────────────────────────────────
async function loadBacktestResults() {
  const body = document.getElementById('backtestBody');
  if (!body) return;
  try {
    const res  = await fetch('/api/backtest/results');
    const data = await res.json();
    if (!data || !data.length) {
      body.innerHTML = '<p style="color:#555;font-size:12px;padding:8px 0;">No backtest data yet — runs weekly on Sunday.</p>';
      return;
    }
    const t = k => (_PRO_I18N[_PRO_LANG] || _PRO_I18N.en)[k] || k;
    const rows = data
      .sort((a, b) => (b.directional_accuracy || 0) - (a.directional_accuracy || 0))
      .slice(0, 30)
      .map(r => {
        const dir    = r.directional_accuracy != null ? (r.directional_accuracy * 100).toFixed(1) + '%' : '—';
        const acc    = r.accuracy            != null ? (r.accuracy * 100).toFixed(1) + '%' : '—';
        const pnl    = r.signal_pnl_pct      != null ? (r.signal_pnl_pct >= 0 ? '+' : '') + r.signal_pnl_pct.toFixed(1) + '%' : '—';
        const pnlCls = r.signal_pnl_pct >= 0 ? 'green' : 'red';
        const dirCls = (r.directional_accuracy || 0) >= 0.55 ? 'green' : (r.directional_accuracy || 0) >= 0.45 ? '' : 'red';
        return `<tr>
          <td class="sym-cell">${escHtml(r.symbol.replace('.CA',''))}</td>
          <td>${escHtml(acc)}</td>
          <td class="${dirCls}">${escHtml(dir)}</td>
          <td class="${pnlCls}">${escHtml(pnl)}</td>
          <td style="color:#555">${r.n_rows || '—'}</td>
        </tr>`;
      }).join('');
    body.innerHTML = `
      <table class="pro-table pro-backtest-table">
        <thead><tr>
          <th>${t('btSymbol')}</th>
          <th>${t('btAcc')}</th>
          <th>${t('btDir')}</th>
          <th>${t('btPnl')}</th>
          <th>${t('btRows')}</th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>`;
  } catch (e) {
    body.innerHTML = '<p style="color:#555;font-size:12px;">Backtest data unavailable.</p>';
  }
}
loadBacktestResults();

// ── Derivatives Brief ────────────────────────────────────────────────
async function loadDerivativesBrief() {
  const ticker   = document.getElementById('derivTicker').value.trim() || 'COMI.CA';
  const spotEl   = document.getElementById('derivSpot');
  const strikeEl = document.getElementById('derivStrike');
  const T        = parseFloat(document.getElementById('derivExpiry').value);

  // Auto-fill spot from live prices if empty
  let S = parseFloat(spotEl.value);
  let K = parseFloat(strikeEl.value);

  if (!S || isNaN(S)) {
    // Try to get from live stats
    try {
      const r = await fetch('/api/stocks');
      const stocks = await r.json();
      const match = stocks.find(s => s.ticker === ticker || s.symbol === ticker);
      if (match && match.close_price) {
        S = parseFloat(match.close_price);
        spotEl.value = S.toFixed(2);
      }
    } catch (_) {}
    if (!S || isNaN(S)) S = 10.0;
  }
  if (!K || isNaN(K)) {
    K = S;  // ATM by default
    strikeEl.value = S.toFixed(2);
  }

  const loading  = document.getElementById('derivLoading');
  const narEl    = document.getElementById('derivNarrative');
  const metrEl   = document.getElementById('derivMetrics');

  loading.style.display = '';
  narEl.innerHTML = '';
  metrEl.innerHTML = '';

  try {
    const params = new URLSearchParams({ S, K, T, r: 0.085, sigma: 0.25, option_type: 'call' });
    const res = await fetch(`/api/derivatives/brief/${encodeURIComponent(ticker)}?${params}`);

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      narEl.innerHTML = `<span class="deriv-error">Pricing service unavailable \u2014 ${err.error || res.status}</span>`;
      return;
    }

    const data = await res.json();
    narEl.innerHTML = `<p class="deriv-narrative-text">${data.narrative}</p>`;

    const m = data.metrics || {};
    const cards = [
      { label: 'Call Price',   value: fmt2(m.call_price),  unit: 'EGP' },
      { label: 'Put Price',    value: fmt2(m.put_price),   unit: 'EGP' },
      { label: 'Straddle',     value: fmt2(m.straddle),    unit: 'EGP' },
      { label: 'Delta',        value: fmt3(m.delta),       unit: '\u0394' },
      { label: 'Gamma',        value: fmt4(m.gamma),       unit: '\u0393' },
      { label: 'Theta / day',  value: fmt2(m.theta),       unit: 'EGP' },
      { label: 'Vega / 1%',    value: fmt2(m.vega),        unit: 'EGP' },
      { label: 'IV used',      value: pct1(m.sigma_used),  unit: '' },
    ];

    metrEl.innerHTML = cards.map(c => `
      <div class="deriv-metric-card">
        <div class="deriv-metric-label">${c.label}</div>
        <div class="deriv-metric-value">${c.value} <span class="deriv-metric-unit">${c.unit}</span></div>
      </div>`).join('');

  } catch (err) {
    narEl.innerHTML = `<span class="deriv-error">Error: ${err.message}</span>`;
  } finally {
    loading.style.display = 'none';
  }
}

function fmt2(v) { return v != null && !isNaN(v) ? Number(v).toFixed(2) : '\u2014'; }
function fmt3(v) { return v != null && !isNaN(v) ? Number(v).toFixed(3) : '\u2014'; }
function fmt4(v) { return v != null && !isNaN(v) ? Number(v).toFixed(4) : '\u2014'; }
function pct1(v) { return v != null && !isNaN(v) ? (Number(v)*100).toFixed(1)+'%' : '\u2014'; }

// Auto-load derivatives brief on page open
loadDerivativesBrief();

// ── Portfolio Forecast Performance ───────────────────────────────────────────

let _portfolios    = [];
let _portfolioChart = null;

function pfShowState(id) {
  ['pfStateLogin', 'pfStateEmpty', 'pfStateData'].forEach(s => {
    const el = document.getElementById(s);
    if (el) el.style.display = s === id ? '' : 'none';
  });
}

async function initPortfolios() {
  try {
    const me = await fetch('/api/auth/me', { credentials: 'include' });
    if (!me.ok) { pfShowState('pfStateLogin'); return; }

    const pfRes = await fetch('/api/portfolio-forecasts', { credentials: 'include' });
    if (!pfRes.ok) { pfShowState('pfStateLogin'); return; }
    const data = await pfRes.json();
    _portfolios = data.portfolios || [];

    if (!_portfolios.length) { pfShowState('pfStateEmpty'); return; }

    // Populate selector
    const sel = document.getElementById('portfolioSelect');
    if (sel) {
      sel.style.display = '';
      sel.innerHTML = _portfolios.map(p =>
        `<option value="${p.id}">${escHtml(p.name)} · ${p.horizon_days}d · ${escHtml(p.scenario || 'base')}</option>`
      ).join('');
    }

    await loadPortfolioChart(_portfolios[0].id);
  } catch (_) { pfShowState('pfStateLogin'); }
}

// ── Auth ─────────────────────────────────────────────────────────────────────

let _proAuthMode = 'login';

function showProModal() {
  _proAuthMode = 'login';
  proSwitchTab('login');
  document.getElementById('proAuthEmail').value = '';
  document.getElementById('proAuthPassword').value = '';
  document.getElementById('proAuthError').style.display = 'none';
  document.getElementById('proAuthModal').style.display = 'flex';
  document.getElementById('proAuthEmail').focus();
}

function hideProModal() {
  document.getElementById('proAuthModal').style.display = 'none';
}

function proSwitchTab(mode) {
  _proAuthMode = mode;
  document.getElementById('proTabLogin').classList.toggle('active', mode === 'login');
  document.getElementById('proTabSignup').classList.toggle('active', mode === 'signup');
  document.getElementById('proAuthSubmit').textContent = mode === 'login' ? 'Login' : 'Sign Up';
  document.getElementById('proAuthPassword').setAttribute('autocomplete',
    mode === 'login' ? 'current-password' : 'new-password');
  document.getElementById('proAuthError').style.display = 'none';
}

async function proHandleSubmit(e) {
  e.preventDefault();
  const email    = document.getElementById('proAuthEmail').value.trim();
  const password = document.getElementById('proAuthPassword').value;
  const errEl    = document.getElementById('proAuthError');
  const submitBtn = document.getElementById('proAuthSubmit');

  errEl.style.display = 'none';
  submitBtn.disabled = true;

  try {
    const endpoint = _proAuthMode === 'login' ? '/api/auth/login' : '/api/auth/signup';
    const res  = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json();

    if (res.ok && data.success) {
      hideProModal();
      proSetLoggedIn(data.user);
      initPortfolios();
    } else {
      const msg = data.error || 'Something went wrong. Please try again.';
      errEl.textContent = res.status === 429 ? 'Too many attempts. Try again later.' : msg;
      errEl.style.display = 'block';
    }
  } catch (_) {
    errEl.textContent = 'Network error. Please try again.';
    errEl.style.display = 'block';
  } finally {
    submitBtn.disabled = false;
  }
}

function proSetLoggedIn(user) {
  const userEl   = document.getElementById('proAuthUser');
  const loginBtn = document.getElementById('proLoginBtn');
  const logoutBtn = document.getElementById('proLogoutBtn');
  if (userEl)    { userEl.textContent = user.email; userEl.style.display = ''; }
  if (loginBtn)  { loginBtn.style.display = 'none'; }
  if (logoutBtn) { logoutBtn.style.display = ''; }
}

function proSetLoggedOut() {
  const userEl   = document.getElementById('proAuthUser');
  const loginBtn = document.getElementById('proLoginBtn');
  const logoutBtn = document.getElementById('proLogoutBtn');
  if (userEl)    { userEl.style.display = 'none'; }
  if (loginBtn)  { loginBtn.style.display = ''; }
  if (logoutBtn) { logoutBtn.style.display = 'none'; }
  pfShowState('pfStateLogin');
  const sel = document.getElementById('portfolioSelect');
  if (sel) sel.style.display = 'none';
}

async function proHandleLogout() {
  try {
    await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' });
  } catch (_) { /* silent */ }
  proSetLoggedOut();
}

async function proCheckAuth() {
  try {
    const res = await fetch('/api/auth/me', { credentials: 'include' });
    if (res.ok) {
      const data = await res.json();
      proSetLoggedIn(data.user);
    } else {
      proSetLoggedOut();
    }
  } catch (_) {
    proSetLoggedOut();
  }
  initPortfolios();
}

// Keyboard: Escape closes modal
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') hideProModal();
});

proCheckAuth();

async function onPortfolioChange() {
  const sel = document.getElementById('portfolioSelect');
  if (sel) await loadPortfolioChart(parseInt(sel.value));
}

async function loadPortfolioChart(portfolioId) {
  try {
    const res  = await fetch(`/api/portfolio-forecasts/${portfolioId}/results`, { credentials: 'include' });
    const data = await res.json();
    if (!data.results || !data.results.length) { pfShowState('pfStateEmpty'); return; }
    renderPortfolioChart(data.portfolio, data.results);
  } catch (_) { /* silent */ }
}

function renderPortfolioChart(portfolio, results) {
  const rows = results.filter(r => r.expected_return_pct != null);
  if (!rows.length) return;

  pfShowState('pfStateData');

  const horiz  = portfolio.horizon_days || 1;
  const invest = portfolio.investment_amount ? parseInt(portfolio.investment_amount) : null;

  // Compute per-row actual values
  const actualVals = rows.map(r => {
    const v = r.actual_return_pct != null ? r.actual_return_pct : r.daily_return_pct;
    return v != null ? parseFloat(v) : null;
  });

  // ── KPI strip ──────────────────────────────────────────────────────────────
  const avgForecast = rows.reduce((s, r) => s + parseFloat(r.expected_return_pct), 0) / rows.length;
  const actualKnown = actualVals.filter(v => v !== null);
  const avgActual   = actualKnown.length ? actualKnown.reduce((s, v) => s + v, 0) / actualKnown.length : null;
  const daysElapsed = rows[0] ? (rows[0].days_elapsed || 0) : 0;
  const progressPct = Math.min(Math.round(daysElapsed / horiz * 100), 100);
  const targetDate  = rows[0] ? String(rows[0].target_date || '').slice(0, 10) : '—';

  const kpiEl = document.getElementById('portfolioKPI');
  if (kpiEl) {
    const fmtKpi = v => (v >= 0 ? '+' : '') + v.toFixed(1) + '%';
    const actualCls = avgActual === null ? '' : (avgActual >= 0 ? 'green' : 'red');
    kpiEl.innerHTML = `
      <div class="pro-pf-kpi">
        <span class="pro-stat-label">Avg Forecast</span>
        <span class="pro-stat-val amber">${fmtKpi(avgForecast)}</span>
      </div>
      <div class="pro-pf-kpi">
        <span class="pro-stat-label">Avg Actual So Far</span>
        <span class="pro-stat-val ${actualCls}">${avgActual !== null ? fmtKpi(avgActual) : '—'}</span>
      </div>
      <div class="pro-pf-kpi">
        <span class="pro-stat-label">Portfolio Progress</span>
        <span class="pro-stat-val">${daysElapsed} <span style="font-size:13px;color:#555">/ ${horiz}d</span></span>
        <div class="pro-pf-prog-track"><div class="pro-pf-prog-fill" style="width:${progressPct}%"></div></div>
        <span class="pro-stat-sub">${progressPct}% to target · ${targetDate}</span>
      </div>
      <div class="pro-pf-kpi">
        <span class="pro-stat-label">Investment</span>
        <span class="pro-stat-val">${invest ? 'EGP ' + invest.toLocaleString() : '—'}</span>
        <span class="pro-stat-sub">${escHtml(portfolio.scenario || 'base')} scenario · ${rows.length} stocks</span>
      </div>
    `;
  }

  // ── Business narrative ─────────────────────────────────────────────────────
  const narEl = document.getElementById('portfolioNarrative');
  if (narEl) {
    const name     = escHtml(portfolio.name || 'Portfolio');
    const scenario = escHtml(portfolio.scenario || 'base');
    const n        = rows.length;

    let phase;
    if (progressPct === 0)        phase = 'just initiated';
    else if (progressPct < 25)    phase = 'in its early stages';
    else if (progressPct < 50)    phase = 'approaching the halfway mark';
    else if (progressPct < 75)    phase = 'past the halfway point';
    else if (progressPct < 100)   phase = 'in the final stretch';
    else                          phase = 'at its target date';

    let perfSentence;
    if (avgActual !== null) {
      const gap      = avgActual - avgForecast;
      const aboveBelow = gap >= 0 ? 'ahead of' : 'below';
      const gapAmt   = Math.abs(gap).toFixed(1);
      const actCls   = avgActual >= 0 ? 'green' : 'red';
      const aheadCount = rows.filter((r, i) => actualVals[i] !== null && actualVals[i] >= parseFloat(r.expected_return_pct)).length;
      const knownCount = rows.filter((r, i) => actualVals[i] !== null).length;
      const scoreStr = knownCount > 0 ? ` ${aheadCount} of ${knownCount} positions with data are meeting or beating their individual AI targets.` : '';
      perfSentence = `Across ${n} positions, the portfolio is averaging <span class="${actCls}"><strong>${fmtChg(avgActual)}</strong></span> actual return against an AI forecast of <span class="amber"><strong>${fmtChg(avgForecast)}</strong></span> — <strong>${gapAmt}pp ${aboveBelow} forecast</strong>.${scoreStr}`;
    } else {
      perfSentence = `Market price data is not yet available for this portfolio — actual vs. forecast comparison will appear once trading data is recorded.`;
    }

    narEl.innerHTML = `<strong>${name}</strong> is a <strong>${scenario}</strong>-scenario portfolio of <strong>${n} EGX stocks</strong> on a <strong>${horiz}-trading-day</strong> horizon, targeting <strong>${targetDate}</strong>. The forecast is <strong>${phase}</strong> — ${daysElapsed} of ${horiz} trading days elapsed (${progressPct}%). ${perfSentence}`;
  }

  // ── Meta row ───────────────────────────────────────────────────────────────
  const meta = document.getElementById('portfolioMeta');
  if (meta) {
    const runDate = rows[0] ? String(rows[0].run_date || '').slice(0, 10) : '—';
    meta.innerHTML = `
      <span>Run: <strong>${runDate}</strong></span>
      <span>Horizon: <strong>${horiz}d</strong></span>
      <span>Target: <strong>${targetDate}</strong></span>
    `;
  }

  // ── Chart ──────────────────────────────────────────────────────────────────
  const labels       = rows.map(r => r.symbol.replace('.CA', ''));
  const expected     = rows.map(r => parseFloat(r.expected_return_pct).toFixed(2));
  const actualColors = actualVals.map(v => v === null ? 'transparent' :
    v >= 0 ? 'rgba(0,200,83,0.75)' : 'rgba(255,23,68,0.75)');

  if (_portfolioChart) { _portfolioChart.destroy(); _portfolioChart = null; }
  const ctx = document.getElementById('portfolioChart');
  if (ctx) {
    ctx.style.height = Math.max(180, rows.length * 32) + 'px';
    _portfolioChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels,
        datasets: [
          { label: 'Forecast %', data: expected,
            backgroundColor: 'rgba(102,126,234,0.55)', borderColor: 'rgba(102,126,234,1)',
            borderWidth: 1, borderRadius: 2 },
          { label: 'Actual %', data: actualVals.map(v => v !== null ? v.toFixed(2) : null),
            backgroundColor: actualColors,
            borderColor: actualColors.map(c => c.replace('0.75', '1')),
            borderWidth: 1, borderRadius: 2 },
        ],
      },
      options: {
        indexAxis: 'y', responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: c => {
            const v = c.parsed.x;
            return v === null ? ' No data' : ` ${c.dataset.label}: ${v >= 0 ? '+' : ''}${v}%`;
          }}},
        },
        scales: {
          x: { ticks: { color: '#555', font: { family: 'Courier New', size: 11 },
              callback: v => (v >= 0 ? '+' : '') + v + '%' },
            grid: { color: '#1e1e1e' }, border: { color: '#2a2a2a' } },
          y: { ticks: { color: '#aaa', font: { family: 'Courier New', size: 12 } },
            grid: { display: false }, border: { color: '#2a2a2a' } },
        },
      },
    });
  }

  // ── Detail table ───────────────────────────────────────────────────────────
  const tbody = document.querySelector('#portfolioDetailTable tbody');
  if (!tbody) return;

  tbody.innerHTML = rows.map((r, i) => {
    const sym      = r.symbol || '';
    const label    = sym.replace('.CA', '');
    const forecast = parseFloat(r.expected_return_pct);
    const actVal   = actualVals[i];
    const gap      = actVal !== null ? (actVal - forecast) : null;
    const gapCls   = gap === null ? '' : (gap >= 0 ? 'green' : 'red');
    const actCls   = actVal === null ? '' : (actVal >= 0 ? 'green' : 'red');
    const cs       = _csMap[sym] || {};
    const rowDays  = r.days_elapsed || 0;
    const rowPct   = Math.min(Math.round(rowDays / horiz * 100), 100);
    const tgt      = String(r.target_date || '').slice(0, 10);

    return `<tr>
      <td class="sym-cell">${escHtml(label)}</td>
      <td class="sig-cell">${signalBadge(cs.prediction)}</td>
      <td class="chg-cell amber">${fmtChg(forecast)}</td>
      <td class="chg-cell ${actCls}">${actVal !== null ? fmtChg(actVal) : '—'}</td>
      <td class="chg-cell ${gapCls}">${gap !== null ? fmtChg(gap) : '—'}</td>
      <td style="min-width:110px">
        <div style="display:flex;align-items:center;gap:6px">
          <div class="pro-pf-prog-track" style="flex:1">
            <div class="pro-pf-prog-fill" style="width:${rowPct}%"></div>
          </div>
          <span style="font-size:10px;color:#555;font-family:'Courier New',monospace;white-space:nowrap">${rowPct}%</span>
        </div>
      </td>
      <td class="conf-cell">${escHtml(tgt || '—')}</td>
    </tr>`;
  }).join('');
}
