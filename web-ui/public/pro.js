/* ─── Xmore Pro — Market Overview ────────────────────────────────────────── */

// ── Bilingual i18n ────────────────────────────────────────────────────────────
let _PRO_LANG = localStorage.getItem('lang') || 'en';

const _PRO_I18N = {
  en: {
    back: '← Dashboard', signIn: 'Sign In', signOut: 'Sign Out',
    modalTitle: 'Sign in to Xmore', login: 'Login', signUp: 'Sign Up',
    email: 'Email', password: 'Password',
    tracked: 'TRACKED', upToday: 'UP', downToday: 'DOWN',
    bestWinRate: 'BEST AGENT WIN RATE', lastData: 'LAST DATA', marketRegime: 'Market Regime',
    egx30Title: 'TASI — Intraday', egxBlueChips: 'Tadawul Leaders',
    topGainers: 'Top Gainers', topLosers: 'Top Losers',
    colSymbol: 'Symbol', colClose: 'Close', colChg: 'Chg%',
    colSignal: 'Signal', colConf: 'Conf',
    colForecast: 'Forecast', colActual: 'Actual', colGap: 'Gap',
    colProgress: 'Progress', colTarget: 'Target Date',
    sectorPerf: 'Sector Performance',
    myPortfolio: 'My Forecast Portfolio',
    pfLoginTitle: 'Track Your Forecast Performance',
    pfLoginDesc: 'Sign in to see how your system-generated stock portfolios are performing in real time — forecast vs actual return per stock, progress to target date, and agent signals.',
    signInArrow: 'Sign In ↗',
    pfEmptyTitle: 'No Forecast Portfolios Yet',
    pfEmptyDesc: 'Create a forecast portfolio on the main dashboard to start tracking forecast accuracy against live Saudi market price movements.',
    createPortfolio: 'Create Portfolio ↗',
    legendForecast: 'Forecast', legendActualPos: 'Actual (positive)', legendActualNeg: 'Actual (negative)',
    derivTitle: 'Derivatives Brief', derivBtn: 'Price ▶', pricing: 'Pricing…',
    macroTitle: 'Macro Brief', macroRefresh: '↺ Refresh',
    backtestTitle: 'Walk-Forward Backtest Results', backtestNote: 'Updated weekly · ML agent only',
    colScore: 'Score', btSymbol: 'Symbol', btAcc: 'Accuracy', btDir: 'Directional', btPnl: 'Signal P&L', btRows: 'Rows',
    loading: 'Loading…',
    etfSignalsTitle: 'ETF & ETP Signals',
  },
  ar: {
    back: '← الرئيسية', signIn: 'دخول', signOut: 'خروج',
    modalTitle: 'تسجيل الدخول إلى Xmore', login: 'دخول', signUp: 'تسجيل',
    email: 'البريد الإلكتروني', password: 'كلمة المرور',
    tracked: 'متتبع', upToday: 'صاعد', downToday: 'هابط',
    bestWinRate: 'أفضل معدل نجاح', lastData: 'آخر بيانات', marketRegime: 'نظام السوق',
    egx30Title: 'تاسي — خلال اليوم', egxBlueChips: 'قادة تداول',
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
    pfEmptyDesc: 'أنشئ محفظة توقعات من اللوحة الرئيسية لبدء تتبع دقة الذكاء الاصطناعي مقارنةً بتحركات السوق السعودي.',
    createPortfolio: 'إنشاء محفظة ↗',
    legendForecast: 'التوقع', legendActualPos: 'الفعلي (موجب)', legendActualNeg: 'الفعلي (سالب)',
    derivTitle: 'موجز المشتقات', derivBtn: 'تسعير ▶', pricing: 'جارٍ التسعير…',
    macroTitle: 'موجز الاقتصاد الكلي', macroRefresh: '↺ تحديث',
    backtestTitle: 'نتائج الاختبار الزمني', backtestNote: 'تحديث أسبوعي · نموذج ML فقط',
    colScore: 'نقاط', btSymbol: 'الرمز', btAcc: 'الدقة', btDir: 'الاتجاه', btPnl: 'ر/خ الإشارة', btRows: 'الصفوف',
    loading: 'جارٍ التحميل…',
    etfSignalsTitle: 'إشارات الصناديق',
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
  localStorage.setItem('lang', _PRO_LANG);
  proApplyLang();
}

proApplyLang();

// ── Theme toggle ──────────────────────────────────────────────────────────────
let _PRO_THEME = localStorage.getItem('theme') || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
function _proApplyTheme() {
  document.documentElement.setAttribute('data-theme', _PRO_THEME);
  const btn = document.getElementById('themeBtn');
  if (btn) btn.title = _PRO_THEME === 'dark' ? 'Switch to light mode' : 'Switch to dark mode';
}
function proToggleTheme() {
  _PRO_THEME = _PRO_THEME === 'light' ? 'dark' : 'light';
  localStorage.setItem('theme', _PRO_THEME);
  _proApplyTheme();
}
_proApplyTheme();

function displaySymbol(symbol) {
  return String(symbol || '').replace(/\.(CA|SR)$/i, '');
}

function isSaudiSymbol(symbol) {
  return /\.SR$/i.test(symbol || '') || /^(TASI|MT30)(\.SR)?$/i.test(symbol || '');
}

// ── Mobile Menu (640px and below) ────────────────────────────────────────────
function initProMobileMenu() {
  const menuBtn = document.getElementById('proMobileMenuBtn');
  const menuDropdown = document.getElementById('proMobileMenuDropdown');
  if (!menuBtn || !menuDropdown) return;

  const menuItems = document.querySelectorAll('#proMobileMenuDropdown .mobile-menu-item');

  menuBtn.addEventListener('click', function(e) {
    e.stopPropagation();
    menuDropdown.classList.toggle('active');
    menuBtn.classList.toggle('active');
    menuBtn.setAttribute('aria-expanded', menuDropdown.classList.contains('active') ? 'true' : 'false');
    menuDropdown.setAttribute('aria-hidden', menuDropdown.classList.contains('active') ? 'false' : 'true');
  });

  menuItems.forEach(function(item) {
    item.addEventListener('click', function() {
      menuDropdown.classList.remove('active');
      menuBtn.classList.remove('active');
      menuBtn.setAttribute('aria-expanded', 'false');
      menuDropdown.setAttribute('aria-hidden', 'true');
    });
  });

  document.addEventListener('click', function(e) {
    if (menuDropdown.classList.contains('active') && !menuBtn.contains(e.target) && !menuDropdown.contains(e.target)) {
      menuDropdown.classList.remove('active');
      menuBtn.classList.remove('active');
      menuBtn.setAttribute('aria-expanded', 'false');
      menuDropdown.setAttribute('aria-hidden', 'true');
    }
  });

  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape' && menuDropdown.classList.contains('active')) {
      menuDropdown.classList.remove('active');
      menuBtn.classList.remove('active');
      menuBtn.setAttribute('aria-expanded', 'false');
      menuDropdown.setAttribute('aria-hidden', 'true');
    }
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initProMobileMenu);
} else {
  initProMobileMenu();
}

