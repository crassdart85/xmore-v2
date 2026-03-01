const API_BASE = '/api/admin';
const TOKEN_KEY = 'admin_token';
const LANG_KEY = 'lang';
const THEME_KEY = 'theme';

const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const uploadStatus = document.getElementById('uploadStatus');
const reportRows = document.getElementById('reportRows');
const auditHealth = document.getElementById('auditHealth');
const agentHealth = document.getElementById('agentHealth');

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function getToken() {
    return sessionStorage.getItem(TOKEN_KEY) || '';
}

function setToken(token) {
    if (token) {
        sessionStorage.setItem(TOKEN_KEY, token);
    } else {
        sessionStorage.removeItem(TOKEN_KEY);
    }
}

function apiHeaders(extra = {}) {
    const headers = { ...extra };
    const token = getToken();
    if (token) headers['Authorization'] = `Bearer ${token}`;
    return headers;
}

function showLoginForm(message) {
    document.getElementById('adminLoginPanel').style.display = '';
    document.getElementById('adminMainContent').style.display = 'none';
    document.getElementById('adminLogoutBtn').style.display = 'none';
    document.getElementById('adminPassword').value = '';
    const status = document.getElementById('loginStatus');
    status.textContent = message || '';
    status.style.color = message ? '#ef4444' : '';
}

function showMainContent() {
    document.getElementById('adminLoginPanel').style.display = 'none';
    document.getElementById('adminMainContent').style.display = '';
    document.getElementById('adminLogoutBtn').style.display = '';
}

async function adminLogin() {
    const username = (document.getElementById('adminUsername').value || '').trim();
    const password = document.getElementById('adminPassword').value || '';
    const loginStatus = document.getElementById('loginStatus');
    const loginBtn = document.getElementById('adminLoginBtn');

    if (!username || !password) {
        loginStatus.textContent = 'Please enter username and password.';
        loginStatus.style.color = '#ef4444';
        return;
    }

    loginBtn.disabled = true;
    loginStatus.textContent = 'Logging in…';
    loginStatus.style.color = '';

    try {
        const resp = await fetch('/api/admin/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        const data = await resp.json();
        if (!resp.ok) {
            loginStatus.textContent = data.error || 'Login failed';
            loginStatus.style.color = '#ef4444';
            return;
        }
        setToken(data.token);
        showMainContent();
        await Promise.all([loadSystemHealth(), loadReports(), loadSources()]);
        const activePanel = document.querySelector('.admin-tab-panel.active');
        if (activePanel && activePanel.id === 'tab-prices') loadPrices();
    } catch (_e) {
        loginStatus.textContent = 'Connection error. Try again.';
        loginStatus.style.color = '#ef4444';
    } finally {
        loginBtn.disabled = false;
    }
}

function adminLogout() {
    setToken('');
    showLoginForm();
}

function bindLoginForm() {
    document.getElementById('adminLoginBtn').addEventListener('click', adminLogin);
    document.getElementById('adminPassword').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') adminLogin();
    });
    document.getElementById('adminUsername').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') document.getElementById('adminPassword').focus();
    });
}

