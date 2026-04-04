(function () {
    'use strict';

    const EXISTING_WIDGET_ID = 'chatToggleBtn';
    const ROOT_ID = 'xAssistantRoot';

    if (document.getElementById(ROOT_ID)) return;

    // Do not duplicate on pages where another chat widget already exists.
    if (document.getElementById(EXISTING_WIDGET_ID)) return;

    const I18N = {
        en: {
            title: 'Research Assistant',
            openLabel: 'Open Research Assistant',
            closeLabel: 'Close assistant',
            placeholder: 'Ask about Tadawul stocks, sectors, or macro...',
            welcome: "Hello! I'm your Tadawul research assistant. Ask me about Saudi stocks, news, or market context.",
            thinking: 'Thinking...',
            macroChip: 'Macro Brief',
            moversChip: 'Top Movers',
            buysChip: 'Buy Signals',
            moversPrompt: 'What are the top movers on Tadawul today?',
            buysPrompt: 'What are the strongest buy signals today?',
            macroPrompt: 'Tadawul macro brief for today',
            sendLabel: 'Send',
            voiceLabel: 'Voice input',
            listeningLabel: 'Listening...',
            micErrorLabel: 'Microphone error. Try again.',
            micUnsupportedLabel: 'Voice input not supported in this browser',
            fallbackError: 'Could not reach the assistant right now.',
            liveData: 'Live data'
        },
        ar: {
            title: 'مساعد البحث',
            openLabel: 'افتح مساعد البحث',
            closeLabel: 'إغلاق المساعد',
            placeholder: 'اسأل عن أسهم تداول أو القطاعات أو الماكرو...',
            welcome: 'مرحباً! أنا مساعد البحث لسوق تداول. اسألني عن الأسهم السعودية أو الأخبار أو سياق السوق.',
            thinking: 'جاري التفكير...',
            macroChip: 'ملخص ماكرو',
            moversChip: 'الأكثر حركة',
            buysChip: 'إشارات الشراء',
            moversPrompt: 'ما هي أكثر الأسهم حركة في تداول اليوم؟',
            buysPrompt: 'ما هي أقوى إشارات الشراء اليوم؟',
            macroPrompt: 'ملخص ماكرو تداول لليوم',
            sendLabel: 'إرسال',
            voiceLabel: 'إدخال صوتي',
            listeningLabel: 'جارٍ الاستماع...',
            micErrorLabel: 'خطأ في الميكروفون. حاول مرة أخرى.',
            micUnsupportedLabel: 'الإدخال الصوتي غير مدعوم في هذا المتصفح',
            fallbackError: 'تعذر الاتصال بالمساعد الآن.',
            liveData: 'بيانات مباشرة'
        }
    };

    const state = {
        open: false,
        lang: getCurrentLang(),
        typingEl: null,
        listening: false,
        recognition: null,
        manualStop: false
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
                <span class="x-assistant-fab-label" aria-hidden="true">Ask</span>
            </button>
            <section id="xAssistantPanel" class="x-assistant-panel x-assistant-hidden" role="dialog" aria-label="${esc(t('title'))}">
                <div class="x-assistant-header">
                    <div class="x-assistant-title-wrap">
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
                    <button id="xAssistantMic" class="x-assistant-mic" type="button" aria-label="${esc(t('voiceLabel'))}">
                        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" aria-hidden="true">
                            <rect x="9" y="2" width="6" height="11" rx="3" fill="currentColor"/>
                            <path d="M5 10a7 7 0 0 0 14 0" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                            <line x1="12" y1="21" x2="12" y2="17" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                            <line x1="8" y1="21" x2="16" y2="21" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                        </svg>
                    </button>
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
        const mic = document.getElementById('xAssistantMic');
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
        if (input && !state.listening) input.placeholder = t('placeholder');
        if (send) send.setAttribute('aria-label', t('sendLabel'));
        if (mic) {
            mic.setAttribute('aria-label', state.listening ? t('listeningLabel') : t('voiceLabel'));
            if (!getSpeechRecognition()) {
                mic.disabled = true;
                mic.setAttribute('title', t('micUnsupportedLabel'));
            }
        }
        if (chips && chips.length === 3) {
            chips[0].textContent = t('macroChip');
            chips[1].textContent = t('moversChip');
            chips[2].textContent = t('buysChip');
        }

        // Stop recognition so it can restart with the new language on the next activation
        if (state.listening) {
            stopListening();
        }
    }

    function appendMessage(role, text, sources, enriched) {
        const messages = document.getElementById('xAssistantMessages');
        if (!messages) return;

        const msg = document.createElement('div');
        msg.className = `x-assistant-msg x-assistant-msg-${role}`;
        msg.textContent = text;

        if (enriched && role === 'ai') {
            const badge = document.createElement('span');
            badge.className = 'x-assistant-live-badge';
            badge.textContent = '\u{1F7E2} ' + t('liveData');
            msg.appendChild(badge);
        }

        if (Array.isArray(sources) && sources.length > 0) {
            const srcWrap = document.createElement('div');
            srcWrap.className = 'x-assistant-sources';
            srcWrap.innerHTML = sources.slice(0, 5).map(function (src) {
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

    function getSpeechRecognition() {
        return window.SpeechRecognition || window.webkitSpeechRecognition || null;
    }

    const LANG_LOCALE = { en: 'en-US', ar: 'ar-SA' };

    function setListening(active) {
        state.listening = active;
        const mic = document.getElementById('xAssistantMic');
        const input = document.getElementById('xAssistantInput');
        if (mic) {
            mic.classList.toggle('x-assistant-mic-listening', active);
            mic.setAttribute('aria-label', active ? t('listeningLabel') : t('voiceLabel'));
        }
        if (input) {
            input.placeholder = active ? t('listeningLabel') : t('placeholder');
        }
    }

    function stopListening() {
        if (state.recognition) {
            state.manualStop = true;
            try { state.recognition.abort(); } catch (_) { }
            state.recognition = null;
        }
        setListening(false);
    }

    function startListening() {
        const SR = getSpeechRecognition();
        if (!SR) return;

        if (state.listening) {
            stopListening();
            return;
        }

        state.manualStop = false;
        const recognition = new SR();
        recognition.lang = LANG_LOCALE[state.lang] || 'en-US';
        recognition.interimResults = true;
        recognition.maxAlternatives = 1;
        recognition.continuous = false;

        recognition.onstart = function () {
            setListening(true);
        };

        recognition.onresult = function (e) {
            const input = document.getElementById('xAssistantInput');
            if (!input) return;
            let transcript = '';
            for (let i = e.resultIndex; i < e.results.length; i++) {
                transcript += e.results[i][0].transcript;
            }
            input.value = transcript;
        };

        recognition.onend = function () {
            setListening(false);
            state.recognition = null;
            if (!state.manualStop) {
                const input = document.getElementById('xAssistantInput');
                if (input && input.value.trim()) {
                    sendMessage();
                }
            }
            state.manualStop = false;
        };

        recognition.onerror = function (e) {
            if (e.error === 'aborted') return;
            setListening(false);
            state.recognition = null;
            if (e.error !== 'no-speech') {
                const input = document.getElementById('xAssistantInput');
                if (input) {
                    input.placeholder = t('micErrorLabel');
                    setTimeout(function () {
                        const inp = document.getElementById('xAssistantInput');
                        if (inp) inp.placeholder = t('placeholder');
                    }, 3000);
                }
            }
        };

        state.recognition = recognition;
        try {
            recognition.start();
        } catch (_) {
            state.recognition = null;
            setListening(false);
        }
    }

    function setOpen(nextOpen) {
        const root = document.getElementById(ROOT_ID);
        const fab = document.getElementById('xAssistantFab');
        const panel = document.getElementById('xAssistantPanel');
        const input = document.getElementById('xAssistantInput');
        if (!panel) return;
        state.open = nextOpen;
        panel.classList.toggle('x-assistant-hidden', !nextOpen);
        if (root) root.classList.toggle('x-assistant-open', nextOpen);
        if (fab) {
            fab.classList.toggle('x-assistant-fab-hidden', nextOpen);
            fab.setAttribute('aria-hidden', nextOpen ? 'true' : 'false');
            fab.style.display = nextOpen ? 'none' : 'inline-flex';
        }
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
            let res = null;
            let data = {};

            // Retry once for transient network/server hiccups.
            for (let attempt = 0; attempt < 2; attempt++) {
                try {
                    res = await fetch('/api/rag/chat', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            question: question,
                            language: state.lang,
                            source_mode: 'hybrid'
                        })
                    });

                    const raw = await res.text();
                    try {
                        data = raw ? JSON.parse(raw) : {};
                    } catch (_) {
                        data = {};
                    }

                    if (attempt === 0 && (!res.ok && res.status >= 500)) {
                        await new Promise(function (resolve) { setTimeout(resolve, 350); });
                        continue;
                    }
                    break;
                } catch (err) {
                    if (attempt === 0) {
                        await new Promise(function (resolve) { setTimeout(resolve, 350); });
                        continue;
                    }
                    throw err;
                }
            }

            if (state.typingEl) state.typingEl.remove();
            state.typingEl = null;

            if (!res.ok || data.error) {
                let errMsg = (data && data.error) ? data.error : t('fallbackError');
                if (res.status === 503 && /GOOGLE_API_KEY/i.test(errMsg)) {
                    errMsg = 'Assistant is not configured yet. Set GOOGLE_API_KEY on the server to enable chat.';
                }
                appendMessage('ai', errMsg);
                return;
            }
            appendMessage('ai', data.answer || '', data.sources || [], !!data.openbb_enriched);
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
        const mic = document.getElementById('xAssistantMic');
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
        if (mic) {
            if (getSpeechRecognition()) {
                mic.addEventListener('click', function () { startListening(); });
            } else {
                mic.disabled = true;
                mic.setAttribute('title', t('micUnsupportedLabel'));
            }
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
