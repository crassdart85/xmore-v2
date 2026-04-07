/* ============================================================
   KSA Dashboard — Tadawul Intelligence
   ksa-dashboard.js
   ============================================================ */

'use strict';

/* ── Translations ────────────────────────────────────────────── */
const KSA_TRANSLATIONS = {
  en: {
    winRate:          'Win Rate',
    sharpeRatio:      'Sharpe (vs SAMA 4.25%)',
    profitFactor:     'Profit Factor',
    signalsToday:     'Signals Today',
    alpha30d:         '30D Alpha vs TASI',
    todaySignals:     "Today's Signals",
    ticker:           'Ticker',
    company:          'Company',
    signal:           'Signal',
    score:            'Score',
    risk:             'Risk',
    move:             'Expected Move',
    shariah:          'Shariah',
    dcfInsights:      'DCF Insights',
    intelFeed:        'Intelligence Feed',
    marketRegime:     'Market Regime',
    freshness:        'Data Freshness',
    viewTrackRecord:  'View Full Track Record →',
    disclaimer:       'Signals are for informational purposes only and do not constitute investment advice',
    headerSubtitle:   'Tadawul Market Intelligence',
    deepValue:        'Deep Value',
    speculative:      'Speculative Alerts',
    noSignals:        'No signals available yet.',
    loading:          'Loading...',
    buy:              'BUY',
    sell:             'SELL',
    hold:             'HOLD',
    riskLow:          'Low',
    riskMedium:       'Medium',
    riskHigh:         'High',
    shariahYes:       'Compliant',
    shariahUnknown:   'Pending',
    calm:             'Calm',
    turbulent:        'Turbulent',
    crisis:           'Crisis',
    errorLoad:        'Failed to load data.',
    pricesUpdated:    'Prices Updated',
    signalsUpdated:   'Signals Updated',
    dcfUpdated:       'DCF Updated',
    minutesAgo:       'min ago',
    hoursAgo:         'h ago',
    justNow:          'just now',
    top5DeepValue:    'Top Deep Value',
    topSpeculative:   'High Speculation Risk',
    margin:           'Margin',
    noData:           'No data available',
  },
  ar: {
    winRate:          'معدل الفوز',
    sharpeRatio:      'نسبة شارب (مقابل SAMA 4.25%)',
    profitFactor:     'عامل الربح',
    signalsToday:     'إشارات اليوم',
    alpha30d:         'ألفا 30 يوم مقابل TASI',
    todaySignals:     'إشارات اليوم',
    ticker:           'الرمز',
    company:          'الشركة',
    signal:           'الإشارة',
    score:            'النقاط',
    risk:             'المخاطرة',
    move:             'التحرك المتوقع',
    shariah:          'شريعة',
    dcfInsights:      'تحليل DCF',
    intelFeed:        'التغذية الاستخباراتية',
    marketRegime:     'نظام السوق',
    freshness:        'حداثة البيانات',
    viewTrackRecord:  'عرض سجل الأداء الكامل ←',
    disclaimer:       'الإشارات لأغراض إعلامية فقط ولا تشكل نصيحة استثمارية',
    headerSubtitle:   'تحليل سوق تداول',
    deepValue:        'قيمة عميقة',
    speculative:      'تنبيهات المضاربة',
    noSignals:        'لا توجد إشارات متاحة بعد.',
    loading:          'جارٍ التحميل...',
    buy:              'شراء',
    sell:             'بيع',
    hold:             'احتفاظ',
    riskLow:          'منخفض',
    riskMedium:       'متوسط',
    riskHigh:         'مرتفع',
    shariahYes:       'متوافق',
    shariahUnknown:   'قيد المراجعة',
    calm:             'هادئ',
    turbulent:        'متقلب',
    crisis:           'أزمة',
    errorLoad:        'فشل تحميل البيانات.',
    pricesUpdated:    'تحديث الأسعار',
    signalsUpdated:   'تحديث الإشارات',
    dcfUpdated:       'تحديث DCF',
    minutesAgo:       'دقيقة مضت',
    hoursAgo:         'ساعة مضت',
    justNow:          'الآن',
    top5DeepValue:    'أعلى قيمة عميقة',
    topSpeculative:   'مخاطر مضاربة عالية',
    margin:           'الهامش',
    noData:           'لا توجد بيانات',
  }
};