function applyThemeAndLanguage() {
    const theme = localStorage.getItem(THEME_KEY) ||
        (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    document.documentElement.setAttribute('data-theme', theme);

    const lang = localStorage.getItem(LANG_KEY) || 'en';
    const isArabic = lang === 'ar';
    document.documentElement.lang = isArabic ? 'ar' : 'en';
    document.documentElement.dir = isArabic ? 'rtl' : 'ltr';
    document.body.classList.toggle('rtl', isArabic);
}

function formatDate(isoDate) {
    if (!isoDate) return '-';
    const d = new Date(isoDate);
    if (Number.isNaN(d.getTime())) return escapeHtml(isoDate);
    return d.toLocaleString();
}

function setUploadMessage(message, isError = false) {
    uploadStatus.className = isError ? 'admin-upload-status error-message' : 'admin-upload-status no-data';
    uploadStatus.textContent = message;
}

async function fetchJson(url, options = {}) {
    const response = await fetch(url, {
        ...options,
        headers: apiHeaders(options.headers || {})
    });

    if (!response.ok) {
        if (response.status === 401) {
            setToken('');
            showLoginForm('Session expired. Please log in again.');
            throw new Error('Session expired. Please log in again.');
        }
        let details = '';
        try {
            const data = await response.json();
            details = data.error || data.details || '';
        } catch (_err) {
            details = '';
        }
        throw new Error(details || `Request failed (${response.status})`);
    }

    return response.json();
}

function renderSystemHealth(data) {
    const audit = data.audit_log;
    const agent = data.agent_performance_daily;

    auditHealth.innerHTML = audit ? `
        <p><strong>Table:</strong> ${escapeHtml(audit.table_name || '-')}</p>
        <p><strong>Field:</strong> ${escapeHtml(audit.field_changed || '-')}</p>
        <p><strong>At:</strong> ${escapeHtml(formatDate(audit.changed_at))}</p>
    ` : '<p class="no-data">No audit data available.</p>';

    agentHealth.innerHTML = agent ? `
        <p><strong>Date:</strong> ${escapeHtml(agent.snapshot_date || '-')}</p>
        <p><strong>Agent:</strong> ${escapeHtml(agent.agent_name || '-')}</p>
        <p><strong>30D:</strong> ${escapeHtml(String(agent.win_rate_30d ?? '-'))}% (${escapeHtml(String(agent.predictions_30d ?? 0))} preds)</p>
        <p><strong>90D:</strong> ${escapeHtml(String(agent.win_rate_90d ?? '-'))}% (${escapeHtml(String(agent.predictions_90d ?? 0))} preds)</p>
    ` : '<p class="no-data">No agent daily data available.</p>';
}

async function loadSystemHealth() {
    try {
        const data = await fetchJson(`${API_BASE}/system-health`);
        renderSystemHealth(data);
    } catch (err) {
        auditHealth.innerHTML = `<p class="error-message">${escapeHtml(err.message)}</p>`;
        agentHealth.innerHTML = `<p class="error-message">${escapeHtml(err.message)}</p>`;
    }
}

function renderReports(reports) {
    if (!reports || reports.length === 0) {
        reportRows.innerHTML = '<tr><td colspan="5" class="no-data">No reports yet.</td></tr>';
        return;
    }

    reportRows.innerHTML = reports.map(report => {
        const status = report.status || 'Pending';
        const statusClass = status === 'Processed' ? 'admin-status-processed' : 'admin-status-pending';
        return `
            <tr>
                <td>${escapeHtml(report.filename || '-')}</td>
                <td>${escapeHtml(formatDate(report.upload_date))}</td>
                <td>${escapeHtml(report.language || '-')}</td>
                <td><span class="admin-status-badge ${statusClass}">${escapeHtml(status)}</span></td>
                <td>${escapeHtml(report.summary || '-')}</td>
            </tr>
        `;
    }).join('');
}

async function loadReports() {
    try {
        const data = await fetchJson(`${API_BASE}/reports`);
        renderReports(data.reports || []);
    } catch (err) {
        reportRows.innerHTML = `<tr><td colspan="5" class="error-message">${escapeHtml(err.message)}</td></tr>`;
    }
}

const ALLOWED_UPLOAD_EXTENSIONS = ['.pdf', '.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff', '.tif'];

async function uploadReport(file) {
    if (!file) return;
    const fileName = file.name || '';
    const ext = fileName.toLowerCase().slice(fileName.lastIndexOf('.'));
    if (!ALLOWED_UPLOAD_EXTENSIONS.includes(ext)) {
        setUploadMessage('Only PDF and image files (PNG, JPG, WEBP, BMP, TIFF) are allowed.', true);
        return;
    }

    setUploadMessage(`Uploading ${fileName}...`);
    const body = new FormData();
    body.append('report', file);

    try {
        const result = await fetchJson(`${API_BASE}/reports/upload`, {
            method: 'POST',
            body
        });
        setUploadMessage(`Processed: ${result.filename} (${result.language})`);
        await Promise.all([loadSystemHealth(), loadReports()]);
    } catch (err) {
        setUploadMessage(err.message, true);
    }
}

function bindDropZone() {
    const openPicker = () => fileInput.click();

    dropZone.addEventListener('click', openPicker);
    dropZone.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            openPicker();
        }
    });

    fileInput.addEventListener('change', (event) => {
        const file = event.target.files && event.target.files[0];
        uploadReport(file);
        fileInput.value = '';
    });

    ['dragenter', 'dragover'].forEach(type => {
        dropZone.addEventListener(type, (event) => {
            event.preventDefault();
            event.stopPropagation();
            dropZone.classList.add('drag-over');
        });
    });

    ['dragleave', 'drop'].forEach(type => {
        dropZone.addEventListener(type, (event) => {
            event.preventDefault();
            event.stopPropagation();
            dropZone.classList.remove('drag-over');
        });
    });

    dropZone.addEventListener('drop', (event) => {
        const file = event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files[0];
        uploadReport(file);
    });
}


// ============================================================
// CUSTOM NEWS SOURCES
// ============================================================

const sourceRows = document.getElementById('sourceRows');
const sourceStatus = document.getElementById('sourceStatus');
const addSourceBtn = document.getElementById('addSourceBtn');
const addSourcePanel = document.getElementById('addSourcePanel');
const saveSrcBtn = document.getElementById('saveSrcBtn');
const cancelSrcBtn = document.getElementById('cancelSrcBtn');
const srcType = document.getElementById('srcType');
const srcName = document.getElementById('srcName');
const srcUrl = document.getElementById('srcUrl');
const srcBotToken = document.getElementById('srcBotToken');
const srcChatId = document.getElementById('srcChatId');
const srcBotRow = document.getElementById('srcBotRow');
const srcChatRow = document.getElementById('srcChatRow');
const srcUrlRow = document.getElementById('srcUrlRow');
const srcLang = document.getElementById('srcLang');
const srcInterval = document.getElementById('srcInterval');

const TYPE_LABELS = {
    url: 'URL',
    rss: 'RSS',
    telegram_public: 'Telegram Public',
    telegram_bot: 'Telegram Bot',
    manual: 'Manual',
};

function setSourceStatus(msg, isError = false) {
    sourceStatus.className = isError ? 'admin-upload-status error-message' : 'admin-upload-status no-data';
    sourceStatus.textContent = msg;
}

