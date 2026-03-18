(function () {
    'use strict';

    const EXISTING_WIDGET_ID = 'chatToggleBtn';
    const ROOT_ID = 'xAssistantRoot';

    if (document.getElementById(ROOT_ID)) return;

    // Do not duplicate on dashboard page where the original chat widget already exists.
    if (document.getElementById(EXISTING_WIDGET_ID)) return;

    const I18N = {
        en: {
            title: 'AI Research Assistant',
            openLabel: 'Open AI Research Assistant',
            closeLabel: 'Close assistant',
            placeholder: 'Ask about EGX stocks, ETFs, or macro...',
            welcome: "Hello! I'm your EGX research assistant. Ask me about stocks, news, or market context.",
            thinking: 'Thinking...',
            macroChip: 'Macro Brief',
            moversChip: 'Top Movers',
            buysChip: 'Buy Signals',
            moversPrompt: 'What are the top movers on EGX today?',
            buysPrompt: 'What are the strongest buy signals today?',
            macroPrompt: 'EGX macro brief for today',
            sendLabel: 'Send',
            fallbackError: 'Could not reach the assistant right now.'
        },
        ar: {
            title: 'مساعد البحث الذكي',
            openLabel: 'افتح مساعد البحث الذكي',
            closeLabel: 'إغلاق المساعد',
            placeholder: 'اسأل عن أسهم EGX أو الصناديق أو الماكرو...',
            welcome: 'مرحباً! أنا مساعد البحث لأسواق EGX. اسألني عن الأسهم أو الأخبار أو سياق السوق.',
            thinking: 'جاري التفكير...',
            macroChip: 'ملخص ماكرو',
            moversChip: 'الأكثر حركة',
            buysChip: 'إشارات الشراء',
            moversPrompt: 'ما هي أكثر الأسهم حركة في EGX اليوم؟',
            buysPrompt: 'ما هي أقوى إشارات الشراء اليوم؟',
            macroPrompt: 'ملخص ماكرو EGX لليوم',
            sendLabel: 'إرسال',
            fallbackError: 'تعذر الاتصال بالمساعد الآن.'
        }
    };

    const state = {
        open: false,
        lang: getCurrentLang(),
        typingEl: null
    };

    function getCurrentLang() {
        try {
            const raw = (localStorage.getItem('lang') || localStorage.getItem('docs-lang') || document.documentElement.lang || 'en').toLowerCase();
            return raw === 'ar' ? 'ar' : 'en';
        } catch (_) {
            return 'en';
        }
    }

    function t(key) {
        const dict = I18N[state.lang] || I18N.en;
        return dict[key] || I18N.en[key] || key;
    }

    function esc(value) {
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function buildWidget() {
        const root = document.createElement('div');
        root.id = ROOT_ID;
        root.innerHTML = `
            <button id="xAssistantFab" class="x-assistant-fab" type="button" aria-label="${esc(t('openLabel'))}" title="${esc(t('openLabel'))}">
                <span class="x-assistant-fab-icon" aria-hidden="true">
                    <svg viewBox="0 0 24 24" width="28" height="28" fill="none">
                        <path d="M4 12a8 8 0 0 1 8-8h6a2 2 0 0 1 2 2v6a8 8 0 0 1-8 8h-1l-4 3v-4A8 8 0 0 1 4 12Z" fill="currentColor" opacity=".93"></path>
                        <circle cx="10" cy="12" r="1.4" fill="#0b1220"></circle>
                        <circle cx="14" cy="12" r="1.4" fill="#0b1220"></circle>
                        <circle cx="18" cy="12" r="1.4" fill="#0b1220"></circle>
                    </svg>
                </span>
            </button>
            <section id="xAssistantPanel" class="x-assistant-panel x-assistant-hidden" role="dialog" aria-label="${esc(t('title'))}">
                <div class="x-assistant-header">
                    <div class="x-assistant-title-wrap">
                        <span class="x-assistant-fab-icon" aria-hidden="true">
                            <svg viewBox="0 0 24 24" width="18" height="18" fill="none">
                                <path d="M4 12a8 8 0 0 1 8-8h6a2 2 0 0 1 2 2v6a8 8 0 0 1-8 8h-1l-4 3v-4A8 8 0 0 1 4 12Z" fill="currentColor"></path>
                            </svg>
                        </span>
                        <span id="xAssistantTitle" class="x-assistant-title">${esc(t('title'))}</span>
                    </div>
                    <button id="xAssistantClose" class="x-assistant-close" type="button" aria-label="${esc(t('closeLabel'))}">&times;</button>
                </div>
                <div id="xAssistantMessages" class="x-assistant-messages" aria-live="polite"></div>
                <div class="x-assistant-chips">
                    <button class="x-assistant-chip" type="button" data-chip="macro">${esc(t('macroChip'))}</button>
                    <button class="x-assistant-chip" type="button" data-chip="movers">${esc(t('moversChip'))}</button>
                    <button class="x-assistant-chip" type="button" data-chip="buys">${esc(t('buysChip'))}</button>
                </div>
                <div class="x-assistant-input-row">
                    <input id="xAssistantInput" class="x-assistant-input" type="text" maxlength="500" placeholder="${esc(t('placeholder'))}" autocomplete="off">
                    <button id="xAssistantSend" class="x-assistant-send" type="button" aria-label="${esc(t('sendLabel'))}">&#10148;</button>
                </div>
            </section>
        `;
        document.body.appendChild(root);
    }

    function refreshLanguage() {
        state.lang = getCurrentLang();

        const fab = document.getElementById('xAssistantFab');
        const panel = document.getElementById('xAssistantPanel');
        const title = document.getElementById('xAssistantTitle');
        const close = document.getElementById('xAssistantClose');
        const input = document.getElementById('xAssistantInput');
        const send = document.getElementById('xAssistantSend');
        const chips = document.querySelectorAll('#xAssistantRoot .x-assistant-chip');

        if (fab) {
            fab.setAttribute('aria-label', t('openLabel'));
            fab.setAttribute('title', t('openLabel'));
        }
        if (panel) {
            panel.setAttribute('aria-label', t('title'));
            panel.setAttribute('dir', state.lang === 'ar' ? 'rtl' : 'ltr');
        }
        if (title) title.textContent = t('title');
        if (close) close.setAttribute('aria-label', t('closeLabel'));
        if (input) input.placeholder = t('placeholder');
        if (send) send.setAttribute('aria-label', t('sendLabel'));
        if (chips && chips.length === 3) {
            chips[0].textContent = t('macroChip');
            chips[1].textContent = t('moversChip');
            chips[2].textContent = t('buysChip');
        }
    }

    function appendMessage(role, text, sources) {
        const messages = document.getElementById('xAssistantMessages');
        if (!messages) return;

        const msg = document.createElement('div');
        msg.className = `x-assistant-msg x-assistant-msg-${role}`;
        msg.textContent = text;

        if (Array.isArray(sources) && sources.length > 0) {
            const srcWrap = document.createElement('div');
            srcWrap.className = 'x-assistant-sources';
            srcWrap.innerHTML = sources.slice(0, 5).map(src => {
                const label = esc(src.title || src.source || 'Source');
                const href = src.url ? esc(src.url) : '';
                if (href) {
                    return `<a class="x-assistant-source" href="${href}" target="_blank" rel="noopener">${label}</a>`;
                }
                return `<span class="x-assistant-source">${label}</span>`;
            }).join('');
            msg.appendChild(srcWrap);
        }

        messages.appendChild(msg);
        messages.scrollTop = messages.scrollHeight;
    }

    function showTyping() {
        const messages = document.getElementById('xAssistantMessages');
        if (!messages) return null;
        const bubble = document.createElement('div');
        bubble.className = 'x-assistant-msg x-assistant-msg-ai x-assistant-msg-typing';
        bubble.textContent = t('thinking');
        messages.appendChild(bubble);
        messages.scrollTop = messages.scrollHeight;
        return bubble;
    }

    function setOpen(nextOpen) {
        const panel = document.getElementById('xAssistantPanel');
        const input = document.getElementById('xAssistantInput');
        if (!panel) return;
        state.open = nextOpen;
        panel.classList.toggle('x-assistant-hidden', !nextOpen);
        if (nextOpen && input) {
            setTimeout(function () { input.focus(); }, 50);
        }
    }

    async function sendMessage(prefill) {
        const input = document.getElementById('xAssistantInput');
        const send = document.getElementById('xAssistantSend');
        if (!input || !send) return;

        if (typeof prefill === 'string') input.value = prefill;
        const question = input.value.trim();
        if (!question) return;

        input.value = '';
        appendMessage('user', question);
        send.disabled = true;
        state.typingEl = showTyping();

        try {
            const res = await fetch('/api/rag/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    question: question,
                    language: state.lang,
                    source_mode: 'hybrid'
                })
            });
            const data = await res.json().catch(function () { return {}; });
            if (state.typingEl) state.typingEl.remove();
            state.typingEl = null;

            if (!res.ok || data.error) {
                appendMessage('ai', (data && data.error) ? data.error : t('fallbackError'));
                return;
            }
            appendMessage('ai', data.answer || '', data.sources || []);
        } catch (_) {
            if (state.typingEl) state.typingEl.remove();
            state.typingEl = null;
            appendMessage('ai', t('fallbackError'));
        } finally {
            send.disabled = false;
            input.focus();
        }
    }

    function bindEvents() {
        const fab = document.getElementById('xAssistantFab');
        const close = document.getElementById('xAssistantClose');
        const send = document.getElementById('xAssistantSend');
        const input = document.getElementById('xAssistantInput');
        const chips = document.querySelectorAll('#xAssistantRoot .x-assistant-chip');

        if (fab) fab.addEventListener('click', function () { setOpen(!state.open); });
        if (close) close.addEventListener('click', function () { setOpen(false); });
        if (send) send.addEventListener('click', function () { sendMessage(); });
        if (input) {
            input.addEventListener('keydown', function (e) {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage();
                }
            });
        }
        if (chips && chips.length) {
            chips.forEach(function (chip) {
                chip.addEventListener('click', function () {
                    const key = chip.getAttribute('data-chip');
                    if (key === 'macro') sendMessage(t('macroPrompt'));
                    if (key === 'movers') sendMessage(t('moversPrompt'));
                    if (key === 'buys') sendMessage(t('buysPrompt'));
                });
            });
        }

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && state.open) setOpen(false);
        });

        window.addEventListener('storage', function (e) {
            if (e.key === 'lang' || e.key === 'docs-lang') refreshLanguage();
        });
    }

    function init() {
        buildWidget();
        refreshLanguage();
        bindEvents();
        appendMessage('ai', t('welcome'));
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
