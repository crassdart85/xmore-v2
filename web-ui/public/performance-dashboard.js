const PERF_TRANSLATIONS = {
    en: {
        perfTitle: 'Xmore Performance',
        proof: 'Proof of Edge',
        stability: 'Stability Metrics',
        accountability: 'Agent Accountability',
        transparency: 'Transparency & Integrity',
        equity: 'Equity Curve',
        alpha: 'Alpha',
        sharpe: 'Sharpe',
        maxDd: 'Max Drawdown',
        volatility: 'Volatility',
        profitFactor: 'Profit Factor',
        winRate: 'Win Rate',
        trades: 'Trades',
        systemHealth: 'System Health',
        stable: 'Stable',
        watch: 'Watch',
        degraded: 'Degraded',
        sinceInception: 'Since Inception',
        liveOnly: 'Live-only immutable logs',
        showBenchmark: 'Show TASI',
        showDrawdown: 'Drawdown',
        noData: 'Performance tracking will appear after live evaluations.',
        openAudit: 'Open Audit Trail',
        showMore: 'Show More',
        window: 'Window',
        agent: 'Agent',
        win30d: '30d Win',
        win90d: '90d Win',
        confidence: 'Confidence',
        predictions: 'Predictions',
        weight: 'Weight',
        date: 'Date',
        symbol: 'Symbol',
        signal: 'Signal',
        noDataRow: 'No data',
        loading: 'Loading performance...',
        loadFailed: 'Failed to load performance dashboard.',
        firstLive: 'First Live',
        totalLive: 'Total Live',
        auditTitle: 'Audit Trail',
        auditWhen: 'When',
        auditTable: 'Table',
        auditRecord: 'Record',
        auditField: 'Field',
        auditOld: 'Old',
        auditNew: 'New',
        auditNoEntries: 'No entries',
        sortino: 'Sortino',
        institutionalMetrics: 'Institutional Metrics',
        sharpeRatio:          'Sharpe Ratio',
        sortinoRatio:         'Sortino Ratio',
        calmarRatio:          'Calmar Ratio',
        informationRatio:     'Information Ratio',
        maxDrawdown:          'Max Drawdown',
        recoveryTime:         'Recovery Time',
        betaVsBenchmark:      'Beta vs TASI',
        downCapture:          'Down Capture',
        benchmarkComparison:  'Benchmark Comparison',
        riskFreeRateApplied:  'Risk-Free Rate Applied',
        rollingSharpe:        '30-Day Rolling Sharpe',
        notEnoughData:        'Min. 30 trades required',
        exportReport:         'Export Report',
        days:                 'days',
        notRecovered:         'Not Recovered',
    },
    ar: {
        perfTitle: 'Ø£Ø¯Ø§Ø¡ Ø¥ÙƒØ³Ù…ÙˆØ±',
        proof: 'Ø¥Ø«Ø¨Ø§Øª Ø§Ù„ØªÙÙˆÙ‚',
        stability: 'Ù…Ù‚Ø§ÙŠÙŠØ³ Ø§Ù„Ø§Ø³ØªÙ‚Ø±Ø§Ø±',
        accountability: 'Ù…Ø³Ø§Ø¡Ù„Ø© Ø§Ù„ÙˆÙƒÙ„Ø§Ø¡',
        transparency: 'Ø§Ù„Ø´ÙØ§ÙÙŠØ© ÙˆØ§Ù„Ù†Ø²Ø§Ù‡Ø©',
        equity: 'Ù…Ù†Ø­Ù†Ù‰ Ø§Ù„Ø£Ø¯Ø§Ø¡',
        alpha: 'Ø£Ù„ÙØ§',
        sharpe: 'Ø´Ø§Ø±Ø¨',
        maxDd: 'Ø£Ù‚ØµÙ‰ ØªØ±Ø§Ø¬Ø¹',
        volatility: 'Ø§Ù„ØªØ°Ø¨Ø°Ø¨',
        profitFactor: 'Ù…Ø¹Ø§Ù…Ù„ Ø§Ù„Ø±Ø¨Ø­',
        winRate: 'Ù†Ø³Ø¨Ø© Ø§Ù„ÙÙˆØ²',
        trades: 'Ø§Ù„ØµÙÙ‚Ø§Øª',
        systemHealth: 'Ø­Ø§Ù„Ø© Ø§Ù„Ù†Ø¸Ø§Ù…',
        stable: 'Ù…Ø³ØªÙ‚Ø±',
        watch: 'Ù…Ø±Ø§Ù‚Ø¨Ø©',
        degraded: 'Ù…ØªØ±Ø§Ø¬Ø¹',
        sinceInception: 'Ù…Ù†Ø° Ø§Ù„Ø§Ù†Ø·Ù„Ø§Ù‚',
        liveOnly: 'Ø³Ø¬Ù„ Ø­ÙŠ ØºÙŠØ± Ù‚Ø§Ø¨Ù„ Ù„Ù„ØªØ¹Ø¯ÙŠÙ„',
        showBenchmark: 'Ø¹Ø±Ø¶ ØªØ§Ø³ÙŠ',
        showDrawdown: 'Ø§Ù„Ù‡Ø¨ÙˆØ·',
        noData: 'Ø³ÙŠØ¸Ù‡Ø± ØªØªØ¨Ø¹ Ø§Ù„Ø£Ø¯Ø§Ø¡ Ø¨Ø¹Ø¯ ØªÙˆÙØ± ØªÙ‚ÙŠÙŠÙ…Ø§Øª Ø­ÙŠØ©.',
        openAudit: 'ÙØªØ­ Ø³Ø¬Ù„ Ø§Ù„ØªØ¯Ù‚ÙŠÙ‚',
        showMore: 'Ø¹Ø±Ø¶ Ø§Ù„Ù…Ø²ÙŠØ¯',
        window: 'Ø§Ù„ÙØªØ±Ø©',
        agent: 'Ø§Ù„ÙˆÙƒÙŠÙ„',
        win30d: 'ÙÙˆØ² 30 ÙŠÙˆÙ…',
        win90d: 'ÙÙˆØ² 90 ÙŠÙˆÙ…',
        confidence: 'Ø§Ù„Ø«Ù‚Ø©',
        predictions: 'Ø§Ù„ØªÙ†Ø¨Ø¤Ø§Øª',
        weight: 'Ø§Ù„ÙˆØ²Ù†',
        date: 'Ø§Ù„ØªØ§Ø±ÙŠØ®',
        symbol: 'Ø§Ù„Ø±Ù…Ø²',
        signal: 'Ø§Ù„Ø¥Ø´Ø§Ø±Ø©',
        noDataRow: 'Ù„Ø§ ØªÙˆØ¬Ø¯ Ø¨ÙŠØ§Ù†Ø§Øª',
        loading: 'Ø¬Ø§Ø±ÙŠ ØªØ­Ù…ÙŠÙ„ Ø§Ù„Ø£Ø¯Ø§Ø¡...',
        loadFailed: 'ÙØ´Ù„ ØªØ­Ù…ÙŠÙ„ Ù„ÙˆØ­Ø© Ø§Ù„Ø£Ø¯Ø§Ø¡.',
        firstLive: 'Ø£ÙˆÙ„ ØªÙ†Ø¨Ø¤ Ø­ÙŠ',
        totalLive: 'Ø¥Ø¬Ù…Ø§Ù„ÙŠ Ø§Ù„ØªÙ†Ø¨Ø¤Ø§Øª Ø§Ù„Ø­ÙŠØ©',
        auditTitle: 'Ø³Ø¬Ù„ Ø§Ù„ØªØ¯Ù‚ÙŠÙ‚',
        auditWhen: 'Ù…ØªÙ‰',
        auditTable: 'Ø§Ù„Ø¬Ø¯ÙˆÙ„',
        auditRecord: 'Ø§Ù„Ø³Ø¬Ù„',
        auditField: 'Ø§Ù„Ø­Ù‚Ù„',
        auditOld: 'Ø§Ù„Ù‚Ø¯ÙŠÙ…',
        auditNew: 'Ø§Ù„Ø¬Ø¯ÙŠØ¯',
        auditNoEntries: 'Ù„Ø§ ØªÙˆØ¬Ø¯ Ù…Ø¯Ø®Ù„Ø§Øª',
        sortino: 'Ø³ÙˆØ±ØªÙŠÙ†Ùˆ',
        institutionalMetrics: 'Ù…Ù‚Ø§ÙŠÙŠØ³ Ù…Ø¤Ø³Ø³ÙŠØ©',
        sharpeRatio:          'Ù†Ø³Ø¨Ø© Ø´Ø§Ø±Ø¨',
        sortinoRatio:         'Ù†Ø³Ø¨Ø© Ø³ÙˆØ±ØªÙŠÙ†Ùˆ',
        calmarRatio:          'Ù†Ø³Ø¨Ø© ÙƒØ§Ù„Ù…Ø§Ø±',
        informationRatio:     'Ù†Ø³Ø¨Ø© Ø§Ù„Ù…Ø¹Ù„ÙˆÙ…Ø§Øª',
        maxDrawdown:          'Ø£Ù‚ØµÙ‰ ØªØ±Ø§Ø¬Ø¹',
        recoveryTime:         'ÙˆÙ‚Øª Ø§Ù„Ø§Ø³ØªØ±Ø¯Ø§Ø¯',
        betaVsBenchmark:      'Ø¨ÙŠØªØ§ Ù…Ù‚Ø§Ø¨Ù„ ØªØ§Ø³ÙŠ',
        downCapture:          'Ù…Ø¹Ø¯Ù„ Ø§Ù„ØªØ±Ø§Ø¬Ø¹',
        benchmarkComparison:  'Ù…Ù‚Ø§Ø±Ù†Ø© Ø§Ù„Ù…Ø±Ø¬Ø¹',
        riskFreeRateApplied:  'Ù…Ø¹Ø¯Ù„ Ø§Ù„Ø®Ø·Ø± Ø§Ù„Ù…Ø·Ø¨Ù‚',
        rollingSharpe:        'Ø´Ø§Ø±Ø¨ Ø§Ù„Ù…ØªØ¬Ø¯Ø¯ 30 ÙŠÙˆÙ…',
        notEnoughData:        'Ù…Ø·Ù„ÙˆØ¨ 30 ØµÙÙ‚Ø© Ø¹Ù„Ù‰ Ø§Ù„Ø£Ù‚Ù„',
        exportReport:         'ØªØµØ¯ÙŠØ± Ø§Ù„ØªÙ‚Ø±ÙŠØ±',
        days:                 'ÙŠÙˆÙ…',
        notRecovered:         'Ù„Ù… ÙŠÙØ³ØªØ±Ø¯',
    }
};

