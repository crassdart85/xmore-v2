// ============================================
// Xmore â€” Market Intelligence Dashboard
// Phase 1 Upgrade: Performance Dashboard, TradingView, Consensus, Compliance
// ============================================

// Global error handler â€” surface JS errors visibly for debugging
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
    if (!menuBtn || !menuDropdown) return;

    const menuItems = document.querySelectorAll('.mobile-menu-item');

    // Toggle menu on button click
    menuBtn.addEventListener('click', function(e) {
        e.stopPropagation();
        menuDropdown.classList.toggle('active');
        menuBtn.classList.toggle('active');
        menuBtn.setAttribute('aria-expanded', menuDropdown.classList.contains('active') ? 'true' : 'false');
        menuDropdown.setAttribute('aria-hidden', menuDropdown.classList.contains('active') ? 'false' : 'true');
    });

    // Close menu when a link is clicked
    menuItems.forEach(function(item) {
        item.addEventListener('click', function() {
            menuDropdown.classList.remove('active');
            menuBtn.classList.remove('active');
            menuBtn.setAttribute('aria-expanded', 'false');
            menuDropdown.setAttribute('aria-hidden', 'true');
        });
    });

    // Close menu when clicking outside
    document.addEventListener('click', function(e) {
        if (menuDropdown.classList.contains('active') && !menuBtn.contains(e.target) && !menuDropdown.contains(e.target)) {
            menuDropdown.classList.remove('active');
            menuBtn.classList.remove('active');
            menuBtn.setAttribute('aria-expanded', 'false');
            menuDropdown.setAttribute('aria-hidden', 'true');
        }
    });

    // Close menu on Escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && menuDropdown.classList.contains('active')) {
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
        subtitle: 'Market Intelligence Dashboard',

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
        predictionsBrief: "Start here: see today's signals by stock and scan for bullish, bearish, or neutral direction.",
        watchlistBrief: 'Track the stocks you care about so the app can personalize signals, briefing, and performance for you.',
        performanceBrief: 'Review strategy quality over time, including win rate, drawdown, and benchmark-relative performance.',
        consensusBrief: 'See where multiple agents agree, plus risk filters, to spot the strongest shared setup.',
        consensusDcfNote: 'DCF valuation is included as a supplementary weekly signal in the consensus layer.',
        globalSearchPlaceholder: 'Search stocks, tabs, or pages...',
        globalSearchNoResults: 'No matching results.',
        globalSearchStocksLabel: 'Stock',
        globalSearchTabLabel: 'Tab',
        globalSearchPageLabel: 'Page',
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
        accuracyDefinition: 'Directional Accuracy: Percentage of predictions where the predicted direction (UP/DOWN) matched the actual 5-day price movement exceeding Â±0.5% threshold.',
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
        viewFullAnalysis: 'Full Analysis â†’',
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
        changesTodayTitle: 'What Changed Today',
        changesTodayLive: 'Live',
        qualityMonitorTitle: 'Freshness & Drift',
        qualityMonitorMonitoring: 'Monitoring',
        noChangesToday: 'No material changes detected yet.',
        noQualityData: 'Monitoring data is not available yet.',
        expectedEdgeLabel: 'Expected edge',
        calibrationLabel: 'Calibrated',
        signalsLabel: 'Signals',
        forecastsLabel: 'Forecasts',
        macroLabel: 'Macro',
        fromLabel: 'from',
        driftLabel: 'Drift',
        freshnessLabel: 'Freshness',
        qualityhealthy: 'Healthy',
        qualitywatch: 'Watch',
        qualityattention: 'Attention',
        qualityfresh: 'Fresh',
        qualitywarning: 'Warning',
        qualitystale: 'Stale',
        qualitystable: 'Stable',
        qualitydegrading: 'Degrading',
        qualityimproving: 'Improving',
        qualityunknown: 'Unknown',
        qualitymissing: 'Missing',

        // Language
        switchLang: 'Ø¹Ø±Ø¨ÙŠ',

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
        scoringModeXmoreNative: 'Xmore (0â€“1)',
        scoringModeStandard100: 'Score (0â€“100)',
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
        alertAbove: 'Above â†‘',
        alertBelow: 'Below â†“',

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
        compBrief: 'Market Brief',

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
        tmLoadingWarning: 'This may take 30â€“60 seconds.',
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
        tmSubPastLabel: 'â® Past',
        tmSubFutureLabel: 'â­ Future',
        fcTitle: 'Future Forecast',
        fcSubtitle: 'System picks the best EGX30 stock for your horizon. 5,000 Monte Carlo paths.',
        fcModeAuto: 'ðŸ¤– Automatic picks',
        fcModeManual: 'ðŸ” I pick manually',
        fcModePortfolio: 'ðŸ“ My Portfolios',
        pf_title: 'My Forecast Portfolios',
        pf_create: '+ New Portfolio',
        fcEndDateLabel: 'Target Date',
        fcEndDateHint: 'Up to 30 days from today â€” System picks the best EGX30 stock for you',
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
        fcBearHint: 'âˆ’2% drift drag',
        fcRunBtn: 'Find Best Stock & Forecast',
        fcSelectDate: 'Please pick a target date.',
        fcChosenBy: 'Top Pick',
        fcSeeRanking: 'See ranking â–¼',
        fcHideRanking: 'Hide â–²',
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
        fcCalculating: 'Scanning EGX30 stocks & running 5,000 Monte Carlo pathsâ€¦',
        fcAnalyzing: 'Computing GBM parameters â€” this takes ~30s',
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
        title: 'Ø¥ÙƒØ³Ù…ÙˆØ±',
        subtitle: 'Ù„ÙˆØ­Ø© Ø§Ù„ØªÙ†Ø¨Ø¤Ø§Øª Ø§Ù„Ø°ÙƒÙŠØ© Ù„Ù„Ø£Ø³Ù‡Ù…',

        stocksTracked: 'Ø§Ù„Ø£Ø³Ù‡Ù… Ø§Ù„Ù…ØªØ§Ø¨Ø¹Ø©',
        totalPredictions: 'Ø¥Ø¬Ù…Ø§Ù„ÙŠ Ø§Ù„ØªÙ†Ø¨Ø¤Ø§Øª',
        overallAccuracy: 'Ø§Ù„Ø¯Ù‚Ø©',
        latestData: 'Ø¢Ø®Ø± ØªØ­Ø¯ÙŠØ«',

        tabPredictions: 'Ø§Ù„ØªÙ†Ø¨Ø¤Ø§Øª',
        tabBriefing: 'Ø§Ù„Ù†Ø´Ø±Ø©',
        tabTrades: 'Ø§Ù„ØªØ¯Ø§ÙˆÙ„',
        tabPortfolio: 'Ø§Ù„Ù…Ø­ÙØ¸Ø©',
        tabWatchlist: 'Ø§Ù„Ù…ØªØ§Ø¨Ø¹Ø©',
        tabPerformance: 'Ø§Ù„Ø£Ø¯Ø§Ø¡',
        tabResults: 'Ø§Ù„Ù†ØªØ§Ø¦Ø¬',
        tabPrices: 'Ø§Ù„Ø£Ø³Ø¹Ø§Ø±',
        predictionsBrief: 'Ø§Ø¨Ø¯Ø£ Ù…Ù† Ù‡Ù†Ø§: Ø±Ø§Ø¬Ø¹ Ø¥Ø´Ø§Ø±Ø§Øª Ø§Ù„Ø°ÙƒØ§Ø¡ Ø§Ù„Ø§ØµØ·Ù†Ø§Ø¹ÙŠ Ø§Ù„ÙŠÙˆÙ…ÙŠØ© Ù„ÙƒÙ„ Ø³Ù‡Ù… (ØµØ§Ø¹Ø¯/Ù‡Ø§Ø¨Ø·/Ù…Ø­Ø§ÙŠØ¯).',
        watchlistBrief: 'ØªØ§Ø¨Ø¹ Ø§Ù„Ø£Ø³Ù‡Ù… Ø§Ù„ØªÙŠ ØªÙ‡Ù…Ùƒ Ù„ÙŠØ®ØµØµ Ø§Ù„Ù†Ø¸Ø§Ù… Ø§Ù„Ø¥Ø´Ø§Ø±Ø§Øª ÙˆØ§Ù„Ù†Ø´Ø±Ø© ÙˆØ§Ù„Ø£Ø¯Ø§Ø¡ Ù„Ùƒ.',
        performanceBrief: 'ØªØ§Ø¨Ø¹ Ø¬ÙˆØ¯Ø© Ø§Ù„Ø§Ø³ØªØ±Ø§ØªÙŠØ¬ÙŠØ© Ø¹Ø¨Ø± Ø§Ù„ÙˆÙ‚ØªØŒ Ø¨Ù…Ø§ ÙÙŠ Ø°Ù„Ùƒ Ù†Ø³Ø¨Ø© Ø§Ù„ÙÙˆØ² ÙˆØ§Ù„Ø³Ø­Ø¨ Ø§Ù„Ø£Ù‚ØµÙ‰ ÙˆØ§Ù„Ø£Ø¯Ø§Ø¡ Ù…Ù‚Ø§Ø¨Ù„ Ø§Ù„Ù…Ø¤Ø´Ø±.',
        consensusBrief: 'Ø§Ø·Ù„Ø¹ Ø¹Ù„Ù‰ Ø§Ù„Ø£Ø³Ù‡Ù… Ø§Ù„ØªÙŠ ÙŠØªÙÙ‚ Ø¹Ù„ÙŠÙ‡Ø§ Ø¹Ø¯Ø© ÙˆÙƒÙ„Ø§Ø¡ Ù…Ø¹ ÙÙ„Ø§ØªØ± Ø§Ù„Ù…Ø®Ø§Ø·Ø± Ù„ØªØ­Ø¯ÙŠØ¯ Ø£Ù‚ÙˆÙ‰ Ø§Ù„ÙØ±Øµ.',
        consensusDcfNote: 'ØªÙ‚ÙŠÙŠÙ… DCF Ù…Ø¶Ù…Ù‘Ù† ÙƒØ¥Ø´Ø§Ø±Ø© Ø£Ø³Ø¨ÙˆØ¹ÙŠØ© Ø¯Ø§Ø¹Ù…Ø© Ø¶Ù…Ù† Ø·Ø¨Ù‚Ø© Ø§Ù„Ø¥Ø¬Ù…Ø§Ø¹.',
        globalSearchPlaceholder: 'Ø§Ø¨Ø­Ø« Ø¹Ù† Ø³Ù‡Ù… Ø£Ùˆ ØªØ¨ÙˆÙŠØ¨ Ø£Ùˆ ØµÙØ­Ø©...',
        globalSearchNoResults: 'Ù„Ø§ ØªÙˆØ¬Ø¯ Ù†ØªØ§Ø¦Ø¬ Ù…Ø·Ø§Ø¨Ù‚Ø©.',
        globalSearchStocksLabel: 'Ø³Ù‡Ù…',
        globalSearchTabLabel: 'ØªØ¨ÙˆÙŠØ¨',
        globalSearchPageLabel: 'ØµÙØ­Ø©',
        resultsBrief: 'Ù‚Ø§Ø±Ù† Ø§Ù„ØªÙˆÙ‚Ø¹Ø§Øª Ø§Ù„Ø³Ø§Ø¨Ù‚Ø© Ø¨Ø§Ù„Ù†ØªØ§Ø¦Ø¬ Ø§Ù„ÙØ¹Ù„ÙŠØ© Ù„ÙÙ‡Ù… Ù…Ø§ Ø£ØµØ§Ø¨Ù‡ Ø§Ù„Ù†Ø¸Ø§Ù… ÙˆÙ…Ø§ Ø£Ø®Ø·Ø£ ÙÙŠÙ‡.',
        pricesBrief: 'Ø±Ø§Ø¬Ø¹ Ø£Ø­Ø¯Ø« Ø§Ù„Ø£Ø³Ø¹Ø§Ø± ÙˆØ£Ø­Ø¬Ø§Ù… Ø§Ù„ØªØ¯Ø§ÙˆÙ„ Ù„Ù„Ø£Ø³Ù‡Ù… Ø§Ù„Ù…ØªØ§Ø¨Ø¹Ø© ÙÙŠ Ø¬Ø¯ÙˆÙ„ ÙˆØ§Ø­Ø¯.',
        briefingBrief: 'Ø§Ø³ØªØ®Ø¯Ù…Ù‡Ø§ ÙƒÙ…Ù„Ø®Øµ ÙŠÙˆÙ…ÙŠ: Ø³ÙŠØ§Ù‚ Ø§Ù„Ø³ÙˆÙ‚ØŒ Ø£ÙˆÙ„ÙˆÙŠØ§Øª Ø§Ù„Ø¥Ø´Ø§Ø±Ø§ØªØŒ ÙˆØ§Ù„Ø®Ø·ÙˆØ§Øª Ø§Ù„Ù…Ù‚ØªØ±Ø­Ø©.',
        tradesBrief: 'Ø§Ø·Ù„Ø¹ Ø¹Ù„Ù‰ Ø£ÙÙƒØ§Ø± ØªØ¯Ø§ÙˆÙ„ Ù‚Ø§Ø¨Ù„Ø© Ù„Ù„ØªÙ†ÙÙŠØ° Ù…Ø¹ Ø§Ù„Ø§ØªØ¬Ø§Ù‡ ÙˆØ§Ù„Ù…Ø¨Ø±Ø± Ø®Ù„Ø§Ù„ Ø¬Ù„Ø³Ø© Ø§Ù„ÙŠÙˆÙ….',
        portfolioBrief: 'Ø±Ø§Ù‚Ø¨ Ø§Ù„Ù…Ø±Ø§ÙƒØ² Ø§Ù„Ù…ÙØªÙˆØ­Ø© ÙˆØªØ§Ø±ÙŠØ® Ø§Ù„ØµÙÙ‚Ø§Øª ÙˆÙ…Ø¤Ø´Ø±Ø§Øª ØµØ­Ø© Ø§Ù„Ù…Ø­ÙØ¸Ø© ÙÙŠ Ù…ÙƒØ§Ù† ÙˆØ§Ø­Ø¯.',

        latestPredictions: 'Ø£Ø­Ø¯Ø« Ø§Ù„ØªÙ†Ø¨Ø¤Ø§Øª',
        agentPerformance: 'Ø£Ø¯Ø§Ø¡ Ø§Ù„ÙˆÙƒÙ„Ø§Ø¡',
        predictionResults: 'Ù†ØªØ§Ø¦Ø¬ Ø§Ù„ØªÙ†Ø¨Ø¤Ø§Øª',
        latestPrices: 'Ø£Ø­Ø¯Ø« Ø£Ø³Ø¹Ø§Ø± Ø§Ù„Ø£Ø³Ù‡Ù…',
        performanceOverview: 'Ù†Ø¸Ø±Ø© Ø¹Ø§Ù…Ø© Ø¹Ù„Ù‰ Ø§Ù„Ø£Ø¯Ø§Ø¡',
        agentAccuracy: 'Ø¯Ù‚Ø© Ø§Ù„ÙˆÙƒÙ„Ø§Ø¡',
        stockPerformance: 'Ø£Ø¯Ø§Ø¡ Ø§Ù„Ø£Ø³Ù‡Ù…',
        monthlyTrend: 'Ø§ØªØ¬Ø§Ù‡ Ø§Ù„Ø¯Ù‚Ø© Ø§Ù„Ø´Ù‡Ø±ÙŠ',

        stock: 'Ø§Ù„Ø³Ù‡Ù…',
        agent: 'Ø§Ù„ÙˆÙƒÙŠÙ„',
        signal: 'Ø§Ù„Ø¥Ø´Ø§Ø±Ø©',
        prediction: 'Ø§Ù„Ø¥Ø´Ø§Ø±Ø©',
        date: 'Ø§Ù„ØªØ§Ø±ÙŠØ®',
        totalPreds: 'Ø¥Ø¬Ù…Ø§Ù„ÙŠ Ø§Ù„ØªÙ†Ø¨Ø¤Ø§Øª',
        correct: 'Ø§Ù„ØµØ­ÙŠØ­Ø©',
        accuracy: 'Ø§Ù„Ø¯Ù‚Ø©',
        closePrice: 'Ø³Ø¹Ø± Ø§Ù„Ø¥ØºÙ„Ø§Ù‚',
        volume: 'Ø§Ù„Ø­Ø¬Ù…',
        actualOutcome: 'Ø§Ù„ÙØ¹Ù„ÙŠ',
        priceChange: 'Ø§Ù„ØªØºÙŠØ± %',
        result: 'Ø§Ù„Ù†ØªÙŠØ¬Ø©',
        targetDate: 'ØªØ§Ø±ÙŠØ® Ø§Ù„Ù‡Ø¯Ù',
        avgReturn: 'Ù…ØªÙˆØ³Ø· Ø§Ù„Ø¹Ø§Ø¦Ø¯',

        up: 'ØµØ§Ø¹Ø¯',
        down: 'Ù‡Ø§Ø¨Ø·',
        hold: 'Ù…Ø­Ø§ÙŠØ¯',
        flat: 'Ù…Ø­Ø§ÙŠØ¯',

        sentiment: 'Ø§Ù„Ù…Ø´Ø§Ø¹Ø±',
        bullish: 'Ø¥ÙŠØ¬Ø§Ø¨ÙŠ',
        neutral: 'Ù…Ø­Ø§ÙŠØ¯',
        bearish: 'Ø³Ù„Ø¨ÙŠ',
        noSentiment: 'Øº/Ù…',

        consensus: 'Ø§Ù„Ø¥Ø¬Ù…Ø§Ø¹',
        agentsAgree: 'ÙˆÙƒÙ„Ø§Ø¡ ÙŠØªÙÙ‚ÙˆÙ†',
        unanimous: 'Ø¥Ø¬Ù…Ø§Ø¹ ØªØ§Ù…',

        directionalAccuracy: 'Ø§Ù„Ø¯Ù‚Ø© Ø§Ù„Ø§ØªØ¬Ø§Ù‡ÙŠØ©',
        totalSignals: 'Ø¥Ø¬Ù…Ø§Ù„ÙŠ Ø§Ù„Ø¥Ø´Ø§Ø±Ø§Øª',
        winRateBuy: 'Ù†Ø³Ø¨Ø© Ø§Ù„Ù†Ø¬Ø§Ø­ (Ø´Ø±Ø§Ø¡)',
        winRateSell: 'Ù†Ø³Ø¨Ø© Ø§Ù„Ù†Ø¬Ø§Ø­ (Ø¨ÙŠØ¹)',
        avgReturnPerSignal: 'Ù…ØªÙˆØ³Ø· Ø§Ù„Ø¹Ø§Ø¦Ø¯/Ø¥Ø´Ø§Ø±Ø©',
        maxDrawdown: 'Ø£Ù‚ØµÙ‰ ØªØ±Ø§Ø¬Ø¹',
        accuracyDefinition: 'Ø§Ù„Ø¯Ù‚Ø© Ø§Ù„Ø§ØªØ¬Ø§Ù‡ÙŠØ©: Ù†Ø³Ø¨Ø© Ø§Ù„ØªÙ†Ø¨Ø¤Ø§Øª Ø§Ù„ØªÙŠ ØªØ·Ø§Ø¨Ù‚ ÙÙŠÙ‡Ø§ Ø§Ù„Ø§ØªØ¬Ø§Ù‡ Ø§Ù„Ù…ØªÙˆÙ‚Ø¹ (ØµØ¹ÙˆØ¯/Ù‡Ø¨ÙˆØ·) Ù…Ø¹ Ø­Ø±ÙƒØ© Ø§Ù„Ø³Ø¹Ø± Ø§Ù„ÙØ¹Ù„ÙŠØ© Ø®Ù„Ø§Ù„ 5 Ø£ÙŠØ§Ù… Ø¨ØªØ¬Ø§ÙˆØ² Ø¹ØªØ¨Ø© Â±0.5%.',
        agentHistoryBadge: 'ØµØ­ÙŠØ­ ØªØ§Ø±ÙŠØ®ÙŠØ§Ù‹',

        noPredictions: 'Ù„Ø§ ØªÙˆØ¬Ø¯ ØªÙ†Ø¨Ø¤Ø§Øª Ù…ØªØ§Ø­Ø©. ÙŠØªÙ… Ø¥Ù†Ø´Ø§Ø¡ Ø§Ù„Ø¥Ø´Ø§Ø±Ø§Øª ÙŠÙˆÙ…ÙŠØ§Ù‹ Ø¨Ø¹Ø¯ Ø¥ØºÙ„Ø§Ù‚ Ø§Ù„Ø³ÙˆÙ‚.',
        noPerformance: 'Ø³ÙŠØ¨Ø¯Ø£ ØªØªØ¨Ø¹ Ø§Ù„Ø£Ø¯Ø§Ø¡ Ø¨Ù…Ø¬Ø±Ø¯ ØªÙ‚ÙŠÙŠÙ… Ø§Ù„ØªÙ†Ø¨Ø¤Ø§Øª.',
        noEvaluations: 'Ù„Ø§ ØªÙˆØ¬Ø¯ Ù†ØªØ§Ø¦Ø¬ ØªÙ†Ø¨Ø¤Ø§Øª Ø¨Ø¹Ø¯.',
        noPrices: 'Ø¬Ø§Ø±ÙŠ Ø¬Ù…Ø¹ Ø¨ÙŠØ§Ù†Ø§Øª Ø§Ù„Ø£Ø³Ø¹Ø§Ø±.',
        errorPredictions: 'ØªØ¹Ø°Ø± ØªØ­Ù…ÙŠÙ„ Ø§Ù„ØªÙ†Ø¨Ø¤Ø§Øª.',
        errorPerformance: 'ØªØ¹Ø°Ø± ØªØ­Ù…ÙŠÙ„ Ø¨ÙŠØ§Ù†Ø§Øª Ø§Ù„Ø£Ø¯Ø§Ø¡.',
        errorEvaluations: 'ØªØ¹Ø°Ø± ØªØ­Ù…ÙŠÙ„ Ø§Ù„Ù†ØªØ§Ø¦Ø¬.',
        errorPrices: 'ØªØ¹Ø°Ø± ØªØ­Ù…ÙŠÙ„ Ø§Ù„Ø£Ø³Ø¹Ø§Ø±.',
        noDetailedPerformance: 'Ø³ØªØªÙˆÙØ± Ø¨ÙŠØ§Ù†Ø§Øª Ø§Ù„Ø£Ø¯Ø§Ø¡ Ø§Ù„ØªÙØµÙŠÙ„ÙŠØ© Ø¨Ø¹Ø¯ ØªÙ‚ÙŠÙŠÙ… Ø§Ù„ØªÙ†Ø¨Ø¤Ø§Øª.',

        refreshData: 'ØªØ­Ø¯ÙŠØ« Ø§Ù„Ø¨ÙŠØ§Ù†Ø§Øª',
        refreshing: 'Ø¬Ø§Ø±ÙŠ Ø§Ù„ØªØ­Ø¯ÙŠØ«...',

        searchPlaceholder: 'Ø§Ù„Ø¨Ø­Ø« Ø¨Ø±Ù…Ø² Ø§Ù„Ø³Ù‡Ù… Ø£Ùˆ Ø§Ø³Ù… Ø§Ù„Ø´Ø±ÙƒØ©...',
        snapshotAlpha30d: 'Ø£Ù„ÙØ§ 30 ÙŠÙˆÙ… Ù…Ù‚Ø§Ø¨Ù„ EGX30',
        snapshotSharpe30d: 'Ù†Ø³Ø¨Ø© Ø´Ø§Ø±Ø¨ (30 ÙŠÙˆÙ…)',
        snapshotMaxDd30d: 'Ø£Ù‚ØµÙ‰ ØªØ±Ø§Ø¬Ø¹ (30 ÙŠÙˆÙ…)',
        snapshotWinRate30d: 'Ù†Ø³Ø¨Ø© Ø§Ù„ÙÙˆØ² Ø§Ù„Ù…ØªØ­Ø±ÙƒØ© (30 ÙŠÙˆÙ…)',
        snapshotTrades: 'Ø¥Ø¬Ù…Ø§Ù„ÙŠ Ø§Ù„ØµÙÙ‚Ø§Øª Ø§Ù„Ø­ÙŠØ©',
        marketRegime: 'Ù†Ø¸Ø§Ù… Ø§Ù„Ø³ÙˆÙ‚',
        signalMix30d: 'Ø¥Ø´Ø§Ø±Ø§Øª 30 ÙŠÙˆÙ…',
        viewFullAnalysis: 'Ø§Ù„ØªØ­Ù„ÙŠÙ„ Ø§Ù„ÙƒØ§Ù…Ù„ â†’',
        consensusSignal: 'Ø¥Ø´Ø§Ø±Ø© Ø§Ù„Ø¥Ø¬Ù…Ø§Ø¹',
        agreement: 'Ù†Ø³Ø¨Ø© Ø§Ù„Ø§ØªÙØ§Ù‚',
        recentAccuracySymbol: 'Ø§Ù„Ø¯Ù‚Ø© Ø§Ù„Ø­Ø¯ÙŠØ«Ø©',
        whySignal: 'Ù„Ù…Ø§Ø°Ø§ Ù‡Ø°Ù‡ Ø§Ù„Ø¥Ø´Ø§Ø±Ø©ØŸ',
        expandDetails: 'Ø§Ù„ØªÙØ§ØµÙŠÙ„',
        conf: 'Ø§Ù„Ø«Ù‚Ø©',
        trend: 'Ø§Ù„Ø§ØªØ¬Ø§Ù‡',
        momentum: 'Ø§Ù„Ø²Ø®Ù…',
        volumeState: 'Ø§Ù„Ø­Ø¬Ù…',
        sentimentState: 'Ø§Ù„Ù…Ø´Ø§Ø¹Ø±',
        agentAgreement: 'Ø§ØªÙØ§Ù‚ Ø§Ù„ÙˆÙƒÙ„Ø§Ø¡',
        tooltipAlpha: 'Ù…ØªÙˆØ³Ø· Ø£Ù„ÙØ§ ÙŠÙˆÙ…ÙŠ Ø®Ù„Ø§Ù„ Ø¢Ø®Ø± 30 ÙŠÙˆÙ…Ø§ Ø­ÙŠØ§ Ù…Ù‚Ø§Ø¨Ù„ EGX30.',
        tooltipSharpe: 'Ø¬ÙˆØ¯Ø© Ø§Ù„Ø¹Ø§Ø¦Ø¯ Ø§Ù„Ù…Ø¹Ø¯Ù„ Ø¨Ø§Ù„Ù…Ø®Ø§Ø·Ø± Ø®Ù„Ø§Ù„ Ø¢Ø®Ø± 30 ÙŠÙˆÙ…Ø§ Ø­ÙŠØ§.',
        tooltipMaxDd: 'Ø£ÙƒØ¨Ø± Ù‡Ø¨ÙˆØ· Ù…Ù† Ù‚Ù…Ø© Ø¥Ù„Ù‰ Ù‚Ø§Ø¹ ÙÙŠ Ø§Ù„Ø¹Ø§Ø¦Ø¯ Ø§Ù„ØªØ±Ø§ÙƒÙ…ÙŠ Ø®Ù„Ø§Ù„ 30 ÙŠÙˆÙ…Ø§.',
        tooltipWinRate: 'Ù†Ø³Ø¨Ø© Ø§Ù„Ø¥Ø´Ø§Ø±Ø§Øª Ø§Ù„Ø­ÙŠØ© Ø§Ù„ØµØ­ÙŠØ­Ø© Ø®Ù„Ø§Ù„ Ø¢Ø®Ø± 30 ÙŠÙˆÙ…Ø§.',
        tooltipTrades: 'Ø§Ù„ØªÙ†Ø¨Ø¤Ø§Øª Ø§Ù„Ø­ÙŠØ© Ø§Ù„Ù…Ø­Ù„Ù„Ø© Ø¶Ù…Ù† Ø§Ù„Ø¥Ø­ØµØ§Ø¡Ø§Øª Ø§Ù„Ø¹Ø§Ù…Ø©. Ø§Ù„Ù‡Ø¯Ù: 100+.',

        changesTodayTitle: 'Ã™â€¦Ã˜Â§ Ã˜Â§Ã™â€žÃ˜Â°Ã™Å  Ã˜ÂªÃ˜ÂºÃ™Å Ã˜Â± Ã˜Â§Ã™â€žÃ™Å Ã™Ë†Ã™â€¦',
        changesTodayLive: 'Ã™â€¦Ã˜Â¨Ã˜Â§Ã˜Â´Ã˜Â±',
        qualityMonitorTitle: 'Ã˜Â§Ã™â€žÃ˜Â­Ã˜Â¯Ã˜Â§Ã˜Â«Ã˜Â© Ã™Ë†Ã˜Â§Ã™â€žÃ˜Â§Ã™â€ Ã˜Â­Ã˜Â±Ã˜Â§Ã™Â',
        qualityMonitorMonitoring: 'Ã™â€¦Ã˜Â±Ã˜Â§Ã™â€šÃ˜Â¨Ã˜Â©',
        noChangesToday: 'Ã™â€žÃ˜Â§ Ã˜ÂªÃ™Ë†Ã˜Â¬Ã˜Â¯ Ã˜ÂªÃ˜ÂºÃ™Å Ã˜Â±Ã˜Â§Ã˜Âª Ã˜Â¬Ã™Ë†Ã™â€¡Ã˜Â±Ã™Å Ã˜Â© Ã˜Â¨Ã˜Â¹Ã˜Â¯.',
        noQualityData: 'Ã˜Â¨Ã™Å Ã˜Â§Ã™â€ Ã˜Â§Ã˜Âª Ã˜Â§Ã™â€žÃ™â€¦Ã˜Â±Ã˜Â§Ã™â€šÃ˜Â¨Ã˜Â© Ã˜ÂºÃ™Å Ã˜Â± Ã™â€¦Ã˜ÂªÃ˜Â§Ã˜Â­Ã˜Â© Ã˜Â¨Ã˜Â¹Ã˜Â¯.',
        expectedEdgeLabel: 'Ã˜Â§Ã™â€žÃ˜Â¹Ã˜Â§Ã˜Â¦Ã˜Â¯ Ã˜Â§Ã™â€žÃ™â€¦Ã˜ÂªÃ™Ë†Ã™â€šÃ˜Â¹',
        calibrationLabel: 'Ã˜Â§Ã™â€žÃ™â€¦Ã˜Â¹Ã˜Â§Ã™Å Ã˜Â±Ã˜Â©',
        signalsLabel: 'Ã˜Â§Ã™â€žÃ˜Â¥Ã˜Â´Ã˜Â§Ã˜Â±Ã˜Â§Ã˜Âª',
        forecastsLabel: 'Ã˜Â§Ã™â€žÃ˜ÂªÃ™Ë†Ã™â€šÃ˜Â¹Ã˜Â§Ã˜Âª',
        macroLabel: 'Ã˜Â§Ã™â€žÃ™â€¦Ã˜Â§Ã™Æ’Ã˜Â±Ã™Ë†',
        fromLabel: 'Ã™â€¦Ã™â€ ',
        driftLabel: 'Ã˜Â§Ã™â€žÃ˜Â§Ã™â€ Ã˜Â­Ã˜Â±Ã˜Â§Ã™Â',
        freshnessLabel: 'Ã˜Â§Ã™â€žÃ˜Â­Ã˜Â¯Ã˜Â§Ã˜Â«Ã˜Â©',
        qualityhealthy: 'Ã˜Â³Ã™â€žÃ™Å Ã™â€¦',
        qualitywatch: 'Ã™â€¦Ã˜Â±Ã˜Â§Ã™â€šÃ˜Â¨Ã˜Â©',
        qualityattention: 'Ã™Å Ã˜Â­Ã˜ÂªÃ˜Â§Ã˜Â¬ Ã™â€¦Ã˜ÂªÃ˜Â§Ã˜Â¨Ã˜Â¹Ã˜Â©',
        qualityfresh: 'Ã˜Â­Ã˜Â¯Ã™Å Ã˜Â«',
        qualitywarning: 'Ã˜ÂªÃ˜Â­Ã˜Â°Ã™Å Ã˜Â±',
        qualitystale: 'Ã™â€¦Ã˜ÂªÃ˜Â£Ã˜Â®Ã˜Â±',
        qualitystable: 'Ã™â€¦Ã˜Â³Ã˜ÂªÃ™â€šÃ˜Â±',
        qualitydegrading: 'Ã™â€¦Ã˜ÂªÃ˜Â±Ã˜Â§Ã˜Â¬Ã˜Â¹',
        qualityimproving: 'Ã™Å Ã˜ÂªÃ˜Â­Ã˜Â³Ã™â€ ',
        qualityunknown: 'Ã˜ÂºÃ™Å Ã˜Â± Ã™â€¦Ã˜Â¹Ã˜Â±Ã™Ë†Ã™Â',
        qualitymissing: 'Ã™â€¦Ã™ÂÃ™â€šÃ™Ë†Ã˜Â¯',
        switchLang: 'English',

        lightMode: 'Ø§Ù„ØªØ¨Ø¯ÙŠÙ„ Ø¥Ù„Ù‰ Ø§Ù„ÙˆØ¶Ø¹ Ø§Ù„ÙØ§ØªØ­',
        darkMode: 'Ø§Ù„ØªØ¨Ø¯ÙŠÙ„ Ø¥Ù„Ù‰ Ø§Ù„ÙˆØ¶Ø¹ Ø§Ù„Ø¯Ø§ÙƒÙ†',

        termsOfService: 'Ø´Ø±ÙˆØ· Ø§Ù„Ø®Ø¯Ù…Ø©',

        // Consensus tab
        tabConsensus: 'Ø§Ù„Ø¥Ø¬Ù…Ø§Ø¹',
        consensusTitle: 'Ø¥Ø¬Ù…Ø§Ø¹ Ø§Ù„Ø¥Ø´Ø§Ø±Ø§Øª',
        bullCase: 'Ø­Ø§Ù„Ø© Ø§Ù„Ø«ÙˆØ±',
        bearCase: 'Ø­Ø§Ù„Ø© Ø§Ù„Ø¯Ø¨',
        riskAction: 'Ø§Ù„Ù…Ø®Ø§Ø·Ø±',
        conviction: 'Ø§Ù„Ù‚Ù†Ø§Ø¹Ø©',
        riskPassed: 'Ø£ÙØ¬ÙŠØ²',
        riskFlagged: 'Ù…ÙØ¹Ù„Ù‘Ù…',
        riskBlocked: 'Ù…Ø­Ø¸ÙˆØ±',
        riskDowngraded: 'Ù…ÙØ®ÙÙ‘Ø¶',
        totalStocks: 'Ø¥Ø¬Ù…Ø§Ù„ÙŠ Ø§Ù„Ø£Ø³Ù‡Ù…',
        avgRisk: 'Ù…ØªÙˆØ³Ø· Ø§Ù„Ù…Ø®Ø§Ø·Ø±',
        noConsensus: 'Ù„Ø§ ØªÙˆØ¬Ø¯ Ø¨ÙŠØ§Ù†Ø§Øª Ø¥Ø¬Ù…Ø§Ø¹ Ø¨Ø¹Ø¯. Ø´ØºÙ‘Ù„ Ø®Ø· Ø§Ù„ØªÙ†Ø¨Ø¤Ø§Øª Ø£ÙˆÙ„Ø§Ù‹.',
        errorConsensus: 'ØªØ¹Ø°Ø± ØªØ­Ù…ÙŠÙ„ Ø¨ÙŠØ§Ù†Ø§Øª Ø§Ù„Ø¥Ø¬Ù…Ø§Ø¹.',
        convictionVeryHigh: 'Ø¹Ø§Ù„ÙŠØ© Ø¬Ø¯Ø§Ù‹',
        convictionHigh: 'Ø¹Ø§Ù„ÙŠØ©',
        convictionModerate: 'Ù…ØªÙˆØ³Ø·Ø©',
        convictionLow: 'Ù…Ù†Ø®ÙØ¶Ø©',
        convictionBlocked: 'Ù…Ø­Ø¸ÙˆØ±',
        scoringModeLabel: 'ÙˆØ¶Ø¹ Ø§Ù„ØªÙ‚ÙŠÙŠÙ…',
        scoringModeXmoreNative: 'Xmore (0â€“1)',
        scoringModeStandard100: 'Ø¯Ø±Ø¬Ø© (0â€“100)',
        scoringModeLetterGrade: 'ØªÙ‚Ø¯ÙŠØ±',
        scoringModeStars: 'Ù†Ø¬ÙˆÙ…',
        scoringModeSignalTier: 'Ù…Ø³ØªÙˆÙ‰',
        scoringModeConviction: 'Ø§Ù‚ØªÙ†Ø§Ø¹',
        scoringPanelTitle: 'ØªÙ‚ÙŠÙŠÙ… Ø§Ù„Ù…Ø³ØªØ«Ù…Ø±ÙŠÙ†',
        scoringComposite: 'Ø§Ù„Ø¯Ø±Ø¬Ø© Ø§Ù„Ù…Ø±ÙƒØ¨Ø©',
        scoringComponents: 'Ø§Ù„Ù…ÙƒÙˆÙ†Ø§Øª',
        scoringConsensus: 'Ø¥Ø¬Ù…Ø§Ø¹',
        scoringExecution: 'ØªÙ†ÙÙŠØ°',
        scoringRegime: 'Ø§Ù„Ù†Ø¸Ø§Ù…',
        scoringMomentum: 'Ø²Ø®Ù…',
        scoringMeetsThreshold: 'Ù‚Ø§Ø¨Ù„ Ù„Ù„ØªÙ†ÙÙŠØ°',
        scoringNoData: 'Ù„Ø§ ØªÙˆØ¬Ø¯ Ø¥Ø´Ø§Ø±Ø§Øª Ù…ÙÙ‚ÙŠÙŽÙ‘Ù…Ø© Ø¨Ø¹Ø¯.',
        riskWarnings: 'ØªØ­Ø°ÙŠØ±Ø§Øª Ø§Ù„Ù…Ø®Ø§Ø·Ø±',
        agentSignals: 'Ø¥Ø´Ø§Ø±Ø§Øª Ø§Ù„ÙˆÙƒÙ„Ø§Ø¡',
        yourWatchlist: 'Ø£Ø³Ù‡Ù…Ùƒ Ø§Ù„Ù…ØªØ§Ø¨Ø¹Ø©',
        allPredictions: 'Ø¬Ù…ÙŠØ¹ ØªÙ†Ø¨Ø¤Ø§Øª Ø§Ù„Ø¨ÙˆØ±ØµØ©',
        followStocksPrompt: 'ØªØ§Ø¨Ø¹ Ø£Ø³Ù‡Ù…Ùƒ Ù…Ù† ØªØ¨ÙˆÙŠØ¨ Ø§Ù„Ù…ØªØ§Ø¨Ø¹Ø© Ù„Ø¹Ø±Ø¶ Ø§Ù„Ø¨ÙŠØ§Ù†Ø§Øª Ø§Ù„Ù…Ø®ØµØµØ© Ù‡Ù†Ø§.',
        noWatchlistLogin: 'Ø³Ø¬Ù‘Ù„ Ø¯Ø®ÙˆÙ„Ùƒ Ù„Ø¹Ø±Ø¶ Ø¨ÙŠØ§Ù†Ø§Øª Ø§Ù„Ø£Ø³Ù‡Ù… Ø§Ù„ØªÙŠ ØªØªØ§Ø¨Ø¹Ù‡Ø§.',

        // Toast notifications (Upgrade 2)
        stockAdded: 'ØªÙ…Øª Ø¥Ø¶Ø§ÙØ© Ø§Ù„Ø³Ù‡Ù… Ù„Ù„Ù…ØªØ§Ø¨Ø¹Ø©',
        stockRemoved: 'ØªÙ… Ø¥Ø²Ø§Ù„Ø© Ø§Ù„Ø³Ù‡Ù… Ù…Ù† Ø§Ù„Ù…ØªØ§Ø¨Ø¹Ø©',
        watchlistFull: 'Ù‚Ø§Ø¦Ù…Ø© Ø§Ù„Ù…ØªØ§Ø¨Ø¹Ø© Ù…Ù…ØªÙ„Ø¦Ø© (Ø§Ù„Ø­Ø¯ Ø§Ù„Ø£Ù‚ØµÙ‰ Ù£Ù  Ø³Ù‡Ù…)',
        loadError: 'ÙØ´Ù„ ØªØ­Ù…ÙŠÙ„ Ø§Ù„Ø¨ÙŠØ§Ù†Ø§Øª. Ø­Ø§ÙˆÙ„ Ù…Ø±Ø© Ø£Ø®Ø±Ù‰.',
        dataRefreshed: 'ØªÙ… ØªØ­Ø¯ÙŠØ« Ø§Ù„Ø¨ÙŠØ§Ù†Ø§Øª Ø¨Ù†Ø¬Ø§Ø­',
        minTradesWarning: 'ÙŠØ¨Ø¯Ø£ ØªØªØ¨Ø¹ Ø§Ù„Ø£Ø¯Ø§Ø¡ Ø¨Ø¹Ø¯ Ù¡Ù Ù  ØªÙˆØµÙŠØ©',
        langSwitched: 'ØªÙ… Ø§Ù„ØªØ¨Ø¯ÙŠÙ„ Ù„Ù„Ø¹Ø±Ø¨ÙŠØ©',

        // Empty states (Upgrade 6)
        emptyPredictions: 'Ù„Ø§ ØªÙˆØ¬Ø¯ ØªÙ†Ø¨Ø¤Ø§Øª Ø¨Ø¹Ø¯',
        emptyPredictionsDesc: 'ÙŠØªÙ… Ø¥Ù†Ø´Ø§Ø¡ Ø§Ù„Ø¥Ø´Ø§Ø±Ø§Øª ÙŠÙˆÙ…ÙŠØ§Ù‹ Ø¨Ø¹Ø¯ Ø¥ØºÙ„Ø§Ù‚ Ø§Ù„Ø³ÙˆÙ‚. ØªØ­Ù‚Ù‚ Ù…Ø¬Ø¯Ø¯Ø§Ù‹ Ù‚Ø±ÙŠØ¨Ø§Ù‹.',
        emptyTrades: 'Ù„Ø§ ÙŠÙˆØ¬Ø¯ Ø³Ø¬Ù„ ØªØ¯Ø§ÙˆÙ„',
        emptyTradesDesc: 'Ø³ØªØ¸Ù‡Ø± ØªÙˆØµÙŠØ§Øª Ø§Ù„ØªØ¯Ø§ÙˆÙ„ Ù‡Ù†Ø§ Ø¨Ø¹Ø¯ Ø¥Ù†Ø´Ø§Ø¦Ù‡Ø§ Ø¨ÙˆØ§Ø³Ø·Ø© Ø§Ù„Ù†Ø¸Ø§Ù….',
        emptyPortfolio: 'Ù„Ø§ ØªÙˆØ¬Ø¯ Ù…Ø±Ø§ÙƒØ² Ù…ÙØªÙˆØ­Ø©',
        emptyPortfolioDesc: 'Ø³ØªØ¸Ù‡Ø± Ø§Ù„Ù…Ø±Ø§ÙƒØ² Ø§Ù„Ù…ÙØªÙˆØ­Ø© Ù‡Ù†Ø§ Ø¨Ø¹Ø¯ ØªÙ†ÙÙŠØ° ØªÙˆØµÙŠØ§Øª Ø§Ù„ØªØ¯Ø§ÙˆÙ„.',
        viewTrades: 'Ø¹Ø±Ø¶ Ø§Ù„ØªÙˆØµÙŠØ§Øª',
        emptyResults: 'Ù„Ø§ ØªÙˆØ¬Ø¯ Ù†ØªØ§Ø¦Ø¬ Ø¨Ø¹Ø¯',
        emptyResultsDesc: 'Ø³ØªØ¸Ù‡Ø± Ø§Ù„Ù†ØªØ§Ø¦Ø¬ Ø¨Ø¹Ø¯ ØªÙ‚ÙŠÙŠÙ… Ø§Ù„ØªÙ†Ø¨Ø¤Ø§Øª Ù…Ù‚Ø§Ø¨Ù„ Ø§Ù„Ù†ØªØ§Ø¦Ø¬ Ø§Ù„ÙØ¹Ù„ÙŠØ©.',

        // Accessibility (Upgrade 7)
        skipToContent: 'Ø§Ù„Ø§Ù†ØªÙ‚Ø§Ù„ Ø¥Ù„Ù‰ Ø§Ù„Ù…Ø­ØªÙˆÙ‰',

        // Forecasts
        tabForecasts: 'Ø§Ù„ØªÙˆÙ‚Ø¹Ø§Øª',
        forecastsBrief: 'ØªØªØ¨Ø¹ Ù…Ø­Ø§ÙØ¸ Ø§Ù„ØªÙˆÙ‚Ø¹Ø§Øª Ø§Ù„Ù…Ø­ÙÙˆØ¸Ø© ÙˆÙ‚Ø§Ø±Ù† Ø§Ù„Ø£Ø¯Ø§Ø¡ Ø§Ù„ÙØ¹Ù„ÙŠ Ù…Ø¹ Ø§Ù„Ù…ØªÙˆÙ‚Ø¹.',

        // Rates tab
        tabRates: 'Ø§Ù„Ø£Ø³Ø¹Ø§Ø±',
        ratesBrief: 'Ø³Ø¹Ø± ØµØ±Ù Ø§Ù„Ø¯ÙˆÙ„Ø§Ø±/Ø§Ù„Ø¬Ù†ÙŠÙ‡ ÙˆØ£Ø³Ø¹Ø§Ø± Ø§Ù„Ø°Ù‡Ø¨ ÙˆØ±Ø³ÙˆÙ… Ø¨ÙŠØ§Ù†ÙŠØ© Ù„Ù€ 30 ÙŠÙˆÙ….',
        ratesHistoryTitle: 'Ø§Ù„Ø³Ø¬Ù„ - 30 ÙŠÙˆÙ…',

        // Alerts
        alertsTitle: 'ØªÙ†Ø¨ÙŠÙ‡Ø§Øª Ø§Ù„Ø£Ø³Ø¹Ø§Ø±',
        alertsHint: 'Ø§Ø­ØµÙ„ Ø¹Ù„Ù‰ ØªÙ†Ø¨ÙŠÙ‡ Ø¹Ù†Ø¯Ù…Ø§ ÙŠØªØ¬Ø§ÙˆØ² Ø³Ù‡Ù… Ø³Ø¹Ø±Ùƒ Ø§Ù„Ù…Ø³ØªÙ‡Ø¯Ù.',
        alertAbove: 'Ø£Ø¹Ù„Ù‰ Ù…Ù† â†‘',
        alertBelow: 'Ø£Ù‚Ù„ Ù…Ù† â†“',

        // Comparison
        compModalTitle: 'Ù…Ù‚Ø§Ø±Ù†Ø© Ø§Ù„Ø£Ø³Ù‡Ù…',
        compMetric: 'Ø§Ù„Ù…Ø¹ÙŠØ§Ø±',
        compSignal: 'Ø§Ù„Ø¥Ø´Ø§Ø±Ø©',
        compScore: 'Ø¯Ø±Ø¬Ø© Xmore',
        compConviction: 'Ø§Ù„Ù‚Ù†Ø§Ø¹Ø©',
        compConfidence: 'Ø§Ù„Ø«Ù‚Ø©',
        compAgentsAgree: 'ØªÙˆØ§ÙÙ‚ Ø§Ù„ÙˆÙƒÙ„Ø§Ø¡',
        compBullScore: 'Ù†Ù‚Ø§Ø· Ø§Ù„ØµØ¹ÙˆØ¯',
        compBearScore: 'Ù†Ù‚Ø§Ø· Ø§Ù„Ù‡Ø¨ÙˆØ·',
        compPrice: 'Ø§Ù„Ø³Ø¹Ø± (Ø¬Ù†ÙŠÙ‡)',
        compDayChange: 'ØªØºÙŠØ± Ø§Ù„ÙŠÙˆÙ…',
        compVolume: 'Ø§Ù„Ø­Ø¬Ù…',
        compBrief: 'Ù…Ù„Ø®Øµ Ø°ÙƒÙŠ',

        // Portfolio totals
        ptlCostLabel: 'Ø§Ù„Ù…Ø³ØªØ«Ù…Ø± (Ø¬Ù†ÙŠÙ‡)',
        ptlValueLabel: 'Ø§Ù„Ù‚ÙŠÙ…Ø© Ø§Ù„Ø³ÙˆÙ‚ÙŠØ© (Ø¬Ù†ÙŠÙ‡)',
        ptlPnlLabel: 'Ø§Ù„Ø±Ø¨Ø­/Ø§Ù„Ø®Ø³Ø§Ø±Ø© (Ø¬Ù†ÙŠÙ‡)',
        ptlRetLabel: 'Ø§Ù„Ø¹Ø§Ø¦Ø¯ %',

        // Multi-horizon
        multiHorizonTitle: 'Ø¯Ù‚Ø© Ø§Ù„Ø¥Ø´Ø§Ø±Ø§Øª Ø­Ø³Ø¨ Ø§Ù„Ø£ÙÙ‚ Ø§Ù„Ø²Ù…Ù†ÙŠ',
        mhSymbol: 'Ø§Ù„Ø±Ù…Ø²',
        mhHorizon: 'Ø§Ù„Ø£ÙÙ‚',
        mhPreds: 'Ø§Ù„ØªÙ†Ø¨Ø¤Ø§Øª',
        mhCorrect: 'Ø§Ù„ØµØ­ÙŠØ­',
        mhAccuracy: 'Ø§Ù„Ø¯Ù‚Ø©',
        mhAvgChange: 'Ù…ØªÙˆØ³Ø· Ø§Ù„ØªØºÙŠØ±',

        // Time Machine
        tabTimeMachine: 'Ø¢Ù„Ø© Ø§Ù„Ø²Ù…Ù†',
        timemachineBrief: 'Ø£Ø¯Ø®Ù„ Ù…Ø¨Ù„ØºØ§Ù‹ ÙˆØªØ§Ø±ÙŠØ®Ø§Ù‹ Ø³Ø§Ø¨Ù‚Ø§Ù‹ Ù„Ù…Ø¹Ø±ÙØ© Ù‚ÙŠÙ…Ø© Ø§Ø³ØªØ«Ù…Ø§Ø±Ùƒ Ø§Ù„ÙŠÙˆÙ… Ù„Ùˆ Ø§ØªØ¨Ø¹Øª ØªÙˆØµÙŠØ§Øª Xmore.',
        tmTitle: 'Ù…Ø§Ø°Ø§ Ù„Ùˆ ÙƒÙ†Øª Ø§Ø³ØªØ«Ù…Ø±ØªØŸ',
        tmSubtitle: 'Ø´Ø§Ù‡Ø¯ ÙƒÙ… Ø³ØªÙƒÙˆÙ† Ù‚ÙŠÙ…Ø© Ø£Ù…ÙˆØ§Ù„Ùƒ Ù„Ùˆ Ø§ØªØ¨Ø¹Øª Ø£ÙØ¶Ù„ ØªÙˆØµÙŠØ§Øª Xmore.',
        tmAmountLabel: 'Ù…Ø¨Ù„Øº Ø§Ù„Ø§Ø³ØªØ«Ù…Ø§Ø± (Ø¬Ù†ÙŠÙ‡)',
        tmDateLabel: 'Ø¨Ø¯Ø¡Ø§Ù‹ Ù…Ù†',
        tm3Months: 'Ù…Ù†Ø° Ù£ Ø£Ø´Ù‡Ø±',
        tm6Months: 'Ù…Ù†Ø° Ù¦ Ø£Ø´Ù‡Ø±',
        tm12Months: 'Ù…Ù†Ø° Ø³Ù†Ø©',
        tmMaxRange: 'Ø§Ù„Ø­Ø¯ Ø§Ù„Ø£Ù‚ØµÙ‰ (Ø³Ù†ØªØ§Ù†)',
        tmSimulate: 'Ù…Ø­Ø§ÙƒØ§Ø©',
        tmYouInvested: 'Ù„Ùˆ Ø§Ø³ØªØ«Ù…Ø±Øª',
        tmWouldBeWorth: 'Ø³ØªØµØ¨Ø­ Ù‚ÙŠÙ…ØªÙ‡Ø§ Ø§Ù„ÙŠÙˆÙ…',
        tmAlpha: 'Ø£Ù„ÙØ§ Ù…Ù‚Ø§Ø¨Ù„ EGX30',
        tmVsEGX30: 'ØªÙÙˆÙ‚ Ø¹Ù„Ù‰ Ø§Ù„Ù…Ø¤Ø´Ø±',
        tmAnnualized: 'Ø§Ù„Ø¹Ø§Ø¦Ø¯ Ø§Ù„Ø³Ù†ÙˆÙŠ',
        tmTotalTrades: 'Ø¥Ø¬Ù…Ø§Ù„ÙŠ Ø§Ù„ØµÙÙ‚Ø§Øª',
        tmWinRate: 'Ù†Ø³Ø¨Ø© Ø§Ù„ÙÙˆØ²',
        tmMaxDrawdown: 'Ø£Ù‚ØµÙ‰ ØªØ±Ø§Ø¬Ø¹',
        tmSharpe: 'Ù†Ø³Ø¨Ø© Ø´Ø§Ø±Ø¨',
        tmEquityCurve: 'Ø£Ù…ÙˆØ§Ù„Ùƒ Ø¹Ø¨Ø± Ø§Ù„Ø²Ù…Ù†',
        tmMonthlyBreakdown: 'Ø§Ù„Ø¹ÙˆØ§Ø¦Ø¯ Ø§Ù„Ø´Ù‡Ø±ÙŠØ©',
        tmMonth: 'Ø§Ù„Ø´Ù‡Ø±',
        tmTopTrades: 'Ø£ÙØ¶Ù„ Ø§Ù„ØµÙÙ‚Ø§Øª',
        tmWorstTrades: 'Ø£Ø³ÙˆØ£ Ø§Ù„ØµÙÙ‚Ø§Øª',
        tmTimeline: 'Ø§Ù„Ø¬Ø¯ÙˆÙ„ Ø§Ù„Ø²Ù…Ù†ÙŠ Ù„Ù„Ø§Ø³ØªØ«Ù…Ø§Ø±',
        tmCalculating: '...Ù†Ø³Ø§ÙØ± Ø¹Ø¨Ø± Ø§Ù„Ø²Ù…Ù†',
        tmAnalyzing: 'Ø¬Ù„Ø¨ Ø¨ÙŠØ§Ù†Ø§Øª Ø§Ù„Ø³ÙˆÙ‚ Ø§Ù„Ø­ÙŠØ© ÙˆØªØ´ØºÙŠÙ„ Ø§Ù„Ù…Ø­Ø§ÙƒØ§Ø©',
        tmLoadingWarning: 'Ù‚Ø¯ ÙŠØ³ØªØºØ±Ù‚ Ù‡Ø°Ø§ Ù£Ù  Ø¥Ù„Ù‰ Ù¦Ù  Ø«Ø§Ù†ÙŠØ©.',
        tmDisclaimer: 'ØªØ³ØªØ®Ø¯Ù… Ù‡Ø°Ù‡ Ø§Ù„Ù…Ø­Ø§ÙƒØ§Ø© Ø¨ÙŠØ§Ù†Ø§Øª Ø£Ø³Ø¹Ø§Ø± Ø§Ù„Ø¨ÙˆØ±ØµØ© Ø§Ù„Ù…ØµØ±ÙŠØ© Ø§Ù„Ø­Ù‚ÙŠÙ‚ÙŠØ© Ù…Ù† Yahoo Finance ÙˆØªØ·Ø¨Ù‚ Ù…Ù†Ø·Ù‚ Ø¥Ø´Ø§Ø±Ø§Øª Xmore Ø¨Ø£Ø«Ø± Ø±Ø¬Ø¹ÙŠ. Ø§Ù„Ø£Ø¯Ø§Ø¡ Ø§Ù„Ø³Ø§Ø¨Ù‚ Ù„Ø§ ÙŠØ¶Ù…Ù† Ø§Ù„Ù†ØªØ§Ø¦Ø¬ Ø§Ù„Ù…Ø³ØªÙ‚Ø¨Ù„ÙŠØ©. Ù‡Ø°Ø§ Ù„ÙŠØ³ Ù†ØµÙŠØ­Ø© Ù…Ø§Ù„ÙŠØ©.',
        tmProfit: 'Ø±Ø¨Ø­',
        tmLoss: 'Ø®Ø³Ø§Ø±Ø©',
        tmBought: 'Ø´Ø±Ø§Ø¡',
        tmSold: 'Ø¨ÙŠØ¹',
        tmHeldFor: 'Ù…Ø¯Ø© Ø§Ù„Ø§Ø­ØªÙØ§Ø¸',
        tmDays: 'ÙŠÙˆÙ…',
        tmInvalidAmount: 'ÙŠØ¬Ø¨ Ø£Ù† ÙŠÙƒÙˆÙ† Ø§Ù„Ù…Ø¨Ù„Øº Ø¨ÙŠÙ† Ù¥Ù¬Ù Ù Ù  Ùˆ Ù¡Ù Ù¬Ù Ù Ù Ù¬Ù Ù Ù  Ø¬Ù†ÙŠÙ‡',
        tmSelectDate: 'ÙŠØ±Ø¬Ù‰ ØªØ­Ø¯ÙŠØ¯ ØªØ§Ø±ÙŠØ® Ø§Ù„Ø¨Ø¯Ø§ÙŠØ©',
        tmErrorGeneric: 'ÙØ´Ù„Øª Ø§Ù„Ù…Ø­Ø§ÙƒØ§Ø©. ÙŠØ±Ø¬Ù‰ Ø§Ù„Ù…Ø­Ø§ÙˆÙ„Ø© Ù…Ø±Ø© Ø£Ø®Ø±Ù‰.',
        tmTryDifferent: 'Ø¬Ø±Ù‘Ø¨ Ù†Ø·Ø§Ù‚ ØªØ§Ø±ÙŠØ® Ø£Ùˆ Ù…Ø¨Ù„Øº Ù…Ø®ØªÙ„Ù.',
        tmNoDataHint: 'ØªØ¹Ø°Ù‘Ø± Ø¥ÙƒÙ…Ø§Ù„ Ø§Ù„Ù…Ø­Ø§ÙƒØ§Ø©. Ø¬Ø±Ù‘Ø¨ Ù†Ø·Ø§Ù‚ ØªØ§Ø±ÙŠØ® Ù…Ø®ØªÙ„Ù.',
        // ETF cards
        etfEgyptExposure: 'ØªØ¹Ø±Ù‘Ø¶ Ù„Ù…ØµØ±',
        etfName: 'Ø§Ù„Ø§Ø³Ù…',
        etfExchange: 'Ø§Ù„Ø¨ÙˆØ±ØµØ©',
        etfPrice: 'Ø§Ù„Ø³Ø¹Ø±',
        etfChange: 'Ø§Ù„ØªØºÙŠØ±',
        etfNav: 'Ø§Ù„Ù‚ÙŠÙ…Ø© Ø§Ù„ØµØ§ÙÙŠØ©',
        etfPremDisc: 'Ø¹Ù„Ø§ÙˆØ©/Ø®ØµÙ…',
        etfHoldings: 'Ø§Ù„Ù…ÙƒÙˆÙ†Ø§Øª',
        etfIssuer: 'Ø§Ù„Ø¬Ù‡Ø© Ø§Ù„Ù…ØµØ¯Ø±Ø©',
        etfRet3m: 'Ø¹Ø§Ø¦Ø¯ 3 Ø£Ø´Ù‡Ø±',
        etfUnderlying: 'Ø§Ù„Ø£ØµÙ„ Ø§Ù„Ø£Ø³Ø§Ø³ÙŠ',
        etfLiquidity: 'Ø§Ù„Ø³ÙŠÙˆÙ„Ø©',
        etfNoData: 'Ù„Ø§ ØªÙˆØ¬Ø¯ Ø¨ÙŠØ§Ù†Ø§Øª Ø¨Ø¹Ø¯',
        etfNoDataSub: 'ÙŠØªÙ… Ø¬Ù…Ø¹ Ø§Ù„Ø¨ÙŠØ§Ù†Ø§Øª ØªÙ„Ù‚Ø§Ø¦ÙŠØ§Ù‹ Ø¨Ø¹Ø¯ Ø¥ØºÙ„Ø§Ù‚ Ø§Ù„Ø³ÙˆÙ‚',
        etfNoResults: 'Ù„Ø§ ØªÙˆØ¬Ø¯ Ù†ØªØ§Ø¦Ø¬ Ù„Ù€',
        etfLoadError: 'ØªØ¹Ø°Ø± ØªØ­Ù…ÙŠÙ„ Ø¨ÙŠØ§Ù†Ø§Øª Ø§Ù„ØµÙ†Ø§Ø¯ÙŠÙ‚.',
        etfHoldingsTitle: 'Ø§Ù„Ù…ÙƒÙˆÙ†Ø§Øª',
        etfNoHoldings: 'Ù„Ø§ ØªÙˆØ¬Ø¯ Ø¨ÙŠØ§Ù†Ø§Øª Ù…ÙƒÙˆÙ†Ø§Øª.',
        // Future tab
        tmSubPastLabel: 'â® Ø§Ù„Ù…Ø§Ø¶ÙŠ',
        tmSubFutureLabel: 'â­ Ø§Ù„Ù…Ø³ØªÙ‚Ø¨Ù„',
        fcTitle: 'Ø§Ù„ØªÙˆÙ‚Ø¹ Ø§Ù„Ù…Ø³ØªÙ‚Ø¨Ù„ÙŠ',
        fcSubtitle: 'Ø§Ù„Ø°ÙƒØ§Ø¡ Ø§Ù„Ø§ØµØ·Ù†Ø§Ø¹ÙŠ ÙŠØ®ØªØ§Ø± Ø£ÙØ¶Ù„ Ø³Ù‡Ù… EGX30 Ù„Ø£ÙÙ‚Ùƒ Ø§Ù„Ø²Ù…Ù†ÙŠ. Ù¥Ù¬Ù Ù Ù  Ù…Ø³Ø§Ø± Ù…ÙˆÙ†ØªÙŠ ÙƒØ§Ø±Ù„Ùˆ.',
        fcModeAuto: 'ðŸ¤– Ø§Ù„Ø°ÙƒØ§Ø¡ Ø§Ù„Ø§ØµØ·Ù†Ø§Ø¹ÙŠ ÙŠØ®ØªØ§Ø± Ù„ÙŠ',
        fcModeManual: 'ðŸ” Ø£Ø®ØªØ§Ø± Ø¨Ù†ÙØ³ÙŠ',
        fcModePortfolio: 'ðŸ“ Ù…Ø­Ø§ÙØ¸ÙŠ',
        pf_title: 'Ù…Ø­Ø§ÙØ¸ Ø§Ù„ØªÙˆÙ‚Ø¹Ø§Øª',
        pf_create: '+ Ù…Ø­ÙØ¸Ø© Ø¬Ø¯ÙŠØ¯Ø©',
        fcEndDateLabel: 'Ø§Ù„ØªØ§Ø±ÙŠØ® Ø§Ù„Ù…Ø³ØªÙ‡Ø¯Ù',
        fcEndDateHint: 'Ø­ØªÙ‰ Ù£Ù  ÙŠÙˆÙ…Ø§Ù‹ Ù…Ù† Ø§Ù„ÙŠÙˆÙ… â€” Ø§Ù„Ø°ÙƒØ§Ø¡ Ø§Ù„Ø§ØµØ·Ù†Ø§Ø¹ÙŠ ÙŠØ®ØªØ§Ø± Ø£ÙØ¶Ù„ Ø³Ù‡Ù… Ù„Ùƒ',
        fcSymbolLabel: 'Ø±Ù…Ø² Ø§Ù„Ø³Ù‡Ù…',
        fcHorizonLabel: 'Ø§Ù„Ø£ÙÙ‚ Ø§Ù„Ø²Ù…Ù†ÙŠ',
        fc1Month: 'Ø´Ù‡Ø±',
        fc2Months: 'Ø´Ù‡Ø±Ø§Ù†',
        fc3Months: 'Ù£ Ø£Ø´Ù‡Ø±',
        fc6Months: 'Ù¦ Ø£Ø´Ù‡Ø±',
        fc1Year: 'Ø³Ù†Ø©',
        fc2Years: 'Ø³Ù†ØªØ§Ù†',
        pf_name_label: 'Ø§Ø³Ù… Ø§Ù„Ù…Ø­ÙØ¸Ø©',
        pf_save: 'Ø­ÙØ¸ Ø§Ù„Ù…Ø­ÙØ¸Ø©',
        pf_cancel: 'Ø¥Ù„ØºØ§Ø¡',
        fcRunBtnManual: 'ØªØ´ØºÙŠÙ„ Ø§Ù„ØªÙˆÙ‚Ø¹',
        fcSelectSymbol: 'ÙŠØ±Ø¬Ù‰ Ø§Ø®ØªÙŠØ§Ø± Ø³Ù‡Ù….',
        fcScenarioLabel: 'Ø§Ù„Ø³ÙŠÙ†Ø§Ø±ÙŠÙˆ',
        fcBase: 'Ù‚Ø§Ø¹Ø¯ÙŠ',
        fcBaseHint: 'Ø§Ù„Ø§Ù†Ø¬Ø±Ø§Ù Ø§Ù„ØªØ§Ø±ÙŠØ®ÙŠ',
        fcBull: 'ØµØ§Ø¹Ø¯',
        fcBullHint: '+Ù¢Ùª ØªØ¹Ø²ÙŠØ²',
        fcBear: 'Ù‡Ø§Ø¨Ø·',
        fcBearHint: 'âˆ’Ù¢Ùª Ø¶ØºØ·',
        fcRunBtn: 'Ø§Ø®ØªØ± Ø£ÙØ¶Ù„ Ø³Ù‡Ù… ÙˆØ§Ø¨Ø¯Ø£ Ø§Ù„ØªÙˆÙ‚Ø¹',
        fcSelectDate: 'ÙŠØ±Ø¬Ù‰ Ø§Ø®ØªÙŠØ§Ø± ØªØ§Ø±ÙŠØ® Ù…Ø³ØªÙ‡Ø¯Ù.',
        fcChosenBy: 'Ø§Ø®ØªÙŠØ§Ø± Ø§Ù„Ø°ÙƒØ§Ø¡ Ø§Ù„Ø§ØµØ·Ù†Ø§Ø¹ÙŠ',
        fcSeeRanking: 'Ø±Ø¤ÙŠØ© Ø§Ù„ØªØ±ØªÙŠØ¨ â–¼',
        fcHideRanking: 'Ø¥Ø®ÙØ§Ø¡ â–²',
        fcExpectedValue: 'Ø§Ù„Ù‚ÙŠÙ…Ø© Ø§Ù„Ù…ØªÙˆÙ‚Ø¹Ø©',
        fcProbProfit: 'Ø§Ø­ØªÙ…Ø§Ù„ÙŠØ© Ø§Ù„Ø±Ø¨Ø­',
        fcVolatility: 'Ø§Ù„ØªÙ‚Ù„Ø¨ Ø§Ù„Ø³Ù†ÙˆÙŠ',
        fcWorstCase: 'Ø£Ø³ÙˆØ£ Ø­Ø§Ù„Ø© (Ø§Ù„Ø®Ø§Ù…Ø³Ùª)',
        fcMedian: 'Ø§Ù„ÙˆØ³ÙŠØ·',
        fcBestCase: 'Ø£ÙØ¶Ù„ Ø­Ø§Ù„Ø© (Ù©Ù¥Ùª)',
        fcBandChartTitle: 'Ø§Ù„Ù‚ÙŠÙ…Ø© Ø§Ù„Ù…ØªÙˆÙ‚Ø¹Ø© Ù„Ù„Ù…Ø­ÙØ¸Ø©',
        fcHistTitle: 'ØªÙˆØ²ÙŠØ¹ Ø§Ù„Ù‚ÙŠÙ… Ø§Ù„Ù†Ù‡Ø§Ø¦ÙŠØ©',
        fcHistSub: 'Ù¥Ù¬Ù Ù Ù  Ù†ØªÙŠØ¬Ø© Ù…Ø­Ø§ÙƒØ§Ø©. Ø£Ø®Ø¶Ø± = Ø±Ø¨Ø­ØŒ Ø£Ø­Ù…Ø± = Ø®Ø³Ø§Ø±Ø©.',
        fcDrift: 'Ø§Ù„Ø§Ù†Ø¬Ø±Ø§Ù Ø§Ù„ØªØ§Ø±ÙŠØ®ÙŠ',
        fcScenarioUsed: 'ØªØ¹Ø¯ÙŠÙ„ Ø§Ù„Ø³ÙŠÙ†Ø§Ø±ÙŠÙˆ',
        fcDataPoints: 'Ù†Ù‚Ø§Ø· Ø§Ù„Ø¨ÙŠØ§Ù†Ø§Øª',
        fcSimCount: 'Ø¹Ø¯Ø¯ Ø§Ù„Ù…Ø­Ø§ÙƒØ§Ø©',
        fcCalculating: '...ÙØ­Øµ Ø£Ø³Ù‡Ù… EGX30 ÙˆØªØ´ØºÙŠÙ„ Ù¥Ù¬Ù Ù Ù  Ù…Ø³Ø§Ø± Ù…ÙˆÙ†ØªÙŠ ÙƒØ§Ø±Ù„Ùˆ',
        fcAnalyzing: 'Ø­Ø³Ø§Ø¨ Ù…Ø¹Ø§Ù…Ù„Ø§Øª GBM â€” Ù‚Ø¯ ÙŠØ³ØªØºØ±Ù‚ ~Ù£Ù  Ø«Ø§Ù†ÙŠØ©',
        fcDisclaimer: 'Ù‡Ø°Ø§ Ø§Ù„ØªÙˆÙ‚Ø¹ Ù‚Ø§Ø¦Ù… Ø¹Ù„Ù‰ Ù†Ù…ÙˆØ°Ø¬ Ø±ÙŠØ§Ø¶ÙŠ ÙˆÙ„Ø§ ÙŠÙ…Ø«Ù„ Ù†ØµÙŠØ­Ø© Ù…Ø§Ù„ÙŠØ©. ØªØ¹ØªÙ…Ø¯ Ø§Ù„Ù†ØªØ§Ø¦Ø¬ Ø¹Ù„Ù‰ Ø§ÙØªØ±Ø§Ø¶Ø§Øª Ø¥Ø­ØµØ§Ø¦ÙŠØ© ØªØ§Ø±ÙŠØ®ÙŠØ© ÙˆØ¸Ø±ÙˆÙ Ø§Ù„Ø³ÙˆÙ‚.',
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
        ar: { name: 'Ø§ØªØ¬Ø§Ù‡ Ø§Ù„Ù…ØªÙˆØ³Ø· Ø§Ù„Ù…ØªØ­Ø±Ùƒ', description: 'ÙŠØ­Ù„Ù„ ØªÙ‚Ø§Ø·Ø¹Ø§Øª Ø§Ù„Ù…ØªÙˆØ³Ø·Ø§Øª Ø§Ù„Ù…ØªØ­Ø±ÙƒØ© Ù„ØªØ­Ø¯ÙŠØ¯ ØªØºÙŠØ±Ø§Øª Ø§Ù„Ø§ØªØ¬Ø§Ù‡.' }
    },
    'ML_RandomForest': {
        en: { name: 'Price Predictor', description: 'Machine learning model using 40+ technical indicators to predict price movements.' },
        ar: { name: 'Ù…ØªÙ†Ø¨Ø¦ Ø§Ù„Ø£Ø³Ø¹Ø§Ø± Ø§Ù„Ø°ÙƒÙŠ', description: 'Ù†Ù…ÙˆØ°Ø¬ ØªØ¹Ù„Ù… Ø¢Ù„ÙŠ ÙŠØ³ØªØ®Ø¯Ù… 40+ Ù…Ø¤Ø´Ø± ÙÙ†ÙŠ Ù„Ù„ØªÙ†Ø¨Ø¤ Ø¨Ø­Ø±ÙƒØ§Øª Ø§Ù„Ø£Ø³Ø¹Ø§Ø±.' }
    },
    'RSI_Agent': {
        en: { name: 'Momentum Indicator', description: 'Uses Relative Strength Index to detect overbought/oversold conditions.' },
        ar: { name: 'Ù…Ø¤Ø´Ø± Ø§Ù„Ø²Ø®Ù…', description: 'ÙŠØ³ØªØ®Ø¯Ù… Ù…Ø¤Ø´Ø± Ø§Ù„Ù‚ÙˆØ© Ø§Ù„Ù†Ø³Ø¨ÙŠØ© Ù„Ø§ÙƒØªØ´Ø§Ù Ø­Ø§Ù„Ø§Øª Ø§Ù„Ø´Ø±Ø§Ø¡/Ø§Ù„Ø¨ÙŠØ¹ Ø§Ù„Ù…ÙØ±Ø·.' }
    },
    'Volume_Spike_Agent': {
        en: { name: 'Volume Analysis', description: 'Monitors unusual volume activity to predict potential price movements.' },
        ar: { name: 'ØªØ­Ù„ÙŠÙ„ Ø§Ù„Ø­Ø¬Ù…', description: 'ÙŠØ±Ø§Ù‚Ø¨ Ù†Ø´Ø§Ø· Ø§Ù„Ø­Ø¬Ù… ØºÙŠØ± Ø§Ù„Ù…Ø¹ØªØ§Ø¯ Ù„Ù„ØªÙ†Ø¨Ø¤ Ø¨ØªØ­Ø±ÙƒØ§Øª Ø§Ù„Ø£Ø³Ø¹Ø§Ø±.' }
    },
    'Consensus': {
        en: { name: 'Consensus Signal', description: 'Weighted vote across all agents based on historical accuracy.' },
        ar: { name: 'Ø¥Ø´Ø§Ø±Ø© Ø§Ù„Ø¥Ø¬Ù…Ø§Ø¹', description: 'ØªØµÙˆÙŠØª Ù…Ø±Ø¬Ø­ Ø¹Ø¨Ø± Ø¬Ù…ÙŠØ¹ Ø§Ù„ÙˆÙƒÙ„Ø§Ø¡ Ø¨Ù†Ø§Ø¡Ù‹ Ø¹Ù„Ù‰ Ø§Ù„Ø¯Ù‚Ø© Ø§Ù„ØªØ§Ø±ÙŠØ®ÙŠØ©.' }
    },
    'DCF_Valuation_Agent': {
        en: { name: 'DCF Valuation', description: 'Supplementary weekly discounted cash flow valuation signal.' },
        ar: { name: 'ØªÙ‚ÙŠÙŠÙ… DCF', description: 'Ø¥Ø´Ø§Ø±Ø© ØªÙ‚ÙŠÙŠÙ… Ø¯Ø§Ø¹Ù…Ø© Ø£Ø³Ø¨ÙˆØ¹ÙŠØ© ØªØ¹ØªÙ…Ø¯ Ø¹Ù„Ù‰ Ø§Ù„ØªØ¯ÙÙ‚Ø§Øª Ø§Ù„Ù†Ù‚Ø¯ÙŠØ© Ø§Ù„Ù…Ø®ØµÙˆÙ…Ø©.' }
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
    loadIntelligencePulse();
    loadRegimeBanner();
}