function renderSources(sources) {
    if (!sources || sources.length === 0) {
        sourceRows.innerHTML = '<tr><td colspan="8" class="no-data">No custom sources yet. Click "Add Source" to get started.</td></tr>';
        return;
    }
    sourceRows.innerHTML = sources.map(s => {
        const activeBadge = s.is_active
            ? '<span class="admin-status-badge admin-status-processed">Active</span>'
            : '<span class="admin-status-badge admin-status-pending">Paused</span>';
        const lastFetched = s.last_fetched_at ? formatDate(s.last_fetched_at) : 'Never';
        const urlDisplay = s.source_url ? `<span title="${escapeHtml(s.source_url)}">${escapeHtml(s.source_url.slice(0, 40))}${s.source_url.length > 40 ? '…' : ''}</span>` : '—';
        const toggleLabel = s.is_active ? 'Pause' : 'Resume';
        return `<tr>
            <td>${escapeHtml(s.name)}</td>
            <td>${escapeHtml(TYPE_LABELS[s.source_type] || s.source_type)}</td>
            <td>${urlDisplay}</td>
            <td>${escapeHtml(s.language || 'auto')}</td>
            <td>${activeBadge}</td>
            <td>${escapeHtml(lastFetched)}</td>
            <td>${escapeHtml(String(s.article_count || 0))}</td>
            <td style="white-space:nowrap;">
                <button class="admin-btn" onclick="fetchSourceNow(${s.id}, this)" ${s.source_type === 'manual' ? 'disabled' : ''}>Fetch Now</button>
                <button class="admin-btn" onclick="toggleSource(${s.id}, ${!s.is_active})">${escapeHtml(toggleLabel)}</button>
                <button class="admin-btn admin-btn-danger" onclick="deleteSource(${s.id})">Delete</button>
            </td>
        </tr>`;
    }).join('');
}

async function loadSources() {
    try {
        const data = await fetchJson(`${API_BASE}/sources`);
        renderSources(data.sources || []);
    } catch (err) {
        sourceRows.innerHTML = `<tr><td colspan="8" class="error-message">${escapeHtml(err.message)}</td></tr>`;
    }
}

async function saveSource() {
    const name = (srcName.value || '').trim();
    const type = srcType.value;
    const url = (srcUrl.value || '').trim();
    const botToken = (srcBotToken.value || '').trim();
    const chatId = (srcChatId.value || '').trim();
    const lang = srcLang.value;
    const interval = srcInterval.value;

    if (!name) return setSourceStatus('Source name is required.', true);
    if (['url', 'rss', 'telegram_public'].includes(type) && !url) {
        return setSourceStatus('URL / channel is required for this source type.', true);
    }
    if (type === 'telegram_bot' && (!botToken || !chatId)) {
        return setSourceStatus('Bot token and Chat ID are required for Telegram Bot sources.', true);
    }

    setSourceStatus('Saving…');
    try {
        await fetchJson(`${API_BASE}/sources`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name, source_type: type, source_url: url || null,
                bot_token: botToken || null, chat_id: chatId || null,
                language: lang, fetch_interval_hours: interval,
            }),
        });
        setSourceStatus(`Source "${name}" added.`);
        addSourcePanel.style.display = 'none';
        srcName.value = '';
        srcUrl.value = '';
        srcBotToken.value = '';
        srcChatId.value = '';
        await loadSources();
    } catch (err) {
        setSourceStatus(err.message, true);
    }
}

