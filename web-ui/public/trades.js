/**
 * Xmore â€” Trades & Portfolio Module
 * Handles Today's Recommendations and User Portfolio display.
 */

// ============================================
// STATE
// ============================================
let todayTrades = [];
let portfolioData = {};
let tradesPerformance = {};

// ============================================
// BILINGUAL TEXT
// ============================================
const tradesText = {
    en: {
        // Today's Trades
        tt_title: "Today's Recommendations",
        tt_subtitle: "Trade signals for today's market session.",
        tt_buy: "BUY",
        tt_sell: "SELL",
        tt_hold: "HOLD",
        tt_watch: "WATCH",
        tt_entry: "Entry Zone",
        tt_target: "Target",
        tt_stop: "Stop Loss",
        tt_risk_reward: "R/R Ratio",
        tt_conviction: "Conviction",
        tt_reasoning: "Analysis",
        tt_execute: "Trade",
        tt_no_trades: "No trade recommendations generated for today yet.",
        tt_login_required: "Login to view personalized trade recommendations.",
        tt_login_btn: "Login",
        tt_retry: "Retry",
        tt_conviction_very_high: "Very High",
        tt_conviction_high: "High",
        tt_conviction_moderate: "Moderate",
        tt_conviction_low: "Low",
        tt_conviction_blocked: "Blocked",
        tt_sector: "Sector",

        // Portfolio
        pt_title: "My Portfolio",
        pt_open: "Open Positions",
        pt_history: "Trade History",
        pt_stats: "Performance Stats",
        pt_symbol: "Symbol",
        pt_entry_date: "Entry Date",
        pt_entry_price: "Entry Price",
        pt_current_price: "Current Price",
        pt_pnl: "P&L %",
        pt_days_held: "Days Held",
        pt_exit_date: "Exit Date",
        pt_exit_price: "Exit Price",
        pt_return: "Return %",
        pt_win_rate: "Win Rate",
        pt_avg_return: "Avg Return",
        pt_total_trades: "Total Trades",
        pt_no_open: "No open positions currently.",
        pt_no_history: "No trade history available.",

        // General
        loading: "Loading data...",
        error: "Error loading data",
    },
    ar: {
        // Today's Trades
        tt_title: "ØªÙˆØµÙŠØ§Øª Ø§Ù„ÙŠÙˆÙ…",
        tt_subtitle: "Ø¥Ø´Ø§Ø±Ø§Øª ØªØ¯Ø§ÙˆÙ„ Ù…ÙˆÙ„Ø¯Ø© Ø¨Ø§Ù„Ø°ÙƒØ§Ø¡ Ø§Ù„Ø§ØµØ·Ù†Ø§Ø¹ÙŠ Ù„Ø¬Ù„Ø³Ø© Ø§Ù„ÙŠÙˆÙ….",
        tt_buy: "Ø´Ø±Ø§Ø¡",
        tt_sell: "Ø¨ÙŠØ¹",
        tt_hold: "Ø§Ø­ØªÙØ§Ø¸",
        tt_watch: "Ù…Ø±Ø§Ù‚Ø¨Ø©",
        tt_entry: "Ù…Ù†Ø·Ù‚Ø© Ø§Ù„Ø¯Ø®ÙˆÙ„",
        tt_target: "Ø§Ù„Ù‡Ø¯Ù",
        tt_stop: "ÙˆÙ‚Ù Ø§Ù„Ø®Ø³Ø§Ø±Ø©",
        tt_risk_reward: "Ø§Ù„Ø¹Ø§Ø¦Ø¯/Ø§Ù„Ù…Ø®Ø§Ø·Ø±Ø©",
        tt_conviction: "Ø§Ù„Ù‚Ù†Ø§Ø¹Ø©",
        tt_reasoning: "Ø§Ù„ØªØ­Ù„ÙŠÙ„",
        tt_execute: "ØªØ¯Ø§ÙˆÙ„",
        tt_no_trades: "Ù„Ù… ÙŠØªÙ… Ø¥Ù†Ø´Ø§Ø¡ ØªÙˆØµÙŠØ§Øª Ù„Ù‡Ø°Ø§ Ø§Ù„ÙŠÙˆÙ… Ø¨Ø¹Ø¯.",
        tt_login_required: "Ø³Ø¬Ù‘Ù„ Ø¯Ø®ÙˆÙ„Ùƒ Ù„Ø¹Ø±Ø¶ Ø§Ù„ØªÙˆØµÙŠØ§Øª Ø§Ù„Ù…Ø®ØµØµØ©.",
        tt_login_btn: "ØªØ³Ø¬ÙŠÙ„ Ø§Ù„Ø¯Ø®ÙˆÙ„",
        tt_retry: "Ø¥Ø¹Ø§Ø¯Ø© Ø§Ù„Ù…Ø­Ø§ÙˆÙ„Ø©",
        tt_conviction_very_high: "Ø¹Ø§Ù„ÙŠØ© Ø¬Ø¯Ø§Ù‹",
        tt_conviction_high: "Ø¹Ø§Ù„ÙŠØ©",
        tt_conviction_moderate: "Ù…ØªÙˆØ³Ø·Ø©",
        tt_conviction_low: "Ù…Ù†Ø®ÙØ¶Ø©",
        tt_conviction_blocked: "Ù…Ø­Ø¸ÙˆØ±",
        tt_sector: "Ø§Ù„Ù‚Ø·Ø§Ø¹",

        // Portfolio
        pt_title: "Ù…Ø­ÙØ¸ØªÙŠ",
        pt_open: "Ø§Ù„Ù…Ø±Ø§ÙƒØ² Ø§Ù„Ù…ÙØªÙˆØ­Ø©",
        pt_history: "Ø³Ø¬Ù„ Ø§Ù„ØªØ¯Ø§ÙˆÙ„",
        pt_stats: "Ø¥Ø­ØµØ§Ø¦ÙŠØ§Øª Ø§Ù„Ø£Ø¯Ø§Ø¡",
        pt_symbol: "Ø§Ù„Ø±Ù…Ø²",
        pt_entry_date: "ØªØ§Ø±ÙŠØ® Ø§Ù„Ø¯Ø®ÙˆÙ„",
        pt_entry_price: "Ø³Ø¹Ø± Ø§Ù„Ø¯Ø®ÙˆÙ„",
        pt_current_price: "Ø§Ù„Ø³Ø¹Ø± Ø§Ù„Ø­Ø§Ù„ÙŠ",
        pt_pnl: "Ø§Ù„Ø±Ø¨Ø­/Ø§Ù„Ø®Ø³Ø§Ø±Ø© %",
        pt_days_held: "Ø£ÙŠØ§Ù… Ø§Ù„Ø§Ø­ØªÙØ§Ø¸",
        pt_exit_date: "ØªØ§Ø±ÙŠØ® Ø§Ù„Ø®Ø±ÙˆØ¬",
        pt_exit_price: "Ø³Ø¹Ø± Ø§Ù„Ø®Ø±ÙˆØ¬",
        pt_return: "Ø§Ù„Ø¹Ø§Ø¦Ø¯ %",
        pt_win_rate: "Ù†Ø³Ø¨Ø© Ø§Ù„Ù†Ø¬Ø§Ø­",
        pt_avg_return: "Ù…ØªÙˆØ³Ø· Ø§Ù„Ø¹Ø§Ø¦Ø¯",
        pt_total_trades: "Ø¥Ø¬Ù…Ø§Ù„ÙŠ Ø§Ù„ØµÙÙ‚Ø§Øª",
        pt_no_open: "Ù„Ø§ ØªÙˆØ¬Ø¯ Ù…Ø±Ø§ÙƒØ² Ù…ÙØªÙˆØ­Ø© Ø­Ø§Ù„ÙŠØ§Ù‹.",
        pt_no_history: "Ù„Ø§ ÙŠÙˆØ¬Ø¯ Ø³Ø¬Ù„ ØªØ¯Ø§ÙˆÙ„ Ù…ØªØ§Ø­.",

        // General
        loading: "Ø¬Ø§Ø±ÙŠ Ø§Ù„ØªØ­Ù…ÙŠÙ„...",
        error: "Ø®Ø·Ø£ ÙÙŠ ØªØ­Ù…ÙŠÙ„ Ø§Ù„Ø¨ÙŠØ§Ù†Ø§Øª",
    }
};

