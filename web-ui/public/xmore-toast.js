/**
 * Xmore Toast & Dialog Utility
 * Replaces alert() / confirm() / prompt() with accessible, themeable alternatives.
 *
 * Usage:
 *   xToast('Saved!', 'success');           // green toast, auto-dismisses
 *   xToast('Something went wrong', 'error');// red toast
 *   xToast('Note: market closed', 'info'); // neutral toast
 *   await xPrompt('Exit price:', '48.50'); // returns string or null (cancelled)
 *   await xConfirm('Delete this?');        // returns true/false
 */

(function () {
  /* ── Inject styles once ─────────────────────────────────────────────────── */
  if (!document.getElementById('xmore-toast-style')) {
    const style = document.createElement('style');
    style.id = 'xmore-toast-style';
    style.textContent = `
      /* Toast container */
      #x-toast-container {
        position: fixed;
        top: 16px;
        right: 16px;
        z-index: 9999;
        display: flex;
        flex-direction: column;
        gap: 8px;
        max-width: 360px;
        width: calc(100vw - 32px);
        pointer-events: none;
      }
      [dir="rtl"] #x-toast-container { right: auto; left: 16px; }

      .x-toast {
        display: flex;
        align-items: flex-start;
        gap: 10px;
        padding: 12px 14px;
        border-radius: 6px;
        font-size: 13px;
        line-height: 1.5;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        box-shadow: 0 4px 20px rgba(0,0,0,0.4);
        pointer-events: all;
        animation: x-toast-in 0.2s ease;
        border: 1px solid transparent;
      }
      .x-toast--success { background: #0d2b1a; color: #4ade80; border-color: #166534; }
      .x-toast--error   { background: #2b0d0d; color: #f87171; border-color: #991b1b; }
      .x-toast--info    { background: #1a1a2b; color: #93c5fd; border-color: #1e3a8a; }

      .x-toast-icon { font-size: 16px; flex-shrink: 0; line-height: 1.4; }
      .x-toast-msg  { flex: 1; }
      .x-toast-close {
        background: none; border: none; cursor: pointer; padding: 0 2px;
        color: inherit; opacity: 0.6; font-size: 16px; line-height: 1; flex-shrink: 0;
      }
      .x-toast-close:hover { opacity: 1; }

      @keyframes x-toast-in {
        from { opacity: 0; transform: translateX(20px); }
        to   { opacity: 1; transform: translateX(0); }
      }
      [dir="rtl"] @keyframes x-toast-in {
        from { opacity: 0; transform: translateX(-20px); }
        to   { opacity: 1; transform: translateX(0); }
      }

      /* Dialog overlay */
      #x-dialog-overlay {
        position: fixed;
        inset: 0;
        background: rgba(0,0,0,0.7);
        z-index: 10000;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 16px;
      }
      #x-dialog {
        background: #141414;
        border: 1px solid #2a2a2a;
        border-radius: 8px;
        padding: 24px;
        width: 100%;
        max-width: 340px;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        display: flex;
        flex-direction: column;
        gap: 14px;
        position: relative;
      }
      #x-dialog-title {
        font-size: 14px;
        font-weight: 600;
        color: #e0e0e0;
      }
      #x-dialog-body {
        font-size: 13px;
        color: #999;
        line-height: 1.5;
      }
      #x-dialog-input {
        background: #1a1a1a;
        border: 1px solid #2a2a2a;
        border-radius: 4px;
        color: #e0e0e0;
        font-size: 14px;
        padding: 8px 10px;
        outline: none;
        font-family: inherit;
        width: 100%;
        transition: border-color 0.15s;
      }
      #x-dialog-input:focus { border-color: #667eea; }
      #x-dialog-actions { display: flex; gap: 8px; justify-content: flex-end; }
      .x-dialog-btn {
        padding: 7px 18px;
        border-radius: 4px;
        font-size: 13px;
        font-weight: 600;
        cursor: pointer;
        font-family: inherit;
        border: none;
        transition: opacity 0.15s;
        min-width: 72px;
      }
      .x-dialog-btn--primary { background: #667eea; color: #fff; }
      .x-dialog-btn--primary:hover { opacity: 0.88; }
      .x-dialog-btn--secondary { background: #2a2a2a; color: #ccc; }
      .x-dialog-btn--secondary:hover { background: #333; }
    `;
    document.head.appendChild(style);
  }

  /* ── Toast container ────────────────────────────────────────────────────── */
  function getContainer() {
    let c = document.getElementById('x-toast-container');
    if (!c) {
      c = document.createElement('div');
      c.id = 'x-toast-container';
      c.setAttribute('role', 'region');
      c.setAttribute('aria-live', 'polite');
      c.setAttribute('aria-label', 'Notifications');
      document.body.appendChild(c);
    }
    return c;
  }

  /* ── xToast ─────────────────────────────────────────────────────────────── */
  const ICONS = { success: '✓', error: '✕', info: 'ℹ' };

  window.xToast = function (message, type = 'info', duration = 4000) {
    const container = getContainer();
    const toast = document.createElement('div');
    toast.className = `x-toast x-toast--${type}`;
    toast.setAttribute('role', 'alert');
    toast.innerHTML = `
      <span class="x-toast-icon" aria-hidden="true">${ICONS[type] || ICONS.info}</span>
      <span class="x-toast-msg">${message}</span>
      <button class="x-toast-close" aria-label="Dismiss notification">×</button>
    `;

    const close = toast.querySelector('.x-toast-close');
    let timer;

    function dismiss() {
      clearTimeout(timer);
      toast.style.opacity = '0';
      toast.style.transition = 'opacity 0.2s';
      setTimeout(() => toast.remove(), 200);
    }

    close.addEventListener('click', dismiss);
    if (duration > 0) timer = setTimeout(dismiss, duration);
    container.appendChild(toast);
  };

  /* ── Internal: build/remove overlay ────────────────────────────────────── */
  function createOverlay() {
    const overlay = document.createElement('div');
    overlay.id = 'x-dialog-overlay';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    document.body.appendChild(overlay);
    document.body.style.overflow = 'hidden';
    return overlay;
  }

  function removeOverlay(overlay, _prevFocus) {
    overlay.remove();
    document.body.style.overflow = '';
    if (_prevFocus && _prevFocus.focus) _prevFocus.focus();
  }

  /* Focus trap helper */
  function trapFocus(container, e) {
    const focusable = Array.from(
      container.querySelectorAll('button, input, textarea, select, [tabindex]:not([tabindex="-1"])')
    ).filter(el => !el.disabled);
    if (!focusable.length) return;
    const first = focusable[0];
    const last  = focusable[focusable.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault(); last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault(); first.focus();
    }
  }

  /* ── xPrompt ────────────────────────────────────────────────────────────── */
  window.xPrompt = function (label, defaultValue = '', title = '') {
    return new Promise((resolve) => {
      const prevFocus = document.activeElement;
      const overlay = createOverlay();

      overlay.innerHTML = `
        <div id="x-dialog" role="document">
          ${title ? `<div id="x-dialog-title">${title}</div>` : ''}
          <label id="x-dialog-body" for="x-dialog-input" style="color:#ccc">${label}</label>
          <input id="x-dialog-input" type="number" step="0.01" min="0.01" value="${defaultValue}" autocomplete="off" />
          <div id="x-dialog-actions">
            <button class="x-dialog-btn x-dialog-btn--secondary" id="x-dialog-cancel">Cancel</button>
            <button class="x-dialog-btn x-dialog-btn--primary" id="x-dialog-ok">Confirm</button>
          </div>
        </div>
      `;

      const input  = overlay.querySelector('#x-dialog-input');
      const ok     = overlay.querySelector('#x-dialog-ok');
      const cancel = overlay.querySelector('#x-dialog-cancel');

      setTimeout(() => { input.focus(); input.select(); }, 50);

      function confirm() {
        const val = input.value.trim();
        removeOverlay(overlay, prevFocus);
        resolve(val || null);
      }
      function dismiss() {
        removeOverlay(overlay, prevFocus);
        resolve(null);
      }

      ok.addEventListener('click', confirm);
      cancel.addEventListener('click', dismiss);
      overlay.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') dismiss();
        if (e.key === 'Enter' && document.activeElement !== cancel) confirm();
        if (e.key === 'Tab') trapFocus(overlay, e);
      });
    });
  };

  /* ── xConfirm ───────────────────────────────────────────────────────────── */
  window.xConfirm = function (message, confirmLabel = 'Confirm', cancelLabel = 'Cancel') {
    return new Promise((resolve) => {
      const prevFocus = document.activeElement;
      const overlay = createOverlay();

      overlay.innerHTML = `
        <div id="x-dialog" role="document">
          <div id="x-dialog-body">${message}</div>
          <div id="x-dialog-actions">
            <button class="x-dialog-btn x-dialog-btn--secondary" id="x-dialog-cancel">${cancelLabel}</button>
            <button class="x-dialog-btn x-dialog-btn--primary" id="x-dialog-ok">${confirmLabel}</button>
          </div>
        </div>
      `;

      const ok     = overlay.querySelector('#x-dialog-ok');
      const cancel = overlay.querySelector('#x-dialog-cancel');

      setTimeout(() => ok.focus(), 50);

      ok.addEventListener('click', () => { removeOverlay(overlay, prevFocus); resolve(true); });
      cancel.addEventListener('click', () => { removeOverlay(overlay, prevFocus); resolve(false); });
      overlay.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') { removeOverlay(overlay, prevFocus); resolve(false); }
        if (e.key === 'Tab') trapFocus(overlay, e);
      });
    });
  };
})();
