// ============================================
// Xmore — AI Stock Prediction Dashboard
// Phase 1 Upgrade: Performance Dashboard, TradingView, Consensus, Compliance
// ============================================

// Global error handler — surface JS errors visibly for debugging
window.onerror = function (msg, url, line, col, error) {
    console.error('Global error:', msg, url, line, col, error);
    const el = document.getElementById('predictions');
    if (el) {
        const p = document.createElement('p');
        p.className = 'error-message';
        p.textContent = `JS Error: ${msg} (line ${line})`;
        el.innerHTML = '';
        el.appendChild(p);
    }
};

const API_URL = '/api';

// Shared HTML escaping utility
function escapeHtml(value) {
    return String(value || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

// ============================================
// UPGRADE 1: ANIMATED NUMBER COUNTERS (CountUp.js)
// ============================================

function animateValue(elementId, endVal, options = {}) {
    const el = document.getElementById(elementId);
    if (!el) return;
    // Skip if already animated with same value
    if (el.getAttribute('data-animated') === String(endVal)) return;

    const defaults = {
        duration: 1.8,
        useGrouping: true,
        decimal: '.',
        separator: ',',
        ...options
    };
    if (typeof countUp !== 'undefined' && countUp.CountUp) {
        const counter = new countUp.CountUp(elementId, endVal, defaults);
        if (!counter.error) {
            counter.start();
        } else {
            el.textContent = formatAnimatedValue(endVal, defaults);
        }
    } else {
        el.textContent = formatAnimatedValue(endVal, defaults);
    }
    el.setAttribute('data-animated', String(endVal));
}

function formatAnimatedValue(val, opts) {
    let str = Number(val).toFixed(opts.decimalPlaces || 0);
    if (opts.prefix) str = opts.prefix + str;
    if (opts.suffix) str = str + opts.suffix;
    return str;
}

function pulseMetric(elementId) {
    const el = document.getElementById(elementId);
    if (el) {
        el.classList.remove('updated');
        void el.offsetWidth; // force reflow
        el.classList.add('updated');
    }
}

// ============================================
// UPGRADE 2: TOAST NOTIFICATION SYSTEM (Notyf)
// ============================================

let notyf = null;

function initNotyf() {
    if (typeof Notyf === 'undefined') return;
    notyf = new Notyf({
        duration: 4000,
        position: { x: 'right', y: 'top' },
        dismissible: true,
        ripple: true,
        types: [
            {
                type: 'info',
                background: 'var(--accent, #667eea)',
                icon: { className: 'notyf-info-icon', tagName: 'span', text: '\u2139' }
            },
            {
                type: 'warning',
                background: '#f59e0b',
                icon: { className: 'notyf-warn-icon', tagName: 'span', text: '\u26A0' }
            }
        ]
    });
}

function showToast(type, message) {
    if (!notyf) initNotyf();
    if (!notyf) { console.log(`[Toast ${type}] ${message}`); return; }
    if (type === 'success') notyf.success(message);
    else if (type === 'error') notyf.error(message);
    else notyf.open({ type: type, message: message });
}

// ============================================
// UPGRADE 4: IMPROVED SKELETON LOADING
// ============================================

const SKELETON_TEMPLATES = {
    predictions: `
        <div class="skeleton-shimmer skeleton-text long"></div>
        ${'<div class="skeleton-shimmer skeleton-card"></div>'.repeat(5)}
    `,
    performance: `
        <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px">
            ${'<div class="skeleton-shimmer skeleton-metric"></div>'.repeat(4)}
        </div>
        <div class="skeleton-shimmer skeleton-chart"></div>
        ${'<div class="skeleton-shimmer skeleton-row"></div>'.repeat(4)}
    `,
    trades: `${'<div class="skeleton-shimmer skeleton-card"></div>'.repeat(3)}`,
    results: `${('<div class="skeleton-shimmer skeleton-text short"></div><div class="skeleton-shimmer skeleton-row"></div><div class="skeleton-shimmer skeleton-row"></div>').repeat(4)}`,
    prices: `${'<div class="skeleton-shimmer skeleton-row"></div>'.repeat(6)}`,
    consensus: `
        <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px">
            ${'<div class="skeleton-shimmer skeleton-metric"></div>'.repeat(4)}
        </div>
        ${'<div class="skeleton-shimmer skeleton-card"></div>'.repeat(3)}
    `,
    briefing: `
        <div class="skeleton-shimmer skeleton-card"></div>
        <div class="skeleton-shimmer skeleton-card"></div>
        <div class="skeleton-shimmer skeleton-card"></div>
    `,
};

function showSkeleton(containerId, type) {
    const el = document.getElementById(containerId);
    if (el && SKELETON_TEMPLATES[type]) {
        el.innerHTML = SKELETON_TEMPLATES[type];
        el.setAttribute('aria-busy', 'true');
    }
}

function clearSkeleton(containerId) {
    const el = document.getElementById(containerId);
    if (el) el.setAttribute('aria-busy', 'false');
}

// ============================================
// UPGRADE 6: EMPTY STATE ILLUSTRATIONS
// ============================================

function renderEmptyState(containerId, icon, titleKey, subtitleKey, ctaKey, ctaAction) {
    const container = document.getElementById(containerId);
    if (!container) return;

    container.innerHTML = `
        <div class="empty-state">
            <div class="empty-state-icon">${icon}</div>
            <h3 data-i18n="${titleKey}">${t(titleKey)}</h3>
            <p class="empty-state-desc" data-i18n="${subtitleKey}">${t(subtitleKey)}</p>
            ${ctaKey ? `<button class="btn btn-primary empty-state-cta" onclick="${ctaAction}" data-i18n="${ctaKey}">${t(ctaKey)}</button>` : ''}
        </div>
    `;
}

// ============================================
// DARK MODE SUPPORT
// ============================================

let currentTheme = localStorage.getItem('theme') ||
    (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');

function applyTheme() {
    document.documentElement.setAttribute('data-theme', currentTheme);
    try { updateThemeButton(); } catch (e) { /* TRANSLATIONS not ready yet */ }
}

function updateThemeButton() {
    const themeBtn = document.getElementById('themeBtn');
    if (themeBtn) {
        const tooltipKey = currentTheme === 'dark' ? 'lightMode' : 'darkMode';
        const tooltip = (typeof t === 'function') ? t(tooltipKey) :
            (currentTheme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode');
        themeBtn.title = tooltip;
    }
}

function toggleTheme() {
    currentTheme = currentTheme === 'light' ? 'dark' : 'light';
    localStorage.setItem('theme', currentTheme);
    applyTheme();
    // Rebuild TradingView widgets with new theme
    loadTradingViewTicker();
    // Update Lightweight Charts theme (Upgrade 3)
    const chartContainer = document.getElementById('equityCurveChartContainer');
    if (chartContainer && chartContainer._chartInstance) {
        const isDark = currentTheme === 'dark';
        chartContainer._chartInstance.applyOptions({
            layout: {
                background: { type: 'solid', color: isDark ? '#1a1a2e' : '#ffffff' },
                textColor: isDark ? '#d1d5db' : '#374151',
            },
            grid: {
                vertLines: { color: isDark ? '#2d2d44' : '#f0f0f0' },
                horzLines: { color: isDark ? '#2d2d44' : '#f0f0f0' },
            },
        });
    }
}

// Apply theme CSS immediately (prevents flash); button tooltip set later in applyLanguage()
applyTheme();

// ============================================
// MOBILE MENU (640px and below)
// ============================================

function initMobileMenu() {
    const menuBtn = document.getElementById('mobileMenuBtn');
    const menuDropdown = document.getElementById('mobileMenuDropdown');
    const menuItems = document.querySelectorAll('.mobile-menu-item');

    if (!menuBtn || !menuDropdown) return;

    // Toggle menu on button click
    menuBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        const isActive = menuDropdown.classList.contains('active');
        if (isActive) {
            menuDropdown.classList.remove('active');
            menuBtn.classList.remove('active');
            menuBtn.setAttribute('aria-expanded', 'false');
            menuDropdown.setAttribute('aria-hidden', 'true');
        } else {
            menuDropdown.classList.add('active');
            menuBtn.classList.add('active');
            menuBtn.setAttribute('aria-expanded', 'true');
            menuDropdown.setAttribute('aria-hidden', 'false');
            // Focus first menu item
            menuItems[0]?.focus();
        }
    });

    // Close menu when a link is clicked
    menuItems.forEach(item => {
        item.addEventListener('click', () => {
            menuDropdown.classList.remove('active');
            menuBtn.classList.remove('active');
            menuBtn.setAttribute('aria-expanded', 'false');
            menuDropdown.setAttribute('aria-hidden', 'true');
        });
    });

    // Close menu when clicking outside
    document.addEventListener('click', (e) => {
        if (!menuBtn.contains(e.target) && !menuDropdown.contains(e.target)) {
            menuDropdown.classList.remove('active');
            menuBtn.classList.remove('active');
            menuBtn.setAttribute('aria-expanded', 'false');
            menuDropdown.setAttribute('aria-hidden', 'true');
        }
    });

    // Close menu on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            menuDropdown.classList.remove('active');
            menuBtn.classList.remove('active');
            menuBtn.setAttribute('aria-expanded', 'false');
            menuDropdown.setAttribute('aria-hidden', 'true');
        }
    });
}

// Initialize mobile menu when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initMobileMenu);
} else {
    initMobileMenu();
}

// ============================================
// BILINGUAL SUPPORT (English / Arabic)
// ============================================

let currentLang = localStorage.getItem('lang') || 'en';