// ── FX rates ──────────────────────────────────────────────────────────────────
async function loadFxRates() {
  const strip = document.getElementById('proFxStrip');
  if (!strip) return;
  try {
    const res  = await fetch('/api/fx-rates');
    const data = await res.json();
    if (!data || data.error) throw new Error(data.error || 'no data');

    const allItems = [
      { label: 'USD/SAR', val: data.USD_SAR?.toFixed(4) || '—' },
      ...(data.XAU_USD ? [{ label: 'Gold/Oz', val: data.XAU_USD?.toFixed(2) + ' USD' }] : []),
    ];
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
      { proName: 'TADAWUL:TASI', title: 'TASI' },
      { proName: 'TADAWUL:2222', title: 'Aramco' },
      { proName: 'TADAWUL:2010', title: 'SABIC' },
      { proName: 'TADAWUL:1120', title: 'Al Rajhi' },
      { proName: 'TADAWUL:7010', title: 'stc' },
      { proName: 'TADAWUL:1150', title: 'Alinma' },
      { proName: 'TADAWUL:1180', title: 'SNB' },
      { proName: 'TADAWUL:1211', title: 'Maaden' },
      { proName: 'TADAWUL:2082', title: 'ACWA' },
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

// ── TASI Intraday Chart ──────────────────────────────────────────────────────
(function loadTASIChart() {
  const container = document.getElementById('tasiChartWidget');
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
    symbol: 'TADAWUL:TASI',
    interval: '5',
    timezone: 'Asia/Riyadh',
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

// ── Tadawul Market Overview ──────────────────────────────────────────────────
(function loadKSAIndices() {
  const container = document.getElementById('ksaIndicesWidget');
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
        title: 'Tadawul Leaders',
        symbols: [
          { s: 'TADAWUL:2222', d: 'Saudi Aramco' },
          { s: 'TADAWUL:2010', d: 'SABIC' },
          { s: 'TADAWUL:1120', d: 'Al Rajhi' },
          { s: 'TADAWUL:7010', d: 'stc' },
          { s: 'TADAWUL:1150', d: 'Alinma' },
          { s: 'TADAWUL:1180', d: 'SNB' },
          { s: 'TADAWUL:1211', d: 'Maaden' },
          { s: 'TADAWUL:2082', d: 'ACWA Power' },
        ],
        originalTitle: 'Tadawul Leaders',
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
  fetch('/api/etf/signals').then(r => r.json()).catch(() => []),
]).then(([prices, stocksData, consensus, stats, perf, etfSignals]) => {
  const stocks = (Array.isArray(stocksData) ? stocksData : (stocksData.stocks || [])).filter(s => isSaudiSymbol(s.symbol));
  const pricesArr = (Array.isArray(prices) ? prices : []).filter(p => isSaudiSymbol(p.symbol));
  const consensusArr = (Array.isArray(consensus) ? consensus : []).filter(c => isSaudiSymbol(c.symbol));
  const perfArr = Array.isArray(perf) ? perf : [];
  const saudiEtfSignals = (Array.isArray(etfSignals) ? etfSignals : (etfSignals.latest || [])).filter(s => isSaudiSymbol(s.symbol));

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
  renderEtfSignals(saudiEtfSignals);
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
    const winAgentEl = document.getElementById('statWinAgent');
    if (winAgentEl) {
        winAgentEl.textContent = best.agent_name.replace('_Agent', '').replace('_', ' ');
    }
  }

  // Regime pill — fetch asynchronously
  fetch('/api/track-record/regime-stats').then(r => r.ok ? r.json() : null).then(data => {
    const el = document.getElementById('statRegime');
    if (!el || !data?.regimes?.length) return;
    const top = data.regimes.sort((a, b) => (b.total_signals || 0) - (a.total_signals || 0))[0];
    const regime = top?.regime || '—';
    el.textContent = regime;
    el.className = 'pro-stat-val regime-val ' + (regime === 'Calm' ? 'green' : regime === 'Crisis' ? 'red' : 'amber');
  }).catch(() => {});
}

// ── renderMovers ──────────────────────────────────────────────────────────────
function renderMovers(prices, stocks, consensus) {
  // Build consensus map: symbol → {prediction, confidence, xmore_score}
  const csMap = {};
  consensus.forEach(c => {
    csMap[c.symbol] = {
      prediction:    c.final_signal || c.consensus_prediction || c.prediction,
      confidence:    c.confidence,
      xmore_score:   c.xmore_score,
      signal_label:  c.signal_label || null,
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
    tbody.innerHTML = '<tr><td colspan="6" style="color:#999;padding:12px 14px;">No data</td></tr>';
    return;
  }

  tbody.innerHTML = rows.map(p => {
    const sym    = p.symbol || '';
    const label  = displaySymbol(sym);
    const chg    = parseFloat(p.change_pct);
    const chgCls = chg > 0 ? 'green' : (chg < 0 ? 'red' : '');
    const cs     = csMap[sym] || {};
    const conf   = cs.confidence ? parseFloat(cs.confidence).toFixed(0) + '%' : '—';
    const score  = cs.xmore_score != null ? parseFloat(cs.xmore_score).toFixed(0) : '—';
    const scoreCls = cs.xmore_score >= 70 ? 'green' : cs.xmore_score >= 45 ? '' : 'red';
    const lblHtml = cs.signal_label ? `<span class="pro-signal-label">${escHtml(cs.signal_label)}</span>` : '';

    return `<tr>
      <td class="sym-cell">${escHtml(label)}</td>
      <td class="chg-cell">${escHtml(fmtClose(p.close))}</td>
      <td class="chg-cell ${chgCls}">${escHtml(fmtChg(p.change_pct))}</td>
      <td class="sig-cell">${signalBadge(cs.prediction)}${lblHtml}</td>
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

// ── ETF Signals ───────────────────────────────────────────────────────────────
function renderEtfSignals(signals) {
  const el = document.getElementById('proEtfSignals');
  if (!el) return;
  if (!signals || signals.length === 0) {
    el.innerHTML = '<p class="pro-empty">No ETF signals yet — signals generate daily.</p>';
    return;
  }
  const rows = signals.map(s => {
    const cls   = s.signal === 'UP' ? 'sig-up' : s.signal === 'DOWN' ? 'sig-down' : 'sig-hold';
    const arrow = s.signal === 'UP' ? '↑' : s.signal === 'DOWN' ? '↓' : '—';
    const conf  = s.confidence ? (parseFloat(s.confidence) * 100).toFixed(0) + '%' : '—';
    const prem  = s.nav_premium_pct != null
      ? `<span class="pro-etf-prem ${parseFloat(s.nav_premium_pct) < 0 ? 'disc' : 'prem'}">${parseFloat(s.nav_premium_pct) >= 0 ? '+' : ''}${parseFloat(s.nav_premium_pct).toFixed(1)}%</span>`
      : '';
    const rsi   = s.rsi_value != null ? `RSI ${parseFloat(s.rsi_value).toFixed(0)}` : '';
    return `<div class="pro-etf-card">
      <div class="pro-etf-top">
        <span class="pro-etf-sym">${s.symbol || ''}</span>
        <span class="pro-etf-signal ${cls}">${arrow} ${s.signal}</span>
      </div>
      <div class="pro-etf-name">${s.name || s.type || ''}</div>
      <div class="pro-etf-meta">
        <span class="pro-etf-conf">Conf: ${conf}</span>
        ${rsi ? `<span class="pro-etf-rsi">${rsi}</span>` : ''}
        ${prem}
      </div>
    </div>`;
  }).join('');
  el.innerHTML = rows;
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
    btn.textContent = '↺ Refresh';
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
          <td class="sym-cell">${escHtml(displaySymbol(r.symbol))}</td>
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
  const ticker   = document.getElementById('derivTicker').value.trim() || '2222.SR';
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
      { label: 'Call Price',   value: fmt2(m.call_price),  unit: 'SAR' },
      { label: 'Put Price',    value: fmt2(m.put_price),   unit: 'SAR' },
      { label: 'Straddle',     value: fmt2(m.straddle),    unit: 'SAR' },
      { label: 'Delta',        value: fmt3(m.delta),       unit: '\u0394' },
      { label: 'Gamma',        value: fmt4(m.gamma),       unit: '\u0393' },
      { label: 'Theta / day',  value: fmt2(m.theta),       unit: 'SAR' },
      { label: 'Vega / 1%',    value: fmt2(m.vega),        unit: 'SAR' },
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
let _proModalPrevFocus = null;

function _proFocusTrap(e) {
  const modal = document.getElementById('proAuthModal');
  if (!modal || modal.style.display === 'none') return;
  const focusable = Array.from(modal.querySelectorAll(
    'button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])'
  ));
  if (!focusable.length) return;
  const first = focusable[0], last = focusable[focusable.length - 1];
  if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
  else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
}

function showProModal() {
  _proModalPrevFocus = document.activeElement;
  _proAuthMode = 'login';
  proSwitchTab('login');
  document.getElementById('proAuthEmail').value = '';
  document.getElementById('proAuthPassword').value = '';
  document.getElementById('proAuthError').style.display = 'none';
  document.getElementById('proAuthModal').style.display = 'flex';
  document.addEventListener('keydown', _proFocusTrap);
  setTimeout(() => document.getElementById('proAuthEmail').focus(), 50);
}

function hideProModal() {
  document.getElementById('proAuthModal').style.display = 'none';
  document.removeEventListener('keydown', _proFocusTrap);
  if (_proModalPrevFocus && _proModalPrevFocus.focus) _proModalPrevFocus.focus();
  _proModalPrevFocus = null;
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
        <span class="pro-stat-val">${invest ? 'SAR ' + invest.toLocaleString() : '—'}</span>
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
      const scoreStr = knownCount > 0 ? ` ${aheadCount} of ${knownCount} positions with data are meeting or beating their individual portfolio targets.` : '';
      perfSentence = `Across ${n} positions, the portfolio is averaging <span class="${actCls}"><strong>${fmtChg(avgActual)}</strong></span> actual return against an forecast of <span class="amber"><strong>${fmtChg(avgForecast)}</strong></span> — <strong>${gapAmt}pp ${aboveBelow} forecast</strong>.${scoreStr}`;
    } else {
      perfSentence = `Market price data is not yet available for this portfolio — actual vs. forecast comparison will appear once trading data is recorded.`;
    }

    narEl.innerHTML = `<strong>${name}</strong> is a <strong>${scenario}</strong>-scenario portfolio of <strong>${n} Saudi stocks</strong> on a <strong>${horiz}-trading-day</strong> horizon, targeting <strong>${targetDate}</strong>. The forecast is <strong>${phase}</strong> — ${daysElapsed} of ${horiz} trading days elapsed (${progressPct}%). ${perfSentence}`;
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
  const labels       = rows.map(r => displaySymbol(r.symbol));
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
    const label    = displaySymbol(sym);
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

