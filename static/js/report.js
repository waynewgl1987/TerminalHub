(function () {
  const state = { currentTerminalId: null, lastReportHtml: '', loadingWindow: null };

  // ── Progress toast controller ─────────────────────────────────────────────
  const Progress = (() => {
    let autoCloseTimer = null;

    function el(id) { return document.getElementById(id); }

    function show(title, steps) {
      clearTimeout(autoCloseTimer);
      const toast = el('progressToast');
      toast.classList.remove('hidden', 'done', 'error');
      el('progressLabel').textContent = title;
      el('progressBar').style.width = '0%';
      el('progressSteps').innerHTML = steps.map((s, i) =>
        `<div class="progress-step" id="pstep-${i}"><span class="step-dot"></span>${s}</div>`
      ).join('');
      toast.classList.remove('hidden');
    }

    function step(index, total) {
      // Activate current step, mark previous as done
      const steps = document.querySelectorAll('.progress-step');
      steps.forEach((s, i) => {
        s.classList.remove('active', 'done-s');
        if (i < index) s.classList.add('done-s');
        if (i === index) s.classList.add('active');
      });
      el('progressBar').style.width = `${Math.round((index / total) * 90)}%`;
    }

    function done(message) {
      const toast = el('progressToast');
      toast.classList.add('done');
      el('progressLabel').textContent = message;
      el('progressBar').style.width = '100%';
      document.querySelectorAll('.progress-step').forEach(s => {
        s.classList.remove('active');
        s.classList.add('done-s');
      });
      autoCloseTimer = setTimeout(() => hide(), 3000);
    }

    function error(message) {
      const toast = el('progressToast');
      toast.classList.add('error');
      el('progressLabel').textContent = message;
      document.querySelectorAll('.progress-step.active').forEach(s => {
        s.classList.remove('active');
        s.classList.add('error-s');
      });
      autoCloseTimer = setTimeout(() => hide(), 5000);
    }

    function hide() {
      clearTimeout(autoCloseTimer);
      el('progressToast').classList.add('hidden');
      el('progressToast').classList.remove('done', 'error');
    }

    // Wire close button
    document.addEventListener('DOMContentLoaded', () => {
      const btn = el('progressClose');
      if (btn) btn.addEventListener('click', hide);
    });
    // Also wire immediately if DOM is ready
    const closeBtn = el('progressClose');
    if (closeBtn) closeBtn.addEventListener('click', hide);

    return { show, step, done, error, hide };
  })();

  // ── Helpers ───────────────────────────────────────────────────────────────
  function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, c =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])
    );
  }

  function setButtonLoading(btn, loading) {
    if (!btn) return;
    btn.classList.toggle('btn-loading', loading);
  }

  // Syntax-highlight code using hljs; falls back to escapeHtml if hljs not loaded
  function highlightCode(code, lang) {
    if (!code) return '';
    if (!window.hljs) return escapeHtml(code);
    try {
      if (lang && window.hljs.getLanguage(lang)) {
        return window.hljs.highlight(code, { language: lang, ignoreIllegals: true }).value;
      }
      return window.hljs.highlightAuto(code).value;
    } catch (_) { return escapeHtml(code); }
  }

  // Track which button is active per diff item (accept/reject mutually exclusive)
  function _setDiffBtnActive(container, index, type) {
    if (type === 'accept' || type === 'reject') {
      container.querySelectorAll(`[data-accept-index="${index}"], [data-reject-index="${index}"]`)
        .forEach(b => b.classList.remove('diff-btn-active'));
    }
    if (type === 'ai') {
      container.querySelectorAll(`[data-ai-index="${index}"]`).forEach(b => b.classList.remove('diff-btn-active'));
    }
    if (type === 'better') {
      container.querySelectorAll(`[data-better-index="${index}"]`).forEach(b => b.classList.remove('diff-btn-active'));
    }
    const sel = type === 'accept' ? `[data-accept-index="${index}"]`
              : type === 'reject' ? `[data-reject-index="${index}"]`
              : type === 'ai'     ? `[data-ai-index="${index}"]`
              :                     `[data-better-index="${index}"]`;
    const btn = container.querySelector(sel);
    if (btn) btn.classList.add('diff-btn-active');
  }

  // ── Better-prompt dialog: replaces window.prompt with a scrollable textarea ─
  function _showBetterPromptDialog(placeholder, cb) {
    const existing = document.getElementById('betterPromptOverlay');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = 'betterPromptOverlay';
    overlay.className = 'better-prompt-overlay';
    overlay.innerHTML = `
      <div class="better-prompt-panel">
        <div class="better-prompt-header">
          <h3><span style="color:#409eff">↺</span> ${escapeHtml(placeholder)}</h3>
          <button class="icon-btn" id="betterPromptCloseX" title="取消"><i class="bi bi-x-lg"></i></button>
        </div>
        <div class="better-prompt-body">
          <textarea id="betterPromptText" class="better-prompt-textarea"
            placeholder="${escapeHtml(placeholder)}" rows="5"></textarea>
        </div>
        <div class="better-prompt-footer">
          <button class="ghost-btn" id="betterPromptCancel">取消</button>
          <button class="primary-btn" id="betterPromptConfirm">确认</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);

    const textarea   = overlay.querySelector('#betterPromptText');
    const closeX     = overlay.querySelector('#betterPromptCloseX');
    const cancelBtn  = overlay.querySelector('#betterPromptCancel');
    const confirmBtn = overlay.querySelector('#betterPromptConfirm');

    function finish(result) { overlay.remove(); cb(result); }

    overlay.addEventListener('click', e => { if (e.target === overlay) finish(null); });
    closeX.addEventListener('click',  () => finish(null));
    cancelBtn.addEventListener('click', () => finish(null));
    confirmBtn.addEventListener('click', () => finish(textarea.value.trim() || null));
    textarea.addEventListener('keydown', e => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); finish(textarea.value.trim() || null); }
      if (e.key === 'Escape') finish(null);
    });
    requestAnimationFrame(() => textarea.focus());
  }

  // AI sub-dialog: a floating popup to show AI analysis without inline scroll
  let _aiSubEl = null;
  function _getAISubDialog() {
    if (_aiSubEl) return _aiSubEl;
    _aiSubEl = document.createElement('div');
    _aiSubEl.className = 'ai-sub-overlay';
    _aiSubEl.id = 'aiSubDialog';
    _aiSubEl.innerHTML = `
      <div class="ai-sub-panel">
        <div class="ai-sub-header">
          <h3><span style="color:#409eff;font-size:1rem">✦</span><span id="aiSubTitle">AI 分析</span></h3>
          <button id="aiSubCloseX" class="icon-btn" title="关闭"><i class="bi bi-x-lg"></i></button>
        </div>
        <div class="ai-sub-body" id="aiSubBody"><em style="opacity:.45">⏳ 正在分析…</em></div>
        <div class="ai-sub-footer" id="aiSubFooter"></div>
      </div>`;
    document.body.appendChild(_aiSubEl);
    _aiSubEl.addEventListener('click', e => { if (e.target === _aiSubEl) _closeAISubDialog(); });
    _aiSubEl.querySelector('#aiSubCloseX').addEventListener('click', _closeAISubDialog);
    return _aiSubEl;
  }
  function _closeAISubDialog() {
    if (_aiSubEl) _aiSubEl.remove();
    _aiSubEl = null;
  }
  function _openAISubDialog(change, index, isBetter = false) {
    _closeAISubDialog(); // fresh each time
    const dialog = _getAISubDialog();
    const filename = change.file_path.split('/').pop();
    document.getElementById('aiSubTitle').textContent = `AI 分析 · ${filename}`;
    const bodyEl   = document.getElementById('aiSubBody');
    const footerEl = document.getElementById('aiSubFooter');
    footerEl.innerHTML = `
      <button class="diff-btn diff-btn-accept" id="aiSubAccept">✓ ${i18n.t('accept')}</button>
      <button class="diff-btn diff-btn-reject" id="aiSubReject">✕ ${i18n.t('reject')}</button>
      <button class="diff-btn diff-btn-better" id="aiSubBetter">↺ ${i18n.t('askBetter')}</button>
      <button class="ghost-btn ml-auto" id="aiSubClose">关闭</button>`;
    const content = document.getElementById('diffModalContent');
    footerEl.querySelector('#aiSubAccept').addEventListener('click', () => {
      if (content) _setDiffBtnActive(content, index, 'accept');
      _closeAISubDialog();
    });
    footerEl.querySelector('#aiSubReject').addEventListener('click', () => {
      if (content) _setDiffBtnActive(content, index, 'reject');
      _closeAISubDialog();
    });
    footerEl.querySelector('#aiSubBetter').addEventListener('click', () => {
      _showBetterPromptDialog(i18n.t('promptBetter'), async req => {
        if (req) {
          bodyEl.innerHTML = '<em style="opacity:.45">⏳ ' + i18n.t('progressAskAI') + '</em>';
          await askAI(change, bodyEl, req);
        }
      });
    });
    footerEl.querySelector('#aiSubClose').addEventListener('click', _closeAISubDialog);

    if (isBetter) {
      _showBetterPromptDialog(i18n.t('promptBetter'), req => {
        if (!req) { _closeAISubDialog(); return; }
        askAI(change, bodyEl, req);
      });
    } else {
      askAI(change, bodyEl);
    }
  }

  function buildLoadingPage(steps = []) {
    const stepHtml = steps.map((step, i) =>
      `<div class="progress-step${i===0?' active':''}" id="lpstep-${i}"><span class="step-dot"></span><span class="step-label">${escapeHtml(step)}</span></div>`
    ).join('');
    // postMessage listener handles all DOM updates — no cross-window DOM access needed
    const listener = `
window.addEventListener('message',function(e){
  var d=e.data;if(!d||d.type!=='th-load')return;
  var done=d.status==='done',err=d.status==='error';
  var sh=document.getElementById('loadShell');
  if(sh)sh.className='shell'+(done?' done':err?' error':'');
  var t=document.getElementById('loadTitle');if(t&&d.title)t.textContent=d.title;
  var h=document.getElementById('loadHint');if(h!=null&&d.hint!==undefined)h.textContent=d.hint;
  var n=d.steps&&d.steps.length,ai=Math.max(d.activeIndex||0,0);
  var pct=n?(done?100:Math.max(8,Math.round((ai+1)/n*90))):0;
  var bar=document.getElementById('loadBar');if(bar)bar.style.width=pct+'%';
  if(d.steps)d.steps.forEach(function(_,i){
    var el=document.getElementById('lpstep-'+i);if(!el)return;
    var cls='progress-step';
    if(i<d.activeIndex)cls+=' done-s';
    else if(i===d.activeIndex)cls+=err?' error-s':' active';
    el.className=cls;
  });
});`;
    return `<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>TerminalHub — 导出中…</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{display:flex;align-items:center;justify-content:center;min-height:100vh;padding:24px;
       font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0f172a;color:#e5eef9}
  .shell{width:min(480px,100%);background:rgba(15,23,42,.96);border:1px solid rgba(148,163,184,.15);
         border-radius:20px;box-shadow:0 24px 56px rgba(0,0,0,.4);padding:22px 20px 18px;transition:border-color .3s}
  .shell.done{border-color:rgba(34,197,94,.35)}
  .shell.error{border-color:rgba(239,68,68,.35)}
  .brand{display:flex;align-items:center;gap:9px;margin-bottom:16px;opacity:.55;font-size:.78rem;font-weight:600;letter-spacing:.05em;text-transform:uppercase}
  .brand-icon{width:18px;height:18px;border-radius:5px;background:linear-gradient(135deg,#409eff,#67c23a);display:grid;place-items:center;font-size:9px}
  .head{display:flex;align-items:center;gap:12px;margin-bottom:4px}
  .spinner{width:20px;height:20px;border-radius:50%;border:2.5px solid rgba(64,158,255,.25);
           border-top-color:#409eff;animation:spin .75s linear infinite;flex-shrink:0;transition:border-color .3s}
  .shell.done  .spinner{border:2.5px solid #22c55e;animation:none;display:grid;place-items:center}
  .shell.done  .spinner::after{content:'✓';color:#22c55e;font-size:11px;font-weight:700}
  .shell.error .spinner{border:2.5px solid #ef4444;animation:none;display:grid;place-items:center}
  .shell.error .spinner::after{content:'✕';color:#ef4444;font-size:11px;font-weight:700}
  @keyframes spin{to{transform:rotate(360deg)}}
  h2{font-size:1rem;font-weight:700;letter-spacing:-.01em}
  .hint{color:#94a3b8;font-size:.82rem;line-height:1.5;margin-top:2px;min-height:1.2em;transition:color .2s}
  .progress-bar-track{height:4px;border-radius:99px;background:rgba(64,158,255,.14);overflow:hidden;margin:14px 0 13px}
  .progress-bar-fill{height:100%;width:8%;border-radius:99px;
                     background:linear-gradient(90deg,#409eff,#67c23a);transition:width .35s ease}
  .shell.done  .progress-bar-fill{background:#22c55e}
  .shell.error .progress-bar-fill{background:#ef4444}
  .progress-steps{display:flex;flex-direction:column;gap:6px;margin-top:2px}
  .progress-step{display:flex;align-items:center;gap:9px;font-size:.82rem;color:#64748b;transition:color .2s}
  .progress-step.active{color:#7ec8ff;font-weight:600}
  .progress-step.done-s{color:#4ade80}
  .progress-step.error-s{color:#f87171}
  .step-dot{width:7px;height:7px;border-radius:50%;background:#334155;flex-shrink:0;transition:background .2s,box-shadow .2s}
  .progress-step.active  .step-dot{background:#409eff;box-shadow:0 0 0 3px rgba(64,158,255,.22)}
  .progress-step.done-s  .step-dot{background:#22c55e}
  .progress-step.error-s .step-dot{background:#ef4444}
</style></head>
<body>
<div class="shell" id="loadShell">
  <div class="brand"><div class="brand-icon">⬡</div>TerminalHub</div>
  <div class="head"><div class="spinner" id="loadSpinner"></div>
    <div><h2 id="loadTitle">正在导出报告…</h2><div class="hint" id="loadHint">${escapeHtml(steps[0] || '请稍等')}</div></div>
  </div>
  <div class="progress-bar-track"><div class="progress-bar-fill" id="loadBar"></div></div>
  <div class="progress-steps" id="loadSteps">${stepHtml}</div>
</div>
<script>${listener}<\/script>
</body></html>`;
  }

  // Send update via localStorage (cross-origin safe) + postMessage as backup
  function updateLoadingWindow({ title, hint = '', steps = [], activeIndex = -1, status = 'loading' }) {
    if (!state.loadingWindow || state.loadingWindow.closed) return;
    const msg = { type: 'th-load', title, hint, steps, activeIndex, status, _seq: Date.now() };
    // localStorage fires 'storage' event in the other tab immediately
    try { localStorage.setItem('th-load-state', JSON.stringify(msg)); } catch (_) {}
    // postMessage as backup (works when both tabs same origin)
    const send = () => {
      if (!state.loadingWindow || state.loadingWindow.closed) return;
      try { state.loadingWindow.postMessage(msg, '*'); } catch (_) {}
    };
    send();
    setTimeout(send, 350);
  }

  // Open the static loading page (uses localStorage for cross-tab state sync)
  function initLoadingWindow(steps) {
    // Clear any stale state first, then write initial state
    const initial = { type: 'th-load', title: i18n.t('generatingReport'), hint: steps[0] || '', steps, activeIndex: 0, status: 'loading', _seq: Date.now() };
    try { localStorage.setItem('th-load-state', JSON.stringify(initial)); } catch (_) {}
    state.loadingWindow = window.open('/static/loading.html', '_blank');
  }

  async function pollJob(jobId) {
    while (true) {
      const data = await fetch(`/api/ai/job/${jobId}`).then(r => r.json());
      if (data.done) return data;
      await new Promise(r => setTimeout(r, 800));
    }
  }

  // ── AI Ask helper (used both in diff modal and export) ────────────────────
  async function askAI(change, targetEl, extra = '') {
    const config = window.TerminalHubApp.getAIConfig();
    if (!config.provider || !config.model) {
      targetEl.textContent = i18n.t('progressError') + ': AI config missing';
      return;
    }
    Progress.show(i18n.t('progressAskAI'), [i18n.t('progressAskAI')]);
    Progress.step(0, 1);
    targetEl.innerHTML = '<em style="opacity:.5">⏳ ' + i18n.t('progressAskAI') + '</em>';
    const prompt = `${extra ? extra + '\n\n' : ''}Analyze this code change in ${change.file_path}.\n\nBefore:\n\`\`\`\n${change.before || ''}\n\`\`\`\n\nAfter:\n\`\`\`\n${change.after || ''}\n\`\`\`\n\nExplain the purpose, quality, potential issues, and whether this is a good change.`;
    try {
      const job = await fetch('/api/ai/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...config, messages: [{ role: 'user', content: prompt }] })
      }).then(r => r.json());
      const result = await pollJob(job.job_id);
      targetEl.textContent = result.ok ? result.text : result.error;
      if (result.ok) Progress.done(i18n.t('progressAIDone'));
      else Progress.error(i18n.t('progressError'));
    } catch (e) {
      targetEl.textContent = String(e);
      Progress.error(i18n.t('progressError'));
    }
  }

  // ── Report Panel (embedded iframe viewer) ────────────────────────────────
  const ReportPanel = (() => {
    let _initialized = false;
    function _init() {
      if (_initialized) return;
      _initialized = true;
      document.getElementById('reportPanelClose').addEventListener('click', close);
      document.getElementById('reportPanelOverlay').addEventListener('click', close);
    }
    function open(url, label) {
      _init();
      const panel   = document.getElementById('reportPanel');
      const overlay = document.getElementById('reportPanelOverlay');
      const frame   = document.getElementById('reportPanelFrame');
      const link    = document.getElementById('reportPanelOpenLink');
      const lbl     = document.getElementById('reportPanelLabel');
      frame.src     = url;
      if (link)  link.href = url;
      if (lbl && label) lbl.textContent = label;
      panel.classList.remove('hidden');
      overlay.classList.remove('hidden');
      // Slide in after paint
      requestAnimationFrame(() => {
        panel.classList.add('open');
        overlay.classList.add('show');
      });
    }
    function close() {
      const panel   = document.getElementById('reportPanel');
      const overlay = document.getElementById('reportPanelOverlay');
      panel.classList.remove('open');
      overlay.classList.remove('show');
      setTimeout(() => {
        panel.classList.add('hidden');
        overlay.classList.add('hidden');
      }, 300);
    }
    return { open, close };
  })();

  window.TerminalHubReportPanel = ReportPanel;

  // ── Report saved path bar ─────────────────────────────────────────────────
  function showReportSavedBar(absPath, relUrl, terminalId) {
    // Remove any previous bar for this terminal
    const prev = document.querySelector(`.report-saved-bar[data-tid="${terminalId}"]`);
    if (prev) prev.remove();

    const bar = document.createElement('div');
    bar.className = 'report-saved-bar';
    bar.dataset.tid = terminalId;

    const pathStr = absPath || relUrl || i18n.t('reportSavedUnknown');
    const labelSaved = i18n.t('reportSaved');
    const labelOpen  = i18n.t('openInBrowser');
    const labelPanel = i18n.t('viewInPanel') || '在页面内查看';
    const labelClose = '×';

    bar.innerHTML = `
      <span class="saved-icon">💾</span>
      <span class="saved-path" title="${escapeHtml(absPath)}">${escapeHtml(pathStr)}</span>
      <button class="saved-panel-btn">${labelPanel}</button>
      <a class="saved-open-link" href="${escapeHtml(relUrl || '#')}" target="_blank">${labelOpen}</a>
      <button class="saved-close-btn" aria-label="close">${labelClose}</button>
    `;

    // Find the terminal card and append below it
    const card = document.querySelector(`[data-terminal-id="${terminalId}"]`);
    if (card) {
      card.insertAdjacentElement('afterend', bar);
    } else {
      document.body.appendChild(bar);
    }

    bar.querySelector('.saved-close-btn').addEventListener('click', () => bar.remove());
    const panelBtn = bar.querySelector('.saved-panel-btn');
    if (panelBtn && relUrl) {
      panelBtn.addEventListener('click', () => {
        ReportPanel.open(window.location.origin + relUrl, `Report · ${terminalId.slice(0, 8)}`);
      });
    }
    // Auto-dismiss after 30 seconds
    setTimeout(() => bar.remove(), 30000);
  }

  // ── Main report export ────────────────────────────────────────────────────
  const TerminalHubReport = {
    async exportReport(terminalId, triggerBtn) {
      setButtonLoading(triggerBtn, true);
      state.currentTerminalId = terminalId;
      const config = window.TerminalHubApp.getAIConfig();
      const hasAI = !!(config.provider && config.model);
      const steps = [
        i18n.t('progressStep1'),
        i18n.t('progressStep2'),
        ...(hasAI ? [i18n.t('progressStep3')] : []),
        i18n.t('progressStep4'),
        i18n.t('progressStep5'),
      ];
      const total = steps.length;
      Progress.show(i18n.t('progressExport'), steps);

      // Open the tab NOW inside the click handler (before any await) so Chrome's
      // popup-blocker treats this as a trusted user gesture.
      // Uses blob URL — avoids about:blank timing/reset issues.
      initLoadingWindow(steps);

      // Small delay so the blob page renders and its postMessage listener is ready
      await new Promise(r => setTimeout(r, 180));

      try {
        // Step 0 — collecting log
        Progress.step(0, total);
        updateLoadingWindow({ title: i18n.t('generatingReport'), hint: steps[0], steps, activeIndex: 0, status: 'loading' });
        await new Promise(r => setTimeout(r, 80));

        // Step 1 — code changes
        Progress.step(1, total);
        updateLoadingWindow({ title: i18n.t('generatingReport'), hint: steps[1], steps, activeIndex: 1, status: 'loading' });
        await new Promise(r => setTimeout(r, 80));

        // Step 2 — AI analysis (if enabled)
        if (hasAI) {
          Progress.step(2, total);
          updateLoadingWindow({ title: i18n.t('generatingReport'), hint: steps[2], steps, activeIndex: 2, status: 'loading' });
        }

        // Step — generate HTML (network call, the real wait)
        const genStep = hasAI ? 3 : 2;
        Progress.step(genStep, total);
        updateLoadingWindow({ title: i18n.t('generatingReport'), hint: steps[genStep], steps, activeIndex: genStep, status: 'loading' });

        // Show elapsed time while waiting for the (potentially slow) server
        let elapsed = 0;
        const elapsedTimer = setInterval(() => {
          elapsed++;
          updateLoadingWindow({ title: i18n.t('generatingReport'), hint: `${steps[genStep]} (${elapsed}s)`, steps, activeIndex: genStep, status: 'loading' });
        }, 1000);

        let response;
        try {
          response = await fetch('/api/report/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            signal: AbortSignal.timeout(140000),  // 140s hard timeout (server scans 45s + AI 90s + buffer)
            body: JSON.stringify({
              terminal_id: terminalId,
              lang: i18n.lang,
              include_ai_analysis: hasAI,
              ai_provider_config: config
            })
          });
        } finally {
          clearInterval(elapsedTimer);
        }
        if (response.status === 422 || response.status === 400) {
          const err = await response.json().catch(() => ({}));
          const msg = err.detail || err.message || 'No code changes detected.';
          updateLoadingWindow({ title: i18n.t('progressError'), hint: msg, steps, activeIndex: genStep, status: 'error' });
          Progress.error(msg);
          return '';
        }
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const html = await response.text();
        state.lastReportHtml = html;

        // Read saved file info from response headers
        const savedPath = response.headers.get('X-Report-Path') || '';
        const savedUrl  = response.headers.get('X-Report-URL') || '';

        // Mark done in the loading page before navigating away
        Progress.step(total - 1, total);
        updateLoadingWindow({ title: i18n.t('progressDone'), hint: steps[total - 1], steps, activeIndex: total - 1, status: 'done' });
        // Brief pause so user sees the "done" state in the loading window
        await new Promise(r => setTimeout(r, 600));
        const reportHref = savedUrl ? (window.location.origin + savedUrl) : null;
        const reportWin = state.loadingWindow;
        if (reportWin && reportHref) {
          reportWin.location.href = reportHref;
        } else if (reportWin) {
          // Fallback: blob if server URL unavailable
          const blob = new Blob([html], { type: 'text/html; charset=utf-8' });
          const blobUrl = URL.createObjectURL(blob);
          reportWin.location.href = blobUrl;
          setTimeout(() => URL.revokeObjectURL(blobUrl), 60000);
        } else {
          window.open(window.location.origin + savedUrl, '_blank');
        }
        Progress.done(i18n.t('progressDone'));

        // Show saved path bar
        showReportSavedBar(savedPath, savedUrl, terminalId);
        // Also auto-open in the embedded panel so user can see it without switching tabs
        if (savedUrl) {
          ReportPanel.open(window.location.origin + savedUrl, `Report · ${terminalId.slice(0, 8)}`);
        }
        return html;
      } catch (e) {
        Progress.error(i18n.t('progressError') + ': ' + e.message);
        updateLoadingWindow({ title: i18n.t('progressError'), hint: e.message, steps, activeIndex: 0, status: 'error' });
        return '';
      } finally {
        state.loadingWindow = null;
        setButtonLoading(triggerBtn, false);
      }
    },

    // ── Code diff modal ───────────────────────────────────────────────────
    async showCodeChanges(terminalId, triggerBtn) {
      state.currentTerminalId = terminalId;
      setButtonLoading(triggerBtn, true);
      Progress.show(i18n.t('progressLoadChanges'), [i18n.t('progressLoadChanges')]);
      Progress.step(0, 1);

      try {
        const result = await fetch(`/api/code-changes/${terminalId}`).then(r => r.json());
        const changes = result.changes || [];
        const content = document.getElementById('diffModalContent');

        if (!changes.length) {
          content.innerHTML = `<div class="empty-state">${i18n.t('noChanges')}</div>`;
        } else {
          content.innerHTML = changes.map((change, index) => {
            const lang = change.language || '';
            const beforeHtml = highlightCode(change.before || '', lang);
            const afterHtml  = highlightCode(change.after  || '', lang);
            const typeClass  = (change.change_type || '').toLowerCase();
            return `
              <article class="diff-item collapsed">
                <div class="diff-item-header">
                  <div class="diff-item-meta">
                    <div class="diff-meta-title-row">
                      <button class="diff-toggle-btn" data-toggle-index="${index}" title="展开/收起" aria-expanded="false">
                        <i class="bi bi-chevron-right diff-toggle-icon"></i>
                      </button>
                      <strong class="diff-filepath">${escapeHtml(change.file_path)}</strong>
                    </div>
                    <div class="diff-meta-tags">
                      <span class="diff-tag diff-tag-type ${typeClass}">${escapeHtml(change.change_type || '')}</span>
                      ${lang ? `<span class="diff-tag">${escapeHtml(lang)}</span>` : ''}
                    </div>
                  </div>
                  <div class="diff-action-btns">
                    <button class="diff-btn diff-btn-ai" data-ai-index="${index}">✦ ${i18n.t('askAI')}</button>
                    <button class="diff-btn diff-btn-accept" data-accept-index="${index}">✓ ${i18n.t('accept')}</button>
                    <button class="diff-btn diff-btn-reject" data-reject-index="${index}">✕ ${i18n.t('reject')}</button>
                    <button class="diff-btn diff-btn-better" data-better-index="${index}">↺ ${i18n.t('askBetter')}</button>
                  </div>
                </div>
                <div class="diff-columns">
                  <div class="diff-pane">
                    <div class="diff-pane-label">${i18n.t('before')}</div>
                    ${change.before
                      ? `<pre class="diff-code hljs">${beforeHtml}</pre>`
                      : `<div class="diff-empty-hint" style="padding:8px;opacity:.5">📄 ${change.change_type === 'created' ? '新建文件，无历史版本' : '(empty)'}</div>`}
                  </div>
                  <div class="diff-pane">
                    <div class="diff-pane-label">${i18n.t('after')}</div>
                    <pre class="diff-code hljs">${afterHtml}</pre>
                  </div>
                </div>
                <div class="diff-render">${change.diff_html || ''}</div>
              </article>`;
          }).join('');

          changes.forEach((change, index) => {
            // Collapse toggle
            content.querySelector(`[data-toggle-index="${index}"]`).addEventListener('click', () => {
              const article = content.querySelectorAll('.diff-item')[index];
              const expanded = !article.classList.contains('collapsed');
              article.classList.toggle('collapsed', expanded);
              const btn = article.querySelector(`[data-toggle-index="${index}"]`);
              btn.setAttribute('aria-expanded', String(!expanded));
            });

            content.querySelector(`[data-ai-index="${index}"]`).addEventListener('click', e => {
              _setDiffBtnActive(content, index, 'ai');
              _openAISubDialog(change, index);
            });
            content.querySelector(`[data-accept-index="${index}"]`).addEventListener('click', () => {
              _setDiffBtnActive(content, index, 'accept');
            });
            content.querySelector(`[data-reject-index="${index}"]`).addEventListener('click', () => {
              _setDiffBtnActive(content, index, 'reject');
            });
            content.querySelector(`[data-better-index="${index}"]`).addEventListener('click', () => {
              _setDiffBtnActive(content, index, 'better');
              _openAISubDialog(change, index, true);
            });
          });
        }

        Progress.done(i18n.t('progressDone'));
        window.TerminalHubApp.openModal('diffModal');
      } catch (e) {
        Progress.error(i18n.t('progressError') + ': ' + e.message);
      } finally {
        setButtonLoading(triggerBtn, false);
      }
    },

    // ── Email modal ───────────────────────────────────────────────────────
    async showEmailModal(terminalId, triggerBtn) {
      state.currentTerminalId = terminalId;
      if (!state.lastReportHtml) {
        state.lastReportHtml = await this.exportReport(terminalId, triggerBtn);
        if (!state.lastReportHtml) return; // export failed
      }
      document.querySelector('#emailForm [name="subject"]').value =
        `${i18n.t('reportTitle')} #${terminalId.slice(0, 8)}`;
      window.TerminalHubApp.openModal('emailModal');
    },

    async sendEmail(event) {
      event.preventDefault();
      const submitBtn = event.target.querySelector('[type="submit"]');
      setButtonLoading(submitBtn, true);

      Progress.show(i18n.t('progressEmail'), [
        i18n.t('progressEmailStep1'),
        i18n.t('progressEmailStep2'),
        i18n.t('progressEmailStep3'),
      ]);
      Progress.step(0, 3);

      try {
        if (!state.lastReportHtml && state.currentTerminalId) {
          state.lastReportHtml = await this.exportReport(state.currentTerminalId);
        }

        Progress.step(1, 3);
        const form = new FormData(event.target);
        const payload = {
          to: form.get('to'),
          subject: form.get('subject'),
          html: state.lastReportHtml,
          smtp_config: {
            smtp_host: form.get('smtp_host'),
            smtp_port: Number(form.get('smtp_port') || 587),
            smtp_user: form.get('smtp_user'),
            smtp_pass: form.get('smtp_pass')
          }
        };

        Progress.step(2, 3);
        const result = await fetch('/api/email/send', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        }).then(r => r.json());

        if (result.ok) {
          Progress.done(i18n.t('progressEmailDone'));
          window.TerminalHubApp.closeModal('emailModal');
        } else {
          Progress.error(i18n.t('progressEmailError') + ': ' + (result.message || ''));
        }
      } catch (e) {
        Progress.error(i18n.t('progressEmailError') + ': ' + e.message);
      } finally {
        setButtonLoading(submitBtn, false);
      }
    }
  };

  window.TerminalHubReport = TerminalHubReport;
  window.TerminalHubProgress = Progress; // expose for use in terminal.js export btn
  document.addEventListener('DOMContentLoaded', () => {
    const emailReportBtn = document.getElementById('emailReportBtn');
    if (emailReportBtn) {
      emailReportBtn.addEventListener('click', (event) => {
        if (!state.currentTerminalId) return;
        TerminalHubReport.showEmailModal(state.currentTerminalId, event.currentTarget);
      });
    }
  });
})();