const TRANSLATIONS = {
    en: {
        // Header
        title: 'Xmore',
        subtitle: 'AI Stock Prediction Dashboard',

        // Stats
        stocksTracked: 'Stocks Tracked',
        totalPredictions: 'Total Predictions',
        overallAccuracy: 'Accuracy',
        latestData: 'Latest Data',

        // Tabs
        tabPredictions: 'Predictions',
        tabBriefing: 'Briefing',
        tabTrades: 'Trades',
        tabPortfolio: 'Portfolio',
        tabWatchlist: 'Watchlist',
        tabPerformance: 'Performance',
        tabResults: 'Results',
        tabPrices: 'Prices',
        predictionsBrief: "Start here: see today's AI signals by stock and scan for bullish, bearish, or neutral direction.",
        watchlistBrief: 'Track the stocks you care about so the app can personalize signals, briefing, and performance for you.',
        performanceBrief: 'Review strategy quality over time, including win rate, drawdown, and benchmark-relative performance.',
        consensusBrief: 'See where multiple agents agree, plus risk filters, to spot the strongest shared setup.',
        resultsBrief: 'Compare past predictions with real outcomes to understand what the model got right or wrong.',
        pricesBrief: 'Check the latest market prices and volume for each tracked stock in one quick table.',
        briefingBrief: 'Use this as your daily summary: key market context, priority signals, and suggested next actions.',
        tradesBrief: 'View executable trade ideas with direction and rationale for the current session.',
        portfolioBrief: 'Monitor open positions, recent trade history, and high-level portfolio health in one place.',

        // Section titles
        latestPredictions: 'Latest Predictions',
        agentPerformance: 'Agent Performance',
        predictionResults: 'Prediction Results',
        latestPrices: 'Latest Stock Prices',
        performanceOverview: 'Performance Overview',
        agentAccuracy: 'Agent Accuracy',
        stockPerformance: 'Stock Performance',
        monthlyTrend: 'Monthly Accuracy Trend',

        // Table headers
        stock: 'Stock',
        agent: 'Agent',
        signal: 'Signal',
        prediction: 'Signal',
        date: 'Date',
        totalPreds: 'Total Predictions',
        correct: 'Correct',
        accuracy: 'Accuracy',
        closePrice: 'Close Price',
        volume: 'Volume',
        actualOutcome: 'Actual',
        priceChange: 'Change %',
        result: 'Result',
        targetDate: 'Target Date',
        avgReturn: 'Avg Return',

        // Signals (Task 6: from predictions to signals)
        up: 'Bullish',
        down: 'Bearish',
        hold: 'Neutral',
        flat: 'Neutral',

        // Sentiment
        sentiment: 'Sentiment',
        bullish: 'Bullish',
        neutral: 'Neutral',
        bearish: 'Bearish',
        noSentiment: 'N/A',

        // Consensus
        consensus: 'Consensus',
        agentsAgree: 'agents agree',
        unanimous: 'Unanimous',

        // Performance
        directionalAccuracy: 'Directional Accuracy',
        totalSignals: 'Total Signals',
        winRateBuy: 'Win Rate (Buy)',
        winRateSell: 'Win Rate (Sell)',
        avgReturnPerSignal: 'Avg Return/Signal',
        maxDrawdown: 'Max Drawdown',
        accuracyDefinition: 'Directional Accuracy: Percentage of predictions where the predicted direction (UP/DOWN) matched the actual 5-day price movement exceeding ±0.5% threshold.',
        agentHistoryBadge: 'correct historically',

        // Messages
        noPredictions: 'No predictions available yet. Signals are generated daily after market close.',
        noPerformance: 'Performance tracking will begin once predictions have been evaluated.',
        noEvaluations: 'No prediction results yet. Results will appear after predictions are evaluated.',
        noPrices: 'Price data is being collected. Please check back later.',
        errorPredictions: 'Unable to load predictions. Please try refreshing.',
        errorPerformance: 'Unable to load performance data.',
        errorEvaluations: 'Unable to load prediction results.',
        errorPrices: 'Unable to load price data.',
        noDetailedPerformance: 'Detailed performance data will be available after prediction evaluation.',

        // Buttons
        refreshData: 'Refresh Data',
        refreshing: 'Refreshing...',

        // Search
        searchPlaceholder: 'Search by stock symbol or company name...',
        snapshotAlpha30d: '30-Day Alpha vs EGX30',
        snapshotSharpe30d: 'Sharpe Ratio (30D)',
        snapshotMaxDd30d: 'Max Drawdown (30D)',
        snapshotWinRate30d: 'Rolling Win Rate (30D)',
        snapshotTrades: 'Total Live Trades',
        marketRegime: 'Market Regime',
        signalMix30d: '30d signals',
        viewFullAnalysis: 'Full Analysis →',
        consensusSignal: 'Consensus Signal',
        agreement: 'Agreement',
        recentAccuracySymbol: 'Recent Accuracy',
        whySignal: 'Why This Signal?',
        expandDetails: 'Details',
        conf: 'Confidence',
        trend: 'Trend',
        momentum: 'Momentum',
        volumeState: 'Volume',
        sentimentState: 'Sentiment',
        agentAgreement: 'Agent agreement',
        tooltipAlpha: 'Average 1-day alpha in the latest 30-day live window versus EGX30.',
        tooltipSharpe: 'Risk-adjusted return quality in the latest 30-day live window.',
        tooltipMaxDd: 'Largest peak-to-trough decline in cumulative returns over 30 days.',
        tooltipWinRate: 'Share of correct resolved live predictions over the latest 30 days.',
        tooltipTrades: 'Resolved live predictions included in public metrics. Target: 100+.',

        // Language
        switchLang: 'عربي',

        // Theme
        lightMode: 'Switch to light mode',
        darkMode: 'Switch to dark mode',

        // Terms
        termsOfService: 'Terms of Service',

        // Consensus tab
        tabConsensus: 'Consensus',
        consensusTitle: 'Signal Consensus',
        bullCase: 'Bull Case',
        bearCase: 'Bear Case',
        riskAction: 'Risk',
        conviction: 'Conviction',
        riskPassed: 'Passed',
        riskFlagged: 'Flagged',
        riskBlocked: 'Blocked',
        riskDowngraded: 'Downgraded',
        totalStocks: 'Total Stocks',
        avgRisk: 'Avg Risk',
        noConsensus: 'No consensus data available yet. Run the prediction pipeline first.',
        errorConsensus: 'Unable to load consensus data.',
        convictionVeryHigh: 'Very High',
        convictionHigh: 'High',
        convictionModerate: 'Moderate',
        convictionLow: 'Low',
        convictionBlocked: 'Blocked',
        scoringModeLabel: 'Score Mode',
        scoringModeXmoreNative: 'Xmore (0–1)',
        scoringModeStandard100: 'Score (0–100)',
        scoringModeLetterGrade: 'Grade',
        scoringModeStars: 'Stars',
        scoringModeSignalTier: 'Tier',
        scoringModeConviction: 'Conviction',
        scoringPanelTitle: 'Investor Scoring',
        scoringComposite: 'Composite Score',
        scoringComponents: 'Components',
        scoringConsensus: 'Consensus',
        scoringExecution: 'Execution',
        scoringRegime: 'Regime',
        scoringMomentum: 'Momentum',
        scoringMeetsThreshold: 'Actionable',
        scoringNoData: 'No scored signals yet.',
        riskWarnings: 'Risk Warnings',
        agentSignals: 'Agent Signals',
        yourWatchlist: 'Your Watchlist',
        allPredictions: 'All EGX Predictions',
        followStocksPrompt: 'Follow stocks from the Watchlist tab to see personalized data here.',
        noWatchlistLogin: 'Login to see personalized data for your followed stocks.',

        // Toast notifications (Upgrade 2)
        stockAdded: 'Stock added to watchlist',
        stockRemoved: 'Stock removed from watchlist',
        watchlistFull: 'Watchlist is full (max 30 stocks)',
        loadError: 'Failed to load data. Please try again.',
        dataRefreshed: 'Data updated successfully',
        minTradesWarning: 'Performance tracking begins after 100 trades',
        langSwitched: 'Switched to English',

        // Empty states (Upgrade 6)
        emptyPredictions: 'No Predictions Yet',
        emptyPredictionsDesc: 'Signals are generated daily after market close. Check back soon.',
        emptyTrades: 'No Trade History',
        emptyTradesDesc: 'Trade recommendations will appear here once the system generates them.',
        emptyPortfolio: 'No Open Positions',
        emptyPortfolioDesc: 'Open positions will show here after executing trade recommendations.',
        viewTrades: 'View Trades',
        emptyResults: 'No Results Yet',
        emptyResultsDesc: 'Results will appear after predictions have been evaluated against actual outcomes.',

        // Accessibility (Upgrade 7)
        skipToContent: 'Skip to content',

        // Forecasts
        tabForecasts: 'Forecasts',
        forecastsBrief: 'Track saved forecast portfolios and monitor actual vs. predicted performance.',

        // Rates tab
        tabRates: 'Rates',
        ratesBrief: 'Live USD/EGP exchange rate, gold prices, and 30-day history charts.',
        ratesHistoryTitle: '30-Day History',

        // Alerts
        alertsTitle: 'Price Alerts',
        alertsHint: 'Get notified when a stock crosses your target price.',
        alertAbove: 'Above ↑',
        alertBelow: 'Below ↓',

        // Comparison
        compModalTitle: 'Stock Comparison',
        compMetric: 'Metric',
        compSignal: 'Signal',
        compScore: 'Xmore Score',
        compConviction: 'Conviction',
        compConfidence: 'Confidence',
        compAgentsAgree: 'Agents Agree',
        compBullScore: 'Bull Score',
        compBearScore: 'Bear Score',
        compPrice: 'Price (EGP)',
        compDayChange: 'Day Change',
        compVolume: 'Volume',
        compBrief: 'AI Brief',

        // Portfolio totals
        ptlCostLabel: 'Invested (EGP)',
        ptlValueLabel: 'Market Value (EGP)',
        ptlPnlLabel: 'P&L (EGP)',
        ptlRetLabel: 'Return %',

        // Multi-horizon
        multiHorizonTitle: 'Signal Accuracy by Horizon',
        mhSymbol: 'Symbol',
        mhHorizon: 'Horizon',
        mhPreds: 'Predictions',
        mhCorrect: 'Correct',
        mhAccuracy: 'Accuracy',
        mhAvgChange: 'Avg Change',

        // Time Machine
        tabTimeMachine: 'Time Machine',
        timemachineBrief: "Enter an amount and a past date to see what your investment would be worth today if you had followed Xmore's recommendations.",
        tmTitle: 'What If You Had Invested?',
        tmSubtitle: "See how much your money would be worth if you had followed Xmore's best recommendations.",
        tmAmountLabel: 'Investment Amount (EGP)',
        tmDateLabel: 'Starting From',
        tm3Months: '3 months ago',
        tm6Months: '6 months ago',
        tm12Months: '1 year ago',
        tmMaxRange: 'Max (2 years)',
        tmSimulate: 'Simulate',
        tmYouInvested: 'You invested',
        tmWouldBeWorth: 'Would be worth today',
        tmAlpha: 'Alpha vs EGX30',
        tmVsEGX30: 'outperformance',
        tmAnnualized: 'Annualized Return',
        tmTotalTrades: 'Total Trades',
        tmWinRate: 'Win Rate',
        tmMaxDrawdown: 'Max Drawdown',
        tmSharpe: 'Sharpe Ratio',
        tmEquityCurve: 'Your Money Over Time',
        tmMonthlyBreakdown: 'Monthly Returns',
        tmMonth: 'Month',
        tmTopTrades: 'Best Trades',
        tmWorstTrades: 'Worst Trades',
        tmTimeline: 'Investment Timeline',
        tmCalculating: 'Traveling through time...',
        tmAnalyzing: 'Fetching live market data & running simulation',
        tmLoadingWarning: 'This may take 30–60 seconds.',
        tmDisclaimer: "This simulation uses real EGX price data from Yahoo Finance and applies Xmore's signal logic retroactively. Past performance does not guarantee future results. This is not financial advice.",
        tmProfit: 'Profit',
        tmLoss: 'Loss',
        tmBought: 'Bought',
        tmSold: 'Sold',
        tmHeldFor: 'Held for',
        tmDays: 'days',
        tmInvalidAmount: 'Amount must be between 5,000 and 10,000,000 EGP',
        tmSelectDate: 'Please select a start date',
        tmErrorGeneric: 'Simulation failed. Please try again.',
        tmTryDifferent: 'Try a different date range or amount.',
        tmNoDataHint: 'Could not complete the simulation. Try a different date range.',
        // ETF cards
        etfEgyptExposure: 'Egypt Exposure',
        etfName: 'Name',
        etfExchange: 'Exchange',
        etfPrice: 'Price',
        etfChange: 'Change',
        etfNav: 'NAV',
        etfPremDisc: 'Prem/Disc',
        etfHoldings: 'Holdings',
        etfIssuer: 'Issuer',
        etfRet3m: '3M Return',
        etfUnderlying: 'Underlying',
        etfLiquidity: 'Liquidity',
        etfNoData: 'No data yet',
        etfNoDataSub: 'Data is collected automatically after market close',
        etfNoResults: 'No results for',
        etfLoadError: 'Could not load fund data.',
        etfHoldingsTitle: 'Holdings',
        etfNoHoldings: 'No holdings data available.',
        // Future tab
        tmSubPastLabel: '⏮ Past',
        tmSubFutureLabel: '⏭ Future',
        fcTitle: 'Future Forecast',
        fcSubtitle: 'AI picks the best EGX30 stock for your horizon. 5,000 Monte Carlo paths.',
        fcModeAuto: '🤖 AI picks for me',
        fcModeManual: '🔍 I pick manually',
        fcModePortfolio: '📁 My Portfolios',
        pf_title: 'My Forecast Portfolios',
        pf_create: '+ New Portfolio',
        fcEndDateLabel: 'Target Date',
        fcEndDateHint: 'Up to 30 days from today — AI picks the best EGX30 stock for you',
        fcSymbolLabel: 'Stock Symbol',
        fcHorizonLabel: 'Time Horizon',
        fc1Month: '1 month',
        fc2Months: '2 months',
        fc3Months: '3 months',
        fc6Months: '6 months',
        fc1Year: '1 year',
        fc2Years: '2 years',
        pf_name_label: 'Portfolio Name',
        pf_save: 'Save Portfolio',
        pf_cancel: 'Cancel',
        fcRunBtnManual: 'Run Forecast',
        fcSelectSymbol: 'Please select a stock.',
        fcScenarioLabel: 'Scenario',
        fcBase: 'Base',
        fcBaseHint: 'Historical drift',
        fcBull: 'Bull',
        fcBullHint: '+2% drift boost',
        fcBear: 'Bear',
        fcBearHint: '−2% drift drag',
        fcRunBtn: 'Find Best Stock & Forecast',
        fcSelectDate: 'Please pick a target date.',
        fcChosenBy: 'AI Best Pick',
        fcSeeRanking: 'See ranking ▼',
        fcHideRanking: 'Hide ▲',
        fcExpectedValue: 'Expected Value',
        fcProbProfit: 'Probability of Profit',
        fcVolatility: 'Annual Volatility',
        fcWorstCase: 'Worst Case (5th pct)',
        fcMedian: 'Median',
        fcBestCase: 'Best Case (95th pct)',
        fcBandChartTitle: 'Projected Portfolio Value',
        fcHistTitle: 'Distribution of Final Values',
        fcHistSub: '5,000 simulated outcomes. Green = profit, Red = loss.',
        fcDrift: 'Historical Drift',
        fcScenarioUsed: 'Scenario Adj.',
        fcDataPoints: 'Data Points',
        fcSimCount: 'Simulations',
        fcCalculating: 'Scanning EGX30 stocks & running 5,000 Monte Carlo paths…',
        fcAnalyzing: 'Computing GBM parameters — this takes ~30s',
        fcDisclaimer: 'This projection is model-based and does not constitute financial advice. Results depend on historical statistical assumptions and market conditions.',
        fcRerun: 'Modify & Re-run \u2191',
        fcModeAutoDesc: 'Auto-selects the best EGX30 stock for your date',
        fcModeManualDesc: 'Pick 1\u201320 stocks and compare forecasts',
        fcModePortfolioDesc: 'Run forecast on your saved portfolios',
        fcStage1: 'Fetching price history...',
        fcStage1Sub: 'Loading historical EGX data',
        fcStage2Auto: 'Scanning EGX30 stocks...',
        fcStage2Manual: 'Computing model parameters...',
        fcStage2Sub: 'Computing GBM parameters per stock',
        fcStage3: 'Running 5,000 Monte Carlo paths...',
        fcStage3Sub: 'Projecting probabilistic outcomes',
    },
    ar: {
        title: 'إكسمور',
        subtitle: 'لوحة التنبؤات الذكية للأسهم',

        stocksTracked: 'الأسهم المتابعة',
        totalPredictions: 'إجمالي التنبؤات',
        overallAccuracy: 'الدقة',
        latestData: 'آخر تحديث',

        tabPredictions: 'التنبؤات',
        tabBriefing: 'النشرة',
        tabTrades: 'التداول',
        tabPortfolio: 'المحفظة',
        tabWatchlist: 'المتابعة',
        tabPerformance: 'الأداء',
        tabResults: 'النتائج',
        tabPrices: 'الأسعار',
        predictionsBrief: 'ابدأ من هنا: راجع إشارات الذكاء الاصطناعي اليومية لكل سهم (صاعد/هابط/محايد).',
        watchlistBrief: 'تابع الأسهم التي تهمك ليخصص النظام الإشارات والنشرة والأداء لك.',
        performanceBrief: 'تابع جودة الاستراتيجية عبر الوقت، بما في ذلك نسبة الفوز والسحب الأقصى والأداء مقابل المؤشر.',
        consensusBrief: 'اطلع على الأسهم التي يتفق عليها عدة وكلاء مع فلاتر المخاطر لتحديد أقوى الفرص.',
        resultsBrief: 'قارن التوقعات السابقة بالنتائج الفعلية لفهم ما أصابه النظام وما أخطأ فيه.',
        pricesBrief: 'راجع أحدث الأسعار وأحجام التداول للأسهم المتابعة في جدول واحد.',
        briefingBrief: 'استخدمها كملخص يومي: سياق السوق، أولويات الإشارات، والخطوات المقترحة.',
        tradesBrief: 'اطلع على أفكار تداول قابلة للتنفيذ مع الاتجاه والمبرر خلال جلسة اليوم.',
        portfolioBrief: 'راقب المراكز المفتوحة وتاريخ الصفقات ومؤشرات صحة المحفظة في مكان واحد.',

        latestPredictions: 'أحدث التنبؤات',
        agentPerformance: 'أداء الوكلاء',
        predictionResults: 'نتائج التنبؤات',
        latestPrices: 'أحدث أسعار الأسهم',
        performanceOverview: 'نظرة عامة على الأداء',
        agentAccuracy: 'دقة الوكلاء',
        stockPerformance: 'أداء الأسهم',
        monthlyTrend: 'اتجاه الدقة الشهري',

        stock: 'السهم',
        agent: 'الوكيل',
        signal: 'الإشارة',
        prediction: 'الإشارة',
        date: 'التاريخ',
        totalPreds: 'إجمالي التنبؤات',
        correct: 'الصحيحة',
        accuracy: 'الدقة',
        closePrice: 'سعر الإغلاق',
        volume: 'الحجم',
        actualOutcome: 'الفعلي',
        priceChange: 'التغير %',
        result: 'النتيجة',
        targetDate: 'تاريخ الهدف',
        avgReturn: 'متوسط العائد',

        up: 'صاعد',
        down: 'هابط',
        hold: 'محايد',
        flat: 'محايد',

        sentiment: 'المشاعر',
        bullish: 'إيجابي',
        neutral: 'محايد',
        bearish: 'سلبي',
        noSentiment: 'غ/م',

        consensus: 'الإجماع',
        agentsAgree: 'وكلاء يتفقون',
        unanimous: 'إجماع تام',

        directionalAccuracy: 'الدقة الاتجاهية',
        totalSignals: 'إجمالي الإشارات',
        winRateBuy: 'نسبة النجاح (شراء)',
        winRateSell: 'نسبة النجاح (بيع)',
        avgReturnPerSignal: 'متوسط العائد/إشارة',
        maxDrawdown: 'أقصى تراجع',
        accuracyDefinition: 'الدقة الاتجاهية: نسبة التنبؤات التي تطابق فيها الاتجاه المتوقع (صعود/هبوط) مع حركة السعر الفعلية خلال 5 أيام بتجاوز عتبة ±0.5%.',
        agentHistoryBadge: 'صحيح تاريخياً',

        noPredictions: 'لا توجد تنبؤات متاحة. يتم إنشاء الإشارات يومياً بعد إغلاق السوق.',
        noPerformance: 'سيبدأ تتبع الأداء بمجرد تقييم التنبؤات.',
        noEvaluations: 'لا توجد نتائج تنبؤات بعد.',
        noPrices: 'جاري جمع بيانات الأسعار.',
        errorPredictions: 'تعذر تحميل التنبؤات.',
        errorPerformance: 'تعذر تحميل بيانات الأداء.',
        errorEvaluations: 'تعذر تحميل النتائج.',
        errorPrices: 'تعذر تحميل الأسعار.',
        noDetailedPerformance: 'ستتوفر بيانات الأداء التفصيلية بعد تقييم التنبؤات.',

        refreshData: 'تحديث البيانات',
        refreshing: 'جاري التحديث...',

        searchPlaceholder: 'البحث برمز السهم أو اسم الشركة...',
        snapshotAlpha30d: 'ألفا 30 يوم مقابل EGX30',
        snapshotSharpe30d: 'نسبة شارب (30 يوم)',
        snapshotMaxDd30d: 'أقصى تراجع (30 يوم)',
        snapshotWinRate30d: 'نسبة الفوز المتحركة (30 يوم)',
        snapshotTrades: 'إجمالي الصفقات الحية',
        marketRegime: 'نظام السوق',
        signalMix30d: 'إشارات 30 يوم',
        viewFullAnalysis: 'التحليل الكامل →',
        consensusSignal: 'إشارة الإجماع',
        agreement: 'نسبة الاتفاق',
        recentAccuracySymbol: 'الدقة الحديثة',
        whySignal: 'لماذا هذه الإشارة؟',
        expandDetails: 'التفاصيل',
        conf: 'الثقة',
        trend: 'الاتجاه',
        momentum: 'الزخم',
        volumeState: 'الحجم',
        sentimentState: 'المشاعر',
        agentAgreement: 'اتفاق الوكلاء',
        tooltipAlpha: 'متوسط ألفا يومي خلال آخر 30 يوما حيا مقابل EGX30.',
        tooltipSharpe: 'جودة العائد المعدل بالمخاطر خلال آخر 30 يوما حيا.',
        tooltipMaxDd: 'أكبر هبوط من قمة إلى قاع في العائد التراكمي خلال 30 يوما.',
        tooltipWinRate: 'نسبة الإشارات الحية الصحيحة خلال آخر 30 يوما.',
        tooltipTrades: 'التنبؤات الحية المحللة ضمن الإحصاءات العامة. الهدف: 100+.',

        switchLang: 'English',

        lightMode: 'التبديل إلى الوضع الفاتح',
        darkMode: 'التبديل إلى الوضع الداكن',

        termsOfService: 'شروط الخدمة',

        // Consensus tab
        tabConsensus: 'الإجماع',
        consensusTitle: 'إجماع الإشارات',
        bullCase: 'حالة الثور',
        bearCase: 'حالة الدب',
        riskAction: 'المخاطر',
        conviction: 'القناعة',
        riskPassed: 'أُجيز',
        riskFlagged: 'مُعلّم',
        riskBlocked: 'محظور',
        riskDowngraded: 'مُخفّض',
        totalStocks: 'إجمالي الأسهم',
        avgRisk: 'متوسط المخاطر',
        noConsensus: 'لا توجد بيانات إجماع بعد. شغّل خط التنبؤات أولاً.',
        errorConsensus: 'تعذر تحميل بيانات الإجماع.',
        convictionVeryHigh: 'عالية جداً',
        convictionHigh: 'عالية',
        convictionModerate: 'متوسطة',
        convictionLow: 'منخفضة',
        convictionBlocked: 'محظور',
        scoringModeLabel: 'وضع التقييم',
        scoringModeXmoreNative: 'Xmore (0–1)',
        scoringModeStandard100: 'درجة (0–100)',
        scoringModeLetterGrade: 'تقدير',
        scoringModeStars: 'نجوم',
        scoringModeSignalTier: 'مستوى',
        scoringModeConviction: 'اقتناع',
        scoringPanelTitle: 'تقييم المستثمرين',
        scoringComposite: 'الدرجة المركبة',
        scoringComponents: 'المكونات',
        scoringConsensus: 'إجماع',
        scoringExecution: 'تنفيذ',
        scoringRegime: 'النظام',
        scoringMomentum: 'زخم',
        scoringMeetsThreshold: 'قابل للتنفيذ',
        scoringNoData: 'لا توجد إشارات مُقيَّمة بعد.',
        riskWarnings: 'تحذيرات المخاطر',
        agentSignals: 'إشارات الوكلاء',
        yourWatchlist: 'أسهمك المتابعة',
        allPredictions: 'جميع تنبؤات البورصة',
        followStocksPrompt: 'تابع أسهمك من تبويب المتابعة لعرض البيانات المخصصة هنا.',
        noWatchlistLogin: 'سجّل دخولك لعرض بيانات الأسهم التي تتابعها.',

        // Toast notifications (Upgrade 2)
        stockAdded: 'تمت إضافة السهم للمتابعة',
        stockRemoved: 'تم إزالة السهم من المتابعة',
        watchlistFull: 'قائمة المتابعة ممتلئة (الحد الأقصى ٣٠ سهم)',
        loadError: 'فشل تحميل البيانات. حاول مرة أخرى.',
        dataRefreshed: 'تم تحديث البيانات بنجاح',
        minTradesWarning: 'يبدأ تتبع الأداء بعد ١٠٠ توصية',
        langSwitched: 'تم التبديل للعربية',

        // Empty states (Upgrade 6)
        emptyPredictions: 'لا توجد تنبؤات بعد',
        emptyPredictionsDesc: 'يتم إنشاء الإشارات يومياً بعد إغلاق السوق. تحقق مجدداً قريباً.',
        emptyTrades: 'لا يوجد سجل تداول',
        emptyTradesDesc: 'ستظهر توصيات التداول هنا بعد إنشائها بواسطة النظام.',
        emptyPortfolio: 'لا توجد مراكز مفتوحة',
        emptyPortfolioDesc: 'ستظهر المراكز المفتوحة هنا بعد تنفيذ توصيات التداول.',
        viewTrades: 'عرض التوصيات',
        emptyResults: 'لا توجد نتائج بعد',
        emptyResultsDesc: 'ستظهر النتائج بعد تقييم التنبؤات مقابل النتائج الفعلية.',

        // Accessibility (Upgrade 7)
        skipToContent: 'الانتقال إلى المحتوى',

        // Forecasts
        tabForecasts: 'التوقعات',
        forecastsBrief: 'تتبع محافظ التوقعات المحفوظة وقارن الأداء الفعلي مع المتوقع.',

        // Rates tab
        tabRates: 'الأسعار',
        ratesBrief: 'سعر صرف الدولار/الجنيه وأسعار الذهب ورسوم بيانية لـ 30 يوم.',
        ratesHistoryTitle: 'السجل - 30 يوم',

        // Alerts
        alertsTitle: 'تنبيهات الأسعار',
        alertsHint: 'احصل على تنبيه عندما يتجاوز سهم سعرك المستهدف.',
        alertAbove: 'أعلى من ↑',
        alertBelow: 'أقل من ↓',

        // Comparison
        compModalTitle: 'مقارنة الأسهم',
        compMetric: 'المعيار',
        compSignal: 'الإشارة',
        compScore: 'درجة Xmore',
        compConviction: 'القناعة',
        compConfidence: 'الثقة',
        compAgentsAgree: 'توافق الوكلاء',
        compBullScore: 'نقاط الصعود',
        compBearScore: 'نقاط الهبوط',
        compPrice: 'السعر (جنيه)',
        compDayChange: 'تغير اليوم',
        compVolume: 'الحجم',
        compBrief: 'ملخص ذكي',

        // Portfolio totals
        ptlCostLabel: 'المستثمر (جنيه)',
        ptlValueLabel: 'القيمة السوقية (جنيه)',
        ptlPnlLabel: 'الربح/الخسارة (جنيه)',
        ptlRetLabel: 'العائد %',

        // Multi-horizon
        multiHorizonTitle: 'دقة الإشارات حسب الأفق الزمني',
        mhSymbol: 'الرمز',
        mhHorizon: 'الأفق',
        mhPreds: 'التنبؤات',
        mhCorrect: 'الصحيح',
        mhAccuracy: 'الدقة',
        mhAvgChange: 'متوسط التغير',

        // Time Machine
        tabTimeMachine: 'آلة الزمن',
        timemachineBrief: 'أدخل مبلغاً وتاريخاً سابقاً لمعرفة قيمة استثمارك اليوم لو اتبعت توصيات Xmore.',
        tmTitle: 'ماذا لو كنت استثمرت؟',
        tmSubtitle: 'شاهد كم ستكون قيمة أموالك لو اتبعت أفضل توصيات Xmore.',
        tmAmountLabel: 'مبلغ الاستثمار (جنيه)',
        tmDateLabel: 'بدءاً من',
        tm3Months: 'منذ ٣ أشهر',
        tm6Months: 'منذ ٦ أشهر',
        tm12Months: 'منذ سنة',
        tmMaxRange: 'الحد الأقصى (سنتان)',
        tmSimulate: 'محاكاة',
        tmYouInvested: 'لو استثمرت',
        tmWouldBeWorth: 'ستصبح قيمتها اليوم',
        tmAlpha: 'ألفا مقابل EGX30',
        tmVsEGX30: 'تفوق على المؤشر',
        tmAnnualized: 'العائد السنوي',
        tmTotalTrades: 'إجمالي الصفقات',
        tmWinRate: 'نسبة الفوز',
        tmMaxDrawdown: 'أقصى تراجع',
        tmSharpe: 'نسبة شارب',
        tmEquityCurve: 'أموالك عبر الزمن',
        tmMonthlyBreakdown: 'العوائد الشهرية',
        tmMonth: 'الشهر',
        tmTopTrades: 'أفضل الصفقات',
        tmWorstTrades: 'أسوأ الصفقات',
        tmTimeline: 'الجدول الزمني للاستثمار',
        tmCalculating: '...نسافر عبر الزمن',
        tmAnalyzing: 'جلب بيانات السوق الحية وتشغيل المحاكاة',
        tmLoadingWarning: 'قد يستغرق هذا ٣٠ إلى ٦٠ ثانية.',
        tmDisclaimer: 'تستخدم هذه المحاكاة بيانات أسعار البورصة المصرية الحقيقية من Yahoo Finance وتطبق منطق إشارات Xmore بأثر رجعي. الأداء السابق لا يضمن النتائج المستقبلية. هذا ليس نصيحة مالية.',
        tmProfit: 'ربح',
        tmLoss: 'خسارة',
        tmBought: 'شراء',
        tmSold: 'بيع',
        tmHeldFor: 'مدة الاحتفاظ',
        tmDays: 'يوم',
        tmInvalidAmount: 'يجب أن يكون المبلغ بين ٥٬٠٠٠ و ١٠٬٠٠٠٬٠٠٠ جنيه',
        tmSelectDate: 'يرجى تحديد تاريخ البداية',
        tmErrorGeneric: 'فشلت المحاكاة. يرجى المحاولة مرة أخرى.',
        tmTryDifferent: 'جرّب نطاق تاريخ أو مبلغ مختلف.',
        tmNoDataHint: 'تعذّر إكمال المحاكاة. جرّب نطاق تاريخ مختلف.',
        // ETF cards
        etfEgyptExposure: 'تعرّض لمصر',
        etfName: 'الاسم',
        etfExchange: 'البورصة',
        etfPrice: 'السعر',
        etfChange: 'التغير',
        etfNav: 'القيمة الصافية',
        etfPremDisc: 'علاوة/خصم',
        etfHoldings: 'المكونات',
        etfIssuer: 'الجهة المصدرة',
        etfRet3m: 'عائد 3 أشهر',
        etfUnderlying: 'الأصل الأساسي',
        etfLiquidity: 'السيولة',
        etfNoData: 'لا توجد بيانات بعد',
        etfNoDataSub: 'يتم جمع البيانات تلقائياً بعد إغلاق السوق',
        etfNoResults: 'لا توجد نتائج لـ',
        etfLoadError: 'تعذر تحميل بيانات الصناديق.',
        etfHoldingsTitle: 'المكونات',
        etfNoHoldings: 'لا توجد بيانات مكونات.',
        // Future tab
        tmSubPastLabel: '⏮ الماضي',
        tmSubFutureLabel: '⏭ المستقبل',
        fcTitle: 'التوقع المستقبلي',
        fcSubtitle: 'الذكاء الاصطناعي يختار أفضل سهم EGX30 لأفقك الزمني. ٥٬٠٠٠ مسار مونتي كارلو.',
        fcModeAuto: '🤖 الذكاء الاصطناعي يختار لي',
        fcModeManual: '🔍 أختار بنفسي',
        fcModePortfolio: '📁 محافظي',
        pf_title: 'محافظ التوقعات',
        pf_create: '+ محفظة جديدة',
        fcEndDateLabel: 'التاريخ المستهدف',
        fcEndDateHint: 'حتى ٣٠ يوماً من اليوم — الذكاء الاصطناعي يختار أفضل سهم لك',
        fcSymbolLabel: 'رمز السهم',
        fcHorizonLabel: 'الأفق الزمني',
        fc1Month: 'شهر',
        fc2Months: 'شهران',
        fc3Months: '٣ أشهر',
        fc6Months: '٦ أشهر',
        fc1Year: 'سنة',
        fc2Years: 'سنتان',
        pf_name_label: 'اسم المحفظة',
        pf_save: 'حفظ المحفظة',
        pf_cancel: 'إلغاء',
        fcRunBtnManual: 'تشغيل التوقع',
        fcSelectSymbol: 'يرجى اختيار سهم.',
        fcScenarioLabel: 'السيناريو',
        fcBase: 'قاعدي',
        fcBaseHint: 'الانجراف التاريخي',
        fcBull: 'صاعد',
        fcBullHint: '+٢٪ تعزيز',
        fcBear: 'هابط',
        fcBearHint: '−٢٪ ضغط',
        fcRunBtn: 'اختر أفضل سهم وابدأ التوقع',
        fcSelectDate: 'يرجى اختيار تاريخ مستهدف.',
        fcChosenBy: 'اختيار الذكاء الاصطناعي',
        fcSeeRanking: 'رؤية الترتيب ▼',
        fcHideRanking: 'إخفاء ▲',
        fcExpectedValue: 'القيمة المتوقعة',
        fcProbProfit: 'احتمالية الربح',
        fcVolatility: 'التقلب السنوي',
        fcWorstCase: 'أسوأ حالة (الخامس٪)',
        fcMedian: 'الوسيط',
        fcBestCase: 'أفضل حالة (٩٥٪)',
        fcBandChartTitle: 'القيمة المتوقعة للمحفظة',
        fcHistTitle: 'توزيع القيم النهائية',
        fcHistSub: '٥٬٠٠٠ نتيجة محاكاة. أخضر = ربح، أحمر = خسارة.',
        fcDrift: 'الانجراف التاريخي',
        fcScenarioUsed: 'تعديل السيناريو',
        fcDataPoints: 'نقاط البيانات',
        fcSimCount: 'عدد المحاكاة',
        fcCalculating: '...فحص أسهم EGX30 وتشغيل ٥٬٠٠٠ مسار مونتي كارلو',
        fcAnalyzing: 'حساب معاملات GBM — قد يستغرق ~٣٠ ثانية',
        fcDisclaimer: 'هذا التوقع قائم على نموذج رياضي ولا يمثل نصيحة مالية. تعتمد النتائج على افتراضات إحصائية تاريخية وظروف السوق.',
        fcRerun: '\u062a\u0639\u062f\u064a\u0644 \u0648\u0625\u0639\u0627\u062f\u0629 \u0627\u0644\u062a\u0634\u063a\u064a\u0644 \u2191',
        fcModeAutoDesc: '\u064a\u062e\u062a\u0627\u0631 \u062a\u0644\u0642\u0627\u0626\u064a\u0627\u064b \u0623\u0641\u0636\u0644 \u0633\u0647\u0645 EGX30 \u0644\u062a\u0627\u0631\u064a\u062e\u0643',
        fcModeManualDesc: '\u0627\u062e\u062a\u0631 \u0645\u0646 \u0661 \u0625\u0644\u0649 \u0662\u0660 \u0633\u0647\u0645\u0627\u064b \u0648\u0642\u0627\u0631\u0646 \u0627\u0644\u062a\u0648\u0642\u0639\u0627\u062a',
        fcModePortfolioDesc: '\u062a\u0634\u063a\u064a\u0644 \u0627\u0644\u062a\u0648\u0642\u0639 \u0639\u0644\u0649 \u0645\u062d\u0627\u0641\u0638\u0643 \u0627\u0644\u0645\u062d\u0641\u0648\u0638\u0629',
        fcStage1: '...\u062c\u0644\u0628 \u062a\u0627\u0631\u064a\u062e \u0627\u0644\u0623\u0633\u0639\u0627\u0631',
        fcStage1Sub: '\u062a\u062d\u0645\u064a\u0644 \u0628\u064a\u0627\u0646\u0627\u062a EGX \u0627\u0644\u062a\u0627\u0631\u064a\u062e\u064a\u0629',
        fcStage2Auto: '...\u0641\u062d\u0635 \u0623\u0633\u0647\u0645 EGX30',
        fcStage2Manual: '...\u062d\u0633\u0627\u0628 \u0645\u0639\u0627\u0645\u0644\u0627\u062a \u0627\u0644\u0646\u0645\u0648\u0630\u062c',
        fcStage2Sub: '\u062d\u0633\u0627\u0628 \u0645\u0639\u0627\u0645\u0644\u0627\u062a GBM \u0644\u0643\u0644 \u0633\u0647\u0645',
        fcStage3: '...\u062a\u0634\u063a\u064a\u0644 5\u060c000 \u0645\u0633\u0627\u0631 \u0645\u0648\u0646\u062a\u064a \u0643\u0627\u0631\u0644\u0648',
        fcStage3Sub: '\u0627\u0633\u062a\u0634\u0631\u0627\u0641 \u0627\u0644\u0646\u062a\u0627\u0626\u062c \u0627\u0644\u0627\u062d\u062a\u0645\u0627\u0644\u064a\u0629',
    }
};

