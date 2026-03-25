/* ============================================================
   KSA Track Record — Tadawul Intelligence
   ksa-track-record.js
   ============================================================ */

'use strict';

/* ── Translations ────────────────────────────────────────────── */
const TR_TRANSLATIONS = {
  en: {
    winRate:              'Win Rate',
    sharpeRatio:          'Sharpe (vs SAMA 4.25%)',
    maxDrawdown:          'Max Drawdown',
    totalSignals:         'Total Signals',
    alpha30d:             '30D Alpha vs TASI',
    profitFactor:         'Profit Factor',
    trackRecordTitle:     'Track Record — Tadawul Signals',
    trackRecordSubtitle:  'All predictions logged before market open. Results verified at close. Risk-free rate: SAMA repo 4.25%. Benchmark: TASI. Currency: SAR.',
    equityCurve:          'Equity Curve',
    xmoreSignals:         'Xmore Signals',
    tasiIndex:            'TASI (Benchmark)',
    rfRateNote:           'Risk-free rate: SAMA repo 4.25% annualised',
    predictionLog:        'Prediction Log',
    exportCsv:            'Export CSV',
    date:                 'Date',
    ticker:               'Ticker',
    signal:               'Signal',
    result:               'Result',
    alpha:                'Alpha',
    dcfLabel:             'DCF Label',
    shariah:              'Shariah',
    agentBreakdown:       'Agent Breakdown',
    agent:                'Agent',
    avgReturn:            'Avg Return',
    sectorBreakdown:      'Sector Breakdown',
    regimePerformance:    'Regime-Aware Performance',
    backToDashboard:      '← Back to Dashboard',
    disclaimer:           'Signals are for informational purposes only and do not constitute investment advice',
    headerSubtitle:       'Tadawul Track Record',
    backLink:             '← Dashboard',
    peakToTrough:         'Peak-to-trough',
    sinceInception:       'Since inception',
    rollingBenchmark:     'Rolling vs benchmark',
    grossProfitOverLoss:  'Gross profit / gross loss',
    sharpeBad:            'Weak — below acceptable threshold',
    sharpeAvg:            'Average — acceptable risk-adjusted return',
    sharpeGood:           'Strong — good risk-adjusted performance',
    sharpeExcept:         'Exceptional — top-tier performance',
    sharpeWeak:           'Weak',
    sharpeAverage:        'Average',
    sharpeStrong:         'Strong',
    sharpeExceptional:    'Exceptional',
    noData:               'No data available',
    errorLoad:            'Failed to load data.',
    loading:              'Loading...',
    buy:                  'BUY',
    sell:                 'SELL',
    hold:                 'HOLD',
    correct:              'Correct',
    incorrect:            'Incorrect',
    partial:              'Partial',
    pending:              'Pending',
    shariahYes:           'Compliant',
    shariahUnknown:       'Pending',
    calm:                 'Calm',
    turbulent:            'Turbulent',
    crisis:               'Crisis',
    prevPage:             '‹',
    nextPage:             '›',
    of:                   'of',
    page:                 'Page',
    sinceInceptionNote:   'Track record since inception of KSA coverage',
  },
  ar: {
    winRate:              'معدل الفوز',
    sharpeRatio:          'نسبة شارب (مقابل SAMA 4.25%)',
    maxDrawdown:          'أقصى تراجع',
    totalSignals:         'إجمالي الإشارات',
    alpha30d:             'ألفا 30 يوم مقابل TASI',
    profitFactor:         'عامل الربح',
    trackRecordTitle:     'سجل الأداء — إشارات تداول',
    trackRecordSubtitle:  'جميع التوقعات مسجلة قبل افتتاح السوق. النتائج موثقة عند الإغلاق. معدل الفائدة: مستودع ساما 4.25%. المعيار: TASI. العملة: ريال.',
    equityCurve:          'منحنى حقوق الملكية',
    xmoreSignals:         'إشارات Xmore',
    tasiIndex:            'مؤشر TASI (المعيار)',
    rfRateNote:           'معدل الفائدة: مستودع ساما 4.25% سنوياً',
    predictionLog:        'سجل التوقعات',
    exportCsv:            'تصدير CSV',
    date:                 'التاريخ',
    ticker:               'الرمز',
    signal:               'الإشارة',
    result:               'النتيجة',
    alpha:                'ألفا',
    dcfLabel:             'تصنيف DCF',
    shariah:              'شريعة',
    agentBreakdown:       'تفاصيل الوكلاء',
    agent:                'الوكيل',
    avgReturn:            'متوسط العائد',
    sectorBreakdown:      'توزيع القطاعات',
    regimePerformance:    'الأداء حسب النظام',
    backToDashboard:      '← العودة للوحة التحكم',
    disclaimer:           'الإشارات لأغراض إعلامية فقط ولا تشكل نصيحة استثمارية',
    headerSubtitle:       'سجل أداء تداول',
    backLink:             '← لوحة التحكم',
    peakToTrough:         'من القمة إلى القاع',
    sinceInception:       'منذ البداية',
    rollingBenchmark:     'متحرك مقابل المعيار',
    grossProfitOverLoss:  'إجمالي الربح / إجمالي الخسارة',
    sharpeBad:            'ضعيف — دون الحد المقبول',
    sharpeAvg:            'متوسط — عائد معدل بالمخاطر مقبول',
    sharpeGood:           'قوي — أداء جيد معدل بالمخاطر',
    sharpeExcept:         'استثنائي — أداء من الدرجة الأولى',
    sharpeWeak:           'ضعيف',
    sharpeAverage:        'متوسط',
    sharpeStrong:         'قوي',
    sharpeExceptional:    'استثنائي',
    noData:               'لا توجد بيانات',
    errorLoad:            'فشل تحميل البيانات.',
    loading:              'جارٍ التحميل...',
    buy:                  'شراء',
    sell:                 'بيع',
    hold:                 'احتفاظ',
    correct:              'صحيح',
    incorrect:            'خاطئ',
    partial:              'جزئي',
    pending:              'قيد الانتظار',
    shariahYes:           'متوافق',
    shariahUnknown:       'قيد المراجعة',
    calm:                 'هادئ',
    turbulent:            'متقلب',
    crisis:               'أزمة',
    prevPage:             '›',
    nextPage:             '‹',
    of:                   'من',
    page:                 'صفحة',
    sinceInceptionNote:   'سجل الأداء منذ بداية تغطية KSA',
  }
};

