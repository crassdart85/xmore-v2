/**
 * Portfolio Forecasts Module
 * Handles the "My Portfolios" section inside the Time Machine → Future tab.
 *
 * Exposed:  window.loadPortfolioForecasts()
 *           window.updatePortfolioForecastsLanguage()
 */
(function () {
    'use strict';

    // ── State ────────────────────────────────────────────────────────────────
    let pfPortfolios    = [];
    let pfActive        = null;   // currently viewed portfolio id
    let pfSelectedSyms  = [];     // symbols chosen in the create/edit form
    let pfAllStocks     = [];     // full stock list for the dropdown
    let pfEditingId     = null;   // null = creating, number = editing
    let pfInitialized   = false;

    const HORIZON_OPTIONS = [
        { days: 21,  label_en: '1 Month',   label_ar: 'شهر'      },
        { days: 42,  label_en: '2 Months',  label_ar: 'شهران'   },
        { days: 63,  label_en: '3 Months',  label_ar: '3 أشهر'  },
        { days: 126, label_en: '6 Months',  label_ar: '6 أشهر'  },
        { days: 252, label_en: '1 Year',    label_ar: 'سنة'      },
        { days: 504, label_en: '2 Years',   label_ar: 'سنتان'   },
    ];
    const SCENARIO_LABELS = { base: 'Base', bull: 'Bull 🐂', bear: 'Bear 🐻' };

    // ── Helpers ──────────────────────────────────────────────────────────────

    function lang() { return localStorage.getItem('lang') || 'en'; }
    function isAr()  { return lang() === 'ar'; }

    function fmt(n, digits = 1) {
        if (n == null || isNaN(n)) return '—';
        const sign = n > 0 ? '+' : '';
        return `${sign}${Number(n).toFixed(digits)}%`;
    }

    function colorClass(n) {
        if (n == null || isNaN(n)) return '';
        return n > 0 ? 'pf-positive' : n < 0 ? 'pf-negative' : '';
    }

    function escHtml(s) {
        return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }

    function apiHeaders() {
        return { 'Content-Type': 'application/json' };
    }

    async function apiFetch(url, opts = {}) {
        const res = await fetch(url, { credentials: 'include', ...opts });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
        return data;
    }

    // ── Stock list loader (reuses same endpoint as Time Machine) ─────────────

    async function loadAllStocks() {
        if (pfAllStocks.length) return pfAllStocks;
        try {
            const data = await apiFetch('/api/stocks');
            pfAllStocks = (data.stocks || data || []).map(s => ({
                symbol: s.symbol,
                name: isAr() ? (s.name_ar || s.name_en || s.symbol) : (s.name_en || s.symbol),
            }));
        } catch {
            pfAllStocks = [];
        }
        return pfAllStocks;
    }

    // ── Main entry point ─────────────────────────────────────────────────────

    window.loadPortfolioForecasts = async function () {
        if (!pfInitialized) {
            bindStaticHandlers();
            pfInitialized = true;
        }
        await refreshPortfolioList();
    };

    window.updatePortfolioForecastsLanguage = function () {
        if (pfInitialized) refreshPortfolioList();
    };

    // ── Refresh portfolio list ────────────────────────────────────────────────

    async function refreshPortfolioList() {
        const listEl = document.getElementById('pfList');
        if (!listEl) return;

        try {
            const data = await apiFetch('/api/portfolio-forecasts');
            pfPortfolios = data.portfolios || [];
            renderPortfolioList(listEl);
        } catch (err) {
            const msg = (err.message || '').toLowerCase();
            if (msg.includes('401') || msg.includes('403') || msg.includes('not authenticated') || msg.includes('unauthorized')) {
                listEl.innerHTML = `<p class="pf-empty">${isAr() ? 'يرجى تسجيل الدخول لعرض المحافظ' : 'Please log in to view your forecast portfolios.'}</p>`;
            } else {
                listEl.innerHTML = `<p class="pf-error">${escHtml(err.message)}</p>`;
            }
        }
    }

    function renderPortfolioList(listEl) {
        if (!pfPortfolios.length) {
            listEl.innerHTML = `<p class="pf-empty">${isAr() ? 'لا توجد محافظ بعد. أنشئ أولى محافظك!' : 'No portfolios yet. Create your first one!'}</p>`;
            return;
        }

        listEl.innerHTML = pfPortfolios.map(p => {
            const stockCount = (p.symbols || []).length;
            const horizonLabel = (HORIZON_OPTIONS.find(h => h.days === p.horizon_days) || {})[`label_${lang()}`] || `${p.horizon_days}d`;
            const scenLabel = SCENARIO_LABELS[p.scenario] || p.scenario;
            return `
            <div class="pf-card" data-id="${p.id}">
                <div class="pf-card-header">
                    <span class="pf-card-name">${escHtml(p.name)}</span>
                    <div class="pf-card-actions">
                        <button class="pf-btn-view"   data-id="${p.id}">${isAr() ? 'عرض' : 'View'}</button>
                        <button class="pf-btn-run"    data-id="${p.id}">${isAr() ? 'تشغيل' : 'Run'}</button>
                        <button class="pf-btn-edit"   data-id="${p.id}">${isAr() ? 'تعديل' : 'Edit'}</button>
                        <button class="pf-btn-delete" data-id="${p.id}">✕</button>
                    </div>
                </div>
                <div class="pf-card-meta">
                    <span>${stockCount} ${isAr() ? 'سهم' : 'stocks'}</span>
                    <span>${horizonLabel}</span>
                    <span class="pf-scenario-badge pf-scenario-${p.scenario}">${scenLabel}</span>
                    <span>${Number(p.investment_amount || 0).toLocaleString()} EGP</span>
                </div>
            </div>`;
        }).join('');

        // Bind card buttons
        listEl.querySelectorAll('.pf-btn-view').forEach(btn => {
            btn.addEventListener('click', () => viewPortfolio(parseInt(btn.dataset.id)));
        });
        listEl.querySelectorAll('.pf-btn-run').forEach(btn => {
            btn.addEventListener('click', () => runPortfolioForecast(parseInt(btn.dataset.id), btn));
        });
        listEl.querySelectorAll('.pf-btn-edit').forEach(btn => {
            btn.addEventListener('click', () => openEditForm(parseInt(btn.dataset.id)));
        });
        listEl.querySelectorAll('.pf-btn-delete').forEach(btn => {
            btn.addEventListener('click', () => deletePortfolio(parseInt(btn.dataset.id)));
        });
    }

    // ── View portfolio results ────────────────────────────────────────────────

    async function viewPortfolio(id) {
        pfActive = id;
        const resultsEl = document.getElementById('pfResults');
        if (!resultsEl) return;
        resultsEl.innerHTML = `<div class="pf-loading">${isAr() ? 'جارٍ التحميل…' : 'Loading…'}</div>`;

        try {
            const data = await apiFetch(`/api/portfolio-forecasts/${id}/results`);
            renderPortfolioResults(resultsEl, data);
        } catch (err) {
            resultsEl.innerHTML = `<p class="pf-error">${escHtml(err.message)}</p>`;
        }
    }

    function renderPortfolioResults(el, data) {
        const { portfolio, results, run_date } = data;
        if (!results || !results.length) {
            el.innerHTML = `
                <div class="pf-results-header">
                    <h4>${escHtml(portfolio.name)}</h4>
                    <p class="pf-empty">${isAr() ? 'لا توجد نتائج بعد. اضغط "تشغيل" لبدء التوقعات.' : 'No results yet. Click "Run" to generate forecasts.'}</p>
                </div>`;
            return;
        }

        const successRows = results.filter(r => r.ok || r.ok === 1);
        const failedRows  = results.filter(r => !r.ok && r.ok !== 1);

        el.innerHTML = `
        <div class="pf-results-header">
            <h4>${escHtml(portfolio.name)}</h4>
            <span class="pf-run-date">${isAr() ? 'تاريخ التشغيل:' : 'Run date:'} ${run_date} → ${results[0]?.target_date || '—'}</span>
        </div>
        <div class="pf-table-wrap">
        <table class="pf-table">
            <thead><tr>
                <th>${isAr() ? 'السهم' : 'Stock'}</th>
                <th>${isAr() ? 'العائد المتوقع' : 'Expected Return'}</th>
                <th>${isAr() ? 'احتمال الارتفاع' : 'Prob. Positive'}</th>
                <th>${isAr() ? 'الأسوأ' : 'Worst'}</th>
                <th>${isAr() ? 'الوسيط' : 'Median'}</th>
                <th>${isAr() ? 'الأفضل' : 'Best'}</th>
                <th>${isAr() ? 'التقلب' : 'Volatility'}</th>
                <th>${isAr() ? 'النتيجة الفعلية' : 'Actual Result'}</th>
            </tr></thead>
            <tbody>
            ${successRows.map(r => {
                const evaluated = r.evaluated || r.evaluated === 1;
                const actualCell = evaluated
                    ? `<span class="${colorClass(r.actual_return_pct)}">${fmt(r.actual_return_pct)} <small>(err ${fmt(r.error_pct)})</small></span>`
                    : `<span class="pf-pending" title="${isAr() ? 'في انتظار تاريخ الهدف' : 'Waiting for target date'}">⏳</span>`;
                return `<tr>
                    <td><strong>${escHtml(r.symbol)}</strong></td>
                    <td class="${colorClass(r.expected_return_pct)}">${fmt(r.expected_return_pct)}</td>
                    <td>${r.probability_positive != null ? Math.round(r.probability_positive) + '%' : '—'}</td>
                    <td class="pf-negative">${fmt(r.worst_case_pct)}</td>
                    <td>${fmt(r.median_pct)}</td>
                    <td class="pf-positive">${fmt(r.best_case_pct)}</td>
                    <td>${r.volatility_annual_pct != null ? Math.round(r.volatility_annual_pct) + '%' : '—'}</td>
                    <td>${actualCell}</td>
                </tr>`;
            }).join('')}
            ${failedRows.map(r => `
                <tr class="pf-row-failed">
                    <td><strong>${escHtml(r.symbol)}</strong></td>
                    <td colspan="7" class="pf-error-cell">⚠ ${escHtml(r.error_reason || 'Forecast unavailable')}</td>
                </tr>`).join('')}
            </tbody>
        </table>
        </div>`;
    }

    // ── Run forecast ─────────────────────────────────────────────────────────

    async function runPortfolioForecast(id, btn) {
        const portfolio = pfPortfolios.find(p => p.id === id);
        const label = portfolio ? escHtml(portfolio.name) : `#${id}`;
        if (btn) { btn.disabled = true; btn.textContent = '⏳'; }

        const resultsEl = document.getElementById('pfResults');
        if (resultsEl) {
            resultsEl.innerHTML = `<div class="pf-loading">${isAr() ? `جارٍ تشغيل التوقعات لـ ${label}…` : `Running forecasts for ${label}…`}</div>`;
        }

        try {
            const data = await apiFetch(`/api/portfolio-forecasts/${id}/run`, { method: 'POST' });
            if (resultsEl) renderPortfolioResults(resultsEl, {
                portfolio: portfolio || { name: label },
                results: data.results,
                run_date: data.run_date,
            });
            await refreshPortfolioList();
        } catch (err) {
            if (resultsEl) resultsEl.innerHTML = `<p class="pf-error">${escHtml(err.message)}</p>`;
        } finally {
            if (btn) { btn.disabled = false; btn.textContent = isAr() ? 'تشغيل' : 'Run'; }
        }
    }

    // ── Create / Edit form ────────────────────────────────────────────────────

    function bindStaticHandlers() {
        const createBtn = document.getElementById('pfCreateBtn');
        if (createBtn) createBtn.addEventListener('click', () => openCreateForm());

        const saveBtn   = document.getElementById('pfSaveBtn');
        if (saveBtn)   saveBtn.addEventListener('click', () => savePortfolio());

        const cancelBtn = document.getElementById('pfCancelBtn');
        if (cancelBtn) cancelBtn.addEventListener('click', () => closeForm());

        const searchEl  = document.getElementById('pfSymbolSearch');
        if (searchEl) {
            searchEl.addEventListener('input',  () => filterPfDropdown(searchEl.value));
            searchEl.addEventListener('focus',  () => filterPfDropdown(searchEl.value));
            searchEl.addEventListener('blur',   () => {
                // Delay hide so checkbox clicks register first
                setTimeout(() => {
                    const dd = document.getElementById('pfSymbolDropdown');
                    if (dd) dd.style.display = 'none';
                }, 200);
            });
        }
        // Close dropdown on outside click
        document.addEventListener('click', (e) => {
            const dd = document.getElementById('pfSymbolDropdown');
            if (dd && !dd.contains(e.target) && e.target !== document.getElementById('pfSymbolSearch')) {
                dd.style.display = 'none';
            }
        });

        // Horizon preset buttons
        document.querySelectorAll('.pf-horizon-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.pf-horizon-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                const hInput = document.getElementById('pfHorizonInput');
                if (hInput) hInput.value = btn.dataset.days;
            });
        });
    }

    async function openCreateForm() {
        pfEditingId = null;
        pfSelectedSyms = [];
        resetForm();
        document.getElementById('pfFormTitle').textContent = isAr() ? 'محفظة جديدة' : 'New Portfolio';
        document.getElementById('pfCreateForm').style.display = 'block';
        await loadAllStocks();
        renderPfDropdown('');
    }

    async function openEditForm(id) {
        const portfolio = pfPortfolios.find(p => p.id === id);
        if (!portfolio) return;
        pfEditingId = id;
        pfSelectedSyms = [...(portfolio.symbols || [])];

        resetForm();
        document.getElementById('pfFormTitle').textContent = isAr() ? 'تعديل المحفظة' : 'Edit Portfolio';
        document.getElementById('pfNameInput').value = portfolio.name;
        document.getElementById('pfAmountInput').value = portfolio.investment_amount || 10000;

        // Set horizon
        const horizonInput = document.getElementById('pfHorizonInput');
        if (horizonInput) horizonInput.value = portfolio.horizon_days || 63;
        document.querySelectorAll('.pf-horizon-btn').forEach(btn => {
            btn.classList.toggle('active', parseInt(btn.dataset.days) === (portfolio.horizon_days || 63));
        });

        // Set scenario
        const scEl = document.querySelector(`input[name="pfScenario"][value="${portfolio.scenario || 'base'}"]`);
        if (scEl) scEl.checked = true;

        document.getElementById('pfCreateForm').style.display = 'block';
        await loadAllStocks();
        renderPfDropdown('');
        renderPfTags();
    }

    function resetForm() {
        const nameEl = document.getElementById('pfNameInput');
        if (nameEl) nameEl.value = '';
        const amtEl  = document.getElementById('pfAmountInput');
        if (amtEl)   amtEl.value = 10000;
        const hEl    = document.getElementById('pfHorizonInput');
        if (hEl)     hEl.value = 63;
        document.querySelectorAll('.pf-horizon-btn').forEach((btn, i) => btn.classList.toggle('active', i === 0));
        const scEl = document.querySelector('input[name="pfScenario"][value="base"]');
        if (scEl) scEl.checked = true;
        renderPfTags();
        document.getElementById('pfFormError').textContent = '';
    }

    function closeForm() {
        document.getElementById('pfCreateForm').style.display = 'none';
        pfEditingId = null;
        pfSelectedSyms = [];
    }

    async function savePortfolio() {
        const name    = (document.getElementById('pfNameInput')?.value || '').trim();
        const amount  = parseFloat(document.getElementById('pfAmountInput')?.value) || 10000;
        const horizon = parseInt(document.getElementById('pfHorizonInput')?.value) || 63;
        const sc      = document.querySelector('input[name="pfScenario"]:checked')?.value || 'base';
        const errEl   = document.getElementById('pfFormError');

        if (!name)                    { errEl.textContent = isAr() ? 'أدخل اسم المحفظة' : 'Enter a portfolio name'; return; }
        if (!pfSelectedSyms.length)   { errEl.textContent = isAr() ? 'اختر سهماً واحداً على الأقل' : 'Select at least one stock'; return; }
        errEl.textContent = '';

        const body = { name, symbols: pfSelectedSyms, horizon_days: horizon, scenario: sc, investment_amount: amount };

        try {
            if (pfEditingId) {
                await apiFetch(`/api/portfolio-forecasts/${pfEditingId}`, { method: 'PUT', headers: apiHeaders(), body: JSON.stringify(body) });
            } else {
                await apiFetch('/api/portfolio-forecasts', { method: 'POST', headers: apiHeaders(), body: JSON.stringify(body) });
            }
            closeForm();
            await refreshPortfolioList();
        } catch (err) {
            errEl.textContent = err.message;
        }
    }

    // ── Symbol picker dropdown ────────────────────────────────────────────────

    function filterPfDropdown(query) {
        renderPfDropdown(query);
    }

    function renderPfDropdown(query) {
        const ddEl = document.getElementById('pfSymbolDropdown');
        if (!ddEl) return;
        const q = (query || '').toLowerCase();
        const filtered = pfAllStocks.filter(s =>
            s.symbol.toLowerCase().includes(q) || s.name.toLowerCase().includes(q)
        ).slice(0, 40);

        if (!filtered.length) {
            ddEl.style.display = 'none';
            return;
        }

        ddEl.innerHTML = filtered.map(s => {
            const checked = pfSelectedSyms.includes(s.symbol);
            return `<label class="pf-dropdown-item ${checked ? 'pf-checked' : ''}">
                <input type="checkbox" value="${escHtml(s.symbol)}" ${checked ? 'checked' : ''}>
                <span class="pf-sym">${escHtml(s.symbol)}</span>
                <span class="pf-name">${escHtml(s.name)}</span>
            </label>`;
        }).join('');

        ddEl.querySelectorAll('input[type=checkbox]').forEach(cb => {
            cb.addEventListener('change', () => togglePfSymbol(cb.value, cb.checked));
        });
        ddEl.style.display = '';
    }

    function togglePfSymbol(symbol, checked) {
        if (checked) {
            if (!pfSelectedSyms.includes(symbol)) pfSelectedSyms.push(symbol);
        } else {
            pfSelectedSyms = pfSelectedSyms.filter(s => s !== symbol);
        }
        renderPfTags();
        renderPfDropdown(document.getElementById('pfSymbolSearch')?.value || '');
    }

    function renderPfTags() {
        const tagsEl = document.getElementById('pfSelectedTags');
        if (!tagsEl) return;
        tagsEl.innerHTML = pfSelectedSyms.map(s => `
            <span class="pf-tag">
                ${escHtml(s)}
                <button class="pf-tag-remove" data-sym="${escHtml(s)}">×</button>
            </span>`).join('');

        tagsEl.querySelectorAll('.pf-tag-remove').forEach(btn => {
            btn.addEventListener('click', () => togglePfSymbol(btn.dataset.sym, false));
        });

        const countEl = document.getElementById('pfSelectionCount');
        if (countEl) countEl.textContent = `${pfSelectedSyms.length}/30`;
    }

    // ── Delete ────────────────────────────────────────────────────────────────

    async function deletePortfolio(id) {
        const portfolio = pfPortfolios.find(p => p.id === id);
        const name = portfolio ? portfolio.name : String(id);
        if (!confirm(isAr() ? `حذف "${name}"؟` : `Delete portfolio "${name}"?`)) return;
        try {
            await apiFetch(`/api/portfolio-forecasts/${id}`, { method: 'DELETE' });
            if (pfActive === id) {
                pfActive = null;
                const resultsEl = document.getElementById('pfResults');
                if (resultsEl) resultsEl.innerHTML = '';
            }
            await refreshPortfolioList();
        } catch (err) {
            alert(err.message);
        }
    }

})();
