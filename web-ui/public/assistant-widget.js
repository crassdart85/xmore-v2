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
            fallbackError: 'Could not reach the assistant right now.',
            voiceLabel: 'Voice Input',
            listeningLabel: 'Listening...',
            listeningInLabel: 'Listening in',
            micErrorLabel: 'Microphone not available',
            micPermissionLabel: 'Microphone permission required',
            unsupportedLabel: 'Voice input not supported in this browser',
            noSpeechLabel: 'No speech detected. Please try again.',
            networkErrorLabel: 'Network error. Please check your connection.',
            unrecognizedLabel: 'Speech not recognized. Please try again.',
            clickToTryAgainLabel: 'Click mic to try again'
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
            fallbackError: 'تعذر الاتصال بالمساعد الآن.',
            voiceLabel: 'إدخال صوتي',
            listeningLabel: 'جاري الاستماع...',
            listeningInLabel: 'الاستماع في',
            micErrorLabel: 'الميكروفون غير متاح',
            micPermissionLabel: 'مطلوب إذن الميكروفون',
            unsupportedLabel: 'إدخال صوتي غير مدعوم في هذا المتصفح',
            noSpeechLabel: 'لم يتم الكشف عن كلام. يرجى المحاولة مرة أخرى.',
            networkErrorLabel: 'خطأ في الشبكة. يرجى التحقق من اتصالك.',
            unrecognizedLabel: 'لم يتم التعرف على الكلام. يرجى المحاولة مرة أخرى.',
            clickToTryAgainLabel: 'انقر على الميك للمحاولة مرة أخرى'
        }
    };

    const state = {
        open: false,
        lang: getCurrentLang(),
        typingEl: null,
        recognition: null,
        isListening: false
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
                    <button id="xAssistantMic" class="x-assistant-mic" type="button" aria-label="${esc(t('voiceLabel'))}" title="${esc(t('voiceLabel'))}">
                        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" aria-hidden="true">
                            <rect x="9" y="2" width="6" height="11" rx="3" fill="currentColor"/>
                            <path d="M5 11a7 7 0 0 0 14 0" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
                            <line x1="12" y1="18" x2="12" y2="21" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
                            <line x1="9" y1="21" x2="15" y2="21" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
                        </svg>
                    </button>
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
        const mic = document.getElementById('xAssistantMic');
        if (mic && !mic.disabled && !state.isListening) {
            mic.setAttribute('aria-label', t('voiceLabel'));
            mic.setAttribute('title', t('voiceLabel'));
        }
        if (state.recognition) {
            state.recognition.lang = state.lang === 'ar' ? 'ar-EG' : 'en-US';
        }
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

        if (state.isListening) stopListening();

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
        const mic = document.getElementById('xAssistantMic');
        if (mic) {
            mic.addEventListener('click', function () {
                if (state.isListening) {
                    stopListening();
                } else if (state.recognition) {
                    startListening();
                }
            });
        }
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
        initSpeechRecognition();
        bindEvents();
        appendMessage('ai', t('welcome'));
    }

    function initSpeechRecognition() {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        const mic = document.getElementById('xAssistantMic');
        if (!SpeechRecognition) {
            if (mic) {
                mic.disabled = true;
                mic.setAttribute('title', t('unsupportedLabel'));
                mic.setAttribute('aria-label', t('unsupportedLabel'));
            }
            return;
        }
        state.recognition = new SpeechRecognition();
        state.recognition.continuous = false;
        state.recognition.interimResults = true;
        state.recognition.lang = state.lang === 'ar' ? 'ar-EG' : 'en-US';

        state.recognition.onresult = function (event) {
            const input = document.getElementById('xAssistantInput');
            if (!input) return;
            let interim = '';
            let final = '';
            for (let i = event.resultIndex; i < event.results.length; i++) {
                const transcript = event.results[i][0].transcript;
                if (event.results[i].isFinal) {
                    final += transcript;
                } else {
                    interim += transcript;
                }
            }
            input.value = final || interim;
            if (final) {
                input.classList.remove('listening');
            }
        };

        state.recognition.onend = function () {
            if (state.isListening) {
                const input = document.getElementById('xAssistantInput');
                const text = input ? input.value.trim() : '';
                stopListening();
                if (text) {
                    setTimeout(function () { sendMessage(); }, 100);
                }
            }
        };

        state.recognition.onerror = function (event) {
            handleSpeechError(event.error);
        };
    }

    function startListening() {
        if (!state.recognition || state.isListening) return;
        state.recognition.lang = state.lang === 'ar' ? 'ar-EG' : 'en-US';
        const input = document.getElementById('xAssistantInput');
        if (input) {
            input.value = '';
            input.placeholder = t('listeningLabel');
            input.classList.add('listening');
        }
        state.isListening = true;
        updateMicButtonState('recording');
        try {
            state.recognition.start();
        } catch (_) {
            state.isListening = false;
            updateMicButtonState('idle');
            if (input) {
                input.placeholder = t('placeholder');
                input.classList.remove('listening');
            }
        }
    }

    function stopListening() {
        if (!state.isListening) return;
        state.isListening = false;
        const input = document.getElementById('xAssistantInput');
        if (input) {
            input.placeholder = t('placeholder');
            input.classList.remove('listening');
        }
        updateMicButtonState('idle');
        if (state.recognition) {
            try { state.recognition.stop(); } catch (_) { /* already stopped */ }
        }
    }

    function handleSpeechError(error) {
        const input = document.getElementById('xAssistantInput');
        let errorMsg = '';
        if (error === 'aborted') {
            stopListening();
            return;
        }
        switch (error) {
            case 'not-allowed':
            case 'permission-denied':
                errorMsg = t('micPermissionLabel');
                break;
            case 'no-speech':
                errorMsg = t('noSpeechLabel');
                break;
            case 'network':
                errorMsg = t('networkErrorLabel');
                break;
            default:
                errorMsg = t('unrecognizedLabel');
        }
        stopListening();
        if (input) {
            const tryAgain = t('clickToTryAgainLabel');
            input.placeholder = errorMsg + ' ' + tryAgain;
            setTimeout(function () {
                if (!state.isListening) {
                    input.placeholder = t('placeholder');
                }
            }, 4000);
        }
        updateMicButtonState('error');
        setTimeout(function () {
            if (!state.isListening) {
                updateMicButtonState('idle');
            }
        }, 4000);
    }

    function updateMicButtonState(micState) {
        const mic = document.getElementById('xAssistantMic');
        if (!mic || mic.disabled) return;
        mic.classList.remove('recording', 'error');
        switch (micState) {
            case 'recording':
                mic.classList.add('recording');
                mic.setAttribute('aria-label', t('listeningLabel'));
                mic.setAttribute('title', t('listeningLabel'));
                break;
            case 'error':
                mic.classList.add('error');
                mic.setAttribute('aria-label', t('micErrorLabel'));
                mic.setAttribute('title', t('micErrorLabel'));
                break;
            default:
                mic.setAttribute('aria-label', t('voiceLabel'));
                mic.setAttribute('title', t('voiceLabel'));
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