/* ── State ────────────────────────────────────────────────────── */
let currentLang  = 'en';
let logPage      = 1;
const LOG_PER_PAGE = 20;
let allLogRows   = [];

/* ── Helpers ─────────────────────────────────────────────────── */
function t(key) {
  const dict = TR_TRANSLATIONS[currentLang] || TR_TRANSLATIONS.en;
  return dict[key] !== undefined ? dict[key] : key;
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

function formatDate(dateStr) {
  if (!dateStr) return '—';
  const d = new Date(String(dateStr).replace('T', ' ').split('.')[0]);
  if (isNaN(d.getTime())) return String(dateStr).slice(0, 10);
  return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
}

function animateValue(el, from, to, decimals, suffix, duration) {
  if (!el) return;
  duration = duration || 900;
  const start = performance.now();
  function step(now) {
    const pct  = Math.min((now - start) / duration, 1);
    const ease = 1 - Math.pow(1 - pct, 3);
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

/* ── Language Toggle ─────────────────────────────────────────── */
function trToggleLang() {
  currentLang = currentLang === 'en' ? 'ar' : 'en';

  const html = document.documentElement;
  html.lang = currentLang;
  html.dir  = currentLang === 'ar' ? 'rtl' : 'ltr';

  const btn = document.getElementById('langToggle');
  if (btn) btn.textContent = currentLang === 'ar' ? '🇬🇧 English' : '🇸🇦 عربي';

  localStorage.setItem('ksaLang', currentLang);
  applyTranslations(currentLang);

  // Re-render pagination with updated lang
  renderLogPage(logPage);
}
window.trToggleLang = trToggleLang;

function applyTranslations(lang) {
  const dict = TR_TRANSLATIONS[lang] || TR_TRANSLATIONS.en;
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    if (dict[key] !== undefined) el.textContent = dict[key];
  });
  document.title = lang === 'ar'
    ? 'Xmore KSA — سجل الأداء'
    : 'Xmore KSA — Track Record';
}

/* ── Signal Pill ─────────────────────────────────────────────── */
function renderSignalPill(direction) {
  const d = (direction || 'HOLD').toUpperCase();
  let cls, label;
  if      (d === 'UP'   || d === 'BUY')  { cls = 'up';   label = t('buy');  }
  else if (d === 'DOWN' || d === 'SELL') { cls = 'down'; label = t('sell'); }
  else                                   { cls = 'hold'; label = t('hold'); }
  return `<span class="signal-pill ${cls}">${escapeHtml(label)}</span>`;
}

/* ── Result Cell ─────────────────────────────────────────────── */
function renderResult(outcome) {
  const o = (outcome || '').toLowerCase();
  if (o === 'correct' || o === 'win')    return `<span class="text-positive" style="font-weight:700">&#10003; ${escapeHtml(t('correct'))}</span>`;
  if (o === 'incorrect' || o === 'loss') return `<span class="text-negative" style="font-weight:700">&#10007; ${escapeHtml(t('incorrect'))}</span>`;
  if (o === 'partial')                   return `<span class="text-gold" style="font-weight:700">~ ${escapeHtml(t('partial'))}</span>`;
  return `<span class="text-muted">${escapeHtml(t('pending'))}</span>`;
}

/* ── Shariah Badge ───────────────────────────────────────────── */
function renderShariahBadge(compliant) {
  if (compliant === true || compliant === 1 || compliant === 'true') {
    return `<span class="shariah-badge">&#9770; ${escapeHtml(t('shariahYes'))}</span>`;
  }
  if (compliant === null || compliant === undefined || compliant === '') {
    return `<span class="shariah-badge unknown">? ${escapeHtml(t('shariahUnknown'))}</span>`;
  }
  return '';
}

/* ── Valuation Label ─────────────────────────────────────────── */
function renderValuationLabel(label) {
  const map = {
    'DEEP_VALUE':  'deep_value',
    'UNDERVALUED': 'undervalued',
    'FAIR_VALUE':  'fair_value',
    'OVERVALUED':  'overvalued',
    'SPECULATIVE': 'speculative',
  };
  const cls  = map[(label || '').toUpperCase()] || 'fair_value';
  const text = (label || '—').replace(/_/g, ' ');
  return `<span class="valuation-label ${cls}">${escapeHtml(text)}</span>`;
}

/* ── Alpha Cell ──────────────────────────────────────────────── */
function renderAlpha(alpha) {
  if (alpha == null || alpha === '') return '<span class="text-muted">—</span>';
  const v = parseFloat(alpha);
  if (isNaN(v)) return '<span class="text-muted">—</span>';
  const cls  = v > 0 ? 'text-positive' : v < 0 ? 'text-negative' : 'text-muted';
  const sign = v > 0 ? '+' : '';
  return `<span class="${cls}" style="font-weight:600">${sign}${v.toFixed(2)}%</span>`;
}

/* ── Sharpe Rating ───────────────────────────────────────────── */
function getSharpeRating(sharpe) {
  const s = parseFloat(sharpe);
  if (isNaN(s)) return null;
  if (s > 2.0)  return { cls: 'exceptional', icon: '&#128309;', label: t('sharpeExceptional'), desc: t('sharpeExcept') };
  if (s >= 1.0) return { cls: 'strong',      icon: '&#128994;', label: t('sharpeStrong'),      desc: t('sharpeGood') };
  if (s >= 0.5) return { cls: 'average',     icon: '&#128993;', label: t('sharpeAverage'),     desc: t('sharpeAvg') };
  return            { cls: 'weak',        icon: '&#128308;', label: t('sharpeWeak'),        desc: t('sharpeBad') };
}

/* ── Load KPIs ───────────────────────────────────────────────── */
async function loadKpis() {
  try {
    // Prefer server-side preloaded data when available
    let data = window.KSA_PRELOAD && Object.keys(window.KSA_PRELOAD).length > 0
      ? window.KSA_PRELOAD
      : null;

    if (!data) {
      const res = await fetch('/api/ksa/track-record/summary');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      data = await res.json();
    }

    /* Win Rate */
    const wr = parseFloat(data.win_rate || data.winRate || 0);
    const elWr = document.getElementById('trValWinRate');
    if (elWr) {
      elWr.innerHTML = '';
      animateValue(elWr, 0, wr, 1, '%');
      if (wr >= 55) elWr.style.color = 'var(--positive)';
      else if (wr < 45) elWr.style.color = 'var(--negative)';
    }

    /* Sharpe */
    const sh = parseFloat(data.sharpe || data.sharpe_ratio || 0);
    const elSh = document.getElementById('trValSharpe');
    if (elSh) {
      elSh.innerHTML = '';
      animateValue(elSh, 0, sh, 2, '');
    }

    const rating = getSharpeRating(sh);
    if (rating) {
      const sec = document.getElementById('sharpeRatingSection');
      if (sec) sec.style.removeProperty('display');

      const iconEl  = document.getElementById('sharpeRatingIcon');
      const lblEl   = document.getElementById('sharpeRatingLabel');
      const descEl  = document.getElementById('sharpeRatingDesc');
      const badgeEl = document.getElementById('sharpeRatingBadge');

      if (iconEl)  iconEl.innerHTML  = rating.icon;
      if (lblEl)   lblEl.textContent = rating.label;
      if (descEl)  descEl.textContent = rating.desc;
      if (badgeEl) {
        badgeEl.className   = `sharpe-rating ${rating.cls}`;
        badgeEl.innerHTML   = `${rating.icon} ${escapeHtml(rating.label)}`;
      }

      const subSh = document.getElementById('trSubSharpe');
      if (subSh) {
        subSh.innerHTML = `<span class="sharpe-rating ${rating.cls}">${rating.icon} ${escapeHtml(rating.label)}</span>`;
      }
    }

    /* Max Drawdown */
    const dd = parseFloat(data.max_drawdown || data.maxDrawdown || 0);
    const elDd = document.getElementById('trValDrawdown');
    if (elDd) {
      elDd.innerHTML = '';
      animateValue(elDd, 0, Math.abs(dd), 1, '%');
      elDd.style.color = 'var(--negative)';
    }

    /* Total Signals */
    const tot = parseInt(data.total_signals || data.totalSignals || 0, 10);
    const elTot = document.getElementById('trValTotal');
    if (elTot) {
      elTot.innerHTML = '';
      animateValue(elTot, 0, tot, 0, '');
      elTot.style.color = 'var(--ksa-gold)';
    }

    /* Alpha 30D */
    const al = parseFloat(data.alpha_30d || data.alpha30d || 0);
    const elAl = document.getElementById('trValAlpha');
    if (elAl) {
      elAl.innerHTML = '';
      animateValue(elAl, 0, al, 2, '%');
      elAl.style.color = al > 0 ? 'var(--positive)' : al < 0 ? 'var(--negative)' : 'var(--text-primary)';
    }

    /* Profit Factor */
    const pf = parseFloat(data.profit_factor || data.profitFactor || 0);
    const elPf = document.getElementById('trValPF');
    if (elPf) {
      elPf.innerHTML = '';
      animateValue(elPf, 0, pf, 2, '');
      elPf.style.color = pf >= 1.5 ? 'var(--positive)' : pf < 1.0 ? 'var(--negative)' : 'var(--ksa-gold)';
    }

  } catch (err) {
    console.warn('[KSA TR] KPI load error:', err.message);
    ['trValWinRate','trValSharpe','trValDrawdown','trValTotal','trValAlpha','trValPF'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.textContent = '—';
    });
  }
}