function applyLanguage() {
    const isArabic = currentLang === 'ar';

    document.documentElement.dir = isArabic ? 'rtl' : 'ltr';
    document.documentElement.lang = currentLang;
    document.body.classList.toggle('rtl', isArabic);

    // Update page title
    document.title = isArabic ? 'Ø¥ÙƒØ³Ù…ÙˆØ± â€” Ù„ÙˆØ­Ø© Ø§Ù„ØªÙ†Ø¨Ø¤Ø§Øª Ø§Ù„Ø°ÙƒÙŠØ© Ù„Ù„Ø£Ø³Ù‡Ù…' : 'Xmore â€” Market Intelligence Dashboard';

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
    const briefIds = ['predictionsBrief', 'watchlistBrief', 'performanceBrief', 'consensusBrief', 'consensusDcfNote', 'resultsBrief', 'pricesBrief', 'briefingBrief', 'tradesBrief', 'portfolioBrief', 'forecastsBrief', 'timemachineBrief', 'ratesBrief'];
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
    const globalSearchInput = document.getElementById('globalSearchInput');
    if (globalSearchInput) globalSearchInput.placeholder = t('globalSearchPlaceholder');

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
    if (typeof refreshGlobalSearchLanguage === 'function') refreshGlobalSearchLanguage();
}