function tt(key) {
    const lang = (typeof currentLang !== 'undefined') ? currentLang : 'en';
    return (tradesText[lang] && tradesText[lang][key]) || tradesText.en[key] || key;
}

function isArabic() {
    return (typeof currentLang !== 'undefined') && currentLang === 'ar';
}

// escapeHtml() is defined globally in app.js

function translateConviction(conviction) {
    if (!conviction) return 'N/A';
    const map = {
        'VERY_HIGH': 'tt_conviction_very_high',
        'VERY HIGH': 'tt_conviction_very_high',
        'HIGH': 'tt_conviction_high',
        'MODERATE': 'tt_conviction_moderate',
        'LOW': 'tt_conviction_low',
        'BLOCKED': 'tt_conviction_blocked',
    };
    const key = map[conviction.toUpperCase()];
    return key ? tt(key) : conviction;
}

// ============================================
// API CALLS
// ============================================

async function listTodayTrades() {
    // Also attach to window for app.js to call
    const container = document.getElementById('todayTradesContainer');
    if (!container) return; // Tab might not exist yet if not in DOM

    if (typeof currentUser === 'undefined' || !currentUser) {
        container.innerHTML = `<div class="login-wall">
            <p>${tt('tt_login_required')}</p>
            <button onclick="showAuthModal('login')" class="auth-trigger-btn">ðŸ” ${tt('tt_login_btn')}</button>
        </div>`;
        return;
    }

    // Show shimmer skeleton while loading (Upgrade 4)
    if (typeof showSkeleton === 'function') {
        showSkeleton('todayTradesContainer', 'trades');
    } else {
        container.innerHTML = `<div class="trades-grid"><div class="trade-card"><p class="loading">${tt('loading')}</p></div></div>`;
    }

    try {
        const res = await fetch('/api/trades/today', { credentials: 'include' });
        // Parse error response if not OK
        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.details || errData.error || tt('error'));
        }
        const data = await res.json();

        todayTrades = data.recommendations || [];
        renderTodayTrades();

        // Update summary stats if elements exist
        if (data.summary) {
            updateTradeSummary(data.summary);
        }
    } catch (err) {
        console.error('Error loading today trades:', err);
        renderError(container, err.message);
        if (typeof showToast === 'function') showToast('error', err.message);
    }
}