// Agent info with bilingual support
const AGENT_INFO = {
    'MA_Crossover_Agent': {
        en: { name: 'Moving Average Trend', description: 'Analyzes short and long-term moving average crossovers to identify trend changes.' },
        ar: { name: 'اتجاه المتوسط المتحرك', description: 'يحلل تقاطعات المتوسطات المتحركة لتحديد تغيرات الاتجاه.' }
    },
    'ML_RandomForest': {
        en: { name: 'AI Price Predictor', description: 'Machine learning model using 40+ technical indicators to predict price movements.' },
        ar: { name: 'متنبئ الأسعار الذكي', description: 'نموذج تعلم آلي يستخدم 40+ مؤشر فني للتنبؤ بحركات الأسعار.' }
    },
    'RSI_Agent': {
        en: { name: 'Momentum Indicator', description: 'Uses Relative Strength Index to detect overbought/oversold conditions.' },
        ar: { name: 'مؤشر الزخم', description: 'يستخدم مؤشر القوة النسبية لاكتشاف حالات الشراء/البيع المفرط.' }
    },
    'Volume_Spike_Agent': {
        en: { name: 'Volume Analysis', description: 'Monitors unusual volume activity to predict potential price movements.' },
        ar: { name: 'تحليل الحجم', description: 'يراقب نشاط الحجم غير المعتاد للتنبؤ بتحركات الأسعار.' }
    },
    'Consensus': {
        en: { name: 'Consensus Signal', description: 'Weighted vote across all agents based on historical accuracy.' },
        ar: { name: 'إشارة الإجماع', description: 'تصويت مرجح عبر جميع الوكلاء بناءً على الدقة التاريخية.' }
    },
};

// Get translation
function t(key) {
    return TRANSLATIONS[currentLang]?.[key] || TRANSLATIONS['en']?.[key] || key;
}

function getAgentDisplayName(agentName) {
    return AGENT_INFO[agentName]?.[currentLang]?.name || AGENT_INFO[agentName]?.en?.name || agentName;
}

function getAgentDescription(agentName) {
    return AGENT_INFO[agentName]?.[currentLang]?.description || AGENT_INFO[agentName]?.en?.description || '';
}

// ============================================
// WATCHLIST FILTER CACHE
// ============================================

let userWatchlistSymbols = new Set();
let watchlistCacheFetched = false;

async function fetchUserWatchlistSymbols() {
    if (typeof currentUser === 'undefined' || !currentUser) {
        userWatchlistSymbols = new Set();
        watchlistCacheFetched = false;
        return;
    }
    if (watchlistCacheFetched) return;
    try {
        const res = await fetch('/api/watchlist', { credentials: 'include' });
        if (res.ok) {
            const data = await res.json();
            userWatchlistSymbols = new Set((data.watchlist || []).map(w => w.symbol));
        }
    } catch (e) {
        console.warn('Failed to fetch watchlist for filtering:', e);
    }
    watchlistCacheFetched = true;
}

function resetWatchlistCache() {
    watchlistCacheFetched = false;
    userWatchlistSymbols = new Set();
}

function isLoggedIn() {
    return typeof currentUser !== 'undefined' && currentUser;
}

function getWatchlistEmptyHtml() {
    if (!isLoggedIn()) {
        return `<p class="no-data">${t('noWatchlistLogin')}</p>`;
    }
    return `<div class="no-data watchlist-prompt">
        <p>${t('followStocksPrompt')}</p>
        <button class="wl-add-btn" onclick="document.querySelector('[data-tab=watchlist]').click()">${t('tabWatchlist')}</button>
    </div>`;
}

// ============================================
// LANGUAGE SWITCH
// ============================================

async function switchLanguage() {
    currentLang = currentLang === 'en' ? 'ar' : 'en';
    localStorage.setItem('lang', currentLang);
    applyLanguage();
    showToast('info', t('langSwitched'));
    await loadSentiment();
    loadStats();
    loadPredictions();
    loadConsensus();
    loadScoringPanel();
    loadPerformance();
    loadPerformanceDetailed();
    loadEvaluations();
    loadPrices();
    loadGlobalSnapshotBar();
    loadRegimeBanner();
}

function applyLanguage() {
    const isArabic = currentLang === 'ar';

    document.documentElement.dir = isArabic ? 'rtl' : 'ltr';
    document.documentElement.lang = currentLang;
    document.body.classList.toggle('rtl', isArabic);

    // Update page title
    document.title = isArabic ? 'إكسمور — لوحة التنبؤات الذكية للأسهم' : 'Xmore — AI Stock Prediction Dashboard';

    const title = document.querySelector('header h1');
    const subtitle = document.querySelector('.subtitle');
    if (title) title.textContent = t('title');
    if (subtitle) subtitle.textContent = t('subtitle');

    // Stat labels
    document.querySelectorAll('.stat-label').forEach((el, index) => {
        const labels = ['stocksTracked', 'totalPredictions', 'overallAccuracy', 'latestData'];
        if (labels[index]) el.textContent = t(labels[index]);
    });

    // Tab buttons
    const tabs = ['tabPredictions', 'tabBriefing', 'tabTrades', 'tabPortfolio', 'tabForecasts', 'tabWatchlist', 'tabConsensus', 'tabPerformance', 'tabResults', 'tabPrices', 'tabTimeMachine', 'tabRates'];
    tabs.forEach(id => {
        const btn = document.getElementById(id);
        if (btn) btn.textContent = t(id);
    });

    // Performance section titles
    const perfAgentTitle = document.getElementById('perfAgentTitle');
    if (perfAgentTitle) perfAgentTitle.textContent = t('agentAccuracy');
    const perfStockTitle = document.getElementById('perfStockTitle');
    if (perfStockTitle) perfStockTitle.textContent = t('stockPerformance');
    const perfMonthlyTitle = document.getElementById('perfMonthlyTitle');
    if (perfMonthlyTitle) perfMonthlyTitle.textContent = t('monthlyTrend');
    const resultsTitle = document.getElementById('resultsTitle');
    if (resultsTitle) resultsTitle.textContent = t('tabResults');
    const briefIds = ['predictionsBrief', 'watchlistBrief', 'performanceBrief', 'consensusBrief', 'resultsBrief', 'pricesBrief', 'briefingBrief', 'tradesBrief', 'portfolioBrief', 'forecastsBrief', 'timemachineBrief', 'ratesBrief'];
    briefIds.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.textContent = t(id);
    });

    // Accuracy definition tooltip
    const accDef = document.getElementById('accuracyDefinition');
    if (accDef) accDef.textContent = t('accuracyDefinition');

    // Search placeholder
    const searchInput = document.getElementById('predictionsSearch');
    if (searchInput) searchInput.placeholder = t('searchPlaceholder');

    // Refresh button
    const refreshBtn = document.getElementById('refreshBtn');
    if (refreshBtn && !refreshBtn.disabled) refreshBtn.textContent = t('refreshData');

    // Disclaimer visibility
    const enDisclaimer = document.getElementById('disclaimerEN');
    const arDisclaimer = document.getElementById('disclaimerAR');
    if (enDisclaimer) enDisclaimer.style.display = isArabic ? 'none' : 'block';
    if (arDisclaimer) arDisclaimer.style.display = isArabic ? 'block' : 'none';

    // Terms link
    const termsLink = document.getElementById('termsLink');
    if (termsLink) termsLink.textContent = t('termsOfService');

    // Language button
    const langBtn = document.getElementById('langBtn');
    if (langBtn) langBtn.textContent = t('switchLang');

    // Skip link (Upgrade 7)
    const skipLink = document.querySelector('.skip-link');
    if (skipLink) skipLink.textContent = t('skipToContent');

    updateThemeButton();

    // Update auth and watchlist text
    if (typeof updateAuthLanguage === 'function') updateAuthLanguage();
    if (typeof updateWatchlistLanguage === 'function') updateWatchlistLanguage();
    if (typeof updateTradesLanguage === 'function') updateTradesLanguage();
    if (typeof updateBriefingLanguage === 'function') updateBriefingLanguage();
    if (typeof updateTimeMachineLanguage === 'function') updateTimeMachineLanguage();
}

// ============================================
// TAB NAVIGATION
// ============================================

function switchToTab(tabId, updateHash) {
    const btn = document.querySelector(`.tab-btn[data-tab="${tabId}"]`);
    if (!btn) return;

    // Guard: watchlist tab requires login
    if (tabId === 'watchlist' && typeof currentUser !== 'undefined' && !currentUser) {
        if (typeof showAuthModal === 'function') showAuthModal('login');
        return;
    }

    // Toggle active tab button + ARIA
    document.querySelectorAll('.tab-btn').forEach(b => {
        b.classList.remove('active');
        b.setAttribute('aria-selected', 'false');
    });
    btn.classList.add('active');
    btn.setAttribute('aria-selected', 'true');

    // Toggle active tab content
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    const content = document.getElementById(`tab-${tabId}`);
    if (content) {
        content.classList.add('active');
        // Re-trigger tab entrance animation (Upgrade 5)
        content.style.animation = 'none';
        void content.offsetWidth;
        content.style.animation = '';
    }

    // Update URL hash
    if (updateHash !== false) {
        history.pushState({ tab: tabId }, '', `#${tabId}`);
    }

    // Lazy-load data
    if (tabId === 'watchlist' && typeof loadWatchlist === 'function') loadWatchlist();
    if (tabId === 'briefing' && typeof loadBriefing === 'function') loadBriefing();
    if (tabId === 'trades' && typeof loadTrades === 'function') loadTrades();
    if (tabId === 'portfolio' && typeof loadPortfolio === 'function') loadPortfolio();
    if (tabId === 'performance' && typeof loadPerformanceDashboard === 'function') loadPerformanceDashboard();
    if (tabId === 'timemachine' && typeof loadTimeMachine === 'function') loadTimeMachine();
    if (tabId === 'etf' && typeof loadEtfTab === 'function') loadEtfTab();
    if (tabId === 'forecasts' && typeof loadPortfolioForecasts === 'function') loadPortfolioForecasts();
    if (tabId === 'rates') loadRatesTab();
    if (tabId === 'portfolio') { loadAlerts(); }
    if (tabId === 'performance') loadSignalAccuracy(5);
}

// Key shared with admin dashboard for frontend tab visibility
const FRONTEND_HIDDEN_TABS_KEY = 'xmore_hidden_frontend_tabs';

function applyFrontendTabVisibility() {
    let hidden = new Set();
    try { hidden = new Set(JSON.parse(localStorage.getItem(FRONTEND_HIDDEN_TABS_KEY) || '[]')); }
    catch (_) {}
    // 'predictions' is always visible — remove it from the hidden set as a safety guard
    hidden.delete('predictions');
    document.querySelectorAll('.tab-btn[data-tab]').forEach(btn => {
        const tabId = btn.getAttribute('data-tab');
        const isHidden = hidden.has(tabId);
        btn.style.display = isHidden ? 'none' : '';
    });
}

function initTabs() {
    applyFrontendTabVisibility();
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.setAttribute('tabindex', '0');
        btn.addEventListener('click', () => {
            switchToTab(btn.getAttribute('data-tab'));
        });
        // Keyboard navigation (Upgrade 7)
        btn.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                btn.click();
            }
            if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
                const tabs = [...document.querySelectorAll('.tab-btn')];
                const idx = tabs.indexOf(btn);
                const dir = e.key === 'ArrowRight' ? 1 : -1;
                const next = tabs[(idx + dir + tabs.length) % tabs.length];
                next.focus();
                next.click();
            }
        });
    });

    // Handle browser back/forward
    window.addEventListener('popstate', (e) => {
        const tabId = (e.state && e.state.tab) || window.location.hash.slice(1) || 'predictions';
        switchToTab(tabId, false);
    });

    // Load initial tab from URL hash
    const initialTab = window.location.hash.slice(1) || 'predictions';
    if (initialTab !== 'predictions') {
        switchToTab(initialTab, false);
    }
}

// ============================================
// COMPANY NAMES
// ============================================