// ============================================
// GLOBAL SEARCH (Bilingual)
// ============================================

let _globalSearchResults = [];
let _globalSearchActiveIndex = -1;

function normalizeSearchValue(v) {
    return String(v || '')
        .toLowerCase()
        .normalize('NFKD')
        .replace(/[\u0300-\u036f]/g, '')
        .trim();
}

function getGlobalSearchItems() {
    const tabItems = [
        { en: 'Predictions', ar: 'Ø§Ù„ØªÙ†Ø¨Ø¤Ø§Øª', target: 'predictions', aliases: 'signals signal stocks ideas opportunities bullish bearish neutral forecast calls scanner screener Ø¥Ø´Ø§Ø±Ø§Øª ÙØ±Øµ Ø£ÙÙƒØ§Ø± Ø§Ù„Ø£Ø³Ù‡Ù… ØµØ¹ÙˆØ¯ Ù‡Ø¨ÙˆØ· Ø­ÙŠØ§Ø¯' },
        { en: 'Consensus', ar: 'Ø§Ù„Ø¥Ø¬Ù…Ø§Ø¹', target: 'consensus', aliases: 'ranked ranking score calibrated confidence expected edge conviction agreement edge alpha what changed today freshness drift ØªØ±ØªÙŠØ¨ Ø¯Ø±Ø¬Ø© Ø§Ù„Ø«Ù‚Ø© Ø§Ù„Ø­Ø§ÙØ© Ø§Ù„Ø¹Ø§Ø¦Ø¯ Ø§Ù„Ù…ØªÙˆÙ‚Ø¹ Ø¥Ø¬Ù…Ø§Ø¹ Ø§Ù†Ø­Ø±Ø§Ù Ø­Ø¯Ø§Ø«Ø©' },
        { en: 'DCF Valuation', ar: 'ØªÙ‚ÙŠÙŠÙ… DCF', target: 'consensus', aliases: 'discounted cash flow intrinsic valuation Ø§Ù„ØªØ¯ÙÙ‚Ø§Øª Ø§Ù„Ù†Ù‚Ø¯ÙŠØ© Ø§Ù„Ù…Ø®ØµÙˆÙ…Ø© ØªÙ‚ÙŠÙŠÙ… Ø¬ÙˆÙ‡Ø±ÙŠ' },
        { en: 'Performance', ar: 'Ø§Ù„Ø£Ø¯Ø§Ø¡', target: 'performance', aliases: 'accuracy win rate drawdown benchmark returns track quality alpha stability Ø¯Ù‚Ø© Ø§Ù„Ø£Ø¯Ø§Ø¡ Ø¹Ø§Ø¦Ø¯ Ù…Ø¤Ø´Ø± ÙÙˆØ² ØªØ±Ø§Ø¬Ø¹' },
        { en: 'Trades', ar: 'Ø§Ù„ØµÙÙ‚Ø§Øª', target: 'trades', aliases: 'recommendations trade ideas entry target stop risk execution session ØªÙˆØµÙŠØ§Øª ØµÙÙ‚Ø§Øª Ø¯Ø®ÙˆÙ„ Ù‡Ø¯Ù Ø¥ÙŠÙ‚Ø§Ù Ø®Ø³Ø§Ø±Ø© ØªÙ†ÙÙŠØ°' },
        { en: 'Portfolio', ar: 'Ø§Ù„Ù…Ø­ÙØ¸Ø©', target: 'portfolio', aliases: 'positions pnl profit loss holdings allocation exposure alerts Ø§Ù„Ù…Ø±Ø§ÙƒØ² Ø§Ù„Ø£Ø±Ø¨Ø§Ø­ Ø§Ù„Ø®Ø³Ø§Ø¦Ø± Ø§Ù„Ø­ÙŠØ§Ø²Ø§Øª ØªÙˆØ²ÙŠØ¹ ØªØ¹Ø±Ø¶ ØªÙ†Ø¨ÙŠÙ‡Ø§Øª' },
        { en: 'Forecasts', ar: 'Ø§Ù„ØªÙˆÙ‚Ø¹Ø§Øª', target: 'forecasts', aliases: 'scenario scenarios projected future simulation monte carlo probabilistic portfolio forecast Ø³ÙŠÙ†Ø§Ø±ÙŠÙˆ Ø³ÙŠÙ†Ø§Ø±ÙŠÙˆÙ‡Ø§Øª Ù…Ø­Ø§ÙƒØ§Ø© Ø§Ù„Ù…Ø³ØªÙ‚Ø¨Ù„ Ø§Ø­ØªÙ…Ø§Ù„ÙŠ ØªÙˆÙ‚Ø¹ Ù…Ø­ÙØ¸Ø©' },
        { en: 'Watchlist', ar: 'Ø§Ù„Ù…ØªØ§Ø¨Ø¹Ø©', target: 'watchlist', aliases: 'favorites favourite saved stocks monitor tracking Ø§Ù„Ù…ÙØ¶Ù„Ø© Ù…ÙØ¶Ù„Ø§Øª Ù…Ø±Ø§Ù‚Ø¨Ø© ØªØªØ¨Ø¹ Ø£Ø³Ù‡Ù… Ù…Ø­ÙÙˆØ¸Ø©' },
        { en: 'Results', ar: 'Ø§Ù„Ù†ØªØ§Ø¦Ø¬', target: 'results', aliases: 'evaluations actual realized outcomes backtest validation compare predicted actual ØªÙ‚ÙŠÙŠÙ… ØªØ­Ù‚Ù‚ Ù†ØªØ§Ø¦Ø¬ ÙØ¹Ù„ÙŠØ© Ù…Ù‚Ø§Ø±Ù†Ø© Ø§Ù„Ù…ØªÙˆÙ‚Ø¹ Ø§Ù„ÙØ¹Ù„ÙŠ' },
        { en: 'Prices', ar: 'Ø§Ù„Ø£Ø³Ø¹Ø§Ø±', target: 'prices', aliases: 'market prices last price volume quote quotes tape feed Ø³Ø¹Ø± Ø£Ø³Ø¹Ø§Ø± Ø­Ø¬Ù… ØªØ¯Ø§ÙˆÙ„ Ø£Ø³Ø¹Ø§Ø± Ø§Ù„Ø³ÙˆÙ‚' },
        { en: 'Time Machine', ar: 'Ø¢Ù„Ø© Ø§Ù„Ø²Ù…Ù†', target: 'timemachine', aliases: 'what if back in time historical simulate past future path investment timeline Ù…Ø§Ø°Ø§ Ù„Ùˆ Ù…Ø§Ø¶ÙŠ ØªØ§Ø±ÙŠØ®ÙŠ Ù…Ø­Ø§ÙƒØ§Ø© Ø§Ù„Ø§Ø³ØªØ«Ù…Ø§Ø± Ø§Ù„Ø¬Ø¯ÙˆÙ„ Ø§Ù„Ø²Ù…Ù†ÙŠ' },
        { en: 'Rates', ar: 'Ø§Ù„Ø£Ø³Ø¹Ø§Ø± Ø§Ù„Ø¹Ø§Ù„Ù…ÙŠØ©', target: 'rates', aliases: 'usd egp fx dollar gold 24k 21k 18k pound currency macro rates foreign exchange Ø¯ÙˆÙ„Ø§Ø± Ø¬Ù†ÙŠÙ‡ Ø°Ù‡Ø¨ 24 21 18 Ø¬Ù†ÙŠÙ‡ Ø°Ù‡Ø¨ Ø¹Ù…Ù„Ø§Øª ÙÙˆØ±ÙƒØ³ Ù…Ø§ÙƒØ±Ùˆ' },
        { en: 'ETFs', ar: 'ØµÙ†Ø§Ø¯ÙŠÙ‚ Ø§Ù„Ø§Ø³ØªØ«Ù…Ø§Ø±', target: 'etf', aliases: 'ETF ETP exchange traded fund exchange-traded fund fund ØµÙ†Ø¯ÙˆÙ‚ Ù…Ø¤Ø´Ø±Ø§Øª ØµÙ†Ø§Ø¯ÙŠÙ‚ Ø§Ù„Ù…Ø¤Ø´Ø±Ø§Øª ØµÙ†Ø§Ø¯ÙŠÙ‚ Ù…ØªØ¯Ø§ÙˆÙ„Ø©' },
    ].map(item => {
        const enLabel = item.en;
        const arLabel = item.ar;
        const aliases = item.aliases || '';
        return {
            type: 'tab',
            target: item.target,
            label: currentLang === 'ar' ? arLabel : enLabel,
            searchText: normalizeSearchValue(`${enLabel} ${arLabel} ${aliases}`)
        };
    });

    const pageItems = [
        { en: 'Home', ar: 'Ø§Ù„Ø±Ø¦ÙŠØ³ÙŠØ©', target: '/', aliases: 'dashboard xmore home main start Ù„ÙˆØ­Ø© Ø§Ù„ØªØ­ÙƒÙ… Ø§Ù„Ø±Ø¦ÙŠØ³ÙŠØ© Ø¨Ø¯Ø§ÙŠØ©' },
        { en: 'Docs', ar: 'Ø§Ù„ØªÙˆØ«ÙŠÙ‚', target: '/docs', aliases: 'features benefits product overview public docs documentation sales page capabilities Ù…Ù…ÙŠØ²Ø§Øª ÙÙˆØ§Ø¦Ø¯ Ù†Ø¸Ø±Ø© Ø¹Ø§Ù…Ø© Ø§Ù„Ù…Ù†ØªØ¬ Ø§Ù„ØªÙˆØ«ÙŠÙ‚ Ø§Ù„Ø¹Ø§Ù…' },
        { en: 'Track Record', ar: 'Ø³Ø¬Ù„ Ø§Ù„Ø£Ø¯Ø§Ø¡', target: '/track-record', aliases: 'verified record proof audit performance history returns transparency Ø³Ø¬Ù„ Ø§Ù„Ø£Ø¯Ø§Ø¡ ØªØ­Ù‚Ù‚ Ø³Ø¬Ù„ ØªØ§Ø±ÙŠØ® Ø§Ù„Ø¹ÙˆØ§Ø¦Ø¯ Ø´ÙØ§ÙÙŠØ©' },
        { en: 'Session', ar: 'ØµÙØ­Ø© Ø§Ù„Ø¬Ù„Ø³Ø©', target: '/session', aliases: 'market session live session daily pulse opening bell close intraday Ø§Ù„Ø¬Ù„Ø³Ø© Ø§Ù„Ø³ÙˆÙ‚ Ø§Ù„ÙŠÙˆÙ… Ø¯Ø§Ø®Ù„ Ø§Ù„Ø¬Ù„Ø³Ø© Ù„Ø­Ø¸ÙŠ' },
        { en: 'Pro', ar: 'Ø¨Ø±Ùˆ', target: '/pro', aliases: 'premium professional advanced institutional workflow Ø§Ø­ØªØ±Ø§ÙÙŠ Ù…ØªÙ‚Ø¯Ù… Ù…Ø­ØªØ±Ù Ø³ÙŠØ± Ø¹Ù…Ù„' },
        { en: 'Landing', ar: 'Ø§Ù„ØµÙØ­Ø© Ø§Ù„ØªØ¹Ø±ÙŠÙÙŠØ©', target: '/landing', aliases: 'landing overview intro marketing product story value proposition ØµÙØ­Ø© ØªØ¹Ø±ÙŠÙÙŠØ© ØªØ¹Ø±Ù Ø§Ù„Ù…Ù†ØªØ¬ Ø§Ù„Ù‚ÙŠÙ…Ø©' },
    ].map(item => ({
        type: 'page',
        target: item.target,
        label: currentLang === 'ar' ? item.ar : item.en,
        searchText: normalizeSearchValue(`${item.en} ${item.ar} ${item.aliases || ''}`)
    }));

    const stockItems = Object.keys(COMPANY_NAMES).map(symbol => {
        const c = COMPANY_NAMES[symbol] || {};
        const enName = c.en || symbol;
        const arName = c.ar || enName;
        return {
            type: 'stock',
            symbol,
            label: `${symbol} â€” ${currentLang === 'ar' ? arName : enName}`,
            searchText: normalizeSearchValue(`${symbol} ${enName} ${arName}`)
        };
    });

    return [...tabItems, ...pageItems, ...stockItems];
}