/* ── Load Equity Curve ───────────────────────────────────────── */
async function loadEquityCurve() {
  const container = document.getElementById('ksaEquityCurve');
  if (!container) return;

  try {
    const res = await fetch('/api/ksa/track-record/equity-curve');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const xmoreSeries = data.xmore || data.equity   || [];
    const tasiSeries  = data.tasi  || data.benchmark || [];

    if (xmoreSeries.length === 0) {
      container.innerHTML = `<p class="text-muted" style="font-size:0.85rem;padding:24px;text-align:center;">${escapeHtml(t('noData'))}</p>`;
      return;
    }

    // Use Lightweight Charts if available, else text fallback
    if (typeof LightweightCharts !== 'undefined') {
      container.innerHTML = '';
      const chart = LightweightCharts.createChart(container, {
        width:  container.clientWidth || 800,
        height: 300,
        layout: {
          background: { color: 'transparent' },
          textColor:  '#94A3B8',
        },
        grid: {
          vertLines: { color: 'rgba(201,168,76,0.07)' },
          horzLines: { color: 'rgba(201,168,76,0.07)' },
        },
        rightPriceScale: { borderColor: 'rgba(201,168,76,0.15)' },
        timeScale:        { borderColor: 'rgba(201,168,76,0.15)', timeVisible: true },
      });

      const xmoreLine = chart.addLineSeries({ color: '#C9A84C', lineWidth: 2 });
      xmoreLine.setData(xmoreSeries);

      if (tasiSeries.length > 0) {
        const tasiLine = chart.addLineSeries({ color: '#60a5fa', lineWidth: 1, lineStyle: 1 });
        tasiLine.setData(tasiSeries);
      }

      chart.timeScale().fitContent();

      const ro = new ResizeObserver(() => {
        chart.applyOptions({ width: container.clientWidth });
      });
      ro.observe(container);

    } else {
      const latest = xmoreSeries[xmoreSeries.length - 1];
      const first  = xmoreSeries[0];
      const totalReturn = (first && first.value && latest && latest.value)
        ? (((latest.value - first.value) / Math.abs(first.value)) * 100).toFixed(2)
        : '—';

      container.innerHTML = `
        <div style="padding:24px;text-align:center;">
          <p style="color:var(--text-secondary);font-size:0.82rem;margin-bottom:12px;">
            Lightweight Charts not loaded. Add the CDN script for the interactive chart.
          </p>
          <div style="font-size:1.5rem;font-weight:800;color:var(--ksa-gold);">
            ${totalReturn !== '—' ? (parseFloat(totalReturn) > 0 ? '+' : '') : ''}${totalReturn}%
          </div>
          <div style="font-size:0.75rem;color:var(--text-muted);margin-top:4px;">
            Total return (${xmoreSeries.length} data points)
          </div>
        </div>
      `;
    }

  } catch (err) {
    console.warn('[KSA TR] Equity curve error:', err.message);
    container.innerHTML = `
      <div style="padding:32px;text-align:center;color:var(--text-muted);font-size:0.82rem;">
        ${escapeHtml(t('noData'))}
      </div>
    `;
  }
}