const COMPANY_NAMES = {
    // US Stocks
    'AAPL': { en: 'Apple Inc.', ar: 'شركة أبل' },
    'GOOGL': { en: 'Alphabet Inc. (Google)', ar: 'ألفابت (جوجل)' },
    'MSFT': { en: 'Microsoft Corporation', ar: 'شركة مايكروسوفت' },
    'AMZN': { en: 'Amazon.com Inc.', ar: 'شركة أمازون' },
    'META': { en: 'Meta Platforms Inc.', ar: 'شركة ميتا' },
    'TSLA': { en: 'Tesla Inc.', ar: 'شركة تسلا' },
    'NVDA': { en: 'NVIDIA Corporation', ar: 'شركة إنفيديا' },
    'JPM': { en: 'JPMorgan Chase & Co.', ar: 'جي بي مورغان' },
    'V': { en: 'Visa Inc.', ar: 'شركة فيزا' },
    'JNJ': { en: 'Johnson & Johnson', ar: 'جونسون آند جونسون' },
    'WMT': { en: 'Walmart Inc.', ar: 'شركة وولمارت' },
    'XOM': { en: 'Exxon Mobil Corporation', ar: 'إكسون موبيل' },
    'BAC': { en: 'Bank of America Corp.', ar: 'بنك أوف أمريكا' },
    'PG': { en: 'Procter & Gamble Co.', ar: 'بروكتر آند غامبل' },
    'HD': { en: 'The Home Depot Inc.', ar: 'هوم ديبوت' },
    // EGX Stocks (Egyptian Exchange)
    'COMI.CA': { en: 'Commercial International Bank CIB', ar: 'البنك التجاري الدولي' },
    'HRHO.CA': { en: 'EFG Holding Hermes', ar: 'هيرميس القابضة' },
    'FWRY.CA': { en: 'Fawry Banking Technology', ar: 'فوري لتكنولوجيا البنوك' },
    'TMGH.CA': { en: 'Talaat Moustafa Group', ar: 'مجموعة طلعت مصطفى' },
    'ORAS.CA': { en: 'Orascom Construction', ar: 'أوراسكوم للإنشاءات' },
    'PHDC.CA': { en: 'Palm Hills Development', ar: 'بالم هيلز للتعمير' },
    'MNHD.CA': { en: 'Madinet Nasr Housing', ar: 'مدينة نصر للإسكان' },
    'OCDI.CA': { en: 'Orascom Development', ar: 'أوراسكوم للتنمية' },
    'SWDY.CA': { en: 'El Sewedy Electric', ar: 'السويدي إليكتريك' },
    'EAST.CA': { en: 'Eastern Company Tobacco', ar: 'الشرقية للدخان' },
    'EFIH.CA': { en: 'Egyptian Financial Industrial', ar: 'المصرية المالية الصناعية' },
    'ESRS.CA': { en: 'Ezz Steel', ar: 'حديد عز' },
    'ETEL.CA': { en: 'Telecom Egypt', ar: 'المصرية للاتصالات' },
    'EMFD.CA': { en: 'E-Finance Digital', ar: 'إي فاينانس' },
    'ALCN.CA': { en: 'Alexandria Container Cargo', ar: 'الإسكندرية للحاويات' },
    'ABUK.CA': { en: 'Abu Qir Fertilizers', ar: 'أبو قير للأسمدة' },
    'MFPC.CA': { en: 'Misr Fertilizers MOPCO', ar: 'موبكو للأسمدة' },
    'SKPC.CA': { en: 'Sidi Kerir Petrochemicals', ar: 'سيدي كرير للبتروكيماويات' },
    'JUFO.CA': { en: 'Juhayna Food Industries', ar: 'جهينة للصناعات الغذائية' },
    'CCAP.CA': { en: 'Cleopatra Hospital', ar: 'مستشفى كليوباترا' },
    'ORWE.CA': { en: 'Oriental Weavers', ar: 'السجاد الشرقي' },
    'AMOC.CA': { en: 'Alexandria Mineral Oils', ar: 'أموك للزيوت المعدنية' },
};

function getCompanyName(symbol) {
    const company = COMPANY_NAMES[symbol];
    if (company) return company[currentLang] || company.en;
    return symbol.replace('.CA', '');
}

// ============================================
// UTILITIES
// ============================================

function formatDate(dateStr) {
    if (!dateStr) return 'N/A';
    try {
        // PostgreSQL DATE columns serialize via JSON as full ISO timestamps
        // (e.g. "2026-02-26T00:00:00.000Z"). Extracting just the YYYY-MM-DD
        // portion and re-parsing as local midnight avoids the UTC+2 offset
        // showing as "02:00" in Cairo.
        const s = String(dateStr);
        const dateMatch = s.match(/^(\d{4}-\d{2}-\d{2})/);
        if (!dateMatch) return dateStr;
        const date = new Date(dateMatch[1] + 'T00:00:00');
        if (isNaN(date.getTime())) return dateStr;
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    } catch (e) {
        return dateStr;
    }
}

// Map symbol to TradingView format
function mapToTradingViewSymbol(symbol) {
    if (symbol.endsWith('.CA')) {
        return 'EGX:' + symbol.replace('.CA', '');
    }
    return symbol; // US stocks use plain symbol
}

// ============================================
// SENTIMENT
// ============================================

let sentimentData = {};

async function loadSentiment() {
    try {
        const response = await fetch(`${API_URL}/sentiment`);
        if (response.ok) {
            const data = await response.json();
            sentimentData = {};
            data.forEach(item => { sentimentData[item.symbol] = item; });
        }
    } catch (error) {
        console.error('Error loading sentiment:', error);
    }
}

function getSentimentBadge(symbol) {
    const sentiment = sentimentData[symbol];
    if (!sentiment || !sentiment.sentiment_label) {
        return `<span class="sentiment-badge sentiment-none">${t('noSentiment')}</span>`;
    }
    const label = sentiment.sentiment_label.toLowerCase();
    const displayLabel = t(label) || sentiment.sentiment_label;
    const score = sentiment.avg_sentiment ? sentiment.avg_sentiment.toFixed(2) : '0.00';
    return `<span class="sentiment-badge sentiment-${label} sentiment-badge-clickable"
        title="Score: ${score} — Click for details"
        onclick="showSentimentEvidence('${symbol}')">${displayLabel}</span>`;
}

// ── Sentiment Evidence Modal ──────────────────────────────────────────────────

async function showSentimentEvidence(symbol) {
    const modal = document.getElementById('sentimentModal');
    const titleEl = document.getElementById('smTitle');
    const bodyEl = document.getElementById('smBody');
    if (!modal || !titleEl || !bodyEl) return;

    titleEl.textContent = `Sentiment Evidence \u2014 ${symbol}`;
    bodyEl.innerHTML = '<p style="text-align:center;padding:20px;color:var(--text-muted);">Loading\u2026</p>';
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';

    try {
        const res = await fetch(`/api/rag/sentiment/${encodeURIComponent(symbol)}/evidence`);
        const data = await res.json();
        if (data.error) throw new Error(data.error);

        const label = (data.sentiment_label || 'N/A').toLowerCase();
        const score = data.avg_sentiment != null ? Number(data.avg_sentiment).toFixed(2) : 'N/A';
        const articles = data.articles || [];

        let html = `
            <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;flex-wrap:wrap;">
                <span class="sentiment-badge sentiment-${label}" style="font-size:15px;padding:6px 16px;">${data.sentiment_label || 'N/A'}</span>
                <span style="color:var(--text-muted);font-size:13px;">Score: ${score} &nbsp;|&nbsp; ${data.article_count || 0} articles</span>
                <span style="color:var(--text-muted);font-size:12px;">(${data.date || ''})</span>
            </div>`;

        if (articles.length === 0) {
            html += `<p style="color:var(--text-muted);font-size:13px;">No individual articles found for this date.</p>`;
        } else {
            html += `<div style="display:flex;flex-direction:column;gap:10px;">`;
            articles.forEach(a => {
                const aLabel = (a.sentiment_label || 'Neutral').toLowerCase();
                const link = a.url
                    ? `<a href="${a.url}" target="_blank" rel="noopener" style="color:var(--accent);text-decoration:none;font-weight:600;">${escHtml(a.headline)}</a>`
                    : `<span style="font-weight:600;color:var(--text-primary);">${escHtml(a.headline)}</span>`;
                html += `
                    <div style="border:1px solid var(--border-color);border-radius:8px;padding:10px 14px;background:var(--input-bg);">
                        <div style="margin-bottom:6px;">${link}</div>
                        <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
                            <span class="sentiment-badge sentiment-${aLabel}" style="font-size:11px;padding:2px 8px;">${a.sentiment_label || 'Neutral'}</span>
                            <span style="color:var(--text-muted);font-size:12px;">${escHtml(a.source || '')} &nbsp;${escHtml(String(a.date || ''))}</span>
                        </div>
                    </div>`;
            });
            html += `</div>`;
        }

        bodyEl.innerHTML = html;
    } catch (e) {
        bodyEl.innerHTML = `<p style="color:#ef4444;font-size:13px;">Error: ${e.message}</p>`;
    }
}

function escHtml(s) {
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function closeSentimentModal() {
    const modal = document.getElementById('sentimentModal');
    if (modal) modal.style.display = 'none';
    document.body.style.overflow = '';
}

// ============================================
// TRADINGVIEW WIDGETS (Task 5)
// ============================================

function loadTradingViewTicker() {
    const container = document.getElementById('tv-ticker-tape');
    if (!container) return;

    const locale = currentLang === 'ar' ? 'ar_AE' : 'en';
    const colorTheme = currentTheme;

    container.innerHTML = '';
    const widgetDiv = document.createElement('div');
    widgetDiv.className = 'tradingview-widget-container__widget';
    container.appendChild(widgetDiv);

    const script = document.createElement('script');
    script.type = 'text/javascript';
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js';
    script.async = true;
    script.textContent = JSON.stringify({
        symbols: [
            { proName: 'EGX:EGX30', title: 'EGX 30' },
            { proName: 'EGX:COMI', title: 'CIB' },
            { proName: 'EGX:HRHO', title: 'Hermes' },
            { proName: 'NASDAQ:AAPL', title: 'Apple' },
            { proName: 'NASDAQ:MSFT', title: 'Microsoft' },
            { proName: 'NASDAQ:NVDA', title: 'NVIDIA' },
        ],
        showSymbolLogo: true,
        colorTheme: colorTheme,
        isTransparent: true,
        displayMode: 'adaptive',
        locale: locale
    });
    container.appendChild(script);
}

// Lazy-load TradingView mini chart for a stock card
function loadTradingViewChart(symbol, containerId) {
    const container = document.getElementById(containerId);
    if (!container || container.dataset.loaded === 'true') return;

    const tvSymbol = mapToTradingViewSymbol(symbol);
    const locale = currentLang === 'ar' ? 'ar_AE' : 'en';

    container.innerHTML = '';
    container.dataset.loaded = 'true';

    const script = document.createElement('script');
    script.type = 'text/javascript';
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js';
    script.async = true;
    script.textContent = JSON.stringify({
        symbol: tvSymbol,
        width: '100%',
        height: '180',
        locale: locale,
        dateRange: '1M',
        colorTheme: currentTheme,
        isTransparent: true,
        autosize: true
    });
    container.appendChild(script);
}

// ============================================
// PERFORMANCE DATA (stored globally for badges)
// ============================================

let agentPerformanceData = {};
let stockPerformanceMap = {};

function trendFromSignal(signalKey) {
    if (signalKey === 'up' || signalKey === 'bullish' || signalKey === 'buy') return t('bullish');
    if (signalKey === 'down' || signalKey === 'bearish' || signalKey === 'sell') return t('bearish');
    return t('neutral');
}

function parsePredictionMetadata(metaRaw) {
    let meta = {};
    if (typeof metaRaw === 'string') {
        try { meta = JSON.parse(metaRaw); } catch (e) { meta = {}; }
    } else if (metaRaw && typeof metaRaw === 'object') {
        meta = metaRaw;
    }

    const rsi = meta.rsi || meta.RSI || meta.rsi_value || null;
    const volume = meta.volume_signal || meta.volume || meta.volume_state || null;
    const sentiment = meta.sentiment_label || meta.sentiment || null;
    const momentum = rsi != null ? `RSI ${Number(rsi).toFixed(1)}` : (meta.momentum || 'N/A');

    return {
        trendPct: meta.trend_score || meta.trend_pct || meta.trend || null,
        sentiment: sentiment || 'N/A',
        volume: volume || 'N/A',
        momentum,
        reasoning: `Trend ${meta.trend_score || meta.trend_pct || 'N/A'} | Sentiment ${sentiment || 'N/A'} | Volume ${volume || 'N/A'} | Momentum ${momentum}`
    };
}

async function loadGlobalSnapshotBar() {
    const el = document.getElementById('globalPerfSnapshot');
    if (!el) return;

    try {
        const response = await fetch('/api/performance-v2/summary');
        const data = await response.json();
        if (!data || !data.available) {
            el.style.display = 'none';
            return;
        }

        const g = data.global || {};
        const r30 = data.rolling?.['30d'] || {};
        const trades = g.total_predictions || 0;
        const progressPct = Math.min(100, Math.round((trades / 100) * 100));
        const sharpe = r30.sharpe_ratio || g.sharpe_ratio || 0;
        const maxDd = r30.max_drawdown || g.max_drawdown || 0;
        const alpha30 = r30.alpha || 0;
        const win30 = r30.win_rate || 0;

        const card = (id, label, cls, tooltip) => `
            <div class="global-snapshot-card ${cls}" title="${tooltip}">
                <div class="global-snapshot-label">${label}</div>
                <div class="global-snapshot-value metric-value" id="${id}">-</div>
            </div>
        `;

        el.innerHTML = `
            <div class="global-snapshot-grid">
                ${card('gsAlpha30', t('snapshotAlpha30d'), alpha30 > 0 ? 'positive' : alpha30 < 0 ? 'negative' : 'neutral', t('tooltipAlpha'))}
                ${card('gsSharpe30', t('snapshotSharpe30d'), sharpe >= 1 ? 'positive' : sharpe > 0 ? 'neutral' : 'negative', t('tooltipSharpe'))}
                ${card('gsMaxDd30', t('snapshotMaxDd30d'), maxDd <= 4 ? 'positive' : maxDd <= 8 ? 'neutral' : 'negative', t('tooltipMaxDd'))}
                ${card('gsWinRate30', t('snapshotWinRate30d'), win30 >= 55 ? 'positive' : win30 >= 45 ? 'neutral' : 'negative', t('tooltipWinRate'))}
                <div class="global-snapshot-card span-2" title="${t('tooltipTrades')}">
                    <div class="global-snapshot-label">${t('snapshotTrades')}</div>
                    <div class="global-snapshot-value metric-value" id="gsTrades">-</div>
                    <div class="global-progress-track"><span class="global-progress-fill progress-fill" style="width:${progressPct}%"></span></div>
                </div>
            </div>
        `;

        // Animate the values (Upgrade 1)
        animateValue('gsAlpha30', alpha30, { decimalPlaces: 2, suffix: '%', prefix: alpha30 > 0 ? '+' : '' });
        animateValue('gsSharpe30', sharpe, { decimalPlaces: 2, prefix: sharpe > 0 ? '+' : '' });
        animateValue('gsMaxDd30', maxDd, { decimalPlaces: 2, suffix: '%' });
        animateValue('gsWinRate30', win30, { decimalPlaces: 1, suffix: '%' });
        animateValue('gsTrades', trades, { decimalPlaces: 0 });
    } catch (error) {
        console.error('Error loading global snapshot bar:', error);
        el.innerHTML = `<div class="global-snapshot-empty">${t('errorPerformance')}</div>`;
    }
}

async function loadRegimeBanner() {
    try {
        const res = await fetch('/api/track-record/regime-stats');
        if (!res.ok) return;
        const data = await res.json();
        const el = document.getElementById('regimeBanner');
        if (!el || !data || !data.regimes) return;

        // Find current regime (most recent data)
        const regimes = data.regimes;
        if (!regimes.length) return;

        // Pick dominant regime by most recent win rate
        const best = regimes.sort((a, b) => (b.total_signals || 0) - (a.total_signals || 0))[0];
        const currentRegime = best?.regime || 'Unknown';
        const regimeClass = currentRegime === 'Calm' ? 'regime-calm'
                          : currentRegime === 'Turbulent' ? 'regime-turbulent'
                          : currentRegime === 'Crisis' ? 'regime-crisis'
                          : 'regime-unknown';

        // Signal distribution
        let distHtml = '';
        try {
            const distRes = await fetch('/api/track-record/signal-distribution?days=30');
            if (distRes.ok) {
                const distData = await distRes.json();
                const summary = distData?.summary || {};
                const total = (summary.BUY || 0) + (summary.SELL || 0) + (summary.HOLD || 0);
                if (total > 0) {
                    const buyPct = Math.round((summary.BUY || 0) / total * 100);
                    const sellPct = Math.round((summary.SELL || 0) / total * 100);
                    distHtml = `
                        <span class="regime-sep">|</span>
                        <span class="regime-dist">
                            <span class="regime-dist-buy">↑ ${buyPct}%</span>
                            <span class="regime-dist-sell">↓ ${sellPct}%</span>
                            <span class="regime-dist-label">${t('signalMix30d') || '30d signals'}</span>
                        </span>
                    `;
                }
            }
        } catch (_) {}

        el.innerHTML = `
            <span class="regime-dot ${regimeClass}"></span>
            <span class="regime-label">${t('marketRegime') || 'Market Regime'}:</span>
            <span class="regime-value ${regimeClass}">${currentRegime}</span>
            ${distHtml}
            <a href="/track-record#regime" class="regime-link">${t('viewFullAnalysis') || 'Full Analysis →'}</a>
        `;
        el.style.display = 'flex';
    } catch (_) {}
}

// ============================================
// LOAD DATA ON PAGE LOAD
// ============================================

window.addEventListener('load', async () => {
    try {
        initNotyf();
        applyLanguage();
        initTabs();
        loadTradingViewTicker();
        loadGlobalSnapshotBar();
        loadRegimeBanner();

        // Show skeletons before data loads (Upgrade 4)
        showSkeleton('predictions', 'predictions');
        showSkeleton('evaluations', 'results');
        showSkeleton('prices', 'prices');
        showSkeleton('consensusCards', 'consensus');

        // Set aria-live on dynamic containers (Upgrade 7)
        ['predictions', 'evaluations', 'prices', 'consensusCards'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.setAttribute('aria-live', 'polite');
        });

        // Fetch watchlist symbols first (needed for filtering all tabs)
        await fetchUserWatchlistSymbols();

        // Load all independent data in parallel
        loadStats();
        loadConsensus();
        loadScoringPanel();
        loadPerformance();
        loadPerformanceDetailed();
        loadEvaluations();
        loadPrices();

        // Predictions need sentiment data for badges, so chain them
        loadSentiment()
            .then(() => loadPredictions())
            .catch(err => {
                console.error('Failed loading predictions chain:', err);
                const el = document.getElementById('predictions');
                if (el) el.innerHTML = `<p class="error-message">Failed to load: ${escapeHtml(err.message)}</p>`;
            });
    } catch (err) {
        console.error('Load handler error:', err);
        const el = document.getElementById('predictions');
        if (el) el.innerHTML = `<p class="error-message">Init error: ${escapeHtml(err.message)}</p>`;
    }
});

document.getElementById('langBtn')?.addEventListener('click', switchLanguage);
document.getElementById('themeBtn')?.addEventListener('click', toggleTheme);

// ============================================
// REFRESH
// ============================================

async function refreshData() {
    const btn = document.getElementById('refreshBtn');
    if (btn) {
        btn.disabled = true;
        btn.textContent = t('refreshing');
        btn.classList.add('loading-btn');
    }

    try {
        // Re-fetch watchlist cache in case user followed/unfollowed stocks
        resetWatchlistCache();
        await fetchUserWatchlistSymbols();

        await loadSentiment();
        await Promise.all([
            loadStats(),
            loadGlobalSnapshotBar(),
            loadPredictions(),
            loadConsensus(),
            loadPerformance(),
            loadPerformanceDetailed(),
            loadEvaluations(),
            loadPrices()
        ]);

        // Load trades if functions exist
        if (typeof loadTrades === 'function') loadTrades();
        if (typeof loadPortfolio === 'function') loadPortfolio();
        showToast('success', t('dataRefreshed'));
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = t('refreshData');
            btn.classList.remove('loading-btn');
        }
    }
}

document.getElementById('refreshBtn')?.addEventListener('click', refreshData);

// ============================================
// LOAD STATS
// ============================================

