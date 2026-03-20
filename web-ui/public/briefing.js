/**
 * Xmore — Daily Market Briefing Module
 * Renders a consolidated morning briefing with 7 sections.
 */

// ============================================
// STATE
// ============================================
let briefingData = null;

// ============================================
// BILINGUAL TEXT
// ============================================
const briefingText = {
    en: {
        br_title: "Daily Market Briefing",
        br_subtitle: "Market overview and personalized action items.",

        // Market Pulse
        br_pulse: "Market Pulse",
        br_direction: "Direction",
        br_bullish: "Bullish",
        br_bearish: "Bearish",
        br_mixed: "Mixed",
        br_breadth: "Breadth",
        br_advancing: "Advancing",
        br_declining: "Declining",
        br_unchanged: "Unchanged",
        br_volume: "Volume",
        br_vs_avg: "vs prev day",
        br_confidence: "Avg Confidence",
        br_top_gainers: "Top Gainers",
        br_top_losers: "Top Losers",

        // Actions Today
        br_actions: "Your Actions Today",
        br_actions_sub: "Urgent BUY/SELL signals for your watchlist.",
        br_no_actions: "No urgent actions today — your positions are steady.",
        br_login_actions: "Login to see personalized trade actions.",
        br_login_btn: "Login",
        br_buy: "BUY",
        br_sell: "SELL",

        // Portfolio Snapshot
        br_portfolio: "Portfolio Snapshot",
        br_open_positions: "Open Positions",
        br_unrealized: "Unrealized P&L",
        br_best: "Best",
        br_worst: "Worst",
        br_no_portfolio: "No open positions.",
        br_symbol: "Symbol",
        br_entry: "Entry",
        br_current: "Current",
        br_pnl: "P&L",
        br_days: "Days",

        // Watchlist Heatmap
        br_heatmap: "Watchlist Signal Map",
        br_heatmap_sub: "Your followed stocks ranked by signal strength.",
        br_signal_strength: "Strength",
        br_no_heatmap: "Follow stocks from the Watchlist tab to see their signals here.",

        // Sector Breakdown
        br_sectors: "Sector Overview",
        br_sector: "Sector",
        br_signals: "Signals",

        // Risk Alerts
        br_risk: "Risk Alerts",
        br_no_risk: "No risk alerts today — all signals passed risk checks.",
        br_flagged: "Flagged",
        br_downgraded: "Downgraded",
        br_blocked: "Blocked",

        // Sentiment
        br_sentiment: "Sentiment Snapshot",
        br_overall: "Overall",
        br_positive: "Positive",
        br_negative: "Negative",
        br_neutral: "Neutral",
        br_articles: "articles",
        br_notable: "Notable Stocks",

        // General
        br_loading: "Loading briefing...",
        br_error: "Error loading briefing",
        br_retry: "Retry",
        br_no_briefing: "No briefing available yet. The briefing is generated daily after market analysis.",
        br_stale: "Data from",
    },
    ar: {
        br_title: "نشرة السوق اليومية",
        br_subtitle: "نظرة عامة على السوق مولدة بالذكاء الاصطناعي.",

        // Market Pulse
        br_pulse: "نبض السوق",
        br_direction: "الاتجاه",
        br_bullish: "صاعد",
        br_bearish: "هابط",
        br_mixed: "مختلط",
        br_breadth: "نطاق السوق",
        br_advancing: "صاعدة",
        br_declining: "هابطة",
        br_unchanged: "مستقرة",
        br_volume: "الحجم",
        br_vs_avg: "مقارنة بالأمس",
        br_confidence: "متوسط الثقة",
        br_top_gainers: "الأكثر صعوداً",
        br_top_losers: "الأكثر هبوطاً",

        // Actions Today
        br_actions: "إجراءاتك اليوم",
        br_actions_sub: "إشارات شراء/بيع عاجلة لأسهمك المتابعة.",
        br_no_actions: "لا توجد إجراءات عاجلة اليوم — مراكزك مستقرة.",
        br_login_actions: "سجّل دخولك لعرض التوصيات المخصصة.",
        br_login_btn: "تسجيل الدخول",
        br_buy: "شراء",
        br_sell: "بيع",

        // Portfolio Snapshot
        br_portfolio: "لمحة المحفظة",
        br_open_positions: "المراكز المفتوحة",
        br_unrealized: "الربح/الخسارة غير المحققة",
        br_best: "الأفضل",
        br_worst: "الأسوأ",
        br_no_portfolio: "لا توجد مراكز مفتوحة.",
        br_symbol: "الرمز",
        br_entry: "الدخول",
        br_current: "الحالي",
        br_pnl: "الربح",
        br_days: "أيام",

        // Watchlist Heatmap
        br_heatmap: "خريطة إشارات المتابعة",
        br_heatmap_sub: "أسهمك المتابعة مرتبة حسب قوة الإشارة.",
        br_signal_strength: "القوة",
        br_no_heatmap: "تابع أسهمك من تبويب المتابعة لعرض إشاراتها هنا.",

        // Sector Breakdown
        br_sectors: "نظرة القطاعات",
        br_sector: "القطاع",
        br_signals: "الإشارات",

        // Risk Alerts
        br_risk: "تنبيهات المخاطر",
        br_no_risk: "لا توجد تنبيهات مخاطر اليوم — جميع الإشارات اجتازت فحص المخاطر.",
        br_flagged: "مُعلَّم",
        br_downgraded: "مُخفَّض",
        br_blocked: "محظور",

        // Sentiment
        br_sentiment: "لمحة المعنويات",
        br_overall: "الإجمالي",
        br_positive: "إيجابي",
        br_negative: "سلبي",
        br_neutral: "محايد",
        br_articles: "مقالات",
        br_notable: "أسهم بارزة",

        // General
        br_loading: "جاري تحميل النشرة...",
        br_error: "خطأ في تحميل النشرة",
        br_retry: "إعادة المحاولة",
        br_no_briefing: "لا تتوفر نشرة بعد. يتم إنشاء النشرة يومياً بعد تحليل السوق.",
        br_stale: "بيانات من",
    }
};