function pt(key) {
    return PERF_TRANSLATIONS[currentLang]?.[key] || PERF_TRANSLATIONS.en[key] || key;
}

let perfHistoryPage = 1;
let perfEquityCurveDays = 90;
let perfChartState = { showBenchmark: true, showDrawdown: true, points: [] };
let perfLwChart = null; // Lightweight Charts instance
let perfLwTasiSeries = null; // TASI benchmark series reference

async function loadPerformanceDashboard() {
    const container = document.getElementById('perfDashboard');
    if (!container) return;
    container.innerHTML = `<p class="loading">${pt('loading')}</p>`;

    try {
        const [summary, agents, equity, history, fullReport] = await Promise.all([
            fetch('/api/performance-v2/summary').then(r => r.json()).catch(() => ({ available: false })),
            fetch('/api/performance-v2/by-agent').then(r => r.json()).catch(() => ({ agents: [] })),
            fetch(`/api/performance-v2/equity-curve?days=${perfEquityCurveDays}`).then(r => r.json()).catch(() => ({ series: [] })),
            fetch(`/api/performance-v2/predictions/history?page=${perfHistoryPage}&limit=10`).then(r => r.json()).catch(() => ({ predictions: [] })),
            fetch('/api/performance-v2/full-report?days=90').then(r => r.json()).catch(() => ({ available: false }))
        ]);

        if (!summary.available) {
            container.innerHTML = `<p class="no-data">${pt('noData')}</p>`;
            if (typeof showToast === 'function') showToast('warning', typeof t === 'function' ? t('minTradesWarning') : pt('noData'));
            return;
        }

        container.innerHTML = '';
        container.appendChild(buildHealth(summary));
        container.appendChild(buildProofOfEdge(summary, equity));
        container.appendChild(buildInstitutionalMetrics(summary, fullReport));
        container.appendChild(buildStability(summary));
        container.appendChild(buildAgentAccountability(agents));
        container.appendChild(buildTransparency(summary, history));
        container.appendChild(buildSinceInception(summary));

        // Render equity curve with Lightweight Charts (Upgrade 3) or canvas fallback
        renderEquityCurve(equity);

        // Animate proof-of-edge metrics (Upgrade 1)
        const r30 = summary.rolling?.['30d'] || {};
        const g = summary.global || {};
        const alpha = Number(r30.alpha ?? 0);
        const sharpe = Number(r30.sharpe_ratio ?? g.sharpe_ratio ?? 0);
        const maxDd = Number(r30.max_drawdown ?? g.max_drawdown ?? 0);
        if (typeof animateValue === 'function') {
            animateValue('perfEdgeAlpha', alpha, { decimalPlaces: 2, suffix: '%', prefix: alpha > 0 ? '+' : '' });
            animateValue('perfEdgeSharpe', sharpe, { decimalPlaces: 2 });
            animateValue('perfEdgeMaxDd', maxDd, { decimalPlaces: 2, suffix: '%' });
            // Since inception
            animateValue('perfInceptionAlpha', g.avg_alpha_1d || 0, { decimalPlaces: 2, suffix: '%', prefix: (g.avg_alpha_1d || 0) > 0 ? '+' : '' });
            animateValue('perfInceptionSharpe', g.sharpe_ratio || 0, { decimalPlaces: 2 });
            animateValue('perfInceptionTotal', g.total_predictions || 0, { decimalPlaces: 0 });
        }
    } catch (e) {
        container.innerHTML = `<p class="error-message">${pt('loadFailed')}</p>`;
        console.error(e);
    }
}