async function loadStats() {
    try {
        const [statsRes, perfRes] = await Promise.all([
            fetch(`${API_URL}/stats`),
            fetch(`${API_URL}/performance`).catch(() => null),
        ]);
        const data = await statsRes.json();

        animateValue('stocksTracked', data.stocksTracked || 0, { decimalPlaces: 0 });
        animateValue('totalPredictions', data.totalPredictions || 0, { decimalPlaces: 0 });
        document.getElementById('latestDate').textContent = formatDate(data.latestDate);

        // Populate accuracy stat from evaluations table (best non-Consensus agent)
        if (perfRes && perfRes.ok) {
            const perf = await perfRes.json();
            const agents = Array.isArray(perf) ? perf.filter(p => p.agent_name !== 'Consensus' && parseFloat(p.accuracy) > 0) : [];
            if (agents.length) {
                agents.sort((a, b) => parseFloat(b.accuracy) - parseFloat(a.accuracy));
                animateValue('overallAccuracy', parseFloat(agents[0].accuracy), { decimalPlaces: 1, suffix: '%' });
            }
        }
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

// ============================================
// LOAD PREDICTIONS (Task 6: Signal terminology)
// ============================================

async function loadPredictions() {
    const container = document.getElementById('predictions');

    try {
        const [predRes, stockPerfRes] = await Promise.all([
            fetch(`${API_URL}/predictions`),
            fetch('/api/performance-v2/by-stock?days=90').catch(() => null)
        ]);
        if (!predRes.ok) throw new Error(`HTTP error: ${predRes.status}`);

        const result = await predRes.json();
        const data = Array.isArray(result) ? result : (result.predictions || []);
        const stockPerfData = stockPerfRes && stockPerfRes.ok ? await stockPerfRes.json() : { stocks: [] };
        stockPerformanceMap = {};
        (stockPerfData.stocks || []).forEach(s => { stockPerformanceMap[s.symbol] = s; });

        clearSkeleton('predictions');
        if (!data || data.length === 0) {
            renderEmptyState('predictions', '\uD83D\uDCCA', 'emptyPredictions', 'emptyPredictionsDesc', null, null);
            return;
        }

        const grouped = {};
        data.forEach(pred => {
            if (!grouped[pred.symbol]) grouped[pred.symbol] = [];
            grouped[pred.symbol].push(pred);
        });

        const allSymbols = Object.keys(grouped);

        if (isLoggedIn()) {
            const watchlistSymbols = allSymbols.filter(s => userWatchlistSymbols.has(s));
            if (userWatchlistSymbols.size === 0) {
                container.innerHTML = getWatchlistEmptyHtml();
                return;
            }
            if (watchlistSymbols.length === 0) {
                container.innerHTML = `<p class="no-data">${t('noPredictions')}</p>`;
                return;
            }
            container.innerHTML = renderPredictionTable(grouped, watchlistSymbols, 'predictionsTable');
        } else {
            container.innerHTML = renderPredictionTable(grouped, allSymbols, 'predictionsTable');
        }
    } catch (error) {
        console.error('Error loading predictions:', error);
        clearSkeleton('predictions');
        container.innerHTML = `<p class="error-message">${t('errorPredictions')}</p>`;
        showToast('error', t('loadError'));
    }
}

const SECTOR_MAP = {
    'COMI.CA':'Banking','ETEL.CA':'Telecom','HRHO.CA':'Real Estate','SWDY.CA':'Construction',
    'TALAAT.CA':'Real Estate','ESRS.CA':'Steel','ACGC.CA':'Chemicals','ABUK.CA':'Food & Bev',
    'PHDC.CA':'Real Estate','EFIH.CA':'Financial Services','MNHD.CA':'Real Estate',
    'OCDI.CA':'Real Estate','CLHO.CA':'Tourism & Leisure','SUGR.CA':'Food & Bev',
    'HELMY.CA':'Financial Services','DCRC.CA':'Financial Services','AMOC.CA':'Petroleum',
    'ORWE.CA':'Textile','SKPC.CA':'Chemicals','AUTO.CA':'Automotive',
    'SPMD.CA':'Construction','HELI.CA':'Aviation','ISPH.CA':'Pharma',
    'ALCN.CA':'Construction','BINV.CA':'Financial Services',
};

function getStockSector(symbol) {
    return SECTOR_MAP[symbol] || 'Other';
}

function populateSectorDropdown(symbols) {
    const select = document.getElementById('screenerSector');
    if (!select) return;
    const sectors = [...new Set(symbols.map(getStockSector))].sort();
    const current = select.value;
    // keep first "All Sectors" option, replace rest
    select.innerHTML = '<option value="">All Sectors</option>' +
        sectors.map(s => `<option value="${s}"${s === current ? ' selected' : ''}>${s}</option>`).join('');
}

function renderPredictionTable(grouped, symbols, tableId) {
    if (symbols.length === 0) return '';

    if (tableId === 'predictionsTable') populateSectorDropdown(symbols);

    const labels = {
        stock: t('stock'),
        signal: t('consensusSignal'),
        agreement: t('agreement'),
        conviction: t('conviction'),
        accuracy: t('recentAccuracySymbol'),
        details: t('expandDetails')
    };

    let html = `<table id="${tableId}" class="predictions-v2-table table-cards"><thead><tr><th>${labels.stock}</th><th>${labels.signal}</th><th>${labels.agreement}</th><th>${labels.conviction}</th><th>${labels.accuracy}</th><th>${labels.details}</th></tr></thead><tbody>`;

    symbols.forEach(symbol => {
        const predictions = grouped[symbol];
        const companyName = getCompanyName(symbol);
        const searchText = `${symbol} ${companyName}`.toLowerCase();
        const tally = { up: 0, down: 0, hold: 0 };
        let confidenceSum = 0;

        const agentDetails = predictions.map(pred => {
            const signalKey = (pred.prediction || 'hold').toLowerCase();
            if (tally[signalKey] == null) tally[signalKey] = 0;
            tally[signalKey] += 1;
            const confidence = Number(pred.confidence || 0);
            confidenceSum += confidence;
            return {
                agentDisplayName: getAgentDisplayName(pred.agent_name),
                agentDescription: getAgentDescription(pred.agent_name),
                signalKey,
                signalText: t(signalKey),
                confidence,
                metadata: parsePredictionMetadata(pred.metadata)
            };
        });

        const consensusKey = Object.keys(tally).sort((a, b) => (tally[b] || 0) - (tally[a] || 0))[0] || 'hold';
        const agreeCount = tally[consensusKey] || 0;
        const agreementPct = predictions.length ? Math.round((agreeCount / predictions.length) * 100) : 0;
        const convictionValue = predictions.length ? confidenceSum / predictions.length : 0;
        const convictionLabel = convictionValue >= 75 ? 'VERY_HIGH' : convictionValue >= 60 ? 'HIGH' : convictionValue >= 40 ? 'MODERATE' : 'LOW';
        const sector = getStockSector(symbol);
        const recentAcc = stockPerformanceMap[symbol]?.win_rate;
        const detailsId = `pred-details-${symbol.replace('.', '-')}`;

        html += `
            <tr data-search="${searchText}" data-signal="${consensusKey}" data-conviction="${convictionLabel}" data-sector="${sector}" data-conf="${Math.round(convictionValue)}" class="group-start pred-stock-row">
                <td data-label="${labels.stock}" class="stock-cell"><strong>${symbol}</strong><br><small class="company-name">${companyName}</small></td>
                <td data-label="${labels.signal}"><span class="signal-${consensusKey}">${t(consensusKey)}</span></td>
                <td data-label="${labels.agreement}">${agreeCount}/${predictions.length} (${agreementPct}%)</td>
                <td data-label="${labels.conviction}">${convictionValue.toFixed(1)}%</td>
                <td data-label="${labels.accuracy}">${recentAcc == null ? 'N/A' : `${Number(recentAcc).toFixed(1)}%`}</td>
                <td data-label="${labels.details}"><button class="perf-action-btn secondary" onclick="togglePredictionDetails('${detailsId}')">${t('expandDetails')}</button></td>
            </tr>
            <tr data-search="${searchText}" class="group-row hidden-row pred-detail-row" id="${detailsId}">
                <td colspan="6">
                    <div class="signal-why-grid">
                        <div class="signal-why-title">${t('whySignal')}</div>
                        <div class="signal-why-item"><span>${t('trend')}</span><strong>${trendFromSignal(consensusKey)}</strong></div>
                        <div class="signal-why-item"><span>${t('momentum')}</span><strong>${agentDetails[0]?.metadata?.momentum || 'N/A'}</strong></div>
                        <div class="signal-why-item"><span>${t('volumeState')}</span><strong>${agentDetails[0]?.metadata?.volume || 'N/A'}</strong></div>
                        <div class="signal-why-item"><span>${t('sentimentState')}</span><strong>${agentDetails[0]?.metadata?.sentiment || 'N/A'}</strong></div>
                        <div class="signal-why-item"><span>${t('agentAgreement')}</span><strong>${agreementPct}%</strong></div>
                    </div>
                    <div class="pred-agent-breakdown">
                        ${agentDetails.map(d => `
                            <div class="pred-agent-row">
                                <div><span class="agent-name" title="${d.agentDescription}">${d.agentDisplayName}</span> <span class="signal-${d.signalKey}">${d.signalText}</span></div>
                                <div>${t('conf')}: ${d.confidence.toFixed(1)}%</div>
                                <div class="pred-reason">${d.metadata.reasoning}</div>
                            </div>
                        `).join('')}
                    </div>
                    <div class="why-signal-btn-row">
                        <button class="perf-action-btn why-signal-btn" onclick="showWhySignal('${symbol}','${consensusKey}')">💡 AI Insight</button>
                    </div>
                </td>
            </tr>
        `;
    });

    html += '</tbody></table>';
    return html;
}

function togglePredictionDetails(id) {
    const row = document.getElementById(id);
    if (!row) return;
    row.classList.toggle('hidden-row');
}

// ============================================
// FILTER PREDICTIONS
// ============================================

function filterPredictions() {
    const searchValue = document.getElementById('predictionsSearch')?.value.toLowerCase().trim() || '';
    const sigFilter = document.getElementById('screenerSignal')?.value || '';
    const convFilter = document.getElementById('screenerConviction')?.value || '';
    const sectorFilter = document.getElementById('screenerSector')?.value || '';
    const minConf = parseFloat(document.getElementById('screenerMinConf')?.value) || 0;

    ['predictionsTable', 'watchlistPredictionsTable'].forEach(tableId => {
        const table = document.getElementById(tableId);
        if (!table) return;

        const rows = table.querySelectorAll('tbody tr');
        let currentGroupVisible = false;

        rows.forEach(row => {
            const isGroupStart = row.classList.contains('group-start');
            if (isGroupStart) {
                const searchText = row.getAttribute('data-search') || '';
                const signal = row.getAttribute('data-signal') || '';
                const conviction = row.getAttribute('data-conviction') || '';
                const sector = row.getAttribute('data-sector') || '';
                const conf = parseFloat(row.getAttribute('data-conf') || '0');
                currentGroupVisible =
                    searchText.includes(searchValue) &&
                    (!sigFilter || signal === sigFilter) &&
                    (!convFilter || conviction === convFilter) &&
                    (!sectorFilter || sector === sectorFilter) &&
                    conf >= minConf;
                row.classList.toggle('hidden-row', !currentGroupVisible);
                return;
            }
            if (row.classList.contains('pred-detail-row')) {
                if (!currentGroupVisible) row.classList.add('hidden-row');
                return;
            }
            row.classList.toggle('hidden-row', !currentGroupVisible);
        });
    });
}

function resetScreener() {
    const sig = document.getElementById('screenerSignal');
    const conv = document.getElementById('screenerConviction');
    const sec = document.getElementById('screenerSector');
    const conf = document.getElementById('screenerMinConf');
    const search = document.getElementById('predictionsSearch');
    if (sig) sig.value = '';
    if (conv) conv.value = '';
    if (sec) sec.value = '';
    if (conf) conf.value = '0';
    if (search) search.value = '';
    filterPredictions();
}

// ============================================
// LOAD PERFORMANCE (basic — existing endpoint)
// ============================================

async function loadPerformance() {
    const container = document.getElementById('perfAgents');
    if (!container) return;

    try {
        const response = await fetch(`${API_URL}/performance`);
        if (!response.ok) throw new Error(`HTTP error: ${response.status}`);

        const data = await response.json();

        // Store for agent accuracy badges
        data.forEach(agent => {
            agentPerformanceData[agent.agent_name] = agent;
        });

        if (!data || data.length === 0) {
            container.innerHTML = `<p class="no-data">${t('noPerformance')}</p>`;
            return;
        }

        const labels = {
            agent: t('agent'),
            total: t('totalPreds'),
            correct: t('correct'),
            accuracy: t('accuracy')
        };
        let html = `<table class="table-cards"><thead><tr><th>${labels.agent}</th><th>${labels.total}</th><th>${labels.correct}</th><th>${labels.accuracy}</th></tr></thead><tbody>`;

        data.forEach(agent => {
            const agentDisplayName = getAgentDisplayName(agent.agent_name);
            const agentDescription = getAgentDescription(agent.agent_name);
            const accuracyClass = agent.accuracy >= 60 ? 'high' : agent.accuracy >= 40 ? 'medium' : 'low';
            html += `
                <tr>
                    <td data-label="${labels.agent}"><strong class="agent-name" title="${agentDescription}">${agentDisplayName}</strong></td>
                    <td data-label="${labels.total}">${agent.total_predictions}</td>
                    <td data-label="${labels.correct}">${agent.correct_predictions}</td>
                    <td data-label="${labels.accuracy}">
                        <div class="accuracy-bar">
                            <div class="accuracy-fill accuracy-${accuracyClass}" style="width: ${agent.accuracy}%">
                                ${agent.accuracy}%
                            </div>
                        </div>
                    </td>
                </tr>
            `;
        });

        html += '</tbody></table>';
        container.innerHTML = html;
    } catch (error) {
        console.error('Error loading performance:', error);
        container.innerHTML = `<p class="error-message">${t('errorPerformance')}</p>`;
    }
}

// ============================================
// LOAD DETAILED PERFORMANCE (Task 4)
// ============================================

async function loadPerformanceDetailed() {
    try {
        const response = await fetch(`${API_URL}/performance/detailed`);
        if (!response.ok) throw new Error(`HTTP error: ${response.status}`);

        const data = await response.json();

        // Update overall accuracy in stats bar (avoids duplicate API call)
        const acc = data?.overall?.directional_accuracy;
        if (data?.overall?.total_predictions > 0) {
            animateValue('overallAccuracy', acc || 0, { decimalPlaces: 1, suffix: '%' });
        }

        // Render overall stats
        renderOverallStats(data.overall);

        // Render per-stock table
        renderPerStockTable(data.per_stock);

        // Render monthly chart
        renderMonthlyChart(data.monthly);

    } catch (error) {
        console.error('Error loading detailed performance:', error);
        const container = document.getElementById('perfOverall');
        if (container) container.innerHTML = `<p class="no-data">${t('noDetailedPerformance')}</p>`;
    }
}

function renderOverallStats(overall) {
    const container = document.getElementById('perfOverall');
    if (!container || !overall) return;

    if (!overall.total_predictions) {
        container.innerHTML = `<p class="no-data">${t('noDetailedPerformance')}</p>`;
        return;
    }

    container.innerHTML = `
        <div class="perf-stats-grid">
            <div class="perf-stat-card">
                <div class="perf-stat-value metric-value" id="perfDirAcc">-</div>
                <div class="perf-stat-label">${t('directionalAccuracy')}</div>
            </div>
            <div class="perf-stat-card">
                <div class="perf-stat-value metric-value" id="perfTotalSig">-</div>
                <div class="perf-stat-label">${t('totalSignals')}</div>
            </div>
            <div class="perf-stat-card">
                <div class="perf-stat-value metric-value" id="perfWinBuy">-</div>
                <div class="perf-stat-label">${t('winRateBuy')}</div>
            </div>
            <div class="perf-stat-card">
                <div class="perf-stat-value metric-value" id="perfWinSell">-</div>
                <div class="perf-stat-label">${t('winRateSell')}</div>
            </div>
            <div class="perf-stat-card">
                <div class="perf-stat-value metric-value" id="perfAvgRet">-</div>
                <div class="perf-stat-label">${t('avgReturnPerSignal')}</div>
            </div>
            <div class="perf-stat-card">
                <div class="perf-stat-value metric-value" id="perfMaxDd">-</div>
                <div class="perf-stat-label">${t('maxDrawdown')}</div>
            </div>
        </div>
    `;
    animateValue('perfDirAcc', overall.directional_accuracy || 0, { decimalPlaces: 1, suffix: '%' });
    animateValue('perfTotalSig', overall.total_predictions || 0, { decimalPlaces: 0 });
    animateValue('perfWinBuy', overall.win_rate_buy || 0, { decimalPlaces: 1, suffix: '%' });
    animateValue('perfWinSell', overall.win_rate_sell || 0, { decimalPlaces: 1, suffix: '%' });
    animateValue('perfAvgRet', (overall.avg_return_per_signal * 100), { decimalPlaces: 2, suffix: '%' });
    animateValue('perfMaxDd', ((overall.max_drawdown || 0) * 100), { decimalPlaces: 1, suffix: '%' });
}

function renderPerStockTable(perStock) {
    const container = document.getElementById('perfStocks');
    if (!container) return;

    let entries = Object.entries(perStock || {});

    // Filter to watchlist stocks for logged-in users
    if (isLoggedIn() && userWatchlistSymbols.size > 0) {
        entries = entries.filter(([symbol]) => userWatchlistSymbols.has(symbol));
    }

    if (entries.length === 0) {
        container.innerHTML = `<p class="no-data">${t('noDetailedPerformance')}</p>`;
        return;
    }

    const labels = {
        stock: t('stock'),
        accuracy: t('accuracy'),
        avgReturn: t('avgReturn'),
        total: t('totalPreds')
    };
    let html = `<table class="table-cards"><thead><tr><th>${labels.stock}</th><th>${labels.accuracy}</th><th>${labels.avgReturn}</th><th>${labels.total}</th></tr></thead><tbody>`;

    entries.forEach(([symbol, stats]) => {
        const companyName = getCompanyName(symbol);
        const accuracyClass = stats.accuracy >= 60 ? 'high' : stats.accuracy >= 40 ? 'medium' : 'low';
        html += `
            <tr>
                <td data-label="${labels.stock}"><strong>${symbol}</strong><br><small class="company-name">${companyName}</small></td>
                <td data-label="${labels.accuracy}">
                    <div class="accuracy-bar">
                        <div class="accuracy-fill accuracy-${accuracyClass}" style="width: ${stats.accuracy}%">${stats.accuracy}%</div>
                    </div>
                </td>
                <td data-label="${labels.avgReturn}" class="${stats.avg_return >= 0 ? 'positive-change' : 'negative-change'}">${(stats.avg_return * 100).toFixed(2)}%</td>
                <td data-label="${labels.total}">${stats.predictions}</td>
            </tr>
        `;
    });

    html += '</tbody></table>';
    container.innerHTML = html;
}

function renderMonthlyChart(monthly) {
    const canvas = document.getElementById('monthlyChart');
    if (!canvas || !monthly || monthly.length === 0) return;

    const ctx = canvas.getContext('2d');
    const padding = 50;
    const width = canvas.width;
    const height = canvas.height;
    const chartWidth = width - padding * 2;
    const chartHeight = height - padding * 2;

    // Clear
    ctx.clearRect(0, 0, width, height);

    // Sort by month
    monthly.sort((a, b) => a.month.localeCompare(b.month));

    const maxAcc = Math.max(...monthly.map(m => m.accuracy), 100);
    const barWidth = Math.min(chartWidth / monthly.length - 4, 40);

    // Style
    const isDark = currentTheme === 'dark';
    ctx.fillStyle = isDark ? '#e0e0e0' : '#333';
    ctx.font = '12px -apple-system, sans-serif';
    ctx.textAlign = 'center';

    // Y-axis label
    ctx.save();
    ctx.translate(15, height / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText(t('accuracy') + ' (%)', 0, 0);
    ctx.restore();

    // Draw bars
    monthly.forEach((m, i) => {
        const x = padding + (i * (chartWidth / monthly.length)) + (chartWidth / monthly.length - barWidth) / 2;
        const barHeight = (m.accuracy / maxAcc) * chartHeight;
        const y = padding + chartHeight - barHeight;

        // Bar gradient
        const gradient = ctx.createLinearGradient(x, y, x, y + barHeight);
        if (m.accuracy >= 60) {
            gradient.addColorStop(0, '#22c55e');
            gradient.addColorStop(1, '#16a34a');
        } else if (m.accuracy >= 40) {
            gradient.addColorStop(0, '#f59e0b');
            gradient.addColorStop(1, '#d97706');
        } else {
            gradient.addColorStop(0, '#ef4444');
            gradient.addColorStop(1, '#dc2626');
        }
        ctx.fillStyle = gradient;

        // Rounded top corners
        const radius = 4;
        ctx.beginPath();
        ctx.moveTo(x + radius, y);
        ctx.lineTo(x + barWidth - radius, y);
        ctx.arcTo(x + barWidth, y, x + barWidth, y + radius, radius);
        ctx.lineTo(x + barWidth, y + barHeight);
        ctx.lineTo(x, y + barHeight);
        ctx.lineTo(x, y + radius);
        ctx.arcTo(x, y, x + radius, y, radius);
        ctx.fill();

        // Value on top
        ctx.fillStyle = isDark ? '#e0e0e0' : '#333';
        ctx.font = '11px -apple-system, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(`${m.accuracy}%`, x + barWidth / 2, y - 6);

        // Month label
        ctx.fillText(m.month.slice(5), x + barWidth / 2, padding + chartHeight + 18);
    });

    // 50% baseline
    const baselineY = padding + chartHeight - (50 / maxAcc) * chartHeight;
    ctx.setLineDash([5, 5]);
    ctx.strokeStyle = isDark ? '#666' : '#ccc';
    ctx.beginPath();
    ctx.moveTo(padding, baselineY);
    ctx.lineTo(width - padding, baselineY);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = isDark ? '#888' : '#999';
    ctx.font = '10px -apple-system, sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText('50%', padding - 30, baselineY + 4);
}

// ============================================
// LOAD EVALUATIONS
// ============================================

async function loadEvaluations() {
    const container = document.getElementById('evaluations');

    try {
        const response = await fetch(`${API_URL}/evaluations`);
        if (!response.ok) throw new Error(`HTTP error: ${response.status}`);

        const data = await response.json();

        clearSkeleton('evaluations');
        if (!data || data.length === 0) {
            renderEmptyState('evaluations', '\uD83D\uDCC8', 'emptyResults', 'emptyResultsDesc', null, null);
            return;
        }

        // Filter to watchlist stocks for logged-in users
        let filteredData = data;
        if (isLoggedIn()) {
            if (userWatchlistSymbols.size === 0) {
                container.innerHTML = getWatchlistEmptyHtml();
                return;
            }
            filteredData = data.filter(item => userWatchlistSymbols.has(item.symbol));
            if (filteredData.length === 0) {
                renderEmptyState('evaluations', '\uD83D\uDCC8', 'emptyResults', 'emptyResultsDesc', null, null);
                return;
            }
        }

        const groupedBySymbol = {};
        filteredData.forEach(item => {
            if (!groupedBySymbol[item.symbol]) groupedBySymbol[item.symbol] = [];
            groupedBySymbol[item.symbol].push(item);
        });

        const symbols = Object.keys(groupedBySymbol).sort((a, b) => a.localeCompare(b));
        let html = '<div class="results-stock-list">';

        symbols.forEach((symbol, index) => {
            const rows = groupedBySymbol[symbol].slice().sort((a, b) => {
                return new Date(b.target_date) - new Date(a.target_date);
            });
            const companyName = getCompanyName(symbol);
            const toneClass = `tone-${(index % 3) + 1}`;

            html += `
                <article class="result-stock-card ${toneClass}">
                    <div class="result-stock-header">
                        <div class="result-stock-symbol">${symbol}</div>
                        <div class="result-stock-company">${companyName}</div>
                    </div>
                    <div class="result-stock-table-wrap">
                        <table class="result-stock-table table-cards">
                            <thead>
                                <tr>
                                    <th>${t('agent')}</th>
                                    <th>${t('signal')}</th>
                                    <th>${t('actualOutcome')}</th>
                                    <th>${t('priceChange')}</th>
                                    <th>${t('result')}</th>
                                    <th>${t('targetDate')}</th>
                                </tr>
                            </thead>
                            <tbody>
            `;

            rows.forEach(item => {
                const agentDisplayName = getAgentDisplayName(item.agent_name);
                const predictionText = t(item.prediction.toLowerCase());
                const actualText = t(item.actual_outcome.toLowerCase());
                const changePercent = item.actual_change_pct ? item.actual_change_pct.toFixed(2) : '0.00';
                const changeClass = parseFloat(changePercent) >= 0 ? 'positive-change' : 'negative-change';
                const resultClass = item.was_correct ? 'result-correct' : 'result-wrong';
                const resultIcon = item.was_correct ? '&#10003;' : '&#10007;';

                const labels = {
                    agent: t('agent'),
                    signal: t('signal'),
                    outcome: t('actualOutcome'),
                    change: t('priceChange'),
                    result: t('result'),
                    date: t('targetDate')
                };
                html += `
                    <tr>
                        <td data-label="${labels.agent}">${agentDisplayName}</td>
                        <td data-label="${labels.signal}"><span class="signal-${item.prediction.toLowerCase()}">${predictionText}</span></td>
                        <td data-label="${labels.outcome}"><span class="signal-${item.actual_outcome.toLowerCase()}">${actualText}</span></td>
                        <td data-label="${labels.change}" class="${changeClass}">${changePercent}%</td>
                        <td data-label="${labels.result}"><span class="${resultClass}">${resultIcon}</span></td>
                        <td data-label="${labels.date}">${formatDate(item.target_date)}</td>
                    </tr>
                `;
            });

            html += `
                            </tbody>
                        </table>
                    </div>
                </article>
            `;
        });

        html += '</div>';
        container.innerHTML = html;
    } catch (error) {
        console.error('Error loading evaluations:', error);
        container.innerHTML = `<p class="error-message">${t('errorEvaluations')}</p>`;
    }
}

// ============================================
// LOAD PRICES
// ============================================

async function loadPrices() {
    const container = document.getElementById('prices');

    try {
        const response = await fetch(`${API_URL}/prices`);
        if (!response.ok) throw new Error(`HTTP error: ${response.status}`);

        const data = await response.json();

        clearSkeleton('prices');
        if (!data || data.length === 0) {
            container.innerHTML = `<p class="no-data">${t('noPrices')}</p>`;
            return;
        }

        // Filter to watchlist stocks for logged-in users
        let filteredData = data;
        if (isLoggedIn()) {
            if (userWatchlistSymbols.size === 0) {
                container.innerHTML = getWatchlistEmptyHtml();
                return;
            }
            filteredData = data.filter(stock => userWatchlistSymbols.has(stock.symbol));
            if (filteredData.length === 0) {
                container.innerHTML = `<p class="no-data">${t('noPrices')}</p>`;
                return;
            }
        }

        const labels = {
            stock: t('stock'),
            date: t('date'),
            close: t('closePrice'),
            volume: t('volume')
        };
        let html = `<div class="scrollable-container"><table class="table-cards"><thead><tr><th>${labels.stock}</th><th class="prices-date-col">${labels.date}</th><th>${labels.close}</th><th>${labels.volume}</th></tr></thead><tbody>`;

        filteredData.forEach(stock => {
            const companyName = getCompanyName(stock.symbol);
            html += `
                <tr>
                    <td data-label="${labels.stock}" class="stock-cell"><strong>${stock.symbol}</strong><br><small class="company-name">${companyName}</small></td>
                    <td data-label="${labels.date}" class="prices-date-col">${formatDate(stock.date)}</td>
                    <td data-label="${labels.close}" class="price-cell">${parseFloat(stock.close).toFixed(2)}</td>
                    <td data-label="${labels.volume}" class="volume-cell">${parseInt(stock.volume).toLocaleString()}</td>
                </tr>
            `;
        });

        html += '</tbody></table></div>';
        container.innerHTML = html;
    } catch (error) {
        console.error('Error loading prices:', error);
        container.innerHTML = `<p class="error-message">${t('errorPrices')}</p>`;
    }
}

// ============================================
// LOAD CONSENSUS DATA (3-Layer Pipeline)
// ============================================

async function loadConsensus() {
    const cardsContainer = document.getElementById('consensusCards');
    if (!cardsContainer) return;

    try {
        // Fetch consensus data and risk overview in parallel
        const [consensusRes, riskRes] = await Promise.all([
            fetch(`${API_URL}/consensus`),
            fetch(`${API_URL}/risk/overview`)
        ]);

        const consensusData = consensusRes.ok ? await consensusRes.json() : [];
        const riskData = riskRes.ok ? await riskRes.json() : { stocks: [], summary: {} };

        // Update risk overview stats
        const summary = riskData.summary || {};
        const elTotal = document.getElementById('riskStocksTotal');
        const elPassed = document.getElementById('riskPassed');
        const elFlagged = document.getElementById('riskFlagged');
        const elBlocked = document.getElementById('riskBlocked');
        if (elTotal) elTotal.textContent = summary.total || 0;
        if (elPassed) elPassed.textContent = summary.passed || 0;
        if (elFlagged) elFlagged.textContent = (summary.flagged || 0) + (summary.downgraded || 0);
        if (elBlocked) elBlocked.textContent = summary.blocked || 0;

        // Update i18n labels
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            if (key) el.textContent = t(key);
        });

        clearSkeleton('consensusCards');
        if (!consensusData || consensusData.length === 0) {
            cardsContainer.innerHTML = `<p class="no-data">${t('noConsensus')}</p>`;
            return;
        }

        // Filter to watchlist stocks for logged-in users
        let filteredConsensus = consensusData;
        if (isLoggedIn()) {
            if (userWatchlistSymbols.size === 0) {
                cardsContainer.innerHTML = getWatchlistEmptyHtml();
                return;
            }
            filteredConsensus = consensusData.filter(item => userWatchlistSymbols.has(item.symbol));
            if (filteredConsensus.length === 0) {
                cardsContainer.innerHTML = `<p class="no-data">${t('noConsensus')}</p>`;
                return;
            }
        }

        // Render consensus cards
        let html = '';
        filteredConsensus.forEach(item => {
            html += renderConsensusCard(item);
        });
        cardsContainer.innerHTML = html;

    } catch (error) {
        console.error('Error loading consensus:', error);
        cardsContainer.innerHTML = `<p class="error-message">${t('errorConsensus')}</p>`;
    }
}

// ─── Universal Investor Scoring Panel ───────────────────────────────────────

let _currentScoringMode = 'standard_100';

const SCORING_MODE_LABELS = {
    en: {
        xmore_native: 'Xmore (0–1)',
        standard_100: 'Score (0–100)',
        letter_grade: 'Grade',
        stars:        'Stars',
        signal_tier:  'Tier',
        conviction:   'Conviction',
    },
    ar: {
        xmore_native: 'Xmore (0–1)',
        standard_100: 'درجة (0–100)',
        letter_grade: 'تقدير',
        stars:        'نجوم',
        signal_tier:  'مستوى',
        conviction:   'اقتناع',
    },
};

async function loadScoringPanel() {
    const container = document.getElementById('scoringPanelContainer');
    if (!container) return;

    try {
        const res = await fetch(`${API_URL}/signals/scored/compare?days=1&action=BUY`);
        if (!res.ok) throw new Error('scoring API not available');
        const data = await res.json();

        container.innerHTML = buildScoringPanelHTML(data);
    } catch (err) {
        const container2 = document.getElementById('scoringPanelContainer');
        if (container2) container2.innerHTML = `<p class="scoring-no-data">${t('scoringNoData')}</p>`;
    }
}

function buildScoringPanelHTML(data) {
    const signals = data.signals || [];
    const modes   = ['xmore_native', 'standard_100', 'letter_grade', 'stars', 'signal_tier', 'conviction'];
    const labels  = SCORING_MODE_LABELS[currentLang] || SCORING_MODE_LABELS.en;

    const modeSelect = `<div class="scoring-mode-bar">
        <span class="scoring-mode-label">${t('scoringModeLabel')}:</span>
        ${modes.map(m => `<button class="scoring-mode-btn${m === _currentScoringMode ? ' active' : ''}"
            onclick="setScoringMode('${m}')">${labels[m]}</button>`).join('')}
    </div>`;

    if (!signals.length) {
        return modeSelect + `<p class="scoring-no-data">${t('scoringNoData')}</p>`;
    }

    const colLabels = {
        stock: t('stock'),
        score: (SCORING_MODE_LABELS[currentLang] || SCORING_MODE_LABELS.en)[_currentScoringMode],
        composite: t('scoringComposite'),
        components: t('scoringComponents'),
        threshold: t('scoringMeetsThreshold')
    };

    const rows = signals.map(sig => {
        const sc   = sig.scores || {};
        const val  = sc[_currentScoringMode] !== undefined ? sc[_currentScoringMode] : '—';
        const disp = _currentScoringMode === 'stars' ? '★'.repeat(Math.round(val)) + ' ' + val : val;
        const comp = sig.components || {};
        return `<tr class="scoring-row${sig.meets_threshold ? ' scoring-above-threshold' : ''}">
            <td data-label="${colLabels.stock}" class="scoring-symbol">${sig.symbol}</td>
            <td data-label="${colLabels.score}" class="scoring-score">${disp}</td>
            <td data-label="${colLabels.composite}" class="scoring-composite">${(sig.composite_score * 100).toFixed(0)}</td>
            <td data-label="${colLabels.components}" class="scoring-bar-cell">
                <div class="scoring-mini-bar">
                    <span class="scoring-bar-seg scoring-bar-consensus" style="width:${(comp.consensus||0)*100}%"></span>
                    <span class="scoring-bar-seg scoring-bar-execution" style="width:${(comp.execution||0)*100}%"></span>
                    <span class="scoring-bar-seg scoring-bar-regime"    style="width:${(comp.regime||0)*100}%"></span>
                    <span class="scoring-bar-seg scoring-bar-momentum"  style="width:${(comp.momentum||0)*100}%"></span>
                </div>
            </td>
            <td data-label="${colLabels.threshold}" class="scoring-threshold">${sig.meets_threshold ? '✓' : ''}</td>
        </tr>`;
    }).join('');

    return `${modeSelect}
    <table class="scoring-table table-cards">
        <thead><tr>
            <th>${labels.stock}</th>
            <th>${labels.score}</th>
            <th>${labels.composite}</th>
            <th>${labels.components}</th>
            <th>${labels.threshold}</th>
        </tr></thead>
        <tbody>${rows}</tbody>
    </table>`;
}

function setScoringMode(mode) {
    _currentScoringMode = mode;
    loadScoringPanel();
}


function renderConsensusCard(item) {
    const isArabic = currentLang === 'ar';
    const companyName = getCompanyName(item.symbol);

    // Signal display
    const display = item.display || {};
    const signalText = isArabic ? (display.signal_text_ar || display.signal_text || item.final_signal) : (display.signal_text || item.final_signal);
    const signalKey = (item.final_signal || 'HOLD').toLowerCase();

    // Conviction
    const convictionText = isArabic ? (display.conviction_text_ar || item.conviction) : (display.conviction_text || item.conviction);
    const convictionClass = (item.conviction || 'LOW').toLowerCase().replace('_', '-');

    // Summary
    const summaryText = isArabic ? (display.summary_ar || display.summary || '') : (display.summary || '');

    // Bull/Bear scores
    const bullScore = item.bull_score || 0;
    const bearScore = item.bear_score || 0;

    // Risk action
    const riskAction = item.risk_action || 'PASS';
    const riskScore = item.risk_score || 0;
    const riskAdjusted = item.risk_adjusted;

    // Risk warnings from risk_assessment
    const riskAssessment = item.risk_assessment || {};
    const riskFlags = isArabic ? (riskAssessment.risk_flags_ar || []) : (riskAssessment.risk_flags || []);

    // Agreement
    const agreementPct = Math.round((item.agent_agreement || 0) * 100);
    const agentsAgreeing = item.agents_agreeing || 0;
    const agentsTotal = item.agents_total || 0;

    // Risk action badge class
    let riskBadgeClass = 'risk-badge-pass';
    let riskBadgeText = '✓ PASS';
    if (riskAction === 'BLOCK') {
        riskBadgeClass = 'risk-badge-block';
        riskBadgeText = '🚫 BLOCK';
    } else if (riskAction === 'DOWNGRADE') {
        riskBadgeClass = 'risk-badge-downgrade';
        riskBadgeText = '⬇ DOWNGRADE';
    } else if (riskAction === 'FLAG') {
        riskBadgeClass = 'risk-badge-flag';
        riskBadgeText = '⚠️ FLAG';
    }

    return `
    <div class="consensus-card ${riskAction === 'BLOCK' ? 'consensus-card-blocked' : ''}">
        <div class="consensus-card-header">
            <div class="consensus-card-stock">
                <strong>${item.symbol}</strong>
                <small class="company-name">${companyName}</small>
            </div>
            <div class="consensus-card-signal">
                <span class="consensus-signal-badge signal-${signalKey}">${signalText}</span>
                ${riskAdjusted ? '<span class="risk-adjusted-badge" title="Risk-adjusted">⚠️</span>' : ''}
            </div>
        </div>

        <div class="consensus-card-body">
            <!-- Conviction & Agreement -->
            <div class="consensus-meta-row">
                <div class="consensus-meta-item">
                    <span class="meta-label">${t('conviction')}:</span>
                    <span class="conviction-badge conviction-${convictionClass}">${convictionText}</span>
                </div>
                <div class="consensus-meta-item">
                    <span class="meta-label">${t('consensus')}:</span>
                    <span class="agreement-text">${agentsAgreeing}/${agentsTotal} (${agreementPct}%)</span>
                </div>
            </div>

            <!-- Bull/Bear Bars -->
            <div class="bull-bear-section">
                <div class="bull-bear-row">
                    <span class="bb-label">🐂 ${t('bullCase')}</span>
                    <div class="bb-bar-container">
                        <div class="bb-bar bb-bull" style="width: ${bullScore}%"></div>
                    </div>
                    <span class="bb-score">${bullScore}</span>
                </div>
                <div class="bull-bear-row">
                    <span class="bb-label">🐻 ${t('bearCase')}</span>
                    <div class="bb-bar-container">
                        <div class="bb-bar bb-bear" style="width: ${bearScore}%"></div>
                    </div>
                    <span class="bb-score">${bearScore}</span>
                </div>
            </div>

            <!-- Risk Badge -->
            <div class="consensus-risk-row">
                <span class="${riskBadgeClass}">${riskBadgeText}</span>
                <span class="risk-score-text">${t('riskAction')}: ${riskScore}/100</span>
            </div>

            <!-- Summary -->
            <div class="consensus-summary">${summaryText}</div>

            ${riskFlags.length > 0 ? `
            <details class="risk-warnings-details">
                <summary>${t('riskWarnings')} (${riskFlags.length})</summary>
                <ul class="risk-warnings-list">
                    ${riskFlags.map(f => `<li>${f}</li>`).join('')}
                </ul>
            </details>` : ''}
        </div>
    </div>`;
}

// ============================================================
// RESEARCH CHAT WIDGET
// ============================================================

let _chatOpen = false;
const _chatHistory = [];

function initChatWidget() {
    const toggleBtn = document.getElementById('chatToggleBtn');
    const closeBtn = document.getElementById('chatClose');
    const input = document.getElementById('chatInput');
    if (!toggleBtn) return;

    toggleBtn.addEventListener('click', () => {
        _chatOpen ? closeChatPanel() : openChatPanel();
    });
    if (closeBtn) closeBtn.addEventListener('click', closeChatPanel);
    if (input) {
        input.addEventListener('keydown', e => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChatMessage(); }
        });
    }

    // Close panel if clicking the backdrop (on mobile the chat doesn't have one, but close on ESC)
    document.addEventListener('keydown', e => { if (e.key === 'Escape') { closeChatPanel(); closeSentimentModal(); } });

    // Add welcome message
    appendChatMessage('ai', currentLang === 'ar'
        ? 'مرحباً! أنا مساعد البحث لسوق البورصة المصرية. اسألني عن أي سهم أو أخبار أو تقرير.'
        : 'Hello! I\'m your EGX research assistant. Ask me about any stock, news, or market report.');
}