function getGlobalSearchTypeLabel(type) {
    if (type === 'stock') return t('globalSearchStocksLabel');
    if (type === 'tab') return t('globalSearchTabLabel');
    return t('globalSearchPageLabel');
}

function renderGlobalSearchResults(items) {
    const resultsEl = document.getElementById('globalSearchResults');
    if (!resultsEl) return;

    if (!items.length) {
        resultsEl.innerHTML = `<button class="global-search-item" type="button" disabled>${escapeHtml(t('globalSearchNoResults'))}</button>`;
        resultsEl.hidden = false;
        return;
    }

    resultsEl.innerHTML = items.map((item, idx) => `
        <button class="global-search-item${idx === _globalSearchActiveIndex ? ' active' : ''}" type="button" data-index="${idx}">
            ${escapeHtml(item.label)}
            <span class="global-search-meta">${escapeHtml(getGlobalSearchTypeLabel(item.type))}</span>
        </button>
    `).join('');
    resultsEl.hidden = false;

    resultsEl.querySelectorAll('.global-search-item[data-index]').forEach(btn => {
        btn.addEventListener('click', () => {
            const i = Number(btn.getAttribute('data-index'));
            const selected = _globalSearchResults[i];
            if (selected) handleGlobalSearchSelect(selected);
        });
    });
}