function metricCard(label, value, cls = '', tip = '', id = '') {
    const idAttr = id ? ` id="${id}"` : '';
    return `<div class="perf-metric-card ${cls}" title="${tip}"><div class="perf-metric-label">${label}</div><div class="perf-metric-value metric-value"${idAttr}>${value}</div></div>`;
}

function buildHealth(summary) {
    const g = summary.global || {};
    const r30 = summary.rolling?.['30d'] || {};
    const sharpe = Number(r30.sharpe_ratio ?? g.sharpe_ratio ?? 0);
    const alpha = Number(r30.alpha ?? g.avg_alpha_1d ?? 0);
    const dd = Number(r30.max_drawdown ?? g.max_drawdown ?? 0);
    let state = 'degraded';
    if (sharpe > 1 && alpha > 0 && dd <= 8) state = 'stable';
    else if (sharpe > 0.6 && alpha >= 0 && dd <= 12) state = 'watch';

    return createSection(`
        <div class="perf-health ${state}">
            <div class="perf-health-title">${pt('systemHealth')}</div>
            <div class="perf-health-state health-badge">${pt(state)}</div>
            <div class="perf-health-note">${pt('liveOnly')}</div>
        </div>
    `);
}

function buildProofOfEdge(summary, equity) {
    const g = summary.global || {};
    const r30 = summary.rolling?.['30d'] || {};
    const alpha = Number(r30.alpha ?? 0);
    const sharpe = Number(r30.sharpe_ratio ?? g.sharpe_ratio ?? 0);
    const maxDd = Number(r30.max_drawdown ?? g.max_drawdown ?? 0);

    return createSection(`
        <h3>${pt('proof')}</h3>
        <div class="perf-proof-grid">
            ${metricCard(pt('alpha'), '-', alpha > 0 ? 'positive' : 'negative', '30-day alpha versus TASI', 'perfEdgeAlpha')}
            ${metricCard(pt('sharpe'), '-', sharpe >= 1 ? 'positive' : 'neutral', '30-day risk-adjusted return', 'perfEdgeSharpe')}
            ${metricCard(pt('maxDd'), '-', maxDd <= 8 ? 'positive' : 'negative', '30-day maximum drawdown', 'perfEdgeMaxDd')}
        </div>
        <div class="perf-section-head">
            <h3>${pt('equity')}</h3>
            <div class="perf-chart-controls">
                <button class="perf-period-btn ${perfEquityCurveDays === 30 ? 'active' : ''}" onclick="changeEquityCurvePeriod(30)">30d</button>
                <button class="perf-period-btn ${perfEquityCurveDays === 60 ? 'active' : ''}" onclick="changeEquityCurvePeriod(60)">60d</button>
                <button class="perf-period-btn ${perfEquityCurveDays === 90 ? 'active' : ''}" onclick="changeEquityCurvePeriod(90)">90d</button>
                <button class="perf-period-btn ${perfEquityCurveDays === 180 ? 'active' : ''}" onclick="changeEquityCurvePeriod(180)">180d</button>
                <label class="benchmark-toggle"><input type="checkbox" id="toggle-tasi" ${perfChartState.showBenchmark ? 'checked' : ''} onchange="toggleBenchmarkLine(this.checked)"> <span data-i18n="showBenchmark">${pt('showBenchmark')}</span></label>
            </div>
        </div>
        <div class="perf-chart-wrap" id="equityCurveChartContainer" style="min-height:350px;"></div>
        <div class="perf-chart-legend">
            <span style="color:#10b981">&#9632; Xmore ${equity.total_xmore > 0 ? '+' : ''}${Number(equity.total_xmore || 0).toFixed(2)}%</span>
            <span style="color:#6b7280">&#9632; TASI ${equity.total_tasi > 0 ? '+' : ''}${Number(equity.total_tasi || 0).toFixed(2)}%</span>
            <span>Alpha ${equity.total_alpha > 0 ? '+' : ''}${Number(equity.total_alpha || 0).toFixed(2)}%</span>
        </div>
    `);
}