async function getPortfolio() {
    const openContainer = document.getElementById('portfolioOpen');
    const closedContainer = document.getElementById('portfolioHistory');

    if (!openContainer || !closedContainer) return;

    if (typeof currentUser === 'undefined' || !currentUser) {
        openContainer.innerHTML = `<p class="login-wall">${tt('tt_login_required')}</p>`;
        closedContainer.innerHTML = '';
        return;
    }

    // Show shimmer skeleton while loading (Upgrade 4)
    if (typeof showSkeleton === 'function') {
        showSkeleton('portfolioOpen', 'trades');
        showSkeleton('portfolioHistory', 'trades');
    } else {
        openContainer.innerHTML = `<p class="loading">${tt('loading')}</p>`;
        closedContainer.innerHTML = `<p class="loading">${tt('loading')}</p>`;
    }

    try {
        const res = await fetch('/api/trades/portfolio', { credentials: 'include' });
        if (!res.ok) throw new Error(tt('error'));
        const data = await res.json();

        portfolioData = data;
        renderPortfolio();
    } catch (err) {
        console.error('Error loading portfolio:', err);
        renderError(openContainer, err.message);
        if (typeof showToast === 'function') showToast('error', err.message);
    }
}

// ============================================
// RENDER LOGIC
// ============================================

function renderTodayTrades() {
    const container = document.getElementById('todayTradesContainer');
    if (!container) return;

    if (todayTrades.length === 0) {
        // Empty state illustration (Upgrade 6)
        if (typeof renderEmptyState === 'function') {
            renderEmptyState('todayTradesContainer', 'ðŸ“‹', 'emptyTrades', 'emptyTradesDesc', null, null);
        } else {
            container.innerHTML = `<p class="no-data">${tt('tt_no_trades')}</p>`;
        }
        return;
    }

    container.innerHTML = `<div class="trades-grid">
        ${todayTrades.map(trade => createTradeCard(trade)).join('')}
    </div>`;
}