/* ── Load Prediction Log ─────────────────────────────────────── */
async function loadPredictionLog() {
  try {
    const res = await fetch('/api/ksa/track-record/predictions?per_page=500&page=1');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    allLogRows = Array.isArray(data) ? data : (data.predictions || data.log || []);
    renderLogPage(1);

  } catch (err) {
    console.warn('[KSA TR] Prediction log error:', err.message);
    const tbody = document.getElementById('logTableBody');
    if (tbody) {
      tbody.innerHTML = `
        <tr>
          <td colspan="7">
            <div class="ksa-error" role="alert">
              <span>&#9888;</span><span>${escapeHtml(t('errorLoad'))}</span>
            </div>
          </td>
        </tr>
      `;
    }
  }
}

function renderLogPage(page) {
  logPage = page;
  const tbody = document.getElementById('logTableBody');
  if (!tbody) return;

  if (allLogRows.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7">
          <div class="ksa-empty">
            <div class="ksa-empty-icon">&#128203;</div>
            <p>${escapeHtml(t('noData'))}</p>
          </div>
        </td>
      </tr>
    `;
    renderPagination(1, 1);
    return;
  }

  const totalPages = Math.ceil(allLogRows.length / LOG_PER_PAGE);
  const start      = (page - 1) * LOG_PER_PAGE;
  const pageRows   = allLogRows.slice(start, start + LOG_PER_PAGE);

  tbody.innerHTML = pageRows.map(row => {
    const date    = escapeHtml(formatDate(row.trading_date || row.date || row.prediction_date));
    const ticker  = escapeHtml(row.ticker || row.symbol || '');
    const signal  = renderSignalPill(row.signal || row.direction);
    const result  = renderResult(row.outcome || row.result || row.actual_outcome);
    const alpha   = renderAlpha(row.alpha || row.alpha_pct);
    const dcfLbl  = renderValuationLabel(row.dcf_label || row.valuation_label);
    const shariah = renderShariahBadge(row.shariah_compliant ?? row.shariah);

    return `
      <tr>
        <td data-label="${escapeHtml(t('date'))}">${date}</td>
        <td data-label="${escapeHtml(t('ticker'))}" style="color:var(--ksa-gold);font-weight:700;">${ticker}</td>
        <td data-label="${escapeHtml(t('signal'))}">${signal}</td>
        <td data-label="${escapeHtml(t('result'))}">${result}</td>
        <td data-label="${escapeHtml(t('alpha'))}">${alpha}</td>
        <td data-label="${escapeHtml(t('dcfLabel'))}">${dcfLbl}</td>
        <td data-label="${escapeHtml(t('shariah'))}">${shariah}</td>
      </tr>
    `;
  }).join('');

  renderPagination(page, totalPages);
}

function renderPagination(current, total) {
  const pag = document.getElementById('logPagination');
  if (!pag) return;

  if (total <= 1) {
    pag.innerHTML = '';
    return;
  }

  const pages = [];
  pages.push(1);
  if (current > 4) pages.push('...');
  for (let i = Math.max(2, current - 2); i <= Math.min(total - 1, current + 2); i++) {
    pages.push(i);
  }
  if (current < total - 3) pages.push('...');
  if (total > 1) pages.push(total);

  const prevBtn = current > 1
    ? `<button class="ksa-page-btn" onclick="renderLogPage(${current - 1})" aria-label="Previous page">${t('prevPage')}</button>`
    : '';

  const nextBtn = current < total
    ? `<button class="ksa-page-btn" onclick="renderLogPage(${current + 1})" aria-label="Next page">${t('nextPage')}</button>`
    : '';

  const pageBtns = pages.map(p => {
    if (p === '...') return `<span style="color:var(--text-muted);padding:0 4px;">&#8230;</span>`;
    const active = p === current ? ' active' : '';
    return `<button class="ksa-page-btn${active}" onclick="renderLogPage(${p})" aria-label="Page ${p}">${p}</button>`;
  }).join('');

  pag.innerHTML = `${prevBtn}${pageBtns}${nextBtn}`;
}