function buildStability(summary) {
    const rows = ['30d', '60d', '90d'].map(k => {
        const d = summary.rolling?.[k] || {};
        return `<tr>
            <td>${k}</td>
            <td>${Number(d.win_rate || 0).toFixed(1)}%</td>
            <td>${Number(d.volatility || 0).toFixed(2)}%</td>
            <td>${Number(d.profit_factor || 0).toFixed(2)}</td>
            <td>${Number(d.trades || 0)}</td>
        </tr>`;
    }).join('');
    return createSection(`
        <h3>${pt('stability')}</h3>
        <div class="perf-table-wrapper">
            <table class="perf-table">
                <thead><tr><th>${pt('window')}</th><th>${pt('winRate')}</th><th>${pt('volatility')}</th><th>${pt('profitFactor')}</th><th>${pt('trades')}</th></tr></thead>
                <tbody>${rows}</tbody>
            </table>
        </div>
    `);
}

function buildAgentAccountability(data) {
    const agents = (data.agents || []).slice().sort((a, b) => (b.win_rate_30d || 0) - (a.win_rate_30d || 0));
    const rows = agents.map(a => {
        const n = typeof getAgentDisplayName === 'function' ? getAgentDisplayName(a.agent) : a.agent;
        return `<tr>
            <td>${n}</td>
            <td>${Number(a.win_rate_30d || 0).toFixed(1)}%</td>
            <td>${Number(a.win_rate_90d || 0).toFixed(1)}%</td>
            <td>${Number(a.avg_confidence_30d || 0).toFixed(1)}%</td>
            <td>${a.predictions_30d || 0}</td>
            <td><div class="mini-weight"><span style="width:${Math.min(100, Number(a.win_rate_30d || 0))}%"></span></div></td>
        </tr>`;
    }).join('');
    return createSection(`
        <h3>${pt('accountability')}</h3>
        <div class="perf-table-wrapper">
            <table class="perf-table">
                <thead><tr><th>${pt('agent')}</th><th>${pt('win30d')}</th><th>${pt('win90d')}</th><th>${pt('confidence')}</th><th>${pt('predictions')}</th><th>${pt('weight')}</th></tr></thead>
                <tbody>${rows || `<tr><td colspan="6">${pt('noDataRow')}</td></tr>`}</tbody>
            </table>
        </div>
    `);
}