function openChatPanel() {
    const panel = document.getElementById('chatPanel');
    if (panel) { panel.classList.remove('chat-hidden'); }
    _chatOpen = true;
    const input = document.getElementById('chatInput');
    if (input) setTimeout(() => input.focus(), 100);
    // Update title for language
    const titleEl = document.getElementById('chatTitle');
    if (titleEl) titleEl.textContent = currentLang === 'ar' ? 'مساعد البحث' : 'AI Research Assistant';
    const inputEl = document.getElementById('chatInput');
    if (inputEl) inputEl.placeholder = currentLang === 'ar' ? 'اسأل عن أي سهم في البورصة المصرية…' : 'Ask about any EGX stock…';
}

function closeChatPanel() {
    const panel = document.getElementById('chatPanel');
    if (panel) { panel.classList.add('chat-hidden'); }
    _chatOpen = false;
}

function appendChatMessage(role, text, sources) {
    const messages = document.getElementById('chatMessages');
    if (!messages) return;

    const div = document.createElement('div');
    div.className = `chat-msg chat-msg-${role}`;
    div.textContent = text;

    if (sources && sources.length > 0) {
        const srcDiv = document.createElement('div');
        srcDiv.className = 'chat-sources';
        srcDiv.innerHTML = sources.slice(0, 5).map(s => {
            const isWeb = s.type === 'web';
            const cls   = isWeb ? 'chat-source-pill chat-source-web' : 'chat-source-pill';
            const label = escHtml(s.title || s.source || 'Source');
            return isWeb && s.url
                ? `<a class="${cls}" href="${escHtml(s.url)}" target="_blank" rel="noopener">${label}</a>`
                : `<span class="${cls}">${label}</span>`;
        }).join(' ');
        div.appendChild(srcDiv);
    }

    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
}