function bt(key) {
    const lang = (typeof currentLang !== 'undefined') ? currentLang : 'en';
    return (briefingText[lang] && briefingText[lang][key]) || briefingText.en[key] || key;
}

function brIsArabic() {
    return (typeof currentLang !== 'undefined') && currentLang === 'ar';
}

function brIsLoggedIn() {
    return typeof currentUser !== 'undefined' && currentUser;
}

// ============================================
// API CALL
// ============================================

async function loadBriefing() {
    const container = document.getElementById('briefingContainer');
    if (!container) return;

    // Show shimmer skeleton while loading (Upgrade 4)
    if (typeof showSkeleton === 'function') {
        showSkeleton('briefingContainer', 'briefing');
    } else {
        container.innerHTML = `<p class="loading">${bt('br_loading')}</p>`;
    }

    try {
        const res = await fetch('/api/briefing/today', { credentials: 'include' });
        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.details || errData.error || bt('br_error'));
        }
        const data = await res.json();

        if (typeof clearSkeleton === 'function') clearSkeleton('briefingContainer');

        if (!data || !data.available) {
            container.innerHTML = `<p class="no-data">${bt('br_no_briefing')}</p>`;
            return;
        }

        briefingData = data;
        renderBriefing();
    } catch (err) {
        console.error('Error loading briefing:', err);
        if (typeof clearSkeleton === 'function') clearSkeleton('briefingContainer');
        container.innerHTML = `
            <div class="error-message">
                <strong>${bt('br_error')}</strong><br>
                <small>${err.message}</small><br>
                <button onclick="window.loadBriefing()" class="refresh-btn retry-btn">${bt('br_retry')}</button>
            </div>`;
        if (typeof showToast === 'function') showToast('error', bt('br_error'));
    }
}

// ============================================
// RENDER ORCHESTRATOR
// ============================================