/* ── State ────────────────────────────────────────────────────── */
let currentLang = 'en';

/* ── Language Toggle ─────────────────────────────────────────── */
function toggleLang() {
  currentLang = currentLang === 'en' ? 'ar' : 'en';

  const html = document.documentElement;
  html.lang = currentLang;
  html.dir  = currentLang === 'ar' ? 'rtl' : 'ltr';

  const btn = document.getElementById('langToggle');
  if (btn) {
    btn.textContent = currentLang === 'ar' ? '🇬🇧 English' : '🇸🇦 عربي';
  }

  applyTranslations(currentLang);
}

/* ── Apply Translations ──────────────────────────────────────── */
function applyTranslations(lang) {
  const dict = KSA_TRANSLATIONS[lang] || KSA_TRANSLATIONS.en;

  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    if (dict[key] !== undefined) {
      el.textContent = dict[key];
    }
  });

  // Update page title
  document.title = lang === 'ar'
    ? 'Xmore KSA — تحليل سوق تداول'
    : 'Xmore KSA — Tadawul Intelligence';
}

/* ── Helpers ─────────────────────────────────────────────────── */
function t(key) {
  const dict = KSA_TRANSLATIONS[currentLang] || KSA_TRANSLATIONS.en;
  return dict[key] || key;
}

function escapeHtml(str) {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function formatRelativeTime(dateStr) {
  if (!dateStr) return t('noData');
  const date = new Date(dateStr);
  if (isNaN(date.getTime())) return '—';
  const diffMs  = Date.now() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1)   return t('justNow');
  if (diffMin < 60)  return `${diffMin} ${t('minutesAgo')}`;
  const diffH = Math.floor(diffMin / 60);
  return `${diffH} ${t('hoursAgo')}`;
}