async function sendChatMessage(prefill) {
    const input = document.getElementById('chatInput');
    const sendBtn = document.getElementById('chatSend');
    if (!input) return;

    if (prefill) input.value = prefill;
    const question = input.value.trim();
    if (!question) return;

    input.value = '';
    appendChatMessage('user', question);
    if (sendBtn) { sendBtn.disabled = true; }

    // Typing indicator
    const typingId = 'chat-typing-' + Date.now();
    const messages = document.getElementById('chatMessages');
    if (messages) {
        const typing = document.createElement('div');
        typing.id = typingId;
        typing.className = 'chat-msg chat-msg-ai chat-typing';
        typing.textContent = currentLang === 'ar' ? 'جاري التفكير…' : 'Thinking…';
        messages.appendChild(typing);
        messages.scrollTop = messages.scrollHeight;
    }

    try {
        const res = await fetch('/api/rag/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question })
        });
        const data = await res.json();
        // Remove typing indicator
        const typingEl = document.getElementById(typingId);
        if (typingEl) typingEl.remove();

        if (data.error) throw new Error(data.error);
        appendChatMessage('ai', data.answer || '(No response)', data.sources || []);
    } catch (e) {
        const typingEl = document.getElementById(typingId);
        if (typingEl) typingEl.remove();
        appendChatMessage('ai', `Error: ${e.message}`);
    } finally {
        if (sendBtn) { sendBtn.disabled = false; }
        if (input) input.focus();
    }
}

async function sendMacroRead() {
    const sendBtn = document.getElementById('chatSend');
    appendChatMessage('user', '📊 EGX Macro Brief for today');

    const typingId = 'chat-typing-' + Date.now();
    const messages = document.getElementById('chatMessages');
    if (messages) {
        const t = document.createElement('div');
        t.id = typingId;
        t.className = 'chat-msg chat-msg-ai chat-typing';
        t.textContent = 'Searching live macro data…';
        messages.appendChild(t);
        messages.scrollTop = messages.scrollHeight;
    }
    if (sendBtn) sendBtn.disabled = true;

    try {
        const res  = await fetch('/api/rag/macro', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
        const data = await res.json();
        const el = document.getElementById(typingId); if (el) el.remove();
        if (data.error) throw new Error(data.error);
        appendChatMessage('ai', data.answer || '(No response)', data.sources || []);
    } catch (e) {
        const el = document.getElementById(typingId); if (el) el.remove();
        appendChatMessage('ai', `Error: ${e.message}`);
    } finally {
        if (sendBtn) sendBtn.disabled = false;
    }
}

// Initialise chat widget when DOM is ready
document.addEventListener('DOMContentLoaded', () => { initChatWidget(); });

// ── Why This Signal? Modal ────────────────────────────────────────────────────

async function showWhySignal(symbol, signal) {
    const modal   = document.getElementById('whySignalModal');
    const title   = document.getElementById('whyModalTitle');
    const loading = document.getElementById('whyModalLoading');
    const content = document.getElementById('whyModalContent');
    const expl    = document.getElementById('whyModalExplanation');
    const srcs    = document.getElementById('whyModalSources');

    if (!modal) return;

    // Reset and show modal
    title.textContent = `💡 AI Insight — ${symbol}`;
    loading.style.display = '';
    content.style.display = 'none';
    expl.innerHTML = '';
    srcs.innerHTML = '';
    modal.style.display = 'flex';

    try {
        const res  = await fetch('/api/rag/why-signal', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({ symbol, signal }),
        });
        const data = await res.json();

        if (!res.ok) throw new Error(data.error || 'Request failed');

        expl.innerHTML = `<p>${(data.explanation || '').replace(/\n/g, '<br>')}</p>`;

        if (data.sources && data.sources.length) {
            srcs.innerHTML = '<div class="why-sources-title">Sources</div>' +
                data.sources.map(s => {
                    const meta    = s.source_meta || {};
                    const label   = meta.filename || meta.headline || `Chunk ${s.chunk_index || ''}`;
                    const subline = meta.date ? ` · ${meta.date}` : '';
                    const pct     = s.similarity != null ? ` (${(s.similarity * 100).toFixed(0)}% match)` : '';
                    return `<div class="why-source-item"><span class="why-source-type">${s.source_type || ''}</span> ${label}${subline}${pct}</div>`;
                }).join('');
        }

        loading.style.display = 'none';
        content.style.display = '';
    } catch (err) {
        loading.textContent = `Error: ${err.message}`;
    }
}

function closeWhyModal() {
    const modal = document.getElementById('whySignalModal');
    if (modal) modal.style.display = 'none';
}

// ── ETF Fund Intelligence Dashboard ────────────────────────────────────────────

let etfLoaded = false;
let _etfAllInstruments = [];
let _etfCurrentSub = 'etfs';
let _etfCurrentView = 'grid';

// ETP instrument types
const _ETP_TYPES = new Set(['GOLD_ETP','INDEX_TRACKER','STRUCTURED_NOTE','ETN','UNKNOWN_ETP','ETP','COMMODITY_ETP']);

function _fmtPct(val) {
    if (val == null) return '—';
    const n = parseFloat(val);
    if (isNaN(n)) return '—';
    return (n >= 0 ? '+' : '') + n.toFixed(2) + '%';
}
function _fmtNum(val, decimals = 2) {
    if (val == null) return '—';
    const n = parseFloat(val);
    if (isNaN(n)) return '—';
    return n.toFixed(decimals);
}
function _pdLabel(val) {
    if (val == null) return '—';
    const n = parseFloat(val);
    if (isNaN(n)) return '—';
    return (n >= 0 ? '+' : '') + (n * 100).toFixed(2) + '%';
}
function _pdClass(val) {
    const n = parseFloat(val);
    if (isNaN(n)) return '';
    return n >= 0 ? 'prem-positive' : 'prem-negative';
}
function _pctClass(val) {
    const n = parseFloat(val);
    if (isNaN(n)) return '';
    return n >= 0 ? 'etf-pos' : 'etf-neg';
}
function _liquidityLabel(valueTradedEGP) {
    const v = parseFloat(valueTradedEGP);
    if (isNaN(v) || v <= 0) return '<span class="etf-liquidity liq-low">Low</span>';
    if (v >= 5_000_000) return '<span class="etf-liquidity liq-high">High</span>';
    if (v >= 500_000)   return '<span class="etf-liquidity liq-med">Med</span>';
    return '<span class="etf-liquidity liq-low">Low</span>';
}
function _typeBadge(type) {
    const map = {
        'ETF':              ['badge-etf',  'ETF'],
        'GOLD_ETP':         ['badge-gold', 'Gold ETP'],
        'INDEX_TRACKER':    ['badge-tracker','Tracker'],
        'STRUCTURED_NOTE':  ['badge-note', 'Note'],
        'ETN':              ['badge-etp',  'ETN'],
        'COMMODITY_ETP':    ['badge-gold', 'Commodity'],
        'ETP':              ['badge-etp',  'ETP'],
        'UNKNOWN_ETP':      ['badge-etp',  'ETP'],
        'EQUITY_FUND':      ['badge-fund', 'Fund'],
    };
    const [cls, label] = map[type] || ['badge-etp', type || 'ETP'];
    return `<span class="etf-type-badge ${cls}">${label}</span>`;
}
function _etfClassify(i) {
    if (!i.region || !i.region.includes('EGX')) return 'global-etfs';
    if (i.type === 'ETF') return 'etfs';
    if (_ETP_TYPES.has(i.type)) return 'etps';
    if (i.type === 'EQUITY_FUND') return 'equity-funds';
    return 'etps';
}

async function loadEtfTab() {
    if (etfLoaded) return;
    etfLoaded = true;
    try {
        const instruments = await fetch('/api/etf/instruments').then(r => r.json());
        _etfAllInstruments = instruments;

        const loading = document.getElementById('etfMainLoading');
        if (loading) loading.style.display = 'none';

        // Classify
        const groups = { 'etfs': [], 'etps': [], 'equity-funds': [], 'global-etfs': [] };
        instruments.forEach(i => { const g = _etfClassify(i); if (groups[g]) groups[g].push(i); });

        // Update badges
        Object.entries(groups).forEach(([key, arr]) => {
            const el = document.getElementById('badge-' + key);
            if (el) el.textContent = arr.length;
        });

        // Render the active sub-panel
        Object.entries(groups).forEach(([key, arr]) => _etfRenderGroup(key, arr));

        // Wire up sub-nav clicks
        document.querySelectorAll('.etf-subnav-btn').forEach(btn => {
            btn.addEventListener('click', () => _etfSwitchSub(btn.dataset.etfsub));
        });

        // Wire up view-toggle clicks
        document.querySelectorAll('.etf-view-btn').forEach(btn => {
            btn.addEventListener('click', () => _etfToggleView(btn.dataset.view));
        });

        // Wire up search
        const searchEl = document.getElementById('etfSearchInput');
        if (searchEl) searchEl.addEventListener('input', _etfApplyFilter);

    } catch (err) {
        const el = document.getElementById('etfMainLoading');
        if (el) el.textContent = t('etfLoadError');
    }
}

function _etfRenderGroup(key, instruments) {
    const panel = document.getElementById('etfPanel-' + key);
    if (!panel) return;
    if (key === 'equity-funds') return; // static coming-soon HTML set in index.html

    if (!instruments.length) {
        panel.innerHTML = `<div class="etf-empty-state">
            <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.35"><rect x="3" y="3" width="18" height="18" rx="3"/><path d="M3 9h18M9 21V9"/></svg>
            <p>${t('etfNoData')}</p><span>${t('etfNoDataSub')}</span></div>`;
        return;
    }

    panel.innerHTML = `
        <div id="etfGrid-${key}" class="etf-grid">${instruments.map(i => _etfBuildCard(i, key)).join('')}</div>
        <div id="etfTable-${key}" class="etf-table-wrap" style="display:none">
            ${_etfBuildTable(instruments, key)}
        </div>`;
}

function _etfBuildCard(i, group) {
    const price = _fmtNum(i.close_price || i.last_price);
    const pct   = _fmtPct(i.pct_change);
    const pctCls = _pctClass(i.pct_change);

    if (group === 'global-etfs') {
        const egyptPct = i.weight_pct != null ? parseFloat(i.weight_pct).toFixed(1) + '%' : '—';
        return `<div class="etf-card" onclick="showEtf${t('etfHoldings')}('${i.symbol}')">
            <div class="etf-card-header">
                <div class="etf-card-symbol-row">
                    <span class="etf-symbol">${i.symbol}</span>
                    ${_typeBadge('ETF')}
                </div>
                <span class="etf-exchange">${i.exchange || ''}</span>
            </div>
            <div class="etf-card-name" title="${i.name || ''}">${i.name || ''}</div>
            <div class="etf-card-row"><span class="etf-label">${t('etfEgyptExposure')}</span><span class="etf-value">${egyptPct}</span></div>
            <div class="etf-card-row"><span class="etf-label">${t('etfPrice')}</span><span class="etf-value">${price}</span></div>
            <div class="etf-card-row"><span class="etf-label">${t('etfChange')}</span><span class="etf-value ${pctCls}">${pct}</span></div>
            <div class="etf-card-row"><span class="etf-label">${t('etfNav')}</span><span class="etf-value">${_fmtNum(i.nav_value)}</span></div>
            <div class="etf-card-row"><span class="etf-label">${t('etfPremDisc')}</span><span class="etf-value ${_pdClass(i.premium_discount)}">${_pdLabel(i.premium_discount)}</span></div>
            <div class="etf-card-actions"><button class="etf-action-btn" onclick="event.stopPropagation();showEtf${t('etfHoldings')}('${i.symbol}')">${t('etfHoldings')}</button></div>
        </div>`;
    }

    if (group === 'etps') {
        const underlying = i.underlying_index || '—';
        const issuer = i.issuer || '—';
        const navVal  = _fmtNum(i.nav_value);
        const ret3m   = _fmtPct(i.pct_change);   // stored as 3-month return from EGX data
        const ret3mCls = _pctClass(i.pct_change);
        return `<div class="etf-card" onclick="showEtf${t('etfHoldings')}('${i.symbol}')">
            <div class="etf-card-header">
                <div class="etf-card-symbol-row">
                    <span class="etf-symbol">${i.symbol}</span>
                    ${_typeBadge(i.type)}
                </div>
            </div>
            <div class="etf-card-name" title="${i.name || ''}">${i.name || ''}</div>
            <div class="etf-card-issuer">${t('etfIssuer')}: ${issuer}</div>
            <div class="etf-card-row"><span class="etf-label">${t('etfNav')}</span><span class="etf-value">${navVal}</span></div>
            <div class="etf-card-row"><span class="etf-label">${t('etfRet3m')}</span><span class="etf-value ${ret3mCls}">${ret3m}</span></div>
            <div class="etf-card-row"><span class="etf-label">${t('etfUnderlying')}</span><span class="etf-value">${underlying}</span></div>
            <div class="etf-card-row"><span class="etf-label">${t('etfLiquidity')}</span><span class="etf-value">${_liquidityLabel(i.value_traded)}</span></div>
        </div>`;
    }

    // Default: ETF card
    return `<div class="etf-card" onclick="showEtf${t('etfHoldings')}('${i.symbol}')">
        <div class="etf-card-header">
            <div class="etf-card-symbol-row">
                <span class="etf-symbol">${i.symbol}</span>
                ${_typeBadge('ETF')}
            </div>
            <span class="etf-exchange">${i.exchange || ''}</span>
        </div>
        <div class="etf-card-name" title="${i.name || ''}">${i.name || ''}</div>
        <div class="etf-card-row"><span class="etf-label">${t('etfPrice')}</span><span class="etf-value">${price}</span></div>
        <div class="etf-card-row"><span class="etf-label">${t('etfChange')}</span><span class="etf-value ${pctCls}">${pct}</span></div>
        <div class="etf-card-row"><span class="etf-label">${t('etfNav')}</span><span class="etf-value">${_fmtNum(i.nav_value)}</span></div>
        <div class="etf-card-row"><span class="etf-label">${t('etfPremDisc')}</span><span class="etf-value ${_pdClass(i.premium_discount)}">${_pdLabel(i.premium_discount)}</span></div>
        <div class="etf-card-row"><span class="etf-label">${t('etfLiquidity')}</span><span class="etf-value">${_liquidityLabel(i.value_traded)}</span></div>
        <div class="etf-card-actions"><button class="etf-action-btn" onclick="event.stopPropagation();showEtf${t('etfHoldings')}('${i.symbol}')">${t('etfHoldings')}</button></div>
    </div>`;
}

function _etfBuildTable(instruments, group) {
    let headers, rowFn;
    const cell = (label, html, cls) =>
        `<td data-label="${label}"${cls ? ` class="${cls}"` : ''}>${html}</td>`;
    if (group === 'global-etfs') {
        headers = [t('mhSymbol'), t('etfName'), t('etfExchange'), t('etfEgyptExposure'), t('etfPrice'), t('etfChange'), t('etfNav'), t('etfPremDisc')];
        rowFn = i => {
            const pct = _fmtPct(i.pct_change);
            const pctCls = _pctClass(i.pct_change);
            const egyptPct = i.weight_pct != null ? parseFloat(i.weight_pct).toFixed(1) + '%' : '—';
            return `<tr onclick="showEtfHoldings('${i.symbol}')" style="cursor:pointer">
                ${cell(headers[0], `<strong>${i.symbol}</strong>`)}
                ${cell(headers[1], `<span style="max-width:180px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:inline-block;" title="${i.name||''}">${i.name||'—'}</span>`)}
                ${cell(headers[2], i.exchange||'—', 'cell-muted')}
                ${cell(headers[3], egyptPct)}
                ${cell(headers[4], _fmtNum(i.close_price||i.last_price))}
                ${cell(headers[5], pct, pctCls)}
                ${cell(headers[6], _fmtNum(i.nav_value))}
                ${cell(headers[7], _pdLabel(i.premium_discount), _pdClass(i.premium_discount))}
            </tr>`;
        };
    } else if (group === 'etps') {
        headers = [t('mhSymbol'), t('etfName'), t('etfIssuer'), t('etfUnderlying'), t('etfPrice'), t('etfChange'), t('etfLiquidity')];
        rowFn = i => {
            const pctCls = _pctClass(i.pct_change);
            return `<tr>
                ${cell(headers[0], `<strong>${i.symbol}</strong> ${_typeBadge(i.type)}`)}
                ${cell(headers[1], `<span style="max-width:200px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:inline-block;" title="${i.name||''}">${i.name||'—'}</span>`)}
                ${cell(headers[2], i.issuer||'—', 'cell-muted')}
                ${cell(headers[3], i.underlying_index||'—', 'cell-muted')}
                ${cell(headers[4], _fmtNum(i.close_price||i.last_price))}
                ${cell(headers[5], _fmtPct(i.pct_change), pctCls)}
                ${cell(headers[6], _liquidityLabel(i.value_traded))}
            </tr>`;
        };
    } else {
        headers = [t('mhSymbol'), t('etfName'), t('etfExchange'), t('etfPrice'), t('etfChange'), t('etfNav'), t('etfPremDisc'), t('etfLiquidity')];
        rowFn = i => {
            const pctCls = _pctClass(i.pct_change);
            return `<tr onclick="showEtfHoldings('${i.symbol}')" style="cursor:pointer">
                ${cell(headers[0], `<strong>${i.symbol}</strong>`)}
                ${cell(headers[1], `<span style="max-width:200px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:inline-block;" title="${i.name||''}">${i.name||'—'}</span>`)}
                ${cell(headers[2], i.exchange||'—', 'cell-muted')}
                ${cell(headers[3], _fmtNum(i.close_price||i.last_price))}
                ${cell(headers[4], _fmtPct(i.pct_change), pctCls)}
                ${cell(headers[5], _fmtNum(i.nav_value))}
                ${cell(headers[6], _pdLabel(i.premium_discount), _pdClass(i.premium_discount))}
                ${cell(headers[7], _liquidityLabel(i.value_traded))}
            </tr>`;
        };
    }
    return `<table class="etf-data-table table-cards">
        <thead><tr>${headers.map(h => `<th>${h}</th>`).join('')}</tr></thead>
        <tbody>${instruments.map(rowFn).join('')}</tbody>
    </table>`;
}

function _etfSwitchSub(key) {
    _etfCurrentSub = key;
    document.querySelectorAll('.etf-subnav-btn').forEach(btn => {
        const active = btn.dataset.etfsub === key;
        btn.classList.toggle('active', active);
        btn.setAttribute('aria-selected', active);
    });
    document.querySelectorAll('.etf-subpanel').forEach(p => p.style.display = 'none');
    const panel = document.getElementById('etfPanel-' + key);
    if (panel) panel.style.display = '';
    _etfApplyFilter();
}

function _etfToggleView(mode) {
    _etfCurrentView = mode;
    document.querySelectorAll('.etf-view-btn').forEach(btn =>
        btn.classList.toggle('active', btn.dataset.view === mode));
    ['etfs','etps','global-etfs'].forEach(key => {
        const grid = document.getElementById('etfGrid-' + key);
        const table = document.getElementById('etfTable-' + key);
        if (grid)  grid.style.display  = mode === 'grid'  ? '' : 'none';
        if (table) table.style.display = mode === 'table' ? '' : 'none';
    });
}