function buildTransparency(summary, history) {
    const g = summary.global || {};
    const preds = history.predictions || [];
    const rows = preds.map(p => `<tr>
        <td>${String(p.prediction_date || '').slice(0, 10)}</td>
        <td>${p.symbol || '-'}</td>
        <td>${p.final_signal || '-'}</td>
        <td>${p.consensus_confidence == null ? '-' : `${Number(p.consensus_confidence).toFixed(1)}%`}</td>
        <td>${p.alpha_1d == null ? '-' : `${p.alpha_1d > 0 ? '+' : ''}${Number(p.alpha_1d).toFixed(2)}%`}</td>
    </tr>`).join('');
    const progress = Math.min(100, Math.round(((g.total_predictions || 0) / 100) * 100));
    return createSection(`
        <h3>${pt('transparency')}</h3>
        <div class="perf-integrity-banner">${pt('liveOnly')}</div>
        <div class="perf-table-wrapper">
            <table class="perf-table">
                <thead><tr><th>${pt('date')}</th><th>${pt('symbol')}</th><th>${pt('signal')}</th><th>${pt('confidence')}</th><th>${pt('alpha')}</th></tr></thead>
                <tbody>${rows || `<tr><td colspan="5">${pt('noDataRow')}</td></tr>`}</tbody>
            </table>
        </div>
        <div class="perf-actions">
            <button class="perf-action-btn secondary" onclick="showAuditLog()">${pt('openAudit')}</button>
            <button class="perf-action-btn" onclick="loadMorePredictions()">${pt('showMore')}</button>
        </div>
        <div class="integrity-progress progress-fill"><span style="width:${progress}%"></span><em>${g.total_predictions || 0}/100</em></div>
        <a href="/track-record#methodology" class="perf-methodology-link">View walk-forward backtest methodology â†’</a>
    `);
}

function buildSinceInception(summary) {
    const g = summary.global || {};
    return createSection(`
        <h3>${pt('sinceInception')}</h3>
        <div class="perf-proof-grid">
            ${metricCard(pt('alpha'), '-', '', '', 'perfInceptionAlpha')}
            ${metricCard(pt('sharpe'), '-', '', '', 'perfInceptionSharpe')}
            ${metricCard(pt('firstLive'), g.first_prediction ? String(g.first_prediction).slice(0, 10) : 'N/A')}
            ${metricCard(pt('totalLive'), '-', '', '', 'perfInceptionTotal')}
        </div>
    `);
}