function renderBriefing() {
    const container = document.getElementById('briefingContainer');
    if (!container || !briefingData) return;

    let html = '';

    // 1. Market Pulse (always visible)
    html += renderMarketPulse(briefingData.market_pulse);

    // 2. Your Actions Today (logged-in only)
    html += renderActionsToday(briefingData.actions_today);

    // 3. Portfolio Snapshot (logged-in only)
    html += renderPortfolioSnapshot(briefingData.portfolio_snapshot);

    // 4. Watchlist Heatmap (logged-in only)
    html += renderWatchlistHeatmap(briefingData.watchlist_heatmap);

    // 5. Sector Breakdown (always visible)
    html += renderSectorBreakdown(briefingData.sector_breakdown);

    // 6. Risk Alerts (always visible)
    html += renderRiskAlerts(briefingData.risk_alerts);

    // 7. Sentiment Snapshot (always visible)
    html += renderSentimentSnapshot(briefingData.sentiment_snapshot);

    container.innerHTML = html;
}

// ============================================
// SECTION RENDERERS
// ============================================

function renderMarketPulse(pulse) {
    if (!pulse) return '';
    const isAr = brIsArabic();

    const dirClass = pulse.direction === 'BULLISH' ? 'direction-bullish'
        : pulse.direction === 'BEARISH' ? 'direction-bearish' : 'direction-mixed';
    const dirLabel = pulse.direction === 'BULLISH' ? bt('br_bullish')
        : pulse.direction === 'BEARISH' ? bt('br_bearish') : bt('br_mixed');

    const total = (pulse.stocks_up || 0) + (pulse.stocks_down || 0) + (pulse.stocks_flat || 0);
    const upPct = total > 0 ? ((pulse.stocks_up / total) * 100).toFixed(0) : 0;
    const downPct = total > 0 ? ((pulse.stocks_down / total) * 100).toFixed(0) : 0;
    const flatPct = total > 0 ? (100 - upPct - downPct) : 0;

    const volRatio = pulse.volume_vs_avg || 1;
    const volLabel = volRatio >= 1.3 ? 'above-avg' : volRatio <= 0.7 ? 'below-avg' : 'normal';

    // Top movers
    const gainers = (pulse.top_gainers || []).slice(0, 3);
    const losers = (pulse.top_losers || []).slice(0, 3);

    const moverHtml = (list, isGainer) => list.map(m => {
        const name = isAr ? (m.name_ar || m.name_en) : m.name_en;
        const sign = m.change_pct >= 0 ? '+' : '';
        const cls = isGainer ? 'pos' : 'neg';
        return `<span class="mover-chip ${cls}">${m.symbol} <strong>${sign}${m.change_pct}%</strong></span>`;
    }).join('');

    return `
    <div class="briefing-section">
        <div class="briefing-section-header">
            <h3>📊 ${bt('br_pulse')}</h3>
            <span class="direction-badge ${dirClass}">${dirLabel}</span>
        </div>
        <div class="briefing-stats-row">
            <div class="briefing-stat">
                <div class="briefing-stat-val">${pulse.confidence || 0}%</div>
                <div class="briefing-stat-lbl">${bt('br_confidence')}</div>
            </div>
            <div class="briefing-stat">
                <div class="briefing-stat-val">${volRatio}x</div>
                <div class="briefing-stat-lbl">${bt('br_volume')} ${bt('br_vs_avg')}</div>
            </div>
            <div class="briefing-stat">
                <div class="briefing-stat-val">${total}</div>
                <div class="briefing-stat-lbl">${bt('br_breadth')}</div>
            </div>
        </div>
        <div class="breadth-bar">
            <div class="breadth-segment breadth-advancing" style="width:${upPct}%">${pulse.stocks_up || 0} ▲</div>
            <div class="breadth-segment breadth-unchanged" style="width:${flatPct}%">${pulse.stocks_flat || 0}</div>
            <div class="breadth-segment breadth-declining" style="width:${downPct}%">${pulse.stocks_down || 0} ▼</div>
        </div>
        <div class="breadth-labels">
            <span class="lbl-advancing">${bt('br_advancing')}</span>
            <span class="lbl-unchanged">${bt('br_unchanged')}</span>
            <span class="lbl-declining">${bt('br_declining')}</span>
        </div>
        ${gainers.length > 0 ? `
        <div class="movers-row">
            <div class="movers-col">
                <strong>${bt('br_top_gainers')}</strong><br>${moverHtml(gainers, true)}
            </div>
            <div class="movers-col">
                <strong>${bt('br_top_losers')}</strong><br>${moverHtml(losers, false)}
            </div>
        </div>` : ''}
    </div>`;
}