function closeGlobalSearchResults() {
    const resultsEl = document.getElementById('globalSearchResults');
    if (!resultsEl) return;
    resultsEl.hidden = true;
    resultsEl.innerHTML = '';
    _globalSearchResults = [];
    _globalSearchActiveIndex = -1;
}

function handleGlobalSearchSelect(item) {
    const input = document.getElementById('globalSearchInput');
    if (input) input.value = item.label;
    closeGlobalSearchResults();

    if (item.type === 'tab') {
        switchToTab(item.target, true);
        return;
    }

    if (item.type === 'page') {
        window.location.href = item.target;
        return;
    }

    switchToTab('predictions', true);
    const predSearch = document.getElementById('predictionsSearch');
    if (predSearch) {
        predSearch.value = item.symbol || '';
        applyPredictionFilters();
        predSearch.focus();
    }
}

function refreshGlobalSearchLanguage() {
    const input = document.getElementById('globalSearchInput');
    if (!input) return;
    if (!input.value.trim()) return;
    const q = normalizeSearchValue(input.value);
    const items = getGlobalSearchItems().filter(x => x.searchText.includes(q)).slice(0, 12);
    _globalSearchResults = items;
    _globalSearchActiveIndex = items.length ? 0 : -1;
    renderGlobalSearchResults(items);
}