function buildInstitutionalMetrics(summary, fullReport) {
    const im = summary.institutional_metrics || {};
    const warn = im.data_quality_warning;
    const warnBanner = warn
        ? `<div class="perf-quality-warning">âš  ${warn}</div>` : '';

    const colorSharpe = (v) => v >= 1.5 ? 'inst-green' : v >= 0.8 ? 'inst-amber' : 'inst-red';
    const colorSortino = (v) => v >= 2 ? 'inst-green' : v >= 1 ? 'inst-amber' : 'inst-red';
    const colorCalmar = (v) => v >= 2 ? 'inst-green' : v >= 1 ? 'inst-amber' : 'inst-red';
    const colorIR = (v) => v >= 0.75 ? 'inst-green' : v >= 0.4 ? 'inst-amber' : 'inst-red';
    const colorMdd = (v) => { const n = parseFloat(v); return n > -10 ? 'inst-green' : n > -20 ? 'inst-amber' : 'inst-red'; };
    const colorRec = (days) => days == null ? 'inst-red' : days <= 10 ? 'inst-green' : days <= 20 ? 'inst-amber' : 'inst-red';
    const colorBeta = (v) => v < 0.8 ? 'inst-green' : v <= 1.2 ? 'inst-amber' : 'inst-red';
    const colorDown = (v) => { const n = v * 100; return n < 80 ? 'inst-green' : n <= 100 ? 'inst-amber' : 'inst-red'; };

    const instCard = (label, value, colorClass, tip) =>
        `<div class="inst-card" title="${tip}">
            <div class="inst-label">${label}</div>
            <div class="inst-value ${colorClass}">${value}</div>
         </div>`;

    const sharpe  = im.sharpe_ratio != null ? Number(im.sharpe_ratio).toFixed(2) : 'â€”';
    const sortino = im.sortino_ratio != null ? Number(im.sortino_ratio).toFixed(2) : 'â€”';
    const calmar  = im.calmar_ratio != null ? Number(im.calmar_ratio).toFixed(2) : 'â€”';
    const ir      = im.information_ratio != null ? Number(im.information_ratio).toFixed(2) : 'â€”';
    const mdd     = im.max_drawdown_pct != null ? `${Number(im.max_drawdown_pct).toFixed(2)}%` : 'â€”';
    const recDays = im.recovery_duration_days;
    const recStr  = im.max_drawdown_recovered === false ? pt('notRecovered') : recDays != null ? `${recDays} ${pt('days')}` : 'â€”';
    const beta    = im.beta_vs_benchmark != null ? Number(im.beta_vs_benchmark).toFixed(2) : 'â€”';
    const downCap = im.down_capture_ratio != null ? Number(im.down_capture_ratio) : 'â€”';
    const downStr = downCap !== 'â€”' ? `${(Number(downCap) * 100).toFixed(0)}%` : 'â€”';

    // Rolling Sharpe sparkline
    const rsData = (fullReport?.rolling_sharpe_30d || []).map(d => d.sharpe);
    let sparklineSvg = '';
    if (rsData.length >= 2) {
        const W = 200, H = 50;
        const minV = Math.min(...rsData), maxV = Math.max(...rsData);
        const rangeV = maxV - minV || 1;
        const pts = rsData.map((v, i) => {
            const x = (i / (rsData.length - 1)) * W;
            const y = H - ((v - minV) / rangeV) * H;
            return `${x.toFixed(1)},${y.toFixed(1)}`;
        }).join(' ');
        const lastV = rsData[rsData.length - 1];
        const lineColor = lastV >= 1 ? '#10b981' : '#ef4444';
        sparklineSvg = `<svg viewBox="0 0 ${W} ${H}" style="width:100%;height:50px;display:block">
            <polyline points="${pts}" fill="none" stroke="${lineColor}" stroke-width="1.5"/>
            <line x1="0" y1="${(H - (1 - minV) / rangeV * H).toFixed(1)}" x2="${W}" y2="${(H - (1 - minV) / rangeV * H).toFixed(1)}" stroke="#6b7280" stroke-width="0.5" stroke-dasharray="3,3"/>
        </svg>`;
    }

    // Benchmark comparison table
    const benchTotalXmore = fullReport?.portfolio_returns ? fullReport.portfolio_returns.reduce((a, b) => a + b, 0).toFixed(2) : 'â€”';
    const benchTotalTasi = fullReport?.benchmark_returns ? fullReport.benchmark_returns.reduce((a, b) => a + b, 0).toFixed(2) : 'â€”';
    const alpha = (benchTotalXmore !== 'â€”' && benchTotalTasi !== 'â€”') ? (Number(benchTotalXmore) - Number(benchTotalTasi)).toFixed(2) : 'â€”';
    const fmtR = v => v === 'â€”' ? 'â€”' : `${Number(v) >= 0 ? '+' : ''}${Number(v).toFixed(2)}%`;
    const benchTable = `
        <table class="inst-bench-table">
            <thead><tr><th></th><th>Xmore2</th><th>TASI</th></tr></thead>
            <tbody>
                <tr><td>Total Return</td><td class="${Number(benchTotalXmore) > Number(benchTotalTasi) ? 'inst-highlight' : ''}">${fmtR(benchTotalXmore)}</td><td>${fmtR(benchTotalTasi)}</td></tr>
                <tr><td>Alpha</td><td class="inst-highlight">${fmtR(alpha)}</td><td>â€”</td></tr>
                <tr><td>Sharpe</td><td class="${Number(sharpe) > 0.43 ? 'inst-highlight' : ''}">${sharpe}</td><td>~0.43</td></tr>
                <tr><td>Max Drawdown</td><td class="${parseFloat(mdd) > -19.8 ? 'inst-highlight' : ''}">${mdd}</td><td>~-19.8%</td></tr>
                <tr><td>Up Capture</td><td class="inst-highlight">${im.up_capture_ratio != null ? `${(Number(im.up_capture_ratio) * 100).toFixed(0)}%` : 'â€”'}</td><td>â€”</td></tr>
                <tr><td>Down Capture</td><td class="${Number(downCap) < 1 ? 'inst-highlight' : ''}">${downStr}</td><td>â€”</td></tr>
            </tbody>
        </table>`;

    return createSection(`
        <div class="inst-header">
            <h3>${pt('institutionalMetrics')}</h3>
            <a href="/api/performance-v2/export-summary" target="_blank" class="perf-action-btn inst-export-btn">${pt('exportReport')} â†—</a>
        </div>
        ${warnBanner}
        <div class="inst-grid">
            ${instCard(pt('sharpeRatio'), sharpe, colorSharpe(Number(sharpe)), 'Return per unit of risk, adjusted for Saudi SAIBOR rate (4.89%)')}
            ${instCard(pt('sortinoRatio'), sortino, colorSortino(Number(sortino)), 'Like Sharpe, but only penalizes downside volatility')}
            ${instCard(pt('calmarRatio'), calmar, colorCalmar(Number(calmar)), 'Annualized return divided by maximum drawdown depth')}
            ${instCard(pt('informationRatio'), ir, colorIR(Number(ir)), 'Alpha per unit of tracking error vs TASI')}
            ${instCard(pt('maxDrawdown'), mdd, colorMdd(mdd), 'Largest peak-to-trough decline in portfolio value')}
            ${instCard(pt('recoveryTime'), recStr, colorRec(recDays), 'Trading days from drawdown trough to new equity high')}
            ${instCard(pt('betaVsBenchmark'), beta, colorBeta(Number(beta)), 'Portfolio sensitivity to TASI movements. <1 = less volatile')}
            ${instCard(pt('downCapture'), downStr, colorDown(Number(downCap)), 'How much of TASI down days the portfolio captures. <80% is excellent')}
        </div>
        <div class="inst-sub-row">
            <div class="inst-sub-card">
                <div class="inst-sub-label">${pt('rollingSharpe')}</div>
                ${sparklineSvg || `<div style="color:var(--text-muted);font-size:11px;padding:8px 0">${pt('notEnoughData')}</div>`}
            </div>
            <div class="inst-sub-card">
                <div class="inst-sub-label">${pt('benchmarkComparison')}</div>
                ${benchTable}
            </div>
        </div>
        <div class="inst-rf-note">${pt('riskFreeRateApplied')}: ${im.risk_free_rate_applied || '4.89%'} (Saudi SAIBOR 3M)</div>
    `);
}

function createSection(html) {
    const el = document.createElement('div');
    el.className = 'perf-section';
    el.innerHTML = html;
    return el;
}