function createTradeCard(trade) {
    const isAr = isArabic();
    const actionClass = `action-${trade.action.toLowerCase()}`; // buy, sell, watch

    const name = isAr ? (trade.name_ar || trade.name_en) : trade.name_en;
    const sector = isAr ? (trade.sector_ar || trade.sector_en || '') : (trade.sector_en || '');

    const reasonsList = Array.isArray(trade.reasons)
        ? trade.reasons.map(r => `<li>â€¢ ${escapeHtml(r)}</li>`).join('')
        : '';

    return `
    <div class="trade-card ${actionClass}-border">
        <div class="trade-header">
            <div class="trade-symbol">
                <h3>${escapeHtml(trade.symbol)}</h3>
                <span class="company-name">${escapeHtml(name)}</span>
                ${sector ? `<span class="wl-card-sector">${escapeHtml(sector)}</span>` : ''}
            </div>
            <div class="trade-action ${actionClass}">
                ${tt('tt_' + trade.action.toLowerCase())}
            </div>
        </div>
        
        <div class="trade-prices">
            <div class="price-item">
                <label>${tt('tt_entry')}</label>
                <span class="val">${trade.close_price.toFixed(2)}</span>
            </div>
            <div class="price-item target">
                <label>${tt('tt_target')}</label>
                <span class="val">${trade.target_price ? trade.target_price.toFixed(2) : '-'}</span>
                ${trade.target_pct ? `<small>(+${trade.target_pct}%)</small>` : ''}
            </div>
            <div class="price-item stop">
                <label>${tt('tt_stop')}</label>
                <span class="val">${trade.stop_loss_price ? trade.stop_loss_price.toFixed(2) : '-'}</span>
                ${trade.stop_loss_pct ? `<small>(${trade.stop_loss_pct}%)</small>` : ''}
            </div>
        </div>
        
        <div class="trade-meta">
            <span class="meta-tag conviction-${trade.conviction ? trade.conviction.toLowerCase() : 'low'}">
                ${translateConviction(trade.conviction)}
            </span>
            <span class="meta-tag">${tt('tt_risk_reward')}: ${trade.risk_reward_ratio || '-'}</span>
        </div>
        
        <div class="trade-reasoning">
            <h4>${tt('tt_reasoning')}</h4>
            <ul>${reasonsList}</ul>
        </div>
    </div>
    `;
}

function updateTradeSummary(summary) {
    // If we have summary stats elements in index.html, update them
    // E.g. <span id="summaryBuy">...</span>
    // This is optional if we add those elements
}

function renderError(container, message) {
    if (!container) return;
    const title = (typeof tt === 'function') ? tt('error') : 'Error';
    container.innerHTML = `
        <div class="error-message">
            <strong>${escapeHtml(title)}</strong><br>
            <small>${escapeHtml(message)}</small><br>
            <button onclick="window.loadTrades()" class="refresh-btn retry-btn">${tt('tt_retry')}</button>
        </div>
    `;
}