function initGlobalSearch() {
    const input = document.getElementById('globalSearchInput');
    const resultsEl = document.getElementById('globalSearchResults');
    if (!input || !resultsEl) return;

    input.addEventListener('input', () => {
        const q = normalizeSearchValue(input.value);
        if (!q) {
            closeGlobalSearchResults();
            return;
        }
        const items = getGlobalSearchItems().filter(x => x.searchText.includes(q)).slice(0, 12);
        _globalSearchResults = items;
        _globalSearchActiveIndex = items.length ? 0 : -1;
        renderGlobalSearchResults(items);
    });

    input.addEventListener('keydown', (e) => {
        if (!resultsEl || resultsEl.hidden || !_globalSearchResults.length) return;
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            _globalSearchActiveIndex = (_globalSearchActiveIndex + 1) % _globalSearchResults.length;
            renderGlobalSearchResults(_globalSearchResults);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            _globalSearchActiveIndex = (_globalSearchActiveIndex - 1 + _globalSearchResults.length) % _globalSearchResults.length;
            renderGlobalSearchResults(_globalSearchResults);
        } else if (e.key === 'Enter') {
            e.preventDefault();
            const selected = _globalSearchResults[Math.max(_globalSearchActiveIndex, 0)];
            if (selected) handleGlobalSearchSelect(selected);
        } else if (e.key === 'Escape') {
            closeGlobalSearchResults();
        }
    });

    document.addEventListener('click', (e) => {
        if (!resultsEl.hidden && !input.contains(e.target) && !resultsEl.contains(e.target)) {
            closeGlobalSearchResults();
        }
    });
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
    // 'predictions' is always visible â€” remove it from the hidden set as a safety guard
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
    'AAPL': { en: 'Apple Inc.', ar: 'Ø´Ø±ÙƒØ© Ø£Ø¨Ù„' },
    'GOOGL': { en: 'Alphabet Inc. (Google)', ar: 'Ø£Ù„ÙØ§Ø¨Øª (Ø¬ÙˆØ¬Ù„)' },
    'MSFT': { en: 'Microsoft Corporation', ar: 'Ø´Ø±ÙƒØ© Ù…Ø§ÙŠÙƒØ±ÙˆØ³ÙˆÙØª' },
    'AMZN': { en: 'Amazon.com Inc.', ar: 'Ø´Ø±ÙƒØ© Ø£Ù…Ø§Ø²ÙˆÙ†' },
    'META': { en: 'Meta Platforms Inc.', ar: 'Ø´Ø±ÙƒØ© Ù…ÙŠØªØ§' },
    'TSLA': { en: 'Tesla Inc.', ar: 'Ø´Ø±ÙƒØ© ØªØ³Ù„Ø§' },
    'NVDA': { en: 'NVIDIA Corporation', ar: 'Ø´Ø±ÙƒØ© Ø¥Ù†ÙÙŠØ¯ÙŠØ§' },
    'JPM': { en: 'JPMorgan Chase & Co.', ar: 'Ø¬ÙŠ Ø¨ÙŠ Ù…ÙˆØ±ØºØ§Ù†' },
    'V': { en: 'Visa Inc.', ar: 'Ø´Ø±ÙƒØ© ÙÙŠØ²Ø§' },
    'JNJ': { en: 'Johnson & Johnson', ar: 'Ø¬ÙˆÙ†Ø³ÙˆÙ† Ø¢Ù†Ø¯ Ø¬ÙˆÙ†Ø³ÙˆÙ†' },
    'WMT': { en: 'Walmart Inc.', ar: 'Ø´Ø±ÙƒØ© ÙˆÙˆÙ„Ù…Ø§Ø±Øª' },
    'XOM': { en: 'Exxon Mobil Corporation', ar: 'Ø¥ÙƒØ³ÙˆÙ† Ù…ÙˆØ¨ÙŠÙ„' },
    'BAC': { en: 'Bank of America Corp.', ar: 'Ø¨Ù†Ùƒ Ø£ÙˆÙ Ø£Ù…Ø±ÙŠÙƒØ§' },
    'PG': { en: 'Procter & Gamble Co.', ar: 'Ø¨Ø±ÙˆÙƒØªØ± Ø¢Ù†Ø¯ ØºØ§Ù…Ø¨Ù„' },
    'HD': { en: 'The Home Depot Inc.', ar: 'Ù‡ÙˆÙ… Ø¯ÙŠØ¨ÙˆØª' },
    // EGX Stocks (Egyptian Exchange)
    'COMI.CA': { en: 'Commercial International Bank CIB', ar: 'Ø§Ù„Ø¨Ù†Ùƒ Ø§Ù„ØªØ¬Ø§Ø±ÙŠ Ø§Ù„Ø¯ÙˆÙ„ÙŠ' },
    'HRHO.CA': { en: 'EFG Holding Hermes', ar: 'Ù‡ÙŠØ±Ù…ÙŠØ³ Ø§Ù„Ù‚Ø§Ø¨Ø¶Ø©' },
    'FWRY.CA': { en: 'Fawry Banking Technology', ar: 'ÙÙˆØ±ÙŠ Ù„ØªÙƒÙ†ÙˆÙ„ÙˆØ¬ÙŠØ§ Ø§Ù„Ø¨Ù†ÙˆÙƒ' },
    'TMGH.CA': { en: 'Talaat Moustafa Group', ar: 'Ù…Ø¬Ù…ÙˆØ¹Ø© Ø·Ù„Ø¹Øª Ù…ØµØ·ÙÙ‰' },
    'ORAS.CA': { en: 'Orascom Construction', ar: 'Ø£ÙˆØ±Ø§Ø³ÙƒÙˆÙ… Ù„Ù„Ø¥Ù†Ø´Ø§Ø¡Ø§Øª' },
    'PHDC.CA': { en: 'Palm Hills Development', ar: 'Ø¨Ø§Ù„Ù… Ù‡ÙŠÙ„Ø² Ù„Ù„ØªØ¹Ù…ÙŠØ±' },
    'MNHD.CA': { en: 'Madinet Nasr Housing', ar: 'Ù…Ø¯ÙŠÙ†Ø© Ù†ØµØ± Ù„Ù„Ø¥Ø³ÙƒØ§Ù†' },
    'OCDI.CA': { en: 'Orascom Development', ar: 'Ø£ÙˆØ±Ø§Ø³ÙƒÙˆÙ… Ù„Ù„ØªÙ†Ù…ÙŠØ©' },
    'SWDY.CA': { en: 'El Sewedy Electric', ar: 'Ø§Ù„Ø³ÙˆÙŠØ¯ÙŠ Ø¥Ù„ÙŠÙƒØªØ±ÙŠÙƒ' },
    'EAST.CA': { en: 'Eastern Company Tobacco', ar: 'Ø§Ù„Ø´Ø±Ù‚ÙŠØ© Ù„Ù„Ø¯Ø®Ø§Ù†' },
    'EFIH.CA': { en: 'Egyptian Financial Industrial', ar: 'Ø§Ù„Ù…ØµØ±ÙŠØ© Ø§Ù„Ù…Ø§Ù„ÙŠØ© Ø§Ù„ØµÙ†Ø§Ø¹ÙŠØ©' },
    'ESRS.CA': { en: 'Ezz Steel', ar: 'Ø­Ø¯ÙŠØ¯ Ø¹Ø²' },
    'ETEL.CA': { en: 'Telecom Egypt', ar: 'Ø§Ù„Ù…ØµØ±ÙŠØ© Ù„Ù„Ø§ØªØµØ§Ù„Ø§Øª' },
    'EMFD.CA': { en: 'E-Finance Digital', ar: 'Ø¥ÙŠ ÙØ§ÙŠÙ†Ø§Ù†Ø³' },
    'ALCN.CA': { en: 'Alexandria Container Cargo', ar: 'Ø§Ù„Ø¥Ø³ÙƒÙ†Ø¯Ø±ÙŠØ© Ù„Ù„Ø­Ø§ÙˆÙŠØ§Øª' },
    'ABUK.CA': { en: 'Abu Qir Fertilizers', ar: 'Ø£Ø¨Ùˆ Ù‚ÙŠØ± Ù„Ù„Ø£Ø³Ù…Ø¯Ø©' },
    'MFPC.CA': { en: 'Misr Fertilizers MOPCO', ar: 'Ù…ÙˆØ¨ÙƒÙˆ Ù„Ù„Ø£Ø³Ù…Ø¯Ø©' },
    'SKPC.CA': { en: 'Sidi Kerir Petrochemicals', ar: 'Ø³ÙŠØ¯ÙŠ ÙƒØ±ÙŠØ± Ù„Ù„Ø¨ØªØ±ÙˆÙƒÙŠÙ…Ø§ÙˆÙŠØ§Øª' },
    'JUFO.CA': { en: 'Juhayna Food Industries', ar: 'Ø¬Ù‡ÙŠÙ†Ø© Ù„Ù„ØµÙ†Ø§Ø¹Ø§Øª Ø§Ù„ØºØ°Ø§Ø¦ÙŠØ©' },
    'CCAP.CA': { en: 'Cleopatra Hospital', ar: 'Ù…Ø³ØªØ´ÙÙ‰ ÙƒÙ„ÙŠÙˆØ¨Ø§ØªØ±Ø§' },
    'ORWE.CA': { en: 'Oriental Weavers', ar: 'Ø§Ù„Ø³Ø¬Ø§Ø¯ Ø§Ù„Ø´Ø±Ù‚ÙŠ' },
    'AMOC.CA': { en: 'Alexandria Mineral Oils', ar: 'Ø£Ù…ÙˆÙƒ Ù„Ù„Ø²ÙŠÙˆØª Ø§Ù„Ù…Ø¹Ø¯Ù†ÙŠØ©' },
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
        title="Score: ${score} â€” Click for details"
        onclick="showSentimentEvidence('${symbol}')">${displayLabel}</span>`;
}

// â”€â”€ Sentiment Evidence Modal â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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

function qualityTextLabel(status) {
    return t(`quality${String(status || 'unknown').toLowerCase()}`);
}

async function loadIntelligencePulse() {
    const changesEl = document.getElementById('changesTodayBody');
    const qualityEl = document.getElementById('qualityMonitorBody');
    const changesTitle = document.getElementById('changesTodayTitle');
    const changesBadge = document.getElementById('changesTodayBadge');
    const qualityTitle = document.getElementById('qualityMonitorTitle');
    const qualityBadge = document.getElementById('qualityMonitorBadge');

    if (changesTitle) changesTitle.textContent = t('changesTodayTitle');
    if (changesBadge) changesBadge.textContent = t('changesTodayLive');
    if (qualityTitle) qualityTitle.textContent = t('qualityMonitorTitle');
    if (qualityBadge) qualityBadge.textContent = t('qualityMonitorMonitoring');
    if (!changesEl || !qualityEl) return;

    try {
        const [changesRes, qualityRes] = await Promise.all([
            fetch('/api/intelligence/changes'),
            fetch('/api/intelligence/quality')
        ]);
        const changesData = changesRes.ok ? await changesRes.json() : {};
        const qualityData = qualityRes.ok ? await qualityRes.json() : {};

        const signalLines = (changesData.signal_changes || []).slice(0, 4).map(item => {
            const signalText = item.signal_changed
                ? `${item.current_signal} ${t('fromLabel')} ${item.previous_signal || 'â€”'}`
                : `${item.current_signal} | ${t('expectedEdgeLabel')} ${Number(item.current_expected_edge_pct || 0).toFixed(2)}%`;
            const deltaClass = Number(item.edge_delta_pct || 0) >= 0 ? 'change-delta-pos' : 'change-delta-neg';
            return `
                <div class="change-line">
                    <div class="change-line-top">
                        <span class="change-line-symbol">${item.symbol}</span>
                        <span class="quality-pill ${item.signal_changed ? 'quality-pill-watch' : 'quality-pill-fresh'}">${t('signalsLabel')}</span>
                    </div>
                    <div class="change-line-meta">${signalText}</div>
                    <div class="change-line-meta ${deltaClass}">${t('expectedEdgeLabel')}: ${Number(item.current_expected_edge_pct || 0).toFixed(2)}% | Î” ${Number(item.edge_delta_pct || 0).toFixed(2)}%</div>
                </div>
            `;
        });

        const forecastLines = (changesData.forecast_changes || []).slice(0, 2).map(item => {
            const deltaClass = Number(item.delta_expected_return_pct || 0) >= 0 ? 'change-delta-pos' : 'change-delta-neg';
            return `
                <div class="change-line">
                    <div class="change-line-top">
                        <span class="change-line-symbol">${item.symbol}</span>
                        <span class="quality-pill quality-pill-unknown">${t('forecastsLabel')}</span>
                    </div>
                    <div class="change-line-meta">${item.portfolio_name}</div>
                    <div class="change-line-meta ${deltaClass}">${Number(item.current_expected_return_pct || 0).toFixed(2)}% | Î” ${Number(item.delta_expected_return_pct || 0).toFixed(2)}%</div>
                </div>
            `;
        });

        const macroLines = (changesData.macro_changes || []).slice(0, 2).map(item => {
            const deltaClass = Number(item.delta || 0) >= 0 ? 'change-delta-pos' : 'change-delta-neg';
            return `
                <div class="change-line">
                    <div class="change-line-top">
                        <span class="change-line-symbol">${item.label}</span>
                        <span class="quality-pill quality-pill-unknown">${t('macroLabel')}</span>
                    </div>
                    <div class="change-line-meta">${item.previous == null ? `${item.current}` : `${item.current} ${t('fromLabel')} ${item.previous}`}</div>
                    ${item.delta == null ? '' : `<div class="change-line-meta ${deltaClass}">Î” ${Number(item.delta).toFixed(2)}</div>`}
                </div>
            `;
        });

        const allChangeLines = [...signalLines, ...forecastLines, ...macroLines];
        changesEl.innerHTML = allChangeLines.length ? allChangeLines.join('') : `<p class="global-snapshot-empty">${t('noChangesToday')}</p>`;

        const freshness = qualityData.freshness || {};
        const freshnessLines = Object.entries(freshness).slice(0, 4).map(([key, item]) => `
            <div class="quality-line">
                <div class="quality-line-top">
                    <span class="quality-line-label">${key.replace(/_/g, ' ')}</span>
                    <span class="quality-pill quality-pill-${String(item.status || 'unknown').toLowerCase()}">${qualityTextLabel(item.status)}</span>
                </div>
                <div class="quality-line-meta">${t('freshnessLabel')}: ${item.age_hours == null ? 'â€”' : `${item.age_hours.toFixed(1)}h`}</div>
            </div>
        `);

        const driftLines = (qualityData.drift || []).slice(0, 3).map(item => `
            <div class="quality-line">
                <div class="quality-line-top">
                    <span class="quality-line-label">${getAgentDisplayName(item.agent_name)}</span>
                    <span class="quality-pill quality-pill-${String(item.status || 'unknown').toLowerCase()}">${qualityTextLabel(item.status)}</span>
                </div>
                <div class="quality-line-meta">${t('driftLabel')}: ${Number(item.drift_gap || 0).toFixed(1)} pts | 30d ${Number(item.win_rate_30d || 0).toFixed(1)}%</div>
            </div>
        `);

        const allQualityLines = [...freshnessLines, ...driftLines];
        qualityEl.innerHTML = allQualityLines.length ? allQualityLines.join('') : `<p class="global-snapshot-empty">${t('noQualityData')}</p>`;
        if (qualityBadge) {
            qualityBadge.textContent = qualityTextLabel(qualityData.overall_status || 'unknown');
            qualityBadge.className = `intelligence-pulse-badge quality-pill quality-pill-${String(qualityData.overall_status || 'unknown').toLowerCase()}`;
        }
    } catch (error) {
        console.error('Error loading intelligence pulse:', error);
        changesEl.innerHTML = `<p class="global-snapshot-empty">${t('noChangesToday')}</p>`;
        qualityEl.innerHTML = `<p class="global-snapshot-empty">${t('noQualityData')}</p>`;
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
                            <span class="regime-dist-buy">â†‘ ${buyPct}%</span>
                            <span class="regime-dist-sell">â†“ ${sellPct}%</span>
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
            <a href="/track-record#regime" class="regime-link">${t('viewFullAnalysis') || 'Full Analysis â†’'}</a>
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
        initGlobalSearch();
        loadTradingViewTicker();
        loadGlobalSnapshotBar();
        loadIntelligencePulse();
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
            loadIntelligencePulse(),
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
                        <button class="perf-action-btn why-signal-btn" onclick="showWhySignal('${symbol}','${consensusKey}')">ðŸ’¡ Insight</button>
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
// LOAD PERFORMANCE (basic â€” existing endpoint)
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

// â”€â”€â”€ Universal Investor Scoring Panel â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

let _currentScoringMode = 'standard_100';

const SCORING_MODE_LABELS = {
    en: {
        xmore_native: 'Xmore (0â€“1)',
        standard_100: 'Score (0â€“100)',
        letter_grade: 'Grade',
        stars:        'Stars',
        signal_tier:  'Tier',
        conviction:   'Conviction',
    },
    ar: {
        xmore_native: 'Xmore (0â€“1)',
        standard_100: 'Ø¯Ø±Ø¬Ø© (0â€“100)',
        letter_grade: 'ØªÙ‚Ø¯ÙŠØ±',
        stars:        'Ù†Ø¬ÙˆÙ…',
        signal_tier:  'Ù…Ø³ØªÙˆÙ‰',
        conviction:   'Ø§Ù‚ØªÙ†Ø§Ø¹',
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
        const val  = sc[_currentScoringMode] !== undefined ? sc[_currentScoringMode] : 'â€”';
        const disp = _currentScoringMode === 'stars' ? 'â˜…'.repeat(Math.round(val)) + ' ' + val : val;
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
            <td data-label="${colLabels.threshold}" class="scoring-threshold">${sig.meets_threshold ? 'âœ“' : ''}</td>
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
    const calibratedConfidence = Number(item.calibrated_confidence || item.confidence || 0);
    const expectedEdge = Number(item.expected_edge_pct || 0);

    // Risk action badge class
    let riskBadgeClass = 'risk-badge-pass';
    let riskBadgeText = 'âœ“ PASS';
    if (riskAction === 'BLOCK') {
        riskBadgeClass = 'risk-badge-block';
        riskBadgeText = 'ðŸš« BLOCK';
    } else if (riskAction === 'DOWNGRADE') {
        riskBadgeClass = 'risk-badge-downgrade';
        riskBadgeText = 'â¬‡ DOWNGRADE';
    } else if (riskAction === 'FLAG') {
        riskBadgeClass = 'risk-badge-flag';
        riskBadgeText = 'âš ï¸ FLAG';
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
                ${riskAdjusted ? '<span class="risk-adjusted-badge" title="Risk-adjusted">âš ï¸</span>' : ''}
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

            <div class="consensus-edge-row">
                <span class="consensus-edge-chip">${t('expectedEdgeLabel')}: ${expectedEdge.toFixed(2)}%</span>
                <span class="consensus-calibration-text">${t('calibrationLabel')}: ${calibratedConfidence.toFixed(1)}%</span>
            </div>

            <!-- Bull/Bear Bars -->
            <div class="bull-bear-section">
                <div class="bull-bear-row">
                    <span class="bb-label">ðŸ‚ ${t('bullCase')}</span>
                    <div class="bb-bar-container">
                        <div class="bb-bar bb-bull" style="width: ${bullScore}%"></div>
                    </div>
                    <span class="bb-score">${bullScore}</span>
                </div>
                <div class="bull-bear-row">
                    <span class="bb-label">ðŸ» ${t('bearCase')}</span>
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

// â”€â”€ Why This Signal? Modal â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

async function showWhySignal(symbol, signal) {
    const modal   = document.getElementById('whySignalModal');
    const title   = document.getElementById('whyModalTitle');
    const loading = document.getElementById('whyModalLoading');
    const content = document.getElementById('whyModalContent');
    const expl    = document.getElementById('whyModalExplanation');
    const srcs    = document.getElementById('whyModalSources');

    if (!modal) return;

    // Reset and show modal
    title.textContent = `ðŸ’¡ Insight â€” ${symbol}`;
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
                    const subline = meta.date ? ` Â· ${meta.date}` : '';
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

// â”€â”€ ETF Fund Intelligence Dashboard â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

let etfLoaded = false;
let _etfAllInstruments = [];
let _etfCurrentSub = 'etfs';
let _etfCurrentView = 'grid';

// ETP instrument types
const _ETP_TYPES = new Set(['GOLD_ETP','INDEX_TRACKER','STRUCTURED_NOTE','ETN','UNKNOWN_ETP','ETP','COMMODITY_ETP']);

function _fmtPct(val) {
    if (val == null) return 'â€”';
    const n = parseFloat(val);
    if (isNaN(n)) return 'â€”';
    return (n >= 0 ? '+' : '') + n.toFixed(2) + '%';
}
function _fmtNum(val, decimals = 2) {
    if (val == null) return 'â€”';
    const n = parseFloat(val);
    if (isNaN(n)) return 'â€”';
    return n.toFixed(decimals);
}
function _pdLabel(val) {
    if (val == null) return 'â€”';
    const n = parseFloat(val);
    if (isNaN(n)) return 'â€”';
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
        const egyptPct = i.weight_pct != null ? parseFloat(i.weight_pct).toFixed(1) + '%' : 'â€”';
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
        const underlying = i.underlying_index || 'â€”';
        const issuer = i.issuer || 'â€”';
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
            const egyptPct = i.weight_pct != null ? parseFloat(i.weight_pct).toFixed(1) + '%' : 'â€”';
            return `<tr onclick="showEtfHoldings('${i.symbol}')" style="cursor:pointer">
                ${cell(headers[0], `<strong>${i.symbol}</strong>`)}
                ${cell(headers[1], `<span style="max-width:180px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:inline-block;" title="${i.name||''}">${i.name||'â€”'}</span>`)}
                ${cell(headers[2], i.exchange||'â€”', 'cell-muted')}
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
                ${cell(headers[1], `<span style="max-width:200px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:inline-block;" title="${i.name||''}">${i.name||'â€”'}</span>`)}
                ${cell(headers[2], i.issuer||'â€”', 'cell-muted')}
                ${cell(headers[3], i.underlying_index||'â€”', 'cell-muted')}
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
                ${cell(headers[1], `<span style="max-width:200px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:inline-block;" title="${i.name||''}">${i.name||'â€”'}</span>`)}
                ${cell(headers[2], i.exchange||'â€”', 'cell-muted')}
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
    if (title)   title.textContent = `${symbol} â€” ${t('etfHoldingsTitle')}`;
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
        if (meta) meta.textContent = `As of ${snap.snapshot_date} Â· Source: ${snap.source} Â· ${snap.currency || ''} Â· Total weight: ${snap.total_weight != null ? parseFloat(snap.total_weight).toFixed(1) + '%' : 'â€”'}`;
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
                    <td data-label="${labels.holding}">${l.holding_name || l.holding_symbol || 'â€”'}</td>
                    <td data-label="${labels.isin}" style="font-size:11px;color:var(--text-muted);">${l.holding_isin || ''}</td>
                    <td data-label="${labels.country}">${l.country || 'â€”'}</td>
                    <td data-label="${labels.sector}">${l.sector || 'â€”'}</td>
                    <td data-label="${labels.weight}"><strong>${l.weight_pct != null ? parseFloat(l.weight_pct).toFixed(2) + '%' : 'â€”'}</strong></td>
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
// PORTFOLIO â€” enhanced with EGP P&L + sector breakdown
// ============================================================