async function toggleSource(id, active) {
    try {
        await fetchJson(`${API_BASE}/sources/${id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ is_active: active }),
        });
        await loadSources();
    } catch (err) {
        setSourceStatus(err.message, true);
    }
}

async function deleteSource(id) {
    if (!confirm('Delete this source? All associated articles will also be removed.')) return;
    try {
        await fetchJson(`${API_BASE}/sources/${id}`, { method: 'DELETE' });
        await loadSources();
    } catch (err) {
        setSourceStatus(err.message, true);
    }
}

async function fetchSourceNow(id, btn) {
    if (btn) {
        btn.disabled = true;
        btn.textContent = 'Fetching…';
    }
    setSourceStatus('Fetching…');
    try {
        const result = await fetchJson(`${API_BASE}/sources/${id}/fetch`, { method: 'POST' });
        const msg = result.ok
            ? `Fetched ${result.articles_fetched} items, ${result.articles_new} new for "${result.source_name}"`
            : `Error: ${result.error || 'Unknown error'}`;
        setSourceStatus(msg, !result.ok);
        await loadSources();
    } catch (err) {
        setSourceStatus(err.message, true);
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = 'Fetch Now'; }
    }
}

function updateSourceFormFields() {
    const type = srcType.value;
    const needsUrl = ['url', 'rss', 'telegram_public'].includes(type);
    const needsBot = type === 'telegram_bot';
    srcUrlRow.style.display = (needsUrl || needsBot) ? '' : 'none';
    srcBotRow.style.display = needsBot ? '' : 'none';
    srcChatRow.style.display = needsBot ? '' : 'none';
    srcUrl.placeholder = type === 'telegram_public' ? 't.me/channelname' : 'https://…';
}

function bindSourceForm() {
    addSourceBtn.addEventListener('click', () => {
        const isVisible = addSourcePanel.style.display !== 'none';
        addSourcePanel.style.display = isVisible ? 'none' : '';
    });
    cancelSrcBtn.addEventListener('click', () => { addSourcePanel.style.display = 'none'; });
    saveSrcBtn.addEventListener('click', saveSource);
    srcType.addEventListener('change', updateSourceFormFields);
    updateSourceFormFields();
}

// ============================================================
// WHATSAPP / MANUAL FEED
// ============================================================

const waDropZone = document.getElementById('waDropZone');
const waFileInput = document.getElementById('waFileInput');
const waText = document.getElementById('waText');
const waSourceName = document.getElementById('waSourceName');
const waSubmitBtn = document.getElementById('waSubmitBtn');
const waStatus = document.getElementById('waStatus');
const waFileName = document.getElementById('waFileName');

let waSelectedFile = null;

function setWaStatus(msg, isError = false) {
    waStatus.className = isError ? 'admin-upload-status error-message' : 'admin-upload-status no-data';
    waStatus.textContent = msg;
}

async function submitWhatsApp() {
    const text = (waText.value || '').trim();
    const sourceName = (waSourceName.value || 'Telegram').trim();

    if (!text && !waSelectedFile) {
        return setWaStatus('Please paste text or select a file.', true);
    }

    setWaStatus('Submitting to pipeline…');
    waSubmitBtn.disabled = true;

    const body = new FormData();
    body.append('text', text);
    body.append('source_name', sourceName);
    if (waSelectedFile) body.append('file', waSelectedFile);

    try {
        const result = await fetchJson(`${API_BASE}/sources/manual`, { method: 'POST', body });
        if (result.ok) {
            const sym = (result.symbols_matched || []).join(', ') || 'general market';
            setWaStatus(`Stored and matched to: ${sym} (${result.language || 'auto'}, ${result.sentiment || '—'})`);
            waText.value = '';
            waSelectedFile = null;
            waFileName.textContent = '';
            await loadSources();
        } else {
            setWaStatus(result.error || 'Failed to process content.', true);
        }
    } catch (err) {
        setWaStatus(err.message, true);
    } finally {
        waSubmitBtn.disabled = false;
    }
}

function bindWaDropZone() {
    const openPicker = () => waFileInput.click();

    waDropZone.addEventListener('click', openPicker);
    waDropZone.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openPicker(); }
    });

    waFileInput.addEventListener('change', (e) => {
        waSelectedFile = e.target.files && e.target.files[0];
        waFileName.textContent = waSelectedFile ? waSelectedFile.name : '';
        waFileInput.value = '';
    });

    ['dragenter', 'dragover'].forEach(t => {
        waDropZone.addEventListener(t, (e) => { e.preventDefault(); e.stopPropagation(); waDropZone.classList.add('drag-over'); });
    });
    ['dragleave', 'drop'].forEach(t => {
        waDropZone.addEventListener(t, (e) => { e.preventDefault(); e.stopPropagation(); waDropZone.classList.remove('drag-over'); });
    });
    waDropZone.addEventListener('drop', (e) => {
        waSelectedFile = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
        waFileName.textContent = waSelectedFile ? waSelectedFile.name : '';
    });

    waSubmitBtn.addEventListener('click', submitWhatsApp);
}

// ============================================================
// INFO BANNERS (dismissible hints for new admins)
// ============================================================

const DISMISSED_HINTS_KEY = 'admin_dismissed_hints';

function loadDismissedHints() {
    try { return new Set(JSON.parse(localStorage.getItem(DISMISSED_HINTS_KEY) || '[]')); }
    catch (_) { return new Set(); }
}

function initInfoBanners() {
    const dismissed = loadDismissedHints();
    document.querySelectorAll('.admin-info-banner').forEach(banner => {
        const key = banner.dataset.hint;
        if (key && dismissed.has(key)) banner.classList.add('dismissed');
    });

    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.admin-info-dismiss');
        if (!btn) return;
        const key = btn.dataset.dismiss;
        const banner = btn.closest('.admin-info-banner');
        if (banner) banner.classList.add('dismissed');
        if (key) {
            const set = loadDismissedHints();
            set.add(key);
            localStorage.setItem(DISMISSED_HINTS_KEY, JSON.stringify([...set]));
        }
    });
}

// ============================================================
// TAB SHOW / HIDE
// ============================================================

const TAB_DEFS = [
    { id: 'tab-health',            label: 'System Health' },
    { id: 'tab-kb',                label: 'Knowledge Base' },
    { id: 'tab-reports',           label: 'Reports' },
    { id: 'tab-prices',            label: 'Prices' },
    { id: 'tab-sources',           label: 'News Sources' },
    { id: 'tab-telegram',          label: 'Telegram Feed' },
    { id: 'tab-forecast-accuracy', label: 'Forecast Accuracy' },
    { id: 'tab-ask-reports',       label: 'Ask Reports' },
    { id: 'tab-settings',          label: 'Settings' },
];

const HIDDEN_TABS_KEY = 'admin_hidden_tabs';
const ACTIVE_TAB_KEY  = 'admin_active_tab';

function loadHiddenTabs() {
    try { return new Set(JSON.parse(localStorage.getItem(HIDDEN_TABS_KEY) || '[]')); }
    catch (_) { return new Set(); }
}

function saveHiddenTabs(hiddenSet) {
    localStorage.setItem(HIDDEN_TABS_KEY, JSON.stringify([...hiddenSet]));
}

function applyTabVisibility(hiddenSet) {
    TAB_DEFS.forEach(({ id }) => {
        const btn = document.querySelector(`[data-tab="${id}"]`);
        if (btn) btn.dataset.hidden = hiddenSet.has(id) ? 'true' : 'false';
    });
}

function switchTab(tabId) {
    document.querySelectorAll('.admin-tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabId);
        btn.setAttribute('aria-selected', btn.dataset.tab === tabId ? 'true' : 'false');
    });
    document.querySelectorAll('.admin-tab-panel').forEach(panel => {
        panel.classList.toggle('active', panel.id === tabId);
    });
    localStorage.setItem(ACTIVE_TAB_KEY, tabId);
}

function firstVisibleTab(hiddenSet) {
    for (const { id } of TAB_DEFS) {
        if (!hiddenSet.has(id)) return id;
    }
    return TAB_DEFS[0].id;
}

function buildTabCheckboxes(hiddenSet) {
    const container = document.getElementById('tabCheckboxes');
    if (!container) return;
    container.innerHTML = TAB_DEFS.map(({ id, label }) => {
        const checked = !hiddenSet.has(id) ? 'checked' : '';
        return `<label>
            <input type="checkbox" data-tab-toggle="${escapeHtml(id)}" ${checked}>
            ${escapeHtml(label)}
        </label>`;
    }).join('');

    container.querySelectorAll('input[data-tab-toggle]').forEach(cb => {
        cb.addEventListener('change', () => {
            const hidden = loadHiddenTabs();
            if (cb.checked) { hidden.delete(cb.dataset.tabToggle); }
            else            { hidden.add(cb.dataset.tabToggle); }

            // Keep at least one tab visible
            const allHidden = TAB_DEFS.every(({ id }) => hidden.has(id));
            if (allHidden) { hidden.delete(cb.dataset.tabToggle); cb.checked = true; }

            saveHiddenTabs(hidden);
            applyTabVisibility(hidden);

            // If the active tab just got hidden, switch to first visible
            const activeId = localStorage.getItem(ACTIVE_TAB_KEY) || TAB_DEFS[0].id;
            if (hidden.has(activeId)) switchTab(firstVisibleTab(hidden));
        });
    });
}

function bindTabBar() {
    document.getElementById('adminTabList').addEventListener('click', (e) => {
        const btn = e.target.closest('.admin-tab-btn');
        if (btn && btn.dataset.tab) switchTab(btn.dataset.tab);
    });

    const configBtn   = document.getElementById('tabConfigBtn');
    const configPanel = document.getElementById('tabConfigPanel');

    configBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        const isOpen = !configPanel.hidden;
        configPanel.hidden = isOpen;
        configBtn.setAttribute('aria-expanded', String(!isOpen));
    });

    document.addEventListener('click', (e) => {
        if (!configPanel.hidden && !configPanel.contains(e.target) && e.target !== configBtn) {
            configPanel.hidden = true;
            configBtn.setAttribute('aria-expanded', 'false');
        }
    });
}

function initTabs() {
    const hidden = loadHiddenTabs();
    applyTabVisibility(hidden);
    buildTabCheckboxes(hidden);
    bindTabBar();
    const saved  = localStorage.getItem(ACTIVE_TAB_KEY);
    const target = (saved && !hidden.has(saved)) ? saved : firstVisibleTab(hidden);
    switchTab(target);
}

// ============================================================
// BOOTSTRAP
// ============================================================
// LATEST STOCK PRICES
// ============================================================

// Minimal company name map — ticker -> display name
const COMPANY_NAMES = {
    // EGX
    'COMI.CA': 'Commercial International Bank',
    'HRHO.CA': 'Heliopolis Housing',
    'ETEL.CA': 'Telecom Egypt',
    'EFIC.CA': 'EFG Hermes',
    'PHDC.CA': 'Palm Hills Developments',
    'CLHO.CA': 'City Edge Developments',
    'MNHD.CA': 'Madinet Nasr Housing',
    'SKPC.CA': 'Sidi Kerir Petrochemicals',
    'SWDY.CA': 'El Sewedy Electric',
    'ESRS.CA': 'Ezz Steel',
    'EGTS.CA': 'Egyptian Gas',
    'ORWE.CA': 'Oriental Weavers',
    'ISPH.CA': 'Ibnsina Pharma',
    'AMOC.CA': 'Alexandria Mineral Oils',
    'ABUK.CA': 'Abu Kir Fertilizers',
    'HELI.CA': 'Helios Investment',
    // US
    'AAPL':  'Apple',
    'MSFT':  'Microsoft',
    'GOOGL': 'Alphabet',
    'AMZN':  'Amazon',
    'TSLA':  'Tesla',
    'NVDA':  'NVIDIA',
    'META':  'Meta',
    'JPM':   'JPMorgan Chase',
    'GS':    'Goldman Sachs',
    'XOM':   'ExxonMobil',
};

let _allPriceRows = [];    // full dataset for client-side search

function formatChange(change, pct) {
    if (change == null || isNaN(change)) return '<td class="num">—</td><td class="num">—</td>';
    const sign  = change >= 0 ? '+' : '';
    const cls   = change >= 0 ? 'price-up' : 'price-down';
    const arrow = change >= 0 ? '&#9650;' : '&#9660;';
    return `<td class="num ${cls}">${sign}${change.toFixed(2)}</td>
            <td class="num ${cls}">${arrow} ${sign}${pct.toFixed(2)}%</td>`;
}

function formatVolume(v) {
    if (v == null || isNaN(v)) return '—';
    if (v >= 1_000_000) return (v / 1_000_000).toFixed(2) + 'M';
    if (v >= 1_000)     return (v / 1_000).toFixed(1) + 'K';
    return String(v);
}

function renderPriceRows(rows) {
    const tbody = document.getElementById('priceRows');
    if (!tbody) return;
    if (!rows || rows.length === 0) {
        tbody.innerHTML = '<tr><td colspan="10" class="no-data">No price data available yet. Data is collected Mon–Fri at 4:30 PM EST.</td></tr>';
        return;
    }
    tbody.innerHTML = rows.map(r => {
        const name   = COMPANY_NAMES[r.symbol] || '—';
        const fmt    = v => (v != null && !isNaN(v)) ? Number(v).toFixed(2) : '—';
        const open   = fmt(r.open);
        const high   = fmt(r.high);
        const low    = fmt(r.low);
        const close  = fmt(r.close);
        const vol    = formatVolume(r.volume);
        const change = r.change != null ? Number(r.change) : null;
        const pct    = r.change_pct != null ? Number(r.change_pct) : null;
        const changeCells = (change != null && pct != null)
            ? formatChange(change, pct)
            : '<td class="num">—</td><td class="num">—</td>';
        return `<tr>
            <td><strong>${escapeHtml(r.symbol)}</strong></td>
            <td>${escapeHtml(name)}</td>
            <td class="num">${escapeHtml(open)}</td>
            <td class="num">${escapeHtml(high)}</td>
            <td class="num">${escapeHtml(low)}</td>
            <td class="num">${escapeHtml(close)}</td>
            ${changeCells}
            <td class="num">${escapeHtml(vol)}</td>
            <td>${escapeHtml(r.date || '—')}</td>
        </tr>`;
    }).join('');
}

function filterPrices(query) {
    if (!query) return renderPriceRows(_allPriceRows);
    const q = query.toLowerCase();
    const filtered = _allPriceRows.filter(r =>
        r.symbol.toLowerCase().includes(q) ||
        (COMPANY_NAMES[r.symbol] || '').toLowerCase().includes(q)
    );
    renderPriceRows(filtered);
}

async function loadPrices() {
    const tbody = document.getElementById('priceRows');
    const dateEl = document.getElementById('pricesDate');
    if (tbody) tbody.innerHTML = '<tr><td colspan="7" class="no-data">Loading…</td></tr>';
    try {
        const rows = await fetchJson('/api/prices');
        _allPriceRows = rows || [];
        renderPriceRows(_allPriceRows);
        if (dateEl && _allPriceRows.length > 0) {
            const latest = _allPriceRows.reduce((a, b) => (a.date > b.date ? a : b)).date || '';
            dateEl.textContent = latest ? `As of: ${latest}` : '';
        }
    } catch (err) {
        if (tbody) tbody.innerHTML = `<tr><td colspan="7" class="error-message">${escapeHtml(err.message)}</td></tr>`;
    }
}

function bindPricesTab() {
    const searchEl  = document.getElementById('pricesSearch');
    const refreshBtn = document.getElementById('pricesRefreshBtn');
    if (searchEl)  searchEl.addEventListener('input', () => filterPrices(searchEl.value.trim()));
    if (refreshBtn) refreshBtn.addEventListener('click', loadPrices);

    // Load prices when the tab is first activated
    document.getElementById('adminTabList').addEventListener('click', (e) => {
        const btn = e.target.closest('.admin-tab-btn');
        if (btn && btn.dataset.tab === 'tab-prices' && _allPriceRows.length === 0) {
            loadPrices();
        }
        if (btn && btn.dataset.tab === 'tab-forecast-accuracy') {
            loadForecastAccuracy();
        }
        if (btn && btn.dataset.tab === 'tab-ask-reports') {
            loadRagEmbedStatus();
            loadRagDocuments();
        }
    });
}

// ============================================================
// FORECAST ACCURACY TAB
// ============================================================

let _faLoaded = false;

async function loadForecastAccuracy() {
    if (_faLoaded) return;
    _faLoaded = true;

    const setVal = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
    setVal('faStatTotal',     '…');
    setVal('faStatEvaluated', '…');
    setVal('faStatAvgError',  '…');
    setVal('faStatHitRate',   '…');

    try {
        const data = await fetchJson(`${API_BASE}/forecast-accuracy`);

        // Summary
        setVal('faStatTotal',     data.summary?.total_forecasts    ?? '—');
        setVal('faStatEvaluated', data.summary?.total_evaluated    ?? '—');
        const avgErr = data.summary?.avg_error_pct;
        setVal('faStatAvgError',  avgErr != null ? avgErr.toFixed(2) + '%' : '—');
        const hitRate = data.summary?.within_10pct_rate;
        setVal('faStatHitRate',   hitRate != null ? (hitRate * 100).toFixed(1) + '%' : '—');

        // Per-stock table
        const stockBody = document.getElementById('faStockTableBody');
        if (stockBody) {
            const rows = data.by_stock || [];
            if (rows.length === 0) {
                stockBody.innerHTML = '<tr><td colspan="6" class="admin-muted" style="text-align:center;padding:20px;">No evaluated forecasts yet. Evaluations run automatically after target dates pass.</td></tr>';
            } else {
                stockBody.innerHTML = rows.map(r => `<tr>
                    <td><strong>${escapeHtml(r.symbol)}</strong></td>
                    <td>${r.total_forecasts}</td>
                    <td class="num">${r.avg_expected_pct != null ? r.avg_expected_pct.toFixed(2) + '%' : '—'}</td>
                    <td class="num">${r.avg_actual_pct != null ? r.avg_actual_pct.toFixed(2) + '%' : '—'}</td>
                    <td class="num">${r.avg_error_pct != null ? r.avg_error_pct.toFixed(2) + '%' : '—'}</td>
                    <td class="num">${r.within_10pct_rate != null ? (r.within_10pct_rate * 100).toFixed(1) + '%' : '—'}</td>
                </tr>`).join('');
            }
        }

        // Recent evaluations table
        const recentBody = document.getElementById('faRecentTableBody');
        if (recentBody) {
            const evals = data.recent_evaluations || [];
            if (evals.length === 0) {
                recentBody.innerHTML = '<tr><td colspan="7" class="admin-muted" style="text-align:center;padding:20px;">No evaluations recorded yet.</td></tr>';
            } else {
                recentBody.innerHTML = evals.map(e => {
                    const errPct = e.error_pct != null ? e.error_pct.toFixed(2) + '%' : '—';
                    const within = e.within_10pct ? '<span style="color:var(--green)">✓ Within 10%</span>' : '<span style="color:var(--red)">✗ Outside 10%</span>';
                    return `<tr>
                        <td>${escapeHtml(e.run_date || '—')}</td>
                        <td><strong>${escapeHtml(e.symbol)}</strong></td>
                        <td>${escapeHtml(e.target_date || '—')}</td>
                        <td class="num">${e.expected_return_pct != null ? e.expected_return_pct.toFixed(2) + '%' : '—'}</td>
                        <td class="num">${e.actual_return_pct != null ? e.actual_return_pct.toFixed(2) + '%' : '—'}</td>
                        <td class="num">${errPct}</td>
                        <td>${within}</td>
                    </tr>`;
                }).join('');
            }
        }
    } catch (err) {
        const stockBody = document.getElementById('faStockTableBody');
        if (stockBody) stockBody.innerHTML = `<tr><td colspan="6" class="error-message">${escapeHtml(err.message)}</td></tr>`;
        setVal('faStatTotal', 'Error');
    }
}

// ============================================================
// FRONTEND TAB VISIBILITY (Settings tab)
// ============================================================

const FRONTEND_HIDDEN_TABS_KEY = 'xmore_hidden_frontend_tabs';

// All tabs that exist in the main dashboard
const FRONTEND_TAB_DEFS = [
    { id: 'predictions', label: 'Predictions',  locked: true  },
    { id: 'briefing',    label: 'Briefing',     locked: false },
    { id: 'trades',      label: 'Trades',       locked: false },
    { id: 'portfolio',   label: 'Portfolio',    locked: false },
    { id: 'watchlist',   label: 'Watchlist',    locked: false },
    { id: 'consensus',   label: 'Consensus',    locked: false },
    { id: 'performance', label: 'Performance',  locked: false },
    { id: 'results',     label: 'Results',      locked: false },
    { id: 'prices',      label: 'Prices',       locked: false },
    { id: 'timemachine', label: 'Time Machine', locked: false },
];

function loadFrontendHidden() {
    try { return new Set(JSON.parse(localStorage.getItem(FRONTEND_HIDDEN_TABS_KEY) || '[]')); }
    catch (_) { return new Set(); }
}

function saveFrontendHidden(hiddenSet) {
    // Never store 'predictions' as hidden
    hiddenSet.delete('predictions');
    localStorage.setItem(FRONTEND_HIDDEN_TABS_KEY, JSON.stringify([...hiddenSet]));
}

function renderFrontendTabToggles() {
    const container = document.getElementById('frontendTabToggles');
    if (!container) return;
    const hidden = loadFrontendHidden();

    container.innerHTML = FRONTEND_TAB_DEFS.map(({ id, label, locked }) => {
        const checked  = !hidden.has(id) ? 'checked' : '';
        const disabled = locked ? 'disabled' : '';
        const lockedNote = locked ? ' <span class="admin-muted">(always visible)</span>' : '';
        return `<div class="admin-settings-toggle-row">
            <label class="admin-toggle-label">
                <span class="admin-toggle-name">${escapeHtml(label)}${lockedNote}</span>
                <span class="admin-toggle-switch">
                    <input type="checkbox" data-frontend-tab="${escapeHtml(id)}" ${checked} ${disabled}>
                    <span class="admin-toggle-track"></span>
                </span>
            </label>
        </div>`;
    }).join('');

    container.querySelectorAll('input[data-frontend-tab]').forEach(cb => {
        cb.addEventListener('change', () => {
            const hidden = loadFrontendHidden();
            if (cb.checked) { hidden.delete(cb.dataset.frontendTab); }
            else            { hidden.add(cb.dataset.frontendTab); }
            saveFrontendHidden(hidden);
        });
    });
}

function bindSettingsTab() {
    const resetBtn = document.getElementById('resetFrontendTabsBtn');
    if (!resetBtn) return;
    resetBtn.addEventListener('click', () => {
        localStorage.removeItem(FRONTEND_HIDDEN_TABS_KEY);
        renderFrontendTabToggles();
    });

    // Re-render toggles when the Settings tab is activated (picks up fresh state)
    document.getElementById('adminTabList').addEventListener('click', (e) => {
        const btn = e.target.closest('.admin-tab-btn');
        if (btn && btn.dataset.tab === 'tab-settings') renderFrontendTabToggles();
    });
}

// ============================================================
// RAG — ASK REPORTS TAB
// ============================================================

const RAG_BASE = '/api/rag';

async function loadRagEmbedStatus() {
    const statusEl = document.getElementById('ragEmbedStatus');
    if (!statusEl) return;
    try {
        const data = await fetchJson(`${RAG_BASE}/embed/status`);
        statusEl.textContent = `${data.chunks || 0} chunks embedded from ${data.reports || 0} report(s).`;
    } catch (e) {
        statusEl.textContent = 'Could not load embed status.';
    }
}

async function loadRagDocuments() {
    const tbody = document.getElementById('ragDocsBody');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="6" class="admin-muted" style="text-align:center;padding:16px;">Loading…</td></tr>';
    try {
        const data = await fetchJson(`${RAG_BASE}/documents`);
        const docs = data.documents || [];
        if (!docs.length) {
            tbody.innerHTML = '<tr><td colspan="6" class="no-data" style="text-align:center;padding:20px;">No documents uploaded yet. Upload a PDF in the Knowledge Base tab.</td></tr>';
            return;
        }
        tbody.innerHTML = docs.map((d, i) => {
            const total = Number(d.total_chunks) || 0;
            const embedded = Number(d.embedded_chunks) || 0;
            let badge;
            if (total === 0) {
                badge = '<span class="admin-status-badge admin-status-pending">Not embedded</span>';
            } else if (embedded < total) {
                badge = `<span class="admin-status-badge" style="background:#f59e0b20;color:#f59e0b;border:1px solid #f59e0b40;">Partial ${embedded}/${total}</span>`;
            } else {
                badge = `<span class="admin-status-badge admin-status-processed">&#10003; ${total} chunks</span>`;
            }
            const langBadge = `<span class="admin-status-badge" style="background:var(--accent);color:#fff;opacity:.85;">${escapeHtml(d.language || 'EN')}</span>`;
            return `<tr>
                <td style="color:var(--text-muted);font-size:12px;">${d.id}</td>
                <td style="font-weight:500;word-break:break-all;">${escapeHtml(d.filename)}</td>
                <td style="white-space:nowrap;">${escapeHtml(formatDate(d.upload_date))}</td>
                <td>${langBadge}</td>
                <td style="text-align:center;">${total}</td>
                <td>${badge}</td>
            </tr>`;
        }).join('');
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="6" class="error-message" style="text-align:center;padding:16px;">${escapeHtml(err.message)}</td></tr>`;
    }
}

async function triggerEmbed() {
    const btn = document.getElementById('ragEmbedBtn');
    const statusEl = document.getElementById('ragEmbedStatus');
    if (btn) { btn.disabled = true; btn.textContent = 'Embedding…'; }
    try {
        await fetchJson(`${RAG_BASE}/embed`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
        if (statusEl) statusEl.textContent = 'Embedding started — check server logs. Refresh status in a minute.';
    } catch (e) {
        if (statusEl) statusEl.textContent = `Embed error: ${e.message}`;
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = '↻ Embed Documents'; }
    }
}

async function askReports() {
    const questionEl = document.getElementById('ragQuestion');
    const answerBox = document.getElementById('ragAnswerBox');
    const answerEl = document.getElementById('ragAnswer');
    const sourcesEl = document.getElementById('ragSources');
    const errorEl = document.getElementById('ragError');
    const askBtn = document.getElementById('ragAskBtn');

    const question = questionEl ? questionEl.value.trim() : '';
    if (!question) return;

    if (askBtn) { askBtn.disabled = true; askBtn.textContent = 'Thinking…'; }
    if (answerBox) answerBox.style.display = 'none';
    if (errorEl) errorEl.style.display = 'none';

    try {
        const data = await fetchJson(`${RAG_BASE}/ask`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question })
        });

        if (answerEl) answerEl.textContent = data.answer || '(No answer returned)';
        if (sourcesEl) {
            const srcs = (data.sources || []).map(s =>
                `<span style="display:inline-block;margin-right:12px;">📄 ${escapeHtml(s.filename)} (similarity: ${s.similarity})</span>`
            ).join('');
            sourcesEl.innerHTML = srcs ? `<strong>Sources:</strong> ${srcs}` : '';
        }
        if (answerBox) answerBox.style.display = 'block';
    } catch (e) {
        if (errorEl) { errorEl.textContent = `Error: ${e.message}`; errorEl.style.display = 'block'; }
    } finally {
        if (askBtn) { askBtn.disabled = false; askBtn.textContent = 'Ask'; }
    }
}

// ============================================================
// ADMIN TAB CONFIG (Settings tab registry)
// ============================================================

// ============================================================

async function bootstrap() {
    applyThemeAndLanguage();
    initInfoBanners();
    // Always bind UI (event listeners are harmless before content is visible)
    initTabs();
    bindDropZone();
    bindLoginForm();
    bindSourceForm();
    bindWaDropZone();
    bindPricesTab();
    renderFrontendTabToggles();
    bindSettingsTab();

    if (getToken()) {
        showMainContent();
        await Promise.all([loadSystemHealth(), loadReports(), loadSources()]);
        const activePanel = document.querySelector('.admin-tab-panel.active');
        if (activePanel && activePanel.id === 'tab-prices') loadPrices();
    } else {
        showLoginForm();
    }
}

bootstrap();