function renderActionsToday(actions) {
    const isAr = brIsArabic();

    if (!brIsLoggedIn()) {
        return `
        <div class="briefing-section">
            <div class="briefing-section-header"><h3>⚡ ${bt('br_actions')}</h3></div>
            <div class="login-wall">
                <p>${bt('br_login_actions')}</p>
                <button onclick="showAuthModal('login')" class="auth-trigger-btn">🔐 ${bt('br_login_btn')}</button>
            </div>
        </div>`;
    }

    if (!actions || actions.length === 0) {
        return `
        <div class="briefing-section">
            <div class="briefing-section-header"><h3>⚡ ${bt('br_actions')}</h3></div>
            <p class="no-data">${bt('br_no_actions')}</p>
        </div>`;
    }

    const cards = actions.map(a => {
        const name = isAr ? (a.name_ar || a.name_en) : a.name_en;
        const actionCls = a.action === 'BUY' ? 'urgent-buy' : 'urgent-sell';
        const actionBadge = a.action === 'BUY' ? 'action-buy' : 'action-sell';
        const reasons = isAr ? (a.reasons_ar || a.reasons || []) : (a.reasons || []);
        const reason = reasons[0] || '';

        return `
        <div class="action-card ${actionCls}">
            <div class="action-card-badge ${actionBadge}">${a.action === 'BUY' ? bt('br_buy') : bt('br_sell')}</div>
            <div class="action-card-body">
                <div class="action-card-symbol">${a.symbol}</div>
                <div class="action-card-name">${name}</div>
                <div class="action-card-meta">
                    ${a.confidence}% · ${a.conviction || ''}
                    ${a.close_price ? ` · EGP ${a.close_price.toFixed(2)}` : ''}
                </div>
                ${reason ? `<div class="action-card-reason">${reason}</div>` : ''}
            </div>
        </div>`;
    }).join('');

    return `
    <div class="briefing-section">
        <div class="briefing-section-header"><h3>⚡ ${bt('br_actions')}</h3></div>
        <div class="actions-grid">${cards}</div>
    </div>`;
}


function renderPortfolioSnapshot(portfolio) {
    if (!brIsLoggedIn()) {
        return ''; // Actions section already shows login prompt
    }

    if (!portfolio || portfolio.open_count === 0) {
        return `
        <div class="briefing-section">
            <div class="briefing-section-header"><h3>💼 ${bt('br_portfolio')}</h3></div>
            <p class="no-data">${bt('br_no_portfolio')}</p>
        </div>`;
    }

    const isAr = brIsArabic();
    const pnlClass = portfolio.total_unrealized_pct >= 0 ? 'pos' : 'neg';
    const pnlSign = portfolio.total_unrealized_pct >= 0 ? '+' : '';

    const positionRows = (portfolio.positions || []).map(p => {
        const cls = p.unrealized_pct >= 0 ? 'pos' : 'neg';
        const sign = p.unrealized_pct >= 0 ? '+' : '';
        return `<tr>
            <td><strong>${p.symbol}</strong></td>
            <td>${p.entry_price ? p.entry_price.toFixed(2) : '-'}</td>
            <td>${p.current_price ? p.current_price.toFixed(2) : '-'}</td>
            <td class="${cls}">${sign}${p.unrealized_pct}%</td>
            <td>${p.days_held || 0}</td>
        </tr>`;
    }).join('');

    return `
    <div class="briefing-section">
        <div class="briefing-section-header"><h3>💼 ${bt('br_portfolio')}</h3></div>
        <div class="briefing-stats-row">
            <div class="briefing-stat">
                <div class="briefing-stat-val">${portfolio.open_count}</div>
                <div class="briefing-stat-lbl">${bt('br_open_positions')}</div>
            </div>
            <div class="briefing-stat">
                <div class="briefing-stat-val ${pnlClass}">${pnlSign}${portfolio.total_unrealized_pct}%</div>
                <div class="briefing-stat-lbl">${bt('br_unrealized')}</div>
            </div>
        </div>
        ${portfolio.positions && portfolio.positions.length > 0 ? `
        <table class="portfolio-table briefing-table">
            <thead><tr>
                <th>${bt('br_symbol')}</th>
                <th>${bt('br_entry')}</th>
                <th>${bt('br_current')}</th>
                <th>${bt('br_pnl')}</th>
                <th>${bt('br_days')}</th>
            </tr></thead>
            <tbody>${positionRows}</tbody>
        </table>` : ''}
    </div>`;
}