function renderPortfolioTotals(totals) {
    const strip = document.getElementById('portfolioTotals');
    if (!strip || !totals) return;
    const fmt = n => n != null ? Number(n).toLocaleString('en-EG', { minimumFractionDigits: 0, maximumFractionDigits: 0 }) : 'â€”';
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
            const condLabel = a.condition === 'above' ? (isAr ? 'Ø£Ø¹Ù„Ù‰ Ù…Ù†' : 'Above') : (isAr ? 'Ø£Ù‚Ù„ Ù…Ù†' : 'Below');
            const cur = parseFloat(a.current_price);
            const diff = cur && a.target_price ? ((cur - a.target_price) / a.target_price * 100).toFixed(1) : null;
            return `<div class="alert-row ${triggered ? 'alert-triggered' : ''}">
                <span class="alert-sym">${a.symbol}</span>
                <span class="alert-cond">${condLabel}</span>
                <span class="alert-price">${parseFloat(a.target_price).toFixed(2)}</span>
                ${cur ? `<span class="alert-cur" style="color:var(--text-muted)">Now: ${cur.toFixed(2)}${diff ? ` (${diff > 0 ? '+' : ''}${diff}%)` : ''}</span>` : ''}
                ${triggered ? `<span class="alert-tag-triggered">${isAr ? 'Ù†ÙØ´ÙÙ‘Ø·' : 'Triggered'}</span>` : ''}
                <button class="alert-del-btn" onclick="deleteAlert(${a.id})">âœ•</button>
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
            if (!sig) return '<span style="color:var(--text-muted)">â€”</span>';
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
            ${rowCell(t('compScore'), rows.map(r => r.c.xmore_score != null ? Math.round(r.c.xmore_score) : 'â€”'))}
            ${rowCell(t('compConviction'), rows.map(r => r.c.conviction || 'â€”'))}
            ${rowCell(t('compConfidence'), rows.map(r => r.c.confidence != null ? r.c.confidence + '%' : 'â€”'))}
            ${rowCell(t('compAgentsAgree'), rows.map(r => r.c.agents_agreeing != null ? r.c.agents_agreeing + '/' + r.c.agents_total : 'â€”'))}
            ${rowCell(t('compBullScore'), rows.map(r => `<span style="color:var(--bullish)">${r.c.bull_score != null ? r.c.bull_score : 'â€”'}</span>`))}
            ${rowCell(t('compBearScore'), rows.map(r => `<span style="color:var(--bearish)">${r.c.bear_score != null ? r.c.bear_score : 'â€”'}</span>`))}
            ${rowCell(t('compPrice'), rows.map(r => r.p.close != null ? parseFloat(r.p.close).toFixed(2) : 'â€”'))}
            ${rowCell(t('compDayChange'), rows.map(r => `<span style="color:${r.chg > 0 ? 'var(--bullish)' : r.chg < 0 ? 'var(--bearish)' : 'inherit'}">${r.chg != null ? (r.chg > 0 ? '+' : '') + r.chg + '%' : 'â€”'}</span>`))}
            ${rowCell(t('compVolume'), rows.map(r => r.p.volume != null ? Number(r.p.volume).toLocaleString() : 'â€”'))}
            ${rowCell(t('compBrief'), rows.map(r => `<button class="pf-btn-view" onclick="loadStockBrief('${r.sym}')">${t('compBrief')} â†’</button>`))}
            </tbody>
        </table>
        </div>
        `;
    } catch (err) {
        resultsEl.innerHTML = `<p style="color:var(--bearish)">${err.message}</p>`;
    }
}