window.renderLogPage = renderLogPage;

/* ── Export CSV ──────────────────────────────────────────────── */
function exportCsv() {
  if (allLogRows.length === 0) return;

  const headers = [
    'Date', 'Ticker', 'Signal', 'Outcome',
    'Alpha (%)', 'DCF Label', 'Shariah Compliant'
  ];

  const rows = allLogRows.map(row => [
    formatDate(row.trading_date || row.date || row.prediction_date),
    row.ticker || row.symbol || '',
    row.signal || row.direction || '',
    row.outcome || row.result || row.actual_outcome || '',
    row.alpha != null ? parseFloat(row.alpha).toFixed(2) : '',
    (row.dcf_label || row.valuation_label || '').replace(/_/g, ' '),
    row.shariah_compliant != null
      ? (row.shariah_compliant ? 'Yes' : 'No')
      : 'Unknown',
  ]);

  const csvContent = [headers, ...rows]
    .map(r => r.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(','))
    .join('\n');

  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url  = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href     = url;
  link.download = `xmore-ksa-track-record-${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
window.exportCsv = exportCsv;

/* ── Load Agent Breakdown ────────────────────────────────────── */
async function loadAgentBreakdown() {
  try {
    const res = await fetch('/api/ksa/track-record/agent-breakdown');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const agents = Array.isArray(data) ? data : (data.agents || []);
    if (agents.length === 0) return;

    const section = document.getElementById('agentSection');
    if (section) section.style.removeProperty('display');

    const tbody = document.getElementById('agentTableBody');
    if (!tbody) return;

    tbody.innerHTML = agents.map(agent => {
      const name      = escapeHtml(agent.agent_name || agent.name || agent.agent || '');
      const signals   = parseInt(agent.total_signals || agent.signals || 0, 10);
      const winRate   = parseFloat(agent.win_rate || agent.winRate || 0);
      const avgReturn = parseFloat(agent.avg_return || agent.avgReturn || 0);

      const wrCls  = winRate >= 60 ? 'high' : winRate >= 45 ? 'medium' : 'low';
      const arSign = avgReturn > 0 ? '+' : '';
      const arColor = avgReturn > 0 ? 'var(--positive)' : avgReturn < 0 ? 'var(--negative)' : 'var(--text-muted)';

      return `
        <tr>
          <td data-label="${escapeHtml(t('agent'))}" style="font-weight:700;color:var(--text-primary);">${name}</td>
          <td data-label="${escapeHtml(t('totalSignals'))}" style="color:var(--ksa-gold);">${signals}</td>
          <td data-label="${escapeHtml(t('winRate'))}">
            <div class="win-rate-bar">
              <div class="win-rate-bar-track">
                <div class="win-rate-bar-fill ${wrCls}" style="width:${Math.min(winRate, 100)}%;"></div>
              </div>
              <span style="font-weight:700;min-width:42px;font-size:0.82rem;">${winRate.toFixed(1)}%</span>
            </div>
          </td>
          <td data-label="${escapeHtml(t('avgReturn'))}" style="font-weight:600;color:${arColor};">${arSign}${avgReturn.toFixed(2)}%</td>
        </tr>
      `;
    }).join('');

  } catch (err) {
    console.warn('[KSA TR] Agent breakdown error:', err.message);
    // Non-critical — section stays hidden
  }
}

/* ── Load Sector Breakdown ───────────────────────────────────── */
async function loadSectorBreakdown() {
  try {
    const res = await fetch('/api/ksa/performance/sectors');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const sectors = Array.isArray(data) ? data : (data.sectors || []);
    if (sectors.length === 0) return;

    const section = document.getElementById('sectorSection');
    if (section) section.style.removeProperty('display');

    const content = document.getElementById('sectorContent');
    if (!content) return;

    content.innerHTML = sectors.map(sec => {
      const name    = escapeHtml(sec.sector || sec.sector_en || sec.name || '');
      const wr      = parseFloat(sec.win_rate || 0);
      const signals = parseInt(sec.total_signals || sec.signals || 0, 10);
      const wrCls   = wr >= 60 ? 'high' : wr >= 45 ? 'medium' : 'low';
      const wrColor = wr >= 60 ? 'var(--positive)' : wr < 45 ? 'var(--negative)' : 'var(--ksa-gold)';

      return `
        <div style="display:flex;align-items:center;gap:12px;padding:8px 0;border-bottom:1px solid rgba(201,168,76,0.06);">
          <div style="min-width:140px;font-size:0.82rem;color:var(--text-secondary);">${name}</div>
          <div class="win-rate-bar" style="flex:1;">
            <div class="win-rate-bar-track">
              <div class="win-rate-bar-fill ${wrCls}" style="width:${Math.min(wr, 100)}%;"></div>
            </div>
          </div>
          <div style="min-width:42px;text-align:right;font-weight:700;font-size:0.82rem;color:${wrColor};">${wr.toFixed(1)}%</div>
          <div style="min-width:52px;text-align:right;font-size:0.75rem;color:var(--text-muted);">${signals} sig</div>
        </div>
      `;
    }).join('');

  } catch (err) {
    console.warn('[KSA TR] Sector breakdown error:', err.message);
  }
}

/* ── Load Regime Performance ─────────────────────────────────── */
async function loadRegimePerformance() {
  try {
    const res = await fetch('/api/ksa/regime/stats');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const regimes = Array.isArray(data) ? data : (data.regimes || []);
    if (regimes.length === 0) return;

    const section = document.getElementById('regimeSection');
    if (section) section.style.removeProperty('display');

    const content = document.getElementById('regimeContent');
    if (!content) return;

    const colorMap = {
      calm:      { dot: 'var(--positive)', border: 'rgba(16,185,129,0.2)' },
      turbulent: { dot: 'var(--ksa-gold)', border: 'rgba(201,168,76,0.2)' },
      crisis:    { dot: 'var(--negative)', border: 'rgba(239,68,68,0.2)'  },
    };

    content.innerHTML = regimes.map(reg => {
      const name    = (reg.regime || 'calm').toLowerCase();
      const label   = escapeHtml(t(name) || name);
      const wr      = parseFloat(reg.win_rate || 0);
      const signals = parseInt(reg.signals || reg.total_signals || 0, 10);
      const ret     = parseFloat(reg.avg_return || 0);
      const col     = colorMap[name] || colorMap.calm;
      const retSign = ret > 0 ? '+' : '';
      const retColor = ret > 0 ? 'var(--positive)' : ret < 0 ? 'var(--negative)' : 'var(--text-muted)';

      return `
        <div style="background:var(--bg-card);border:1px solid ${col.border};border-radius:12px;padding:16px;">
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:12px;">
            <div style="width:12px;height:12px;border-radius:50%;background:${col.dot};flex-shrink:0;"></div>
            <span style="font-weight:700;font-size:0.9rem;">${label}</span>
          </div>
          <div style="display:flex;flex-direction:column;gap:6px;font-size:0.8rem;">
            <div style="display:flex;justify-content:space-between;">
              <span style="color:var(--text-muted);">${escapeHtml(t('winRate'))}</span>
              <span style="font-weight:700;color:${wr >= 55 ? 'var(--positive)' : 'var(--text-primary)'};">${wr.toFixed(1)}%</span>
            </div>
            <div style="display:flex;justify-content:space-between;">
              <span style="color:var(--text-muted);">${escapeHtml(t('totalSignals'))}</span>
              <span style="font-weight:600;color:var(--ksa-gold);">${signals}</span>
            </div>
            <div style="display:flex;justify-content:space-between;">
              <span style="color:var(--text-muted);">${escapeHtml(t('avgReturn'))}</span>
              <span style="font-weight:700;color:${retColor};">${retSign}${ret.toFixed(2)}%</span>
            </div>
          </div>
        </div>
      `;
    }).join('');

  } catch (err) {
    console.warn('[KSA TR] Regime performance error:', err.message);
  }
}

/* ── Init ────────────────────────────────────────────────────── */
async function init() {
  // Restore language preference
  const savedLang = localStorage.getItem('ksaLang') || 'en';
  if (savedLang !== currentLang) {
    currentLang = savedLang;
    const html = document.documentElement;
    html.lang = currentLang;
    html.dir  = currentLang === 'ar' ? 'rtl' : 'ltr';
    const btn = document.getElementById('langToggle');
    if (btn) btn.textContent = currentLang === 'ar' ? '&#127468;&#127463; English' : '&#127480;&#127462; &#1593;&#1585;&#1576;&#1610;';
  }

  applyTranslations(currentLang);

  // All loaders run in parallel — each non-fatal individually
  await Promise.allSettled([
    loadKpis(),
    loadEquityCurve(),
    loadPredictionLog(),
    loadAgentBreakdown(),
    loadSectorBreakdown(),
    loadRegimePerformance(),
  ]);
}

document.addEventListener('DOMContentLoaded', init);