function renderPortfolio() {
    const openContainer = document.getElementById('portfolioOpen');
    const closedContainer = document.getElementById('portfolioHistory');
    const statsContainer = document.getElementById('portfolioStats');

    // Empty state when no portfolio data at all (Upgrade 6)
    const hasOpen = portfolioData.open_positions && portfolioData.open_positions.length > 0;
    const hasClosed = portfolioData.closed_positions && portfolioData.closed_positions.length > 0;
    if (!portfolioData.stats && !hasOpen && !hasClosed) {
        if (typeof renderEmptyState === 'function' && openContainer) {
            renderEmptyState('portfolioOpen', 'ðŸ’¼', 'emptyPortfolio', 'emptyPortfolioDesc', 'viewTrades', "switchToTab('trades')");
            if (closedContainer) closedContainer.innerHTML = '';
            if (statsContainer) statsContainer.innerHTML = '';
        }
        return;
    }

    // 1. Stats
    if (statsContainer && portfolioData.stats) {
        const s = portfolioData.stats;
        statsContainer.innerHTML = `
            <div class="stat-box">
                <div class="val">${s.total_trades}</div>
                <div class="lbl">${tt('pt_total_trades')}</div>
            </div>
            <div class="stat-box">
                <div class="val ${s.avg_return >= 0 ? 'pos' : 'neg'}">${s.avg_return}%</div>
                <div class="lbl">${tt('pt_avg_return')}</div>
            </div>
            <div class="stat-box">
                <div class="val">${s.win_rate}%</div>
                <div class="lbl">${tt('pt_win_rate')}</div>
            </div>
        `;
    }

    // 1b. EGP Totals + Sector Breakdown (new)
    if (typeof renderPortfolioTotals === 'function') renderPortfolioTotals(portfolioData.totals);
    if (typeof renderSectorBreakdown === 'function') renderSectorBreakdown(portfolioData.sector_breakdown);

    // 2. Open Positions
    if (openContainer) {
        const open = portfolioData.open_positions;
        if (!open || open.length === 0) {
            openContainer.innerHTML = `<p class="no-data">${tt('pt_no_open')}</p>`;
        } else {
            openContainer.innerHTML = `
             <table class="portfolio-table">
                <thead>
                    <tr>
                        <th>${tt('pt_symbol')}</th>
                        <th>${tt('pt_entry_date')}</th>
                        <th>${tt('pt_entry_price')}</th>
                        <th>Qty</th>
                        <th>${tt('pt_current_price')}</th>
                        <th>Cost (EGP)</th>
                        <th>Value (EGP)</th>
                        <th>P&amp;L (EGP)</th>
                        <th>${tt('pt_pnl')}</th>
                    </tr>
                </thead>
                <tbody>
                    ${open.map(p => {
                        const name = isArabic() ? (p.name_ar || p.name_en) : p.name_en;
                        const qty = p.quantity || 1;
                        const costEgp = p.cost_egp != null ? p.cost_egp.toFixed(0) : '-';
                        const valueEgp = p.value_egp != null ? p.value_egp.toFixed(0) : '-';
                        const pnlEgp = p.pnl_egp != null ? p.pnl_egp.toFixed(0) : '-';
                        const pnlClass = (p.pnl_egp || 0) >= 0 ? 'pos' : 'neg';
                        return `
                        <tr>
                            <td><strong>${escapeHtml(p.symbol)}</strong>${name ? `<br><small class="company-name">${escapeHtml(name)}</small>` : ''}</td>
                            <td>${formatDateSimple(p.entry_date)}</td>
                            <td>${p.entry_price.toFixed(2)}</td>
                            <td>${qty}</td>
                            <td>${p.current_price ? p.current_price.toFixed(2) : '-'}</td>
                            <td>${costEgp}</td>
                            <td>${valueEgp}</td>
                            <td class="${pnlClass}">${pnlEgp}</td>
                            <td class="${p.unrealized_return_pct >= 0 ? 'pos' : 'neg'}">
                                ${p.unrealized_return_pct}%
                            </td>
                        </tr>`;
                    }).join('')}
                </tbody>
             </table>`;
        }
    }

    // 3. Closed Positions
    if (closedContainer) {
        const closed = portfolioData.closed_positions;
        if (!closed || closed.length === 0) {
            closedContainer.innerHTML = `<p class="no-data">${tt('pt_no_history')}</p>`;
        } else {
            closedContainer.innerHTML = `
             <table class="portfolio-table">
                <thead>
                    <tr>
                        <th>${tt('pt_symbol')}</th>
                        <th>${tt('pt_entry_date')}</th>
                        <th>${tt('pt_exit_date')}</th>
                        <th>${tt('pt_return')}</th>
                    </tr>
                </thead>
                <tbody>
                     ${closed.map(p => {
                        const name = isArabic() ? (p.name_ar || p.name_en) : p.name_en;
                        return `
                        <tr>
                            <td><strong>${escapeHtml(p.symbol)}</strong>${name ? `<br><small class="company-name">${escapeHtml(name)}</small>` : ''}</td>
                            <td>${formatDateSimple(p.entry_date)}</td>
                            <td>${formatDateSimple(p.exit_date)}</td>
                            <td class="${p.return_pct >= 0 ? 'pos' : 'neg'}">
                                ${p.return_pct.toFixed(2)}%
                            </td>
                        </tr>`;
                    }).join('')}
                </tbody>
             </table>`;
        }
    }
}

function formatDateSimple(dateStr) {
    if (!dateStr) return '-';
    return dateStr.split('T')[0];
}

// ============================================
// GLOBAL EXPORTS
// ============================================
window.updateTradesLanguage = function () {
    renderTodayTrades();
    renderPortfolio();

    // Update static text if any IDs exist
    const titles = {
        'tradesTitle': 'tt_title',
        'tradesSubtitle': 'tt_subtitle',
        'portfolioTitle': 'pt_title',
        'portfolioOpenTitle': 'pt_open',
        'portfolioHistoryTitle': 'pt_history',
        'portfolioStatsTitle': 'pt_stats'
    };

    Object.keys(titles).forEach(id => {
        const el = document.getElementById(id);
        if (el) el.textContent = tt(titles[id]);
    });
};

window.loadTrades = function () {
    listTodayTrades();
};

window.loadPortfolio = function () {
    getPortfolio();
};

// Auto-init specific listeners if needed