// ============================================================
// PER-STOCK Market Brief
// ============================================================

async function loadStockBrief(symbol) {
    const modal = document.getElementById('briefModal');
    const bodyEl = document.getElementById('briefModalBody');
    const titleEl = document.getElementById('briefModalSymbol');
    if (!modal) return;
    titleEl.textContent = symbol + ' â€” Market Brief';
    bodyEl.innerHTML = '<p class="loading">Loading brief...</p>';
    modal.style.display = 'flex';
    try {
        const r = await fetch(`/api/stocks/${encodeURIComponent(symbol)}/brief`, { credentials: 'include' });
        const data = await r.json();
        if (!r.ok) throw new Error(data.error || 'Error');
        bodyEl.textContent = data.brief;
    } catch (err) {
        bodyEl.textContent = 'Could not load brief: ' + err.message;
    }
}

function closeBriefModal() {
    const m = document.getElementById('briefModal');
    if (m) m.style.display = 'none';
}

// ============================================================
// RATES TAB â€” FX & Gold with history charts
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
            { label: 'USD / EGP', value: live.USD_EGP, key: 'usd_egp', icon: 'ðŸ’µ' },
            { label: 'Gold 24K / gram', value: live.GOLD_24K_EGP_G, key: 'gold_24k_egp_g', icon: 'ðŸ¥‡', suffix: 'EGP' },
            { label: 'Gold 21K / gram', value: live.GOLD_21K_EGP_G, key: 'gold_21k_egp_g', icon: 'ðŸ…', suffix: 'EGP' },
            { label: 'Gold Pound', value: live.GOLD_POUND_EGP, key: 'gold_pound_egp', icon: 'ðŸ’°', suffix: 'EGP' },
            { label: 'Gold 18K / gram', value: live.GOLD_18K_EGP_G, key: null, icon: 'ðŸ”¶', suffix: 'EGP' },
            { label: 'USD / SAR', value: live.USD_SAR, key: null, icon: 'ðŸ‡¸ðŸ‡¦' },
            { label: 'SAR / EGP', value: live.SAR_EGP, key: null, icon: 'â†”ï¸' },
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
            el.innerHTML = `<p style="color:var(--text-muted)">No D+${horizon} data yet â€” runs after 10+ trading days of consensus signals.</p>`;
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



