/**
 * KSA Execution Simulation — Phase B
 * Simulates a Derayah-style order flow for each signal.
 * No real trades are placed. Pure UI simulation.
 */

'use strict';

// ── Open/close modal ──────────────────────────────────────────────────────────

function openExecModal(ticker) {
    const modal = document.getElementById('execModal');
    const body  = document.getElementById('execModalBody');
    const label = document.getElementById('execTicker');
    if (!modal) return;

    label.textContent = ticker;
    body.innerHTML    = '<div class="exec-loading">Loading execution data…</div>';
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';

    Promise.all([
        fetch(`/api/ksa/execution/${encodeURIComponent(ticker)}`).then(r => r.json()),
        fetch(`/api/ksa/context/${encodeURIComponent(ticker)}`).then(r => r.json()),
    ]).then(([exec, ctx]) => {
        body.innerHTML = renderExecPanel(exec, ctx);
    }).catch(err => {
        body.innerHTML = `<div class="exec-error">Failed to load data: ${err.message}</div>`;
    });
}

function closeExecModal() {
    const modal = document.getElementById('execModal');
    if (modal) modal.style.display = 'none';
    document.body.style.overflow = '';
}

document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeExecModal();
});

// ── Render execution panel ────────────────────────────────────────────────────

function renderExecPanel(exec, ctx) {
    if (!exec?.available) {
        return `<div class="exec-no-data">
            <div class="exec-no-data-icon">📊</div>
            <div>No execution data yet for <strong>${exec?.ticker || '—'}</strong>.</div>
            <div style="margin-top:6px;font-size:12px;color:var(--text-muted,#888)">Data populates after the next pipeline run.</div>
        </div>`;
    }

    const fmt    = (v, d = 2) => v != null && isFinite(v) ? Number(v).toFixed(d) : '—';
    const fmtSAR = (v) => v != null && isFinite(v) ? `SAR ${Number(v).toFixed(2)}` : '—';
    const pct    = (v) => v != null && isFinite(v) ? `${v >= 0 ? '+' : ''}${Number(v).toFixed(2)}%` : '—';
    const sign   = exec.signal || 'HOLD';
    const signCls = sign === 'BUY' ? 'exec-sig-buy' : sign === 'SELL' ? 'exec-sig-sell' : 'exec-sig-hold';
    const entry  = exec.entry_price;
    const rr     = exec.risk_reward;

    // Context block
    const ctxFlag  = ctx?.context_flag || null;
    const ctxClass = ctx?.context_class || 'neutral';
    const ctxHtml  = ctxFlag ? `<span class="exec-context-badge exec-ctx-${ctxClass}">${ctxFlag}</span>` : '';

    // Sentiment bar
    const sentVal   = ctx?.sentiment?.score ?? 0;
    const sentPct   = Math.min(100, Math.max(0, (sentVal + 1) * 50));
    const sentLabel = ctx?.sentiment?.label || 'neutral';
    const sentColor = sentVal > 0.2 ? '#10b981' : sentVal < -0.2 ? '#ef4444' : '#6b7280';

    // Pivot table
    const pivotRows = [
        exec.r2   != null ? `<tr><td>R2</td><td class="exec-level-r">${fmtSAR(exec.r2)}</td></tr>` : '',
        exec.r1   != null ? `<tr><td>R1</td><td class="exec-level-r">${fmtSAR(exec.r1)}</td></tr>` : '',
        exec.pivot != null ? `<tr class="exec-pivot-row"><td>Pivot</td><td>${fmtSAR(exec.pivot)}</td></tr>` : '',
        exec.s1   != null ? `<tr><td>S1</td><td class="exec-level-s">${fmtSAR(exec.s1)}</td></tr>` : '',
        exec.s2   != null ? `<tr><td>S2</td><td class="exec-level-s">${fmtSAR(exec.s2)}</td></tr>` : '',
    ].filter(Boolean).join('');

    // Position sizer (simple fixed-risk: risk 2% of SAR 100,000 portfolio)
    const PORTFOLIO_SAR = 100_000;
    const RISK_PCT      = 0.02;
    const riskAmt       = PORTFOLIO_SAR * RISK_PCT;
    const stopDiff      = entry && exec.stop_loss ? Math.abs(entry - exec.stop_loss) : null;
    const sharesRaw     = stopDiff && stopDiff > 0 ? riskAmt / stopDiff : null;
    const shares        = sharesRaw ? Math.floor(sharesRaw) : null;
    const posValue      = shares && entry ? shares * entry : null;

    // Simulated order lifecycle
    const lifecycle = [
        { step: '1', label: 'Place Order', detail: `${sign === 'SELL' ? 'Market Sell' : 'Market Buy'} @ ${fmtSAR(entry)}`, icon: '📋' },
        { step: '2', label: 'Set Stop Loss', detail: `Stop at ${fmtSAR(exec.stop_loss)} (${pct(exec.stop_loss_pct)})`, icon: '🛡' },
        { step: '3', label: 'Set Take Profit', detail: `Target ${fmtSAR(exec.target_price)} (${pct(exec.target_pct)})`, icon: '🎯' },
        { step: '4', label: 'Monitor', detail: `Check signal again in 1 trading session`, icon: '👁' },
    ];

    // Recent news
    const newsHtml = (ctx?.recent_news || []).length > 0 ? `
        <div class="exec-section-title">Recent News</div>
        <div class="exec-news-list">
            ${ctx.recent_news.map(n => `
                <div class="exec-news-item">
                    <div class="exec-news-title">${escExec(n.title || '')}</div>
                    <div class="exec-news-meta">${escExec(n.source || '')} · ${String(n.published_at || '').slice(0, 10)}</div>
                </div>
            `).join('')}
        </div>
    ` : '';

    return `
    <div class="exec-body">
        <!-- Signal + context -->
        <div class="exec-signal-row">
            <span class="exec-signal-badge ${signCls}">${sign}</span>
            <span class="exec-conviction">${exec.conviction || '—'}</span>
            <span class="exec-score">Score ${fmt(exec.xmore_score, 0)}</span>
            ${ctxHtml}
        </div>

        <!-- Sentiment bar -->
        <div class="exec-sent-row">
            <span class="exec-sent-label">Sentiment</span>
            <div class="exec-sent-bar-wrap">
                <div class="exec-sent-bar" style="width:${sentPct.toFixed(1)}%;background:${sentColor}"></div>
            </div>
            <span class="exec-sent-val" style="color:${sentColor}">${sentLabel} (${sentVal >= 0 ? '+' : ''}${fmt(sentVal, 2)})</span>
        </div>

        <!-- Price levels grid -->
        <div class="exec-section-title">Price Levels</div>
        <div class="exec-levels-grid">
            <div class="exec-level-card exec-level-entry">
                <div class="exec-level-lbl">Entry</div>
                <div class="exec-level-val">${fmtSAR(entry)}</div>
                <div class="exec-level-sub">as of ${String(exec.as_of || '—').slice(0, 10)}</div>
            </div>
            <div class="exec-level-card exec-level-stop">
                <div class="exec-level-lbl">Stop Loss</div>
                <div class="exec-level-val red">${fmtSAR(exec.stop_loss)}</div>
                <div class="exec-level-sub">${pct(exec.stop_loss_pct)}</div>
            </div>
            <div class="exec-level-card exec-level-target">
                <div class="exec-level-lbl">Take Profit</div>
                <div class="exec-level-val green">${fmtSAR(exec.target_price)}</div>
                <div class="exec-level-sub">${pct(exec.target_pct)}</div>
            </div>
            <div class="exec-level-card">
                <div class="exec-level-lbl">R/R Ratio</div>
                <div class="exec-level-val ${rr && rr >= 2 ? 'green' : rr && rr >= 1 ? '' : 'red'}">${rr ? '1 : ' + fmt(rr) : '—'}</div>
                <div class="exec-level-sub">${rr >= 2 ? 'Favorable' : rr >= 1 ? 'Acceptable' : 'Caution'}</div>
            </div>
        </div>

        <!-- Pivot table -->
        ${pivotRows ? `
        <div class="exec-section-title">Pivot Levels (Daily)</div>
        <table class="exec-pivot-table"><tbody>${pivotRows}</tbody></table>
        ` : ''}

        <!-- Position sizer -->
        <div class="exec-section-title">Position Sizer <span class="exec-sim-note">(2% risk · SAR 100K portfolio)</span></div>
        <div class="exec-pos-grid">
            <div><span class="exec-pos-lbl">Risk Budget</span><strong>SAR ${riskAmt.toLocaleString()}</strong></div>
            <div><span class="exec-pos-lbl">Suggested Shares</span><strong>${shares != null ? shares.toLocaleString() : '—'}</strong></div>
            <div><span class="exec-pos-lbl">Position Value</span><strong>${posValue != null ? fmtSAR(posValue) : '—'}</strong></div>
            <div><span class="exec-pos-lbl">Max Loss</span><strong class="red">SAR ${riskAmt.toLocaleString()}</strong></div>
        </div>

        <!-- Simulated order lifecycle -->
        <div class="exec-section-title">Simulated Order Flow</div>
        <div class="exec-lifecycle">
            ${lifecycle.map(s => `
            <div class="exec-step">
                <div class="exec-step-icon">${s.icon}</div>
                <div class="exec-step-body">
                    <div class="exec-step-label">Step ${s.step}: ${s.label}</div>
                    <div class="exec-step-detail">${s.detail}</div>
                </div>
            </div>`).join('')}
        </div>

        ${newsHtml}

        <div class="exec-disclaimer">
            ⚠️ Simulation only. No real order has been placed.
            This tool does not connect to Derayah Financial or any brokerage.
            Always verify prices and risk levels before trading.
        </div>
    </div>`;
}

// ── Minimal XSS escape ────────────────────────────────────────────────────────
function escExec(s) {
    return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