/* Animate a numeric value with a simple counter */
function animateValue(el, from, to, decimals, suffix, duration) {
  if (!el) return;
  duration = duration || 800;
  const start = performance.now();
  function step(now) {
    const pct  = Math.min((now - start) / duration, 1);
    const ease = 1 - Math.pow(1 - pct, 3); // cubic ease out
    const val  = from + (to - from) * ease;
    el.textContent = val.toFixed(decimals) + (suffix || '');
    if (pct < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

function showError(containerId, msg) {
  const el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = `<div class="ksa-error" role="alert"><span>⚠</span><span>${escapeHtml(msg)}</span></div>`;
}

/* ── Load Stats ──────────────────────────────────────────────── */
async function loadStats() {
  const strip = document.querySelector('.ksa-stats-strip');
  try {
    const res  = await fetch('/api/ksa/performance/summary');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    /* Hide ribbon when backend has no evaluated signals */
    if (!data.available || data.total_signals < 5) {
      if (strip) strip.style.display = 'none';
      return;
    }

    /* Win Rate */
    const wr = parseFloat(data.win_rate || data.winRate || 0);
    const elWr = document.getElementById('valWinRate');
    if (elWr) {
      animateValue(elWr, 0, wr, 1, '%');
      elWr.classList.toggle('positive', wr >= 55);
      elWr.classList.toggle('negative', wr < 45);
    }

    /* Sharpe */
    const sh = parseFloat(data.sharpe || data.sharpe_ratio || 0);
    const elSh = document.getElementById('valSharpe');
    if (elSh) {
      animateValue(elSh, 0, sh, 2, '');
      elSh.classList.toggle('positive', sh >= 1.0);
      elSh.classList.toggle('negative', sh < 0.5);
    }

    /* Profit Factor */
    const pf = parseFloat(data.profit_factor || data.profitFactor || 0);
    const elPf = document.getElementById('valPF');
    if (elPf) {
      animateValue(elPf, 0, pf, 2, '');
      elPf.classList.toggle('positive', pf >= 1.5);
      elPf.classList.toggle('negative', pf < 1.0);
    }

    /* Signals Today */
    const sig = parseInt(data.signals_today || data.signalsToday || 0, 10);
    const elSig = document.getElementById('valSignals');
    if (elSig) {
      animateValue(elSig, 0, sig, 0, '');
      elSig.classList.add('gold');
    }

    /* Alpha */
    const alpha = parseFloat(data.alpha_30d || data.alpha30d || 0);
    const elAlpha = document.getElementById('valAlpha');
    if (elAlpha) {
      animateValue(elAlpha, 0, alpha, 2, '%');
      elAlpha.classList.toggle('positive', alpha > 0);
      elAlpha.classList.toggle('negative', alpha < 0);
    }

  } catch (err) {
    console.warn('[KSA] Stats load error:', err.message);
    /* Hide ribbon on error — better than showing misleading zeros */
    if (strip) strip.style.display = 'none';
  }
}

/* ── Load Regime ─────────────────────────────────────────────── */
async function loadRegime() {
  try {
    const res  = await fetch('/api/ksa/regime');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const regime    = (data.regime || 'calm').toLowerCase();
    const label     = t(regime) || regime;
    const probStr   = data.probability != null ? ` (${(data.probability * 100).toFixed(0)}%)` : '';

    /* Badge in header */
    const badge = document.getElementById('regimeBadge');
    if (badge) {
      const dot = document.createElement('span');
      dot.style.cssText = `
        display:inline-block;width:8px;height:8px;border-radius:50%;
        background:${regime === 'calm' ? 'var(--positive)' : regime === 'turbulent' ? 'var(--ksa-gold)' : 'var(--negative)'};
        margin-right:6px;
      `;
      badge.textContent = '';
      badge.appendChild(dot);
      badge.appendChild(document.createTextNode(label + probStr));
    }

    /* Regime card in side column */
    const regimeContent = document.getElementById('regimeContent');
    if (regimeContent) {
      const dotClass = regime === 'calm' ? 'calm' : regime === 'turbulent' ? 'turbulent' : 'crisis';
      const desc = data.description || (regime === 'calm'
        ? 'Low volatility, trend-following signals favoured'
        : regime === 'turbulent'
        ? 'Elevated volatility, reduce position sizes'
        : 'Crisis conditions, capital preservation mode');

      regimeContent.innerHTML = `
        <div class="ksa-regime-card">
          <div class="regime-dot-lg ${escapeHtml(dotClass)}" aria-hidden="true"></div>
          <div class="regime-info">
            <h4>${escapeHtml(label)}${escapeHtml(probStr)}</h4>
            <p>${escapeHtml(desc)}</p>
          </div>
        </div>
      `;
    }

  } catch (err) {
    console.warn('[KSA] Regime load error:', err.message);
    const badge = document.getElementById('regimeBadge');
    if (badge) badge.textContent = '—';
    const regimeContent = document.getElementById('regimeContent');
    if (regimeContent) showError('regimeContent', t('errorLoad'));
  }
}

/* ── Render Signal Pill ──────────────────────────────────────── */
function renderSignalPill(direction) {
  const d = (direction || 'HOLD').toUpperCase();
  let cls, label;
  if (d === 'UP' || d === 'BUY') {
    cls = 'up'; label = t('buy');
  } else if (d === 'DOWN' || d === 'SELL') {
    cls = 'down'; label = t('sell');
  } else {
    cls = 'hold'; label = t('hold');
  }
  return `<span class="signal-pill ${cls}">${escapeHtml(label)}</span>`;
}

/* ── Render Score Badge ──────────────────────────────────────── */
function renderScoreBadge(score) {
  const s = parseFloat(score);
  if (isNaN(s)) return '<span class="score-badge low">—</span>';
  const cls = s >= 70 ? 'high' : s >= 45 ? 'medium' : 'low';
  return `<span class="score-badge ${cls}">${Math.round(s)}</span>`;
}

/* ── Render Risk Label ───────────────────────────────────────── */
function renderRiskLabel(risk) {
  const r = (risk || '').toLowerCase();
  let cls, label;
  if (r === 'low')    { cls = 'low';    label = t('riskLow'); }
  else if (r === 'high') { cls = 'high'; label = t('riskHigh'); }
  else                { cls = 'medium'; label = t('riskMedium'); }
  return `<span class="risk-label ${cls}">${escapeHtml(label)}</span>`;
}

/* ── Render Shariah Badge ────────────────────────────────────── */
function renderShariahBadge(compliant) {
  if (compliant === true || compliant === 1 || compliant === 'true') {
    return `<span class="shariah-badge">☪ ${escapeHtml(t('shariahYes'))}</span>`;
  }
  if (compliant === null || compliant === undefined || compliant === '') {
    return `<span class="shariah-badge unknown">? ${escapeHtml(t('shariahUnknown'))}</span>`;
  }
  return '';
}

/* ── Load Signals ────────────────────────────────────────────── */
async function loadSignals() {
  try {
    const res  = await fetch('/api/ksa/signals/today');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const signals = Array.isArray(data) ? data : (data.signals || []);
    const tbody   = document.getElementById('signalTableBody');
    if (!tbody) return;

    if (signals.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="7">
            <div class="ksa-empty">
              <div class="ksa-empty-icon">📊</div>
              <p>${escapeHtml(t('noSignals'))}</p>
            </div>
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = signals.map(sig => {
      const ticker   = escapeHtml(sig.ticker || sig.symbol || '');
      const company  = escapeHtml(sig.company || sig.name_en || sig.name || '');
      const signal   = renderSignalPill(sig.signal || sig.direction);
      const score    = renderScoreBadge(sig.score || sig.confidence_score);
      const risk     = renderRiskLabel(sig.risk || sig.risk_level);
      const move     = escapeHtml(sig.expected_move || sig.move || '—');
      const shariah  = renderShariahBadge(sig.shariah_compliant ?? sig.shariah);

      return `
        <tr>
          <td class="td-ticker" data-label="${escapeHtml(t('ticker'))}">${ticker}</td>
          <td class="td-company" data-label="${escapeHtml(t('company'))}" title="${company}">${company}</td>
          <td data-label="${escapeHtml(t('signal'))}">${signal}</td>
          <td data-label="${escapeHtml(t('score'))}">${score}</td>
          <td data-label="${escapeHtml(t('risk'))}">${risk}</td>
          <td data-label="${escapeHtml(t('move'))}">${move}</td>
          <td data-label="${escapeHtml(t('shariah'))}">${shariah}</td>
        </tr>
      `;
    }).join('');

  } catch (err) {
    console.warn('[KSA] Signals load error:', err.message);
    const tbody = document.getElementById('signalTableBody');
    if (tbody) {
      tbody.innerHTML = `
        <tr>
          <td colspan="7">
            <div class="ksa-error" role="alert">
              <span>⚠</span><span>${escapeHtml(t('errorLoad'))}</span>
            </div>
          </td>
        </tr>
      `;
    }
  }
}

/* ── Valuation Label HTML ────────────────────────────────────── */
function renderValuationLabel(label) {
  const map = {
    'DEEP_VALUE':   'deep_value',
    'UNDERVALUED':  'undervalued',
    'FAIR_VALUE':   'fair_value',
    'OVERVALUED':   'overvalued',
    'SPECULATIVE':  'speculative',
  };
  const cls  = map[(label || '').toUpperCase()] || 'fair_value';
  const text = (label || '').replace(/_/g, ' ');
  return `<span class="valuation-label ${cls}">${escapeHtml(text)}</span>`;
}

/* ── Load DCF ────────────────────────────────────────────────── */
async function loadDcf() {
  try {
    const res  = await fetch('/api/ksa/dcf/summary');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const deepValue   = (data.deep_value   || []).slice(0, 5);
    const speculative = (data.speculative  || []).slice(0, 5);

    const dcfContent = document.getElementById('dcfContent');
    if (!dcfContent) return;

    if (deepValue.length === 0 && speculative.length === 0) {
      dcfContent.innerHTML = `<p class="text-muted" style="font-size:0.82rem;padding:8px 0;">${escapeHtml(t('noData'))}</p>`;
      return;
    }

    const renderList = (items) => items.map(item => {
      const sym    = escapeHtml(item.ticker || item.symbol || '');
      const margin = item.margin_of_safety != null
        ? `${parseFloat(item.margin_of_safety).toFixed(1)}%`
        : '—';
      const valLabel = renderValuationLabel(item.valuation_label || item.label);
      return `
        <div class="dcf-item">
          <span class="dcf-sym">${sym}</span>
          ${valLabel}
          <span class="dcf-margin">${escapeHtml(margin)}</span>
        </div>
      `;
    }).join('');

    dcfContent.innerHTML = `
      <div class="ksa-dcf-panel">
        <div class="dcf-column deep-value">
          <h4>${escapeHtml(t('top5DeepValue'))}</h4>
          ${deepValue.length ? renderList(deepValue) : `<p class="text-muted" style="font-size:0.78rem">${escapeHtml(t('noData'))}</p>`}
        </div>
        <div class="dcf-column speculative">
          <h4>${escapeHtml(t('topSpeculative'))}</h4>
          ${speculative.length ? renderList(speculative) : `<p class="text-muted" style="font-size:0.78rem">${escapeHtml(t('noData'))}</p>`}
        </div>
      </div>
    `;

  } catch (err) {
    console.warn('[KSA] DCF load error:', err.message);
    showError('dcfContent', t('errorLoad'));
  }
}

/* ── Urgency Dot Class ───────────────────────────────────────── */
function urgencyClass(signal) {
  const s = (signal || '').toUpperCase();
  if (s === 'UP' || s === 'BUY')    return 'green';
  if (s === 'DOWN' || s === 'SELL') return 'red';
  return 'amber';
}

/* ── Load Intelligence Feed ──────────────────────────────────── */
async function loadIntel() {
  try {
    const res  = await fetch('/api/ksa/signals/latest?limit=10');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const items = Array.isArray(data) ? data : (data.signals || data.items || []);
    const intelContent = document.getElementById('intelContent');
    if (!intelContent) return;

    if (items.length === 0) {
      intelContent.innerHTML = `<p class="text-muted" style="font-size:0.82rem;padding:8px 0;">${escapeHtml(t('noData'))}</p>`;
      return;
    }

    intelContent.innerHTML = `
      <div class="ksa-intel-feed" role="list">
        ${items.map(item => {
          const ticker = escapeHtml(item.ticker || item.symbol || '');
          const text   = escapeHtml(item.summary || item.signal_text || item.description || `${t(item.signal)} signal`);
          const time   = formatRelativeTime(item.created_at || item.signal_time || item.date);
          const dotCls = urgencyClass(item.signal || item.direction);

          return `
            <div class="intel-item" role="listitem">
              <div class="urgency-dot ${dotCls}" aria-hidden="true"></div>
              <div class="intel-body">
                <div class="intel-ticker">${ticker}</div>
                <div class="intel-text">${text}</div>
              </div>
              <div class="intel-time">${time}</div>
            </div>
          `;
        }).join('')}
      </div>
    `;

  } catch (err) {
    console.warn('[KSA] Intel load error:', err.message);
    showError('intelContent', t('errorLoad'));
  }
}

/* ── Load Freshness ──────────────────────────────────────────── */
async function loadFreshness() {
  try {
    const res  = await fetch('/api/ksa/freshness');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const freshnessContent = document.getElementById('freshnessContent');
    if (!freshnessContent) return;

    const items = [
      { label: t('pricesUpdated'),  value: formatRelativeTime(data.prices_updated  || data.pricesUpdated),  cls: getFreshClass(data.prices_updated  || data.pricesUpdated) },
      { label: t('signalsUpdated'), value: formatRelativeTime(data.signals_updated || data.signalsUpdated), cls: getFreshClass(data.signals_updated || data.signalsUpdated) },
      { label: t('dcfUpdated'),     value: formatRelativeTime(data.dcf_updated     || data.dcfUpdated),     cls: getFreshClass(data.dcf_updated     || data.dcfUpdated) },
    ];

    freshnessContent.innerHTML = items.map(item => `
      <div class="freshness-row">
        <span class="freshness-label">${escapeHtml(item.label)}</span>
        <span class="freshness-value ${item.cls}">${escapeHtml(item.value)}</span>
      </div>
    `).join('');

  } catch (err) {
    console.warn('[KSA] Freshness load error:', err.message);
    /* Non-critical — hide panel gracefully */
    const el = document.getElementById('freshnessPanel');
    if (el) el.style.display = 'none';
  }
}

function getFreshClass(dateStr) {
  if (!dateStr) return 'old';
  const diffMin = (Date.now() - new Date(dateStr).getTime()) / 60000;
  if (diffMin < 30)  return 'fresh';
  if (diffMin < 180) return 'stale';
  return 'old';
}

/* ── Load Ticker Tape ────────────────────────────────────────── */
async function loadTickerTape() {
  try {
    const res  = await fetch('/api/ksa/ticker');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const items  = Array.isArray(data) ? data : (data.tickers || []);
    const inner  = document.getElementById('tickerInner');
    if (!inner || items.length === 0) return;

    // Double the list for seamless infinite scroll
    const html = [...items, ...items].map(item => {
      const sym    = escapeHtml(item.ticker || item.symbol || '');
      const change = parseFloat(item.change_pct || item.pct_change || 0);
      const arrow  = change >= 0 ? '▲' : '▼';
      const cls    = change >= 0 ? 'ticker-up' : 'ticker-down';
      const price  = item.price != null ? parseFloat(item.price).toFixed(2) : '—';
      return `
        <span class="ksa-ticker-item">
          <span class="ticker-sym">${sym}</span>
          <span class="${cls}">${arrow} ${Math.abs(change).toFixed(2)}%</span>
          <span>${price}</span>
        </span>
        <span style="color:var(--text-muted);margin:0 4px">|</span>
      `;
    }).join('');

    inner.innerHTML = html;

  } catch (err) {
    console.warn('[KSA] Ticker load error:', err.message);
    /* Ticker tape is cosmetic — hide quietly */
    const tape = document.querySelector('.ksa-ticker-tape');
    if (tape) tape.style.display = 'none';
  }
}

/* ── Init ────────────────────────────────────────────────────── */
async function init() {
  // Restore language from localStorage if set
  const savedLang = localStorage.getItem('ksaLang') || 'en';
  if (savedLang !== currentLang) {
    currentLang = savedLang;
    const html = document.documentElement;
    html.lang = currentLang;
    html.dir  = currentLang === 'ar' ? 'rtl' : 'ltr';
    const btn = document.getElementById('langToggle');
    if (btn) btn.textContent = currentLang === 'ar' ? '🇬🇧 English' : '🇸🇦 عربي';
  }

  applyTranslations(currentLang);

  // Persist lang choice
  const origToggle = window.toggleLang;
  window.toggleLang = function () {
    origToggle && origToggle();
    localStorage.setItem('ksaLang', currentLang);
  };

  // Run all loaders in parallel — non-fatal individually
  await Promise.allSettled([
    loadStats(),
    loadRegime(),
    loadSignals(),
    loadDcf(),
    loadIntel(),
    loadFreshness(),
    loadTickerTape(),
  ]);
}

document.addEventListener('DOMContentLoaded', init);