function renderWatchlistHeatmap(heatmap) {
    if (!brIsLoggedIn()) {
        return ''; // Actions section already shows login prompt
    }

    if (!heatmap || heatmap.length === 0) {
        return `
        <div class="briefing-section">
            <div class="briefing-section-header"><h3>🗺️ ${bt('br_heatmap')}</h3></div>
            <p class="no-data">${bt('br_no_heatmap')}</p>
        </div>`;
    }

    const isAr = brIsArabic();
    const maxStrength = Math.max(...heatmap.map(h => h.signal_strength || 0), 1);

    const cards = heatmap.map(h => {
        const name = isAr ? (h.name_ar || h.name_en) : h.name_en;
        const signal = h.final_signal || 'FLAT';
        const strength = h.signal_strength || 0;
        const pct = Math.round((strength / maxStrength) * 100);

        let colorClass = 'heatmap-neutral';
        if (signal === 'UP' && strength > maxStrength * 0.5) colorClass = 'heatmap-strong-bull';
        else if (signal === 'UP') colorClass = 'heatmap-mild-bull';
        else if (signal === 'DOWN' && strength > maxStrength * 0.5) colorClass = 'heatmap-strong-bear';
        else if (signal === 'DOWN') colorClass = 'heatmap-mild-bear';

        const signalBadge = signal === 'UP' ? 'signal-up' : signal === 'DOWN' ? 'signal-down' : 'signal-flat';

        return `
        <div class="heatmap-card ${colorClass}">
            <div class="heatmap-symbol">${h.symbol}</div>
            <div class="heatmap-name">${name}</div>
            <span class="consensus-signal-badge ${signalBadge}">${signal}</span>
            <div class="heatmap-conf">${h.confidence || 0}%</div>
        </div>`;
    }).join('');

    return `
    <div class="briefing-section">
        <div class="briefing-section-header"><h3>🗺️ ${bt('br_heatmap')}</h3></div>
        <div class="heatmap-grid">${cards}</div>
    </div>`;
}


function renderSectorBreakdown(sectors) {
    if (!sectors || sectors.length === 0) return '';

    const isAr = brIsArabic();

    const rows = sectors.map(s => {
        const name = isAr ? (s.sector_ar || s.sector_en) : s.sector_en;
        const total = (s.up || 0) + (s.down || 0) + (s.flat || 0);
        const upPct = total > 0 ? ((s.up / total) * 100).toFixed(0) : 0;
        const downPct = total > 0 ? ((s.down / total) * 100).toFixed(0) : 0;
        const flatPct = total > 0 ? (100 - upPct - downPct) : 0;

        const dirClass = s.direction === 'BULLISH' ? 'direction-bullish'
            : s.direction === 'BEARISH' ? 'direction-bearish' : 'direction-mixed';
        const dirLabel = s.direction === 'BULLISH' ? bt('br_bullish')
            : s.direction === 'BEARISH' ? bt('br_bearish') : bt('br_mixed');

        return `
        <div class="sector-row">
            <div class="sector-label">${name}</div>
            <div class="sector-bar">
                <div class="breadth-segment breadth-advancing" style="width:${upPct}%"></div>
                <div class="breadth-segment breadth-unchanged" style="width:${flatPct}%"></div>
                <div class="breadth-segment breadth-declining" style="width:${downPct}%"></div>
            </div>
            <span class="direction-badge ${dirClass} direction-badge-sm">${dirLabel}</span>
            <span class="sector-conf">${s.avg_confidence || 0}%</span>
        </div>`;
    }).join('');

    return `
    <div class="briefing-section">
        <div class="briefing-section-header"><h3>🏭 ${bt('br_sectors')}</h3></div>
        ${rows}
    </div>`;
}


