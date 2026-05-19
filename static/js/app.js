(function () {
  const state = {
    widgets: new Map(),
    monitorSocket: null
  };

  const TerminalHubApp = {
    async init() {
      this.grid = document.getElementById('terminalGrid');
      this.overlay = document.getElementById('modalOverlay');
      this.bindGlobalEvents();
      this.applyTheme(localStorage.getItem('terminalhub-theme') || document.documentElement.dataset.theme || 'light');
      i18n.setLang(localStorage.getItem('terminalhub-lang') || document.documentElement.lang || 'zh');
      await window.AIConfigPanel.init();
      document.getElementById('emailForm').addEventListener('submit', (event) => window.TerminalHubReport.sendEmail(event));
      await this.loadTerminals();
      this.connectMonitor();
      this._initStickyFab();
    },
    bindGlobalEvents() {
      document.getElementById('newTerminalBtn').addEventListener('click', () => this.openModal('newTerminalModal'));
      document.getElementById('themeToggle').addEventListener('click', () => this.toggleTheme());
      document.getElementById('langToggle').addEventListener('click', () => i18n.setLang(i18n.lang === 'zh' ? 'en' : 'zh'));
      document.getElementById('newTerminalForm').addEventListener('submit', (event) => this.handleCreateTerminal(event));
      this.overlay.addEventListener('click', () => this.closeAllModals());
      document.querySelectorAll('[data-close-modal]').forEach((btn) => {
        btn.addEventListener('click', () => this.closeModal(btn.dataset.closeModal));
      });
      window.addEventListener('terminalhub:lang-changed', () => {
        i18n.apply();
        this.renderEmptyState();
      });
      // Drag-and-drop path support for CWD and watch path inputs in the new terminal modal
      this._initInputDragDrop('input[name="cwd"]');
      this._initInputDragDrop('input[name="watch_path"]');
    },

    _initStickyFab() {
      const topbar = document.querySelector('.topbar');
      const fabContainer = document.getElementById('fabContainer');
      const sentinel = document.getElementById('fabSentinel');
      if (!topbar || !fabContainer || !sentinel) return;

      // Measure topbar height and expose as CSS variable so the sticky top value stays accurate.
      const updateTopbarH = () => {
        document.documentElement.style.setProperty('--topbar-h', topbar.offsetHeight + 'px');
      };
      updateTopbarH();
      new ResizeObserver(updateTopbarH).observe(topbar);

      // IntersectionObserver on the zero-height sentinel above the fab-container.
      // When the sentinel exits the viewport (scrolled up above it), the FAB is stuck
      // → add .is-stuck for frosted-glass styling feedback.
      const observer = new IntersectionObserver(
        ([entry]) => fabContainer.classList.toggle('is-stuck', !entry.isIntersecting),
        { rootMargin: `-${topbar.offsetHeight}px 0px 0px 0px`, threshold: 0 }
      );
      observer.observe(sentinel);
    },

    // Make a path-type input accept dragged files/folders from Finder
    _initInputDragDrop(selector) {
      const input = document.querySelector(selector);
      if (!input) return;
      input.addEventListener('dragover', (e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'copy';
        input.classList.add('drag-active');
      });
      input.addEventListener('dragleave', () => input.classList.remove('drag-active'));
      input.addEventListener('drop', (e) => {
        e.preventDefault();
        input.classList.remove('drag-active');
        const uriList = e.dataTransfer.getData('text/uri-list');
        let path = '';
        if (uriList) {
          const first = uriList.split(/\r?\n/).find(l => l.trim() && !l.startsWith('#'));
          if (first && first.startsWith('file://')) {
            try { path = decodeURIComponent(new URL(first.trim()).pathname); }
            catch (_) { path = decodeURIComponent(first.replace(/^file:\/\/[^/]*/, '')); }
          }
        }
        if (!path) path = e.dataTransfer.getData('text/plain').trim();
        if (path) { input.value = path; input.dispatchEvent(new Event('input')); }
      });
    },
    openModal(id) {
      this.overlay.classList.remove('hidden');
      document.getElementById(id).classList.remove('hidden');
    },
    closeModal(id) {
      document.getElementById(id).classList.add('hidden');
      if ([...document.querySelectorAll('.th-modal:not(.hidden)')].length === 0) {
        this.overlay.classList.add('hidden');
      }
    },
    closeAllModals() {
      document.querySelectorAll('.th-modal').forEach((modal) => modal.classList.add('hidden'));
      this.overlay.classList.add('hidden');
    },
    toggleTheme() {
      this.applyTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');
    },
    applyTheme(theme) {
      document.documentElement.dataset.theme = theme;
      localStorage.setItem('terminalhub-theme', theme);
      // Sync hljs theme with app theme
      const lightEl = document.getElementById('hljs-theme-light');
      const darkEl  = document.getElementById('hljs-theme-dark');
      if (lightEl) lightEl.disabled = (theme === 'dark');
      if (darkEl)  darkEl.disabled  = (theme !== 'dark');
      window.dispatchEvent(new CustomEvent('terminalhub:theme-changed', { detail: theme }));
    },
    getAIConfig() {
      return JSON.parse(localStorage.getItem('terminalhub-ai-config') || '{}');
    },
    async handleCreateTerminal(event) {
      event.preventDefault();
      const submitBtn = document.getElementById('createTerminalSubmit');
      const originalText = submitBtn.textContent;

      // Disable button and show inline progress
      submitBtn.disabled = true;
      submitBtn.classList.add('btn-loading');
      submitBtn.innerHTML = `<span class="btn-spinner"></span> ${i18n.t('creating')}…`;

      const form = new FormData(event.target);
      try {
        await this.createTerminal({
          shell: form.get('shell'),
          cwd: form.get('cwd') || undefined,
          title: form.get('title') || undefined,
          watch_path: form.get('watch_path') || undefined,
          description: form.get('description') || undefined
        });
        event.target.reset();
        this.closeModal('newTerminalModal');
      } catch (err) {
        console.error('Failed to create terminal:', err);
      } finally {
        submitBtn.disabled = false;
        submitBtn.classList.remove('btn-loading');
        submitBtn.textContent = originalText;
      }
    },
    async createTerminal(payload) {
      const terminal = await fetch('/api/terminals', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      }).then((r) => r.json());
      this.upsertTerminal(terminal);
    },
    async killTerminal(tid) {
      await fetch(`/api/terminals/${tid}`, { method: 'DELETE' });
      const widget = state.widgets.get(tid);
      if (widget) widget.dispose();
      state.widgets.delete(tid);
      this.renderEmptyState();
    },
    async loadTerminals() {
      const terminals = await fetch('/api/terminals').then((r) => r.json());
      this.syncTerminals(terminals);
    },
    connectMonitor() {
      const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
      state.monitorSocket = new WebSocket(`${protocol}//${location.host}/ws/monitor`);
      state.monitorSocket.onmessage = (event) => {
        const payload = JSON.parse(event.data);
        if (payload.type === 'monitor') {
          this.updateSummary(payload.system, payload.terminals);
          this.syncTerminals(payload.terminals, payload.code_changes || {});
        }
      };
      state.monitorSocket.onclose = () => setTimeout(() => this.connectMonitor(), 1500);
    },
    updateSummary(system, terminals) {
      document.getElementById('systemCpuValue').textContent = `${system.cpu_pct || 0}%`;
      document.getElementById('systemMemValue').textContent = `${system.mem_used_gb || 0} / ${system.mem_total_gb || 0} GB`;
      document.getElementById('terminalCountValue').textContent = `${terminals.length}`;
      document.getElementById('aiCountValue').textContent = `${terminals.filter((item) => item.ai_info?.detected).length}`;
    },
    syncTerminals(terminals, codeCounts = {}) {
      const prevSize = state.widgets.size;
      const seen = new Set();
      terminals.forEach((terminal) => {
        seen.add(terminal.id);
        terminal.code_changes = codeCounts[terminal.id] ?? terminal.code_changes ?? 0;
        this.upsertTerminal(terminal);
      });
      [...state.widgets.keys()].forEach((id) => {
        if (!seen.has(id)) {
          state.widgets.get(id).dispose();
          state.widgets.delete(id);
        }
      });
      this.renderEmptyState();
      // If the number of terminals changed, the grid layout changes (1→2 columns etc.)
      // so all xterm instances need to refit to their new dimensions.
      if (state.widgets.size !== prevSize) this._refitAll();
    },
    upsertTerminal(terminal) {
      let widget = state.widgets.get(terminal.id);
      const isNew = !widget;
      if (!widget) {
        const card = document.createElement('section');
        this.grid.appendChild(card);
        widget = new TerminalWidget(terminal.id, card, terminal.title, terminal);
        widget.init();
        state.widgets.set(terminal.id, widget);
      } else {
        widget.applyMetadata(terminal);
      }
      // New terminal changes grid layout — refit all after CSS reflow settles
      if (isNew) this._refitAll();
    },
    _refitAll() {
      // Two rAF passes: first lets CSS grid recalculate, second lets the browser
      // paint the new layout, then we refit all xterm instances to pixel-accurate widths.
      // A short timeout safety net covers edge-cases where grid reflow takes longer.
      requestAnimationFrame(() => requestAnimationFrame(() => {
        state.widgets.forEach(w => w.fit && w.fit());
        // Second pass after 80ms ensures any late CSS transitions / scrollbar changes
        // don't leave residual clipping artefacts.
        setTimeout(() => state.widgets.forEach(w => w.fit && w.fit()), 80);
      }));
    },
    renderEmptyState() {
      this.grid.querySelectorAll('.empty-state').forEach((node) => node.remove());
      if (!state.widgets.size) {
        const empty = document.createElement('div');
        empty.className = 'empty-state';
        empty.textContent = i18n.t('noTerminals');
        this.grid.appendChild(empty);
      }
    }
  };

  window.TerminalHubApp = TerminalHubApp;
  window.addEventListener('DOMContentLoaded', () => {
    TerminalHubApp.init();
    // Reveal page after app initialises — prevents FOUC on first load.
    // Fallback timeout ensures it shows even if init somehow stalls.
    requestAnimationFrame(() => {
      document.body.style.opacity = '1';
    });
  });
  // Safety net: always show within 2 s regardless of JS state
  setTimeout(() => { document.body.style.opacity = '1'; }, 2000);
})();