function _etfApplyFilter() {
    const q = (document.getElementById('etfSearchInput')?.value || '').toLowerCase().trim();
    const key = _etfCurrentSub;
    if (key === 'equity-funds') return;

    const instruments = _etfAllInstruments.filter(i => {
        if (_etfClassify(i) !== key) return false;
        if (!q) return true;
        return (i.symbol||'').toLowerCase().includes(q) || (i.name||'').toLowerCase().includes(q) || (i.issuer||'').toLowerCase().includes(q);
    });

    const panel = document.getElementById('etfPanel-' + key);
    if (!panel) return;

    const gridEl = document.getElementById('etfGrid-' + key);
    const tableEl = document.getElementById('etfTable-' + key);

    if (!instruments.length) {
        if (gridEl) gridEl.innerHTML = `<div style="color:var(--text-muted);font-size:13px;padding:20px 0;">${q ? t('etfNoResults') + ' \"' + q + '\"' : t('etfNoData')}</div>`;
        if (tableEl) tableEl.innerHTML = '';
        return;
    }

    if (gridEl) gridEl.innerHTML = instruments.map(i => _etfBuildCard(i, key)).join('');
    if (tableEl) tableEl.innerHTML = _etfBuildTable(instruments, key);
}

async function showEtfHoldings(symbol) {
    const modal   = document.getElementById('etfHoldingsModal');
    const title   = document.getElementById('etfModalTitle');
    const loading = document.getElementById('etfModalLoading');
    const content = document.getElementById('etfModalContent');
    const meta    = document.getElementById('etfModalMeta');
    const lines   = document.getElementById('etfModalLines');
    if (!modal) return;

    modal.style.display = 'flex';
    if (title)   title.textContent = `${symbol} — ${t('etfHoldingsTitle')}`;
    if (loading) loading.style.display = 'block';
    if (content) content.style.display = 'none';

    try {
        const data = await fetch(`/api/etf/holdings/${symbol}`).then(r => r.json());
        if (loading) loading.style.display = 'none';
        if (!data || !data.snapshot) {
            if (content) { content.style.display = 'block'; }
            if (meta) meta.textContent = t('etfNoHoldings');
            if (lines) lines.innerHTML = '';
            return;
        }
        const snap = data.snapshot;
        if (meta) meta.textContent = `As of ${snap.snapshot_date} · Source: ${snap.source} · ${snap.currency || ''} · Total weight: ${snap.total_weight != null ? parseFloat(snap.total_weight).toFixed(1) + '%' : '—'}`;
        if (lines) {
            const labels = {
                line: 'Line',
                holding: 'Holding',
                isin: 'ISIN',
                country: 'Country',
                sector: 'Sector',
                weight: 'Weight %'
            };
            lines.innerHTML = (data.lines || []).map(l => `
                <tr>
                    <td data-label="${labels.line}">${l.line_no}</td>
                    <td data-label="${labels.holding}">${l.holding_name || l.holding_symbol || '—'}</td>
                    <td data-label="${labels.isin}" style="font-size:11px;color:var(--text-muted);">${l.holding_isin || ''}</td>
                    <td data-label="${labels.country}">${l.country || '—'}</td>
                    <td data-label="${labels.sector}">${l.sector || '—'}</td>
                    <td data-label="${labels.weight}"><strong>${l.weight_pct != null ? parseFloat(l.weight_pct).toFixed(2) + '%' : '—'}</strong></td>
                </tr>`).join('') || '<tr><td colspan="6" style="text-align:center;color:var(--text-muted);">No holding lines.</td></tr>';
        }
        if (content) content.style.display = 'block';
    } catch (err) {
        if (loading) loading.textContent = `Error: ${err.message}`;
    }
}

function closeEtfModal() {
    const modal = document.getElementById('etfHoldingsModal');
    if (modal) modal.style.display = 'none';
}

// ============================================================
// PORTFOLIO — enhanced with EGP P&L + sector breakdown
// ============================================================

function renderPortfolioTotals(totals) {
    const strip = document.getElementById('portfolioTotals');
    if (!strip || !totals) return;
    const fmt = n => n != null ? Number(n).toLocaleString('en-EG', { minimumFractionDigits: 0, maximumFractionDigits: 0 }) : '—';
    const pnl = totals.total_pnl_egp;
    const ret = totals.total_return_pct;
    document.getElementById('ptlCost').textContent = fmt(totals.total_cost_egp) + ' EGP';
    document.getElementById('ptlValue').textContent = fmt(totals.total_value_egp) + ' EGP';
    const pnlEl = document.getElementById('ptlPnl');
    pnlEl.textContent = (pnl >= 0 ? '+' : '') + fmt(pnl) + ' EGP';
    pnlEl.style.color = pnl >= 0 ? 'var(--bullish)' : 'var(--bearish)';
    const retEl = document.getElementById('ptlRet');
    retEl.textContent = (ret >= 0 ? '+' : '') + Number(ret).toFixed(2) + '%';
    retEl.style.color = ret >= 0 ? 'var(--bullish)' : 'var(--bearish)';
    strip.style.display = 'flex';
}

function renderSectorBreakdown(sectors) {
    const el = document.getElementById('portfolioSectors');
    if (!el || !sectors || !sectors.length) return;
    el.innerHTML = sectors.map(s =>
        `<div class="pf-sector-pill" title="${s.sector}: ${s.weight_pct}%">
            <div class="pf-sector-bar-fill" style="width:${s.weight_pct}%"></div>
            <span class="pf-sector-name">${s.sector}</span>
            <span class="pf-sector-pct">${s.weight_pct}%</span>
        </div>`
    ).join('');
    el.style.display = 'flex';
}

// ============================================================
// PRICE ALERTS
// ============================================================

async function loadAlerts() {
    const listEl = document.getElementById('alertsList');
    if (!listEl) return;
    try {
        const data = await fetch('/api/trades/alerts', { credentials: 'include' }).then(r => r.json());
        const alerts = data.alerts || [];
        if (!alerts.length) {
            listEl.innerHTML = '<p style="color:var(--text-muted);font-size:0.88rem">No alerts set. Add one above.</p>';
            return;
        }
        const isAr = document.documentElement.lang === 'ar' || localStorage.getItem('lang') === 'ar';
        listEl.innerHTML = alerts.map(a => {
            const triggered = !a.active;
            const condLabel = a.condition === 'above' ? (isAr ? 'أعلى من' : 'Above') : (isAr ? 'أقل من' : 'Below');
            const cur = parseFloat(a.current_price);
            const diff = cur && a.target_price ? ((cur - a.target_price) / a.target_price * 100).toFixed(1) : null;
            return `<div class="alert-row ${triggered ? 'alert-triggered' : ''}">
                <span class="alert-sym">${a.symbol}</span>
                <span class="alert-cond">${condLabel}</span>
                <span class="alert-price">${parseFloat(a.target_price).toFixed(2)}</span>
                ${cur ? `<span class="alert-cur" style="color:var(--text-muted)">Now: ${cur.toFixed(2)}${diff ? ` (${diff > 0 ? '+' : ''}${diff}%)` : ''}</span>` : ''}
                ${triggered ? `<span class="alert-tag-triggered">${isAr ? 'نُشِّط' : 'Triggered'}</span>` : ''}
                <button class="alert-del-btn" onclick="deleteAlert(${a.id})">✕</button>
            </div>`;
        }).join('');
    } catch {
        const listEl2 = document.getElementById('alertsList');
        if (listEl2) listEl2.innerHTML = '<p style="color:var(--text-muted)">Sign in to use price alerts.</p>';
    }
}

async function addPriceAlert() {
    const sym = (document.getElementById('alertSymbol')?.value || '').trim().toUpperCase();
    const cond = document.getElementById('alertCondition')?.value || 'above';
    const price = parseFloat(document.getElementById('alertPrice')?.value);
    if (!sym || isNaN(price) || price <= 0) return;
    try {
        const r = await fetch('/api/trades/alerts', {
            method: 'POST', credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ symbol: sym, condition: cond, target_price: price })
        });
        if (!r.ok) { const e = await r.json(); alert(e.error || 'Error'); return; }
        document.getElementById('alertSymbol').value = '';
        document.getElementById('alertPrice').value = '';
        loadAlerts();
    } catch (e) { alert(e.message); }
}

async function deleteAlert(id) {
    try {
        await fetch(`/api/trades/alerts/${id}`, { method: 'DELETE', credentials: 'include' });
        loadAlerts();
    } catch {}
}

// ============================================================
// STOCK COMPARISON TOOL
// ============================================================

function openComparisonModal() {
    const m = document.getElementById('comparisonModal');
    if (m) m.style.display = 'flex';
}
function closeComparisonModal() {
    const m = document.getElementById('comparisonModal');
    if (m) m.style.display = 'none';
}

async function runComparison() {
    const syms = ['compSym1','compSym2','compSym3','compSym4']
        .map(id => (document.getElementById(id)?.value || '').trim().toUpperCase())
        .filter(Boolean);
    if (syms.length < 2) { alert('Enter at least 2 symbols to compare.'); return; }

    const resultsEl = document.getElementById('compResults');
    resultsEl.innerHTML = '<p class="loading">Loading...</p>';

    try {
        const [consensus, prices] = await Promise.all([
            fetch('/api/consensus', { credentials: 'include' }).then(r => r.json()),
            fetch('/api/prices', { credentials: 'include' }).then(r => r.json()),
        ]);
        const cMap = {};
        (Array.isArray(consensus) ? consensus : []).forEach(c => { cMap[c.symbol] = c; });
        const pMap = {};
        (Array.isArray(prices) ? prices : (prices.prices || [])).forEach(p => { pMap[p.symbol] = p; });

        const rows = syms.map(sym => {
            const c = cMap[sym] || {};
            const p = pMap[sym] || {};
            const chg = p.close && p.open ? ((p.close - p.open) / p.open * 100).toFixed(2) : null;
            return { sym, c, p, chg };
        });

        const signalBadge = (sig) => {
            if (!sig) return '<span style="color:var(--text-muted)">—</span>';
            const cls = sig === 'UP' ? 'bullish' : sig === 'DOWN' ? 'bearish' : 'neutral';
            return `<span class="signal-badge ${cls}">${sig}</span>`;
        };

        const metricLabel = t('compMetric');
        const rowCell = (label, values) =>
            `<tr><td data-label="${metricLabel}">${label}</td>` +
            values.map((v, i) => `<td data-label="${rows[i].sym}">${v}</td>`).join('') +
            `</tr>`;

        resultsEl.innerHTML = `
        <div class="table-responsive">
        <table class="data-table comp-table table-cards">
            <thead><tr>
                <th>${metricLabel}</th>
                ${rows.map(r => `<th>${r.sym}</th>`).join('')}
            </tr></thead>
            <tbody>
            ${rowCell(t('compSignal'), rows.map(r => signalBadge(r.c.final_signal)))}
            ${rowCell(t('compScore'), rows.map(r => r.c.xmore_score != null ? Math.round(r.c.xmore_score) : '—'))}
            ${rowCell(t('compConviction'), rows.map(r => r.c.conviction || '—'))}
            ${rowCell(t('compConfidence'), rows.map(r => r.c.confidence != null ? r.c.confidence + '%' : '—'))}
            ${rowCell(t('compAgentsAgree'), rows.map(r => r.c.agents_agreeing != null ? r.c.agents_agreeing + '/' + r.c.agents_total : '—'))}
            ${rowCell(t('compBullScore'), rows.map(r => `<span style="color:var(--bullish)">${r.c.bull_score != null ? r.c.bull_score : '—'}</span>`))}
            ${rowCell(t('compBearScore'), rows.map(r => `<span style="color:var(--bearish)">${r.c.bear_score != null ? r.c.bear_score : '—'}</span>`))}
            ${rowCell(t('compPrice'), rows.map(r => r.p.close != null ? parseFloat(r.p.close).toFixed(2) : '—'))}
            ${rowCell(t('compDayChange'), rows.map(r => `<span style="color:${r.chg > 0 ? 'var(--bullish)' : r.chg < 0 ? 'var(--bearish)' : 'inherit'}">${r.chg != null ? (r.chg > 0 ? '+' : '') + r.chg + '%' : '—'}</span>`))}
            ${rowCell(t('compVolume'), rows.map(r => r.p.volume != null ? Number(r.p.volume).toLocaleString() : '—'))}
            ${rowCell(t('compBrief'), rows.map(r => `<button class="pf-btn-view" onclick="loadStockBrief('${r.sym}')">${t('compBrief')} →</button>`))}
            </tbody>
        </table>
        </div>
        `;
    } catch (err) {
        resultsEl.innerHTML = `<p style="color:var(--bearish)">${err.message}</p>`;
    }
}

// ============================================================
// PER-STOCK AI BRIEF
// ============================================================

async function loadStockBrief(symbol) {
    const modal = document.getElementById('briefModal');
    const bodyEl = document.getElementById('briefModalBody');
    const titleEl = document.getElementById('briefModalSymbol');
    if (!modal) return;
    titleEl.textContent = symbol + ' — AI Brief';
    bodyEl.innerHTML = '<p class="loading">Generating brief...</p>';
    modal.style.display = 'flex';
    try {
        const r = await fetch(`/api/stocks/${encodeURIComponent(symbol)}/brief`, { credentials: 'include' });
        const data = await r.json();
        if (!r.ok) throw new Error(data.error || 'Error');
        bodyEl.textContent = data.brief;
    } catch (err) {
        bodyEl.textContent = 'Could not generate brief: ' + err.message;
    }
}

function closeBriefModal() {
    const m = document.getElementById('briefModal');
    if (m) m.style.display = 'none';
}

// ============================================================
// RATES TAB — FX & Gold with history charts
// ============================================================

async function loadRatesTab() {
    const cardsEl = document.getElementById('ratesCards');
    const chartsEl = document.getElementById('ratesHistoryCharts');
    if (!cardsEl) return;

    try {
        const [live, history] = await Promise.all([
            fetch('/api/fx-rates').then(r => r.json()),
            fetch('/api/fx-rates/history?days=30').then(r => r.json()),
        ]);

        // Live cards
        const rateItems = [
            { label: 'USD / EGP', value: live.USD_EGP, key: 'usd_egp', icon: '💵' },
            { label: 'Gold 24K / gram', value: live.GOLD_24K_EGP_G, key: 'gold_24k_egp_g', icon: '🥇', suffix: 'EGP' },
            { label: 'Gold 21K / gram', value: live.GOLD_21K_EGP_G, key: 'gold_21k_egp_g', icon: '🏅', suffix: 'EGP' },
            { label: 'Gold Pound', value: live.GOLD_POUND_EGP, key: 'gold_pound_egp', icon: '💰', suffix: 'EGP' },
            { label: 'Gold 18K / gram', value: live.GOLD_18K_EGP_G, key: null, icon: '🔶', suffix: 'EGP' },
            { label: 'USD / SAR', value: live.USD_SAR, key: null, icon: '🇸🇦' },
            { label: 'SAR / EGP', value: live.SAR_EGP, key: null, icon: '↔️' },
        ];
        cardsEl.innerHTML = rateItems.filter(r => r.value != null).map(r => `
            <div class="rate-card">
                <span class="rate-icon">${r.icon}</span>
                <span class="rate-label">${r.label}</span>
                <span class="rate-value">${parseFloat(r.value).toLocaleString('en-EG', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}${r.suffix ? ' ' + r.suffix : ''}</span>
            </div>`).join('');

        // History sparkline charts
        if (!chartsEl || !history.length) return;
        const sparkDefs = [
            { label: 'USD/EGP Rate', key: 'usd_egp', color: '#3b82f6' },
            { label: 'Gold 24K (EGP/g)', key: 'gold_24k_egp_g', color: '#f59e0b' },
            { label: 'Gold 21K (EGP/g)', key: 'gold_21k_egp_g', color: '#d97706' },
            { label: 'Gold Pound (EGP)', key: 'gold_pound_egp', color: '#b45309' },
        ];
        chartsEl.innerHTML = sparkDefs.map(d => `
            <div class="rate-chart-card">
                <div class="rate-chart-label">${d.label}</div>
                <canvas id="chart_${d.key}" height="80"></canvas>
            </div>`).join('');

        // Draw sparklines using simple canvas
        sparkDefs.forEach(def => {
            const canvas = document.getElementById('chart_' + def.key);
            if (!canvas) return;
            const vals = history.map(h => parseFloat(h[def.key])).filter(v => !isNaN(v));
            if (vals.length < 2) return;
            drawSparkline(canvas, vals, def.color);
        });

    } catch (err) {
        if (cardsEl) cardsEl.innerHTML = `<p style="color:var(--bearish)">${err.message}</p>`;
    }
}

function drawSparkline(canvas, values, color) {
    const ctx = canvas.getContext('2d');
    const W = canvas.offsetWidth || 200;
    const H = canvas.height || 80;
    canvas.width = W;
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;
    const pad = 4;
    ctx.clearRect(0, 0, W, H);
    ctx.beginPath();
    values.forEach((v, i) => {
        const x = pad + (i / (values.length - 1)) * (W - 2 * pad);
        const y = H - pad - ((v - min) / range) * (H - 2 * pad);
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.stroke();
    // Fill under
    const lastX = pad + ((values.length - 1) / (values.length - 1)) * (W - 2 * pad);
    ctx.lineTo(lastX, H);
    ctx.lineTo(pad, H);
    ctx.closePath();
    ctx.fillStyle = color + '22';
    ctx.fill();
    // Current value label
    const last = values[values.length - 1];
    ctx.fillStyle = color;
    ctx.font = '11px sans-serif';
    ctx.fillText(last.toLocaleString('en-EG', { minimumFractionDigits: 2, maximumFractionDigits: 2 }), pad, H - pad - 2);
}

// ============================================================
// MULTI-HORIZON SIGNAL ACCURACY
// ============================================================

async function loadSignalAccuracy(horizon) {
    horizon = horizon || 5;
    // Update active button
    document.querySelectorAll('.horizon-btn').forEach(b => {
        b.classList.toggle('active', parseInt(b.dataset.horizon) === horizon);
    });
    const el = document.getElementById('signalAccuracyTable');
    if (!el) return;
    el.innerHTML = '<p class="loading">Loading...</p>';
    try {
        const data = await fetch(`/api/signal-accuracy?horizon=${horizon}`).then(r => r.json());
        if (!Array.isArray(data) || !data.length) {
            el.innerHTML = `<p style="color:var(--text-muted)">No D+${horizon} data yet — runs after 10+ trading days of consensus signals.</p>`;
            return;
        }
        const labels = {
            symbol: t('mhSymbol'),
            horizon: t('mhHorizon'),
            preds: t('mhPreds'),
            correct: t('mhCorrect'),
            accuracy: t('mhAccuracy'),
            avgChange: t('mhAvgChange')
        };
        el.innerHTML = `
        <div class="table-responsive">
        <table class="data-table table-cards">
            <thead><tr><th>${labels.symbol}</th><th>${labels.horizon}</th><th>${labels.preds}</th><th>${labels.correct}</th><th>${labels.accuracy}</th><th>${labels.avgChange}</th></tr></thead>
            <tbody>${data.map(r => `
            <tr>
                <td data-label="${labels.symbol}"><strong>${r.symbol}</strong></td>
                <td data-label="${labels.horizon}">D+${r.horizon_days}</td>
                <td data-label="${labels.preds}">${r.total}</td>
                <td data-label="${labels.correct}">${r.correct}</td>
                <td data-label="${labels.accuracy}" style="color:${parseFloat(r.accuracy_pct) >= 60 ? 'var(--bullish)' : 'var(--bearish)'};font-weight:700">${parseFloat(r.accuracy_pct).toFixed(1)}%</td>
                <td data-label="${labels.avgChange}" style="color:${parseFloat(r.avg_change_pct) >= 0 ? 'var(--bullish)' : 'var(--bearish)'}">${parseFloat(r.avg_change_pct) >= 0 ? '+' : ''}${parseFloat(r.avg_change_pct).toFixed(2)}%</td>
            </tr>`).join('')}
            </tbody>
        </table>
        </div>`;
    } catch (err) {
        el.innerHTML = `<p style="color:var(--bearish)">${err.message}</p>`;
    }
}