async function changeEquityCurvePeriod(days) {
    perfEquityCurveDays = days;
    // Destroy old chart instance
    const container = document.getElementById('equityCurveChartContainer');
    if (container && container._chartInstance) {
        container._chartInstance.remove();
        container._chartInstance = null;
    }
    if (container && container._resizeObserver) {
        container._resizeObserver.disconnect();
        container._resizeObserver = null;
    }
    perfLwChart = null;
    perfLwTasiSeries = null;
    await loadPerformanceDashboard();
}

function toggleBenchmarkLine(v) {
    perfChartState.showBenchmark = !!v;
    // If Lightweight Charts instance exists, toggle series visibility
    if (perfLwTasiSeries) {
        perfLwTasiSeries.applyOptions({ visible: v });
        return;
    }
    // Fallback: re-render canvas
    const chartData = { series: perfChartState.points };
    renderEquityCurveCanvas(chartData);
}

function toggleDrawdownShading(v) {
    perfChartState.showDrawdown = !!v;
    // For Lightweight Charts, we don't have drawdown shading built in,
    // so we re-render if using canvas fallback
    if (!perfLwChart) {
        const chartData = { series: perfChartState.points };
        renderEquityCurveCanvas(chartData);
    }
}

// ============================================
// UPGRADE 3: LIGHTWEIGHT CHARTS EQUITY CURVE
// ============================================

function renderEquityCurve(data) {
    const container = document.getElementById('equityCurveChartContainer');
    if (!container) return;

    const points = data.series || [];
    perfChartState.points = points;

    if (points.length < 2) {
        container.innerHTML = '<p class="no-data" style="text-align:center;padding:40px;">Not enough data for chart.</p>';
        return;
    }

    // Try Lightweight Charts first, fall back to canvas
    if (typeof LightweightCharts !== 'undefined') {
        renderEquityCurveLW(container, points);
    } else {
        // Fallback: inject a canvas and use the old renderer
        container.innerHTML = '<canvas id="equityCurveCanvas"></canvas><div id="perfChartTooltip" class="perf-chart-tooltip"></div>';
        renderEquityCurveCanvas(data);
    }
}

function renderEquityCurveLW(container, points) {
    // Clear previous chart
    if (container._chartInstance) {
        container._chartInstance.remove();
        container._chartInstance = null;
    }
    if (container._resizeObserver) {
        container._resizeObserver.disconnect();
        container._resizeObserver = null;
    }
    container.innerHTML = '';

    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';

    const chart = LightweightCharts.createChart(container, {
        width: container.clientWidth,
        height: 350,
        layout: {
            background: { type: 'solid', color: isDark ? '#1a1a2e' : '#ffffff' },
            textColor: isDark ? '#d1d5db' : '#374151',
            fontFamily: "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif",
        },
        grid: {
            vertLines: { color: isDark ? '#2d2d44' : '#f0f0f0' },
            horzLines: { color: isDark ? '#2d2d44' : '#f0f0f0' },
        },
        crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
        rightPriceScale: {
            borderColor: isDark ? '#2d2d44' : '#e0e0e0',
        },
        timeScale: {
            borderColor: isDark ? '#2d2d44' : '#e0e0e0',
            timeVisible: false,
        },
        localization: {
            priceFormatter: (price) => price.toFixed(2) + '%',
        },
    });

    // Xmore performance area
    const xmoreSeries = chart.addAreaSeries({
        lineColor: '#10b981',
        topColor: 'rgba(16, 185, 129, 0.3)',
        bottomColor: 'rgba(16, 185, 129, 0.02)',
        lineWidth: 2,
        title: 'Xmore',
    });

    const xmoreData = points
        .filter(d => d.date)
        .map(d => ({
            time: String(d.date).slice(0, 10),
            value: Number(d.xmore || d.cumulative_return || 0),
        }));
    if (xmoreData.length > 0) xmoreSeries.setData(xmoreData);

    // TASI benchmark line
    const tasiSeries = chart.addLineSeries({
        color: '#6b7280',
        lineWidth: 1,
        lineStyle: LightweightCharts.LineStyle.Dashed,
        title: 'TASI',
        visible: perfChartState.showBenchmark,
    });

    const tasiData = points
        .filter(d => d.date)
        .map(d => ({
            time: String(d.date).slice(0, 10),
            value: Number(d.tasi || d.tasi_return || 0),
        }));
    if (tasiData.length > 0) tasiSeries.setData(tasiData);

    // Responsive resize
    const resizeObserver = new ResizeObserver(entries => {
        for (const entry of entries) {
            chart.applyOptions({ width: entry.contentRect.width });
        }
    });
    resizeObserver.observe(container);

    // Store references
    container._chartInstance = chart;
    container._resizeObserver = resizeObserver;
    perfLwChart = chart;
    perfLwTasiSeries = tasiSeries;

    chart.timeScale().fitContent();
}