function renderRiskAlerts(alerts) {
    if (!alerts || alerts.length === 0) {
        return `
        <div class="briefing-section">
            <div class="briefing-section-header"><h3>⚠️ ${bt('br_risk')}</h3></div>
            <p class="no-data" style="color: var(--accent-green, #10b981);">${bt('br_no_risk')}</p>
        </div>`;
    }

    const isAr = brIsArabic();

    const items = alerts.map(a => {
        const name = isAr ? (a.name_ar || a.name_en) : a.name_en;
        const badgeClass = a.risk_action === 'BLOCK' ? 'risk-badge-block'
            : a.risk_action === 'DOWNGRADE' ? 'risk-badge-downgrade' : 'risk-badge-flag';
        const label = a.risk_action === 'BLOCK' ? bt('br_blocked')
            : a.risk_action === 'DOWNGRADE' ? bt('br_downgraded') : bt('br_flagged');
        const flags = Array.isArray(a.risk_flags) ? a.risk_flags.join(', ') : '';

        return `
        <div class="risk-alert-item">
            <span class="risk-badge ${badgeClass}">${label}</span>
            <strong>${a.symbol}</strong> — ${name}
            ${flags ? `<div class="risk-flags-text">${flags}</div>` : ''}
        </div>`;
    }).join('');

    return `
    <div class="briefing-section">
        <div class="briefing-section-header"><h3>⚠️ ${bt('br_risk')}</h3></div>
        ${items}
    </div>`;
}


function renderSentimentSnapshot(sentiment) {
    if (!sentiment) return '';

    const isAr = brIsArabic();
    const dirLabel = sentiment.direction === 'POSITIVE' ? bt('br_positive')
        : sentiment.direction === 'NEGATIVE' ? bt('br_negative') : bt('br_neutral');
    const dirClass = sentiment.direction === 'POSITIVE' ? 'pos'
        : sentiment.direction === 'NEGATIVE' ? 'neg' : '';
    const emoji = sentiment.direction === 'POSITIVE' ? '😊'
        : sentiment.direction === 'NEGATIVE' ? '😟' : '😐';

    const notable = (sentiment.notable || []).slice(0, 5);
    const notableHtml = notable.map(n => {
        const name = isAr ? (n.name_ar || n.name_en) : n.name_en;
        const cls = n.avg_sentiment >= 0.1 ? 'pos' : n.avg_sentiment <= -0.1 ? 'neg' : '';
        return `<div class="notable-item">
            <strong>${n.symbol}</strong> <span class="company-name">${name}</span>
            <span class="${cls}">${n.avg_sentiment >= 0 ? '+' : ''}${n.avg_sentiment}</span>
        </div>`;
    }).join('');

    return `
    <div class="briefing-section">
        <div class="briefing-section-header"><h3>📰 ${bt('br_sentiment')}</h3></div>
        <div class="briefing-stats-row">
            <div class="briefing-stat">
                <div class="briefing-stat-val ${dirClass}">${emoji} ${dirLabel}</div>
                <div class="briefing-stat-lbl">${bt('br_overall')} (${sentiment.avg_score || 0})</div>
            </div>
            <div class="briefing-stat">
                <div class="briefing-stat-val pos">${sentiment.positive_count || 0}</div>
                <div class="briefing-stat-lbl">${bt('br_positive')}</div>
            </div>
            <div class="briefing-stat">
                <div class="briefing-stat-val neg">${sentiment.negative_count || 0}</div>
                <div class="briefing-stat-lbl">${bt('br_negative')}</div>
            </div>
            <div class="briefing-stat">
                <div class="briefing-stat-val">${sentiment.neutral_count || 0}</div>
                <div class="briefing-stat-lbl">${bt('br_neutral')}</div>
            </div>
        </div>
        ${notable.length > 0 ? `
        <div class="notable-list">
            <strong>${bt('br_notable')}</strong>
            ${notableHtml}
        </div>` : ''}
    </div>`;
}


// ============================================
// GLOBAL EXPORTS
// ============================================
window.loadBriefing = loadBriefing;

window.updateBriefingLanguage = function () {
    // Re-render with current language
    if (briefingData) {
        renderBriefing();
    }

    // Update static titles
    const el = document.getElementById('briefingTitle');
    if (el) el.textContent = bt('br_title');
    const sub = document.getElementById('briefingSubtitle');
    if (sub) sub.textContent = bt('br_subtitle');
};