// Canvas fallback (kept for graceful degradation)
function renderEquityCurveCanvas(data) {
    const canvas = document.getElementById('equityCurveCanvas');
    const tip = document.getElementById('perfChartTooltip');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const points = data.series || [];
    perfChartState.points = points;

    const wrap = canvas.parentElement;
    const w = Math.max(320, Math.floor((wrap?.clientWidth || 860) - 12));
    const h = 330;
    canvas.width = w;
    canvas.height = h;
    ctx.clearRect(0, 0, w, h);
    if (points.length < 2) return;

    const pad = { top: 20, left: 54, right: 18, bottom: 28 };
    const cW = w - pad.left - pad.right;
    const cH = h - pad.top - pad.bottom;
    const values = points.flatMap(p => [Number(p.xmore || 0), Number(p.tasi || 0)]);
    const min = Math.min(...values, 0) - 0.8;
    const max = Math.max(...values, 0) + 0.8;
    const range = Math.max(1, max - min);
    const toX = i => pad.left + (i / (points.length - 1)) * cW;
    const toY = v => pad.top + (1 - ((v - min) / range)) * cH;

    ctx.strokeStyle = 'rgba(127,127,127,0.25)';
    for (let i = 0; i < 5; i++) {
        const y = pad.top + (i / 4) * cH;
        ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(w - pad.right, y); ctx.stroke();
    }

    if (perfChartState.showDrawdown) {
        let peak = -Infinity;
        ctx.fillStyle = 'rgba(220, 38, 38, 0.08)';
        for (let i = 0; i < points.length; i++) {
            const cur = Number(points[i].xmore || 0);
            if (cur > peak) peak = cur;
            if (cur < peak) {
                const x = toX(i);
                const y1 = toY(peak);
                const y2 = toY(cur);
                ctx.fillRect(x - 1, Math.min(y1, y2), 2, Math.abs(y2 - y1));
            }
        }
    }

    if (perfChartState.showBenchmark) {
        ctx.strokeStyle = '#9ca3af';
        ctx.lineWidth = 2;
        ctx.setLineDash([5, 4]);
        ctx.beginPath();
        points.forEach((p, i) => i ? ctx.lineTo(toX(i), toY(Number(p.tasi || 0))) : ctx.moveTo(toX(i), toY(Number(p.tasi || 0))));
        ctx.stroke();
        ctx.setLineDash([]);
    }

    ctx.strokeStyle = '#16a34a';
    ctx.lineWidth = 2.4;
    ctx.beginPath();
    points.forEach((p, i) => i ? ctx.lineTo(toX(i), toY(Number(p.xmore || 0))) : ctx.moveTo(toX(i), toY(Number(p.xmore || 0))));
    ctx.stroke();

    const move = (ev) => {
        const rect = canvas.getBoundingClientRect();
        const mx = ev.clientX - rect.left;
        let idx = Math.round(((mx - pad.left) / cW) * (points.length - 1));
        idx = Math.max(0, Math.min(points.length - 1, idx));
        const p = points[idx];
        if (!tip || !p) return;
        tip.style.display = 'block';
        tip.style.left = `${Math.min(w - 170, Math.max(8, mx + 10))}px`;
        tip.style.top = '10px';
        tip.innerHTML = `Xmore: ${Number(p.xmore).toFixed(2)}%<br>TASI: ${Number(p.tasi).toFixed(2)}%<br>Alpha: ${Number(p.alpha).toFixed(2)}%`;
    };
    canvas.onmousemove = move;
    canvas.onmouseleave = () => { if (tip) tip.style.display = 'none'; };
}

async function loadMorePredictions() {
    perfHistoryPage += 1;
    await loadPerformanceDashboard();
}

async function showAuditLog() {
    const triggerBtn = document.activeElement;
    const data = await fetch('/api/performance-v2/audit?limit=80').then(r => r.json()).catch(() => ({ audit_entries: [] }));
    const modal = document.createElement('div');
    modal.className = 'perf-modal-overlay';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.setAttribute('aria-labelledby', 'auditModalTitle');
    modal.onclick = (e) => {
        if (e.target === modal) {
            modal.remove();
            if (triggerBtn) triggerBtn.focus();
        }
    };
    // Close on Escape (Upgrade 7)
    modal.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            modal.remove();
            if (triggerBtn) triggerBtn.focus();
        }
    });
    modal.innerHTML = `<div class="perf-modal">
        <button class="perf-modal-close" onclick="this.closest('.perf-modal-overlay').remove()" aria-label="Close">&times;</button>
        <h3 id="auditModalTitle">${pt('auditTitle')}</h3>
        <div class="perf-table-wrapper"><table class="perf-table"><thead><tr><th>${pt('auditWhen')}</th><th>${pt('auditTable')}</th><th>${pt('auditRecord')}</th><th>${pt('auditField')}</th><th>${pt('auditOld')}</th><th>${pt('auditNew')}</th></tr></thead>
        <tbody>${(data.audit_entries || []).map(e => `<tr><td>${e.changed_at || '-'}</td><td>${e.table_name || '-'}</td><td>${e.record_id || '-'}</td><td>${e.field_changed || '-'}</td><td>${e.old_value || '-'}</td><td>${e.new_value || '-'}</td></tr>`).join('') || `<tr><td colspan="6">${pt('auditNoEntries')}</td></tr>`}</tbody></table></div>
    </div>`;
    document.body.appendChild(modal);
    // Focus the close button (Upgrade 7)
    const closeBtn = modal.querySelector('.perf-modal-close');
    if (closeBtn) closeBtn.focus();
}

document.addEventListener('DOMContentLoaded', () => {
    const perfTab = document.querySelector('[data-tab="performance"]');
    if (perfTab) perfTab.addEventListener('click', () => setTimeout(loadPerformanceDashboard, 60));
});

