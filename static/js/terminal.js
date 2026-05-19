(function () {
  class TerminalWidget {
    constructor(terminalId, containerEl, title, metadata) {
      this.terminalId = terminalId;
      this.containerEl = containerEl;
      this.title = title;
      this.metadata = metadata || {};
      this.ws = null;
      this.term = null;
      this.fitAddon = null;
      this.resizeObserver = null;
      this._liveCwd = undefined; // set by per-terminal stats; preserved across monitor updates
    }

    init() {
      this.render();
      this.initTerminal();
      this.connectSocket();
      this.applyMetadata(this.metadata);
      window.addEventListener('terminalhub:theme-changed', () => this.applyTheme());
      window.addEventListener('terminalhub:lang-changed', () => this.refreshLabels());
    }

    render() {
      this.containerEl.className = 'terminal-card';
      this.containerEl.dataset.terminalId = this.terminalId;
      this.containerEl.innerHTML = `
        <div class="terminal-header">
          <div class="terminal-title-row">
            <div class="terminal-title-wrap">
              <button class="icon-btn toggle-info"><i class="bi bi-chevron-right"></i></button>
              <div>
                <div class="terminal-title"></div>
                <div class="terminal-subtitle"></div>
              </div>
            </div>
            <div class="terminal-header-center">
              <span class="badge ai-badge">AI</span>
            </div>
            <div class="terminal-header-right">
              <button class="kill-btn"><i class="bi bi-stop-circle"></i> <span class="kill-label">${i18n.t('kill')}</span></button>
              <div class="connection-status">
                <span class="badge status-badge">${i18n.t('disconnected')}</span>
                <span class="status-dot connection-dot"></span>
              </div>
            </div>
          </div>
          <div class="terminal-info">
            <div class="info-grid">
              <div class="info-chip"><span>${i18n.t('cpu')}</span><strong class="cpu-value">0%</strong></div>
              <div class="info-chip"><span>${i18n.t('memory')}</span><strong class="mem-value">0 MB</strong></div>
              <div class="info-chip"><span>${i18n.t('threads')}</span><strong class="threads-value">0</strong></div>
              <div class="info-chip"><span>${i18n.t('latency')}</span><strong class="latency-value">— ms</strong></div>
              <div class="info-chip"><span>${i18n.t('framework')}</span><strong class="framework-value">-</strong></div>
              <div class="info-chip"><span>${i18n.t('watch')}</span><strong class="watch-value">-</strong></div>
              <div class="info-chip"><span>${i18n.t('pid')}</span><strong class="pid-value">-</strong></div>
            </div>
          </div>
        </div>
        <div class="terminal-body" data-drop-hint="${i18n.t('dropFileHint')}"><div class="terminal-instance"></div></div>
        <div class="terminal-footer">
          <div class="footer-left">
            <div class="theme-picker-wrap">
              <button class="theme-picker-btn" title="${i18n.t('themePickerTitle')}">
                <span class="theme-picker-icon"><i class="bi bi-palette2"></i></span>
                <span class="theme-picker-label" data-i18n="theme">${i18n.t('theme')}</span>
                <span class="theme-picker-current"></span>
                <span class="theme-picker-arrow">▾</span>
              </button>
              <div class="theme-dropdown hidden">
                <div class="theme-dropdown-header" data-i18n="themePickerHeader">${i18n.t('themePickerHeader')}</div>
                <div class="theme-option" data-theme="dark">🌑 Dark</div>
                <div class="theme-option" data-theme="dracula">🧛 Dracula</div>
                <div class="theme-option" data-theme="grass">🌿 Grass</div>
                <div class="theme-option" data-theme="ocean">🌊 Ocean</div>
                <div class="theme-option" data-theme="solarized">☀️ Solarized</div>
                <div class="theme-option" data-theme="nord">❄️ Nord</div>
                <div class="theme-option" data-theme="monokai">🎭 Monokai</div>
                <div class="theme-option" data-theme="light">🌤 Light</div>
              </div>
            </div>
          </div>
          <div class="footer-actions">
            <button class="action-btn export-btn">
              <span class="action-icon"><i class="bi bi-file-earmark-text"></i></span>
              <span class="action-label">${i18n.t('exportLog')}</span>
              <span class="action-info-icon" data-help="export" title="${i18n.t('helpExport')}">ⓘ</span>
            </button>
            <button class="action-btn diff-btn">
              <span class="action-icon"><i class="bi bi-code-slash"></i></span>
              <span class="action-label">${i18n.t('viewDiff')}</span>
              <span class="action-info-icon" data-help="diff" title="${i18n.t('helpDiff')}">ⓘ</span>
            </button>
            <button class="action-btn email-icon-btn" title="${i18n.t('sendEmail')}"><i class="bi bi-envelope"></i></button>
          </div>
        </div>
      `;
      this.titleEl = this.containerEl.querySelector('.terminal-title');
      this.subtitleEl = this.containerEl.querySelector('.terminal-subtitle');
      this.connectionDot = this.containerEl.querySelector('.connection-dot');
      this.statusBadge = this.containerEl.querySelector('.status-badge');
      this.aiBadge = this.containerEl.querySelector('.ai-badge');
      this.cpuEl = this.containerEl.querySelector('.cpu-value');
      this.memEl = this.containerEl.querySelector('.mem-value');
      this.threadsEl = this.containerEl.querySelector('.threads-value');
      this.latencyEl = this.containerEl.querySelector('.latency-value');
      this.frameworkEl = this.containerEl.querySelector('.framework-value');
      this.watchEl = this.containerEl.querySelector('.watch-value');
      this.pidEl = this.containerEl.querySelector('.pid-value');
      this.infoEl = this.containerEl.querySelector('.terminal-info');
      this.containerEl.querySelector('.toggle-info').addEventListener('click', () => this.toggleInfo());
      this.containerEl.querySelector('.export-btn').addEventListener('click', e => {
        if (e.target.closest('.action-info-icon')) return; // handled by popover
        window.TerminalHubReport.exportReport(this.terminalId, e.currentTarget);
      });
      this.containerEl.querySelector('.diff-btn').addEventListener('click', e => {
        if (e.target.closest('.action-info-icon')) return;
        window.TerminalHubReport.showCodeChanges(this.terminalId, e.currentTarget);
      });
      this.containerEl.querySelector('.email-icon-btn').addEventListener('click', () => {
        window.TerminalHubReport.showEmailModal(this.terminalId, null);
      });
      this.containerEl.querySelector('.kill-btn').addEventListener('click', e => {
        if (e.target.closest('.action-info-icon')) return;
        this._confirmKill(e.currentTarget);
      });
      this._initHelpPopovers();
      this._initThemePicker();
    }

    // ── Kill confirmation bubble (position: fixed, above the button) ─────────
    _confirmKill(killBtn) {
      const existing = document.querySelector('.kill-confirm');
      if (existing) { existing.remove(); return; }

      const bubble = document.createElement('div');
      bubble.className = 'kill-confirm';
      bubble.innerHTML = `
        <span class="kill-confirm-msg">${i18n.t('killConfirmMsg')}</span>
        <div class="kill-confirm-actions">
          <button class="kill-confirm-cancel">${i18n.t('cancel')}</button>
          <button class="kill-confirm-ok">${i18n.t('killConfirmOk')}</button>
        </div>
      `;
      // Append inside the button so CSS `position:absolute; bottom:calc(100%+8px)`
      // positions it correctly above the button without any manual calculation.
      killBtn.appendChild(bubble);

      bubble.querySelector('.kill-confirm-cancel').addEventListener('click', (e) => {
        e.stopPropagation();
        bubble.remove();
      });
      bubble.querySelector('.kill-confirm-ok').addEventListener('click', (e) => {
        e.stopPropagation();
        bubble.remove();
        window.TerminalHubApp.killTerminal(this.terminalId);
      });

      setTimeout(() => {
        const close = (ev) => {
          if (!bubble.contains(ev.target) && !killBtn.contains(ev.target)) {
            bubble.remove();
            document.removeEventListener('click', close);
          }
        };
        document.addEventListener('click', close);
      }, 0);
    }

    initTerminal() {
      const savedTheme = localStorage.getItem(`terminalhub-term-theme-${this.terminalId}`) || 'dark';
      this.term = new Terminal({
        cursorBlink: true,
        fontSize: 13,
        theme: TerminalWidget.THEMES[savedTheme] || TerminalWidget.THEMES.dark,
        scrollback: 2000,       // lower than 5000 → less memory, faster redraws
        allowTransparency: false,
        fastScrollModifier: 'alt',
      });
      this.fitAddon = new FitAddon.FitAddon();
      this.term.loadAddon(this.fitAddon);
      this.term.loadAddon(new WebLinksAddon.WebLinksAddon());
      this.term.open(this.containerEl.querySelector('.terminal-instance'));
      // Double rAF: first pass lets CSS grid assign the card its column width,
      // second pass gives the browser time to actually paint, then fit.
      requestAnimationFrame(() => requestAnimationFrame(() => { if (this.fitAddon) this._doFit(); }));
      this.term.onData((data) => this.send({ type: 'input', data }));
      this.term.onResize(({ rows, cols }) => this.send({ type: 'resize', rows, cols }));

      // ResizeObserver fires AFTER layout (element dimensions are already final).
      // Strategy:
      //   • rAF before fit() ensures we measure after the browser has applied layout
      //     changes from the resize gesture (avoids stale dimension reads).
      //   • PTY SIGWINCH is debounced 80 ms → avoids flooding the shell.
      //   • term.refresh() is debounced 150 ms → fires once after the drag settles,
      //     forcing a full canvas repaint so text reflows to the new dimensions.
      //     NOT called mid-drag (that caused canvas corruption).
      let _ptyResizeTimer = null;
      let _refreshTimer = null;
      this.resizeObserver = new ResizeObserver(() => {
        if (!this.fitAddon) return;
        // Use rAF to measure after layout is final for this frame
        requestAnimationFrame(() => {
          if (!this.fitAddon) return;
          this.fitAddon.fit();

          clearTimeout(_ptyResizeTimer);
          _ptyResizeTimer = setTimeout(() => {
            if (this.term) this.send({ type: 'resize', rows: this.term.rows, cols: this.term.cols });
          }, 80);

          // After the resize gesture finishes, force a full repaint so content
          // visually adapts to the new column / row count, and keep cursor visible.
          clearTimeout(_refreshTimer);
          _refreshTimer = setTimeout(() => {
            if (!this.fitAddon || !this.term) return;
            this.fitAddon.fit();  // second fit after scrollbar may have appeared/disappeared
            this.term.refresh(0, this.term.rows - 1);
            this.term.scrollToBottom();
          }, 150);
        });
      });
      this.resizeObserver.observe(this.containerEl.querySelector('.terminal-body'));

      // Global window resize — catches viewport-width changes that may not trigger
      // the ResizeObserver (e.g. browser zoom, devtools open/close).
      this._windowResizeHandler = () => {
        requestAnimationFrame(() => { if (this.fitAddon) this._doFit(); });
      };
      window.addEventListener('resize', this._windowResizeHandler);

      this._initDragDrop();
    }

    // Fit xterm to its container and force a full viewport repaint so that
    // previously rendered content is correctly reflowed to the new column count.
    _doFit() {
      if (!this.fitAddon || !this.term) return;
      this.fitAddon.fit();
      this.term.refresh(0, this.term.rows - 1);
      this.term.scrollToBottom();  // keep cursor/input line visible after resize
      this.send({ type: 'resize', rows: this.term.rows, cols: this.term.cols });
      // Second pass after one frame — catches cases where the first fit measured
      // slightly stale dimensions (e.g. scrollbar appearing after content reflow).
      requestAnimationFrame(() => {
        if (!this.fitAddon || !this.term) return;
        this.fitAddon.fit();
        this.term.refresh(0, this.term.rows - 1);
        this.term.scrollToBottom();
        this.send({ type: 'resize', rows: this.term.rows, cols: this.term.cols });
      });
    }

    fit() {
      this._doFit();
    }

    // ── File/folder drag-and-drop → insert path into terminal ─────────────────
    // Key insight: xterm.js canvas elements absorb ALL pointer/drag events.
    // Using capture-phase listeners on .terminal-body + stopPropagation() means
    // our handlers fire FIRST (parent capture → child target → child bubble) and
    // xterm's canvas never sees the drag event at all.
    _initDragDrop() {
      const body = this.containerEl.querySelector('.terminal-body');
      if (!body) return;

      // Overlay for visual feedback only — event flow is handled by capture listeners.
      const overlay = document.createElement('div');
      overlay.className = 'terminal-drop-overlay';
      overlay.setAttribute('data-drop-hint', i18n.t('dropFileHint'));
      body.appendChild(overlay);
      this._dropOverlay = overlay;
      this._dragBody = body;

      const isFileDrag = (dt) => {
        const types = [...(dt?.types || [])];
        return types.includes('Files') || types.includes('public.file-url');
      };

      const onDragEnter = (e) => {
        if (!isFileDrag(e.dataTransfer)) return;
        overlay.classList.add('active');
        e.preventDefault();
        e.stopPropagation();
      };

      const onDragOver = (e) => {
        if (!isFileDrag(e.dataTransfer)) return;
        e.preventDefault();
        e.stopPropagation();
        e.dataTransfer.dropEffect = 'copy';
      };

      // Hide overlay only when cursor actually leaves the terminal body area.
      const onDragLeave = (e) => {
        if (!body.contains(e.relatedTarget)) {
          overlay.classList.remove('active');
        }
      };

      const onDrop = async (e) => {
        if (!isFileDrag(e.dataTransfer)) return;
        e.preventDefault();
        e.stopPropagation();
        overlay.classList.remove('active');

        // Try browser DataTransfer APIs first (works natively in Safari)
        let paths = this._extractPaths(e.dataTransfer);

        // Always try the server resolver — it tracks actual shell cwd via psutil,
        // so it reliably resolves the full path even after the user has cd'd.
        // We do this unconditionally: if browser gave us a path already we verify
        // it; if not, we resolve from name.
        if (e.dataTransfer.items && e.dataTransfer.items.length) {
          const resolveOne = async (item) => {
            const entry = item.webkitGetAsEntry ? item.webkitGetAsEntry() : null;
            const file  = item.getAsFile ? item.getAsFile() : null;
            const name  = entry?.name ?? file?.name ?? null;
            const size  = (file && !entry?.isDirectory) ? file.size : undefined;
            if (!name) return null;
            try {
              const resp = await fetch(`/api/terminals/${this.terminalId}/resolve-path`, {
                method: 'POST',
                headers: { 'content-type': 'application/json' },
                body: JSON.stringify({ name, size }),
                signal: AbortSignal.timeout(3000),
              });
              const data = await resp.json();
              return data.path || null;
            } catch (_) { return null; }
          };
          const serverPaths = (await Promise.all([...e.dataTransfer.items].map(resolveOne)))
            .filter(Boolean);
          if (serverPaths.length) paths = serverPaths;  // server result wins
        }

        if (!paths.length) return;
        const text = paths.map(p => /\s/.test(p) ? `"${p}"` : p).join(' ');
        this.send({ type: 'input', data: text });
        this.term.focus();
      };

      // All four listeners use capture (true) so they intercept before xterm.
      body.addEventListener('dragenter', onDragEnter, true);
      body.addEventListener('dragover',  onDragOver,  true);
      body.addEventListener('dragleave', onDragLeave, true);
      body.addEventListener('drop',      onDrop,      true);
      this._dragHandlers = { onDragEnter, onDragOver, onDragLeave, onDrop };
    }

    // Extract filesystem paths from a DataTransfer object.
    // Priority order (cross-browser):
    //   1. text/uri-list  — Firefox, Safari, some Chrome versions
    //   2. public.file-url — Chrome on macOS for Finder drags (returns file:// URI)
    //   3. text/plain      — last resort plain-text path
    _extractPaths(dataTransfer) {
      const paths = [];

      // Helper: convert a file:// URI string to an OS path
      const fileUriToPath = (uri) => {
        uri = uri.trim();
        if (!uri.startsWith('file://')) return uri;
        try { return decodeURIComponent(new URL(uri).pathname); }
        catch (_) { return decodeURIComponent(uri.replace(/^file:\/\/[^/]*/, '')); }
      };

      // 1. text/uri-list — one URI per line
      const uriList = dataTransfer.getData('text/uri-list');
      if (uriList) {
        uriList.split(/\r?\n/).forEach(line => {
          line = line.trim();
          if (!line || line.startsWith('#')) return;
          paths.push(fileUriToPath(line));
        });
      }

      // 2. public.file-url — Chrome on macOS exposes this instead of text/uri-list
      if (paths.length === 0) {
        const publicUrl = dataTransfer.getData('public.file-url');
        if (publicUrl && publicUrl.trim()) paths.push(fileUriToPath(publicUrl.trim()));
      }

      // 3. text/plain — some apps paste the path directly as plain text
      if (paths.length === 0) {
        const plain = dataTransfer.getData('text/plain');
        if (plain && plain.trim()) paths.push(plain.trim());
      }

      return paths.filter(p => p.startsWith('/'));  // discard non-absolute (e.g. bare file:// URIs)
    }

    // ── ⓘ Help popovers (inline icon inside each action button) ──────────────
    _initHelpPopovers() {
      this.containerEl.querySelectorAll('.action-info-icon').forEach(icon => {
        icon.addEventListener('click', (e) => {
          e.stopPropagation(); // don't trigger the parent button's action
          const key = icon.dataset.help;
          const btn = icon.closest('.action-btn');
          const existing = btn.querySelector('.help-popover');
          if (existing) { existing.remove(); return; }
          // Close any other open popover
          document.querySelectorAll('.help-popover').forEach(p => p.remove());

          const popover = document.createElement('div');
          popover.className = 'help-popover';
          popover.dataset.helpKey = key;
          popover.innerHTML = `<strong>${i18n.t('help_' + key + '_title')}</strong><p>${i18n.t('help_' + key + '_body')}</p>`;
          btn.appendChild(popover);

          setTimeout(() => {
            const close = (ev) => {
              if (!popover.contains(ev.target) && !icon.contains(ev.target)) {
                popover.remove();
                document.removeEventListener('click', close);
              }
            };
            document.addEventListener('click', close);
          }, 0);
        });
      });
    }

    connectSocket() {
      const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
      this.ws = new WebSocket(`${protocol}//${location.host}/ws/terminal/${this.terminalId}`);
      this._pingInterval = null;
      this._pingStart = 0;

      this.ws.onopen = () => {
        this.send({ type: 'resize', rows: this.term.rows, cols: this.term.cols });
        // Start latency probe: send a ping every 1.5 seconds for responsive display
        this._pingInterval = setInterval(() => {
          if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this._pingStart = performance.now();
            this.ws.send(JSON.stringify({ type: 'ping', t: this._pingStart }));
          }
        }, 1500);
        // First ping immediately
        this._pingStart = performance.now();
        this.ws.send(JSON.stringify({ type: 'ping', t: this._pingStart }));
      };

      this.ws.onmessage = (event) => {
        const payload = JSON.parse(event.data);
        if (payload.type === 'output') {
          this.term.write(payload.data);
          // Scroll to bottom so input prompt stays visible during heavy AI output.
          // xterm only auto-scrolls if the viewport is already at bottom; force it
          // here so the cursor/prompt is never clipped during rapid output bursts.
          this.term.scrollToBottom();
        }
        if (payload.type === 'status') this.updateStatus(payload.connected);
        if (payload.type === 'stats') this.updateStats(payload);
        if (payload.type === 'ai_info') this.updateAIInfo(payload);
        if (payload.type === 'pong') this.updateLatency(performance.now() - payload.t);
      };

      this.ws.onclose = () => {
        this.updateStatus(false);
        if (this._pingInterval) { clearInterval(this._pingInterval); this._pingInterval = null; }
      };
    }

    send(payload) {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify(payload));
      }
    }

    toggleInfo() {
      this.infoEl.classList.toggle('expanded');
    }

    updateStatus(connected) {
      this.connectionDot.classList.toggle('online', !!connected);
      this.statusBadge.textContent = connected ? i18n.t('connected') : i18n.t('disconnected');
    }

    updateStats(stats) {
      this.cpuEl.textContent = `${stats.cpu ?? 0}%`;
      this.memEl.textContent = `${stats.mem_mb ?? 0} MB`;
      this.threadsEl.textContent = `${stats.threads ?? 0}`;
      // Update live cwd in subtitle when AI or user runs cd
      if (stats.cwd && stats.cwd !== this._liveCwd) {
        this._liveCwd = stats.cwd;
        this.metadata.cwd = stats.cwd;
        const desc = this.metadata.description || '';
        const cwd  = stats.cwd;
        this.subtitleEl.textContent = `${desc}${desc && cwd ? ' · ' : ''}${cwd}`;
      }
    }

    updateLatency(ms) {
      if (!this.latencyEl) return;
      const rounded = Math.round(ms);
      this.latencyEl.textContent = `${rounded} ms`;
      // Colour-code: green ≤20 ms, yellow ≤80 ms, red >80 ms
      this.latencyEl.className = 'latency-value ' + (
        rounded <= 20 ? 'latency-good' : rounded <= 80 ? 'latency-ok' : 'latency-bad'
      );
    }

    updateAIInfo(info) {
      const text = info.detected ? `${info.framework || info.provider}${info.model ? ` · ${info.model}` : ''}` : i18n.t('aiNotDetected');
      this.aiBadge.textContent = text;
      this.aiBadge.classList.toggle('ai-detected', !!info.detected);
      this.aiBadge.classList.toggle('ai-undetected', !info.detected);
      this.frameworkEl.textContent = text;
    }

    updateCodeChanges(count) {
      // Badge removed; keep as no-op for compatibility
    }

    applyMetadata(metadata) {
      // Preserve live cwd captured from per-terminal stats (psutil) — it is more
      // accurate than session.cwd (the initial directory) and must not be
      // overwritten by the monitor-socket broadcast every 2 s.
      const liveCwd = this._liveCwd;
      this.metadata = { ...this.metadata, ...metadata };
      if (liveCwd !== undefined) this.metadata.cwd = liveCwd;
      this.titleEl.textContent = this.metadata.title || this.title;
      const desc = this.metadata.description || '';
      const cwd  = this.metadata.cwd || '';
      this.subtitleEl.textContent = `${desc}${desc && cwd ? ' · ' : ''}${cwd}`;
      this.watchEl.textContent = this.metadata.watch_path || '-';
      this.pidEl.textContent = `${this.metadata.pid || '-'}`;
      if (this.metadata.stats) this.updateStats({
        cpu: this.metadata.stats.cpu_pct,
        mem_mb: this.metadata.stats.mem_mb,
        threads: this.metadata.stats.threads
      });
      if (this.metadata.ai_info) this.updateAIInfo(this.metadata.ai_info);
      this.updateCodeChanges(this.metadata.code_changes || 0);
      this.updateStatus(this.metadata.alive);
    }

    refreshLabels() {
      this.containerEl.querySelector('.export-btn .action-label').textContent = i18n.t('exportLog');
      this.containerEl.querySelector('.diff-btn .action-label').textContent = i18n.t('viewDiff');
      const killBtn = this.containerEl.querySelector('.kill-btn');
      if (killBtn) {
        const lbl = killBtn.querySelector('.kill-label');
        if (lbl) lbl.textContent = i18n.t('kill');
      }
      const emailBtn = this.containerEl.querySelector('.email-icon-btn');
      if (emailBtn) emailBtn.title = i18n.t('sendEmail');
      if (this._dropOverlay) this._dropOverlay.setAttribute('data-drop-hint', i18n.t('dropFileHint'));
      // Update theme picker labels
      const themeBtn = this.containerEl.querySelector('.theme-picker-btn');
      if (themeBtn) {
        themeBtn.title = i18n.t('themePickerTitle');
        const lbl = themeBtn.querySelector('.theme-picker-label');
        if (lbl) lbl.textContent = i18n.t('theme');
      }
      const themeHeader = this.containerEl.querySelector('.theme-dropdown-header');
      if (themeHeader) themeHeader.textContent = i18n.t('themePickerHeader');
      this.applyMetadata(this.metadata);
    }

    applyTheme() {
      // No-op: terminal theme is controlled per-terminal via the theme picker.
      // Global UI theme changes don't override the user's chosen terminal palette.
      this._doFit();
    }

    applyTerminalTheme(themeKey) {
      if (!this.term) return;
      const t = TerminalWidget.THEMES[themeKey] || TerminalWidget.THEMES.dark;
      this.term.options.theme = t;
      // Update active state in dropdown
      this.containerEl.querySelectorAll('.theme-option').forEach(el => {
        el.classList.toggle('active', el.dataset.theme === themeKey);
      });
      localStorage.setItem(`terminalhub-term-theme-${this.terminalId}`, themeKey);
    }

    _initThemePicker() {
      const btn = this.containerEl.querySelector('.theme-picker-btn');
      const dropdown = this.containerEl.querySelector('.theme-dropdown');
      const currentLabel = this.containerEl.querySelector('.theme-picker-current');
      if (!btn || !dropdown) return;

      const themeLabels = {
        dark: 'Dark', dracula: 'Dracula', grass: 'Grass', ocean: 'Ocean',
        solarized: 'Solarized', nord: 'Nord', monokai: 'Monokai', light: 'Light'
      };

      const setActive = (themeKey) => {
        dropdown.querySelectorAll('.theme-option').forEach(el => {
          el.classList.toggle('active', el.dataset.theme === themeKey);
        });
        if (currentLabel) currentLabel.textContent = themeLabels[themeKey] || themeKey;
      };

      // Mark saved theme as active and show in button
      const saved = localStorage.getItem(`terminalhub-term-theme-${this.terminalId}`) || 'dark';
      setActive(saved);

      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const isHidden = dropdown.classList.contains('hidden');
        // Close all other open dropdowns first
        document.querySelectorAll('.theme-dropdown:not(.hidden)').forEach(d => d.classList.add('hidden'));
        dropdown.classList.toggle('hidden', !isHidden);
      });

      dropdown.querySelectorAll('.theme-option').forEach(el => {
        el.addEventListener('click', () => {
          this.applyTerminalTheme(el.dataset.theme);
          setActive(el.dataset.theme);
          dropdown.classList.add('hidden');
        });
      });

      // Close on outside click
      document.addEventListener('click', (e) => {
        if (!btn.contains(e.target) && !dropdown.contains(e.target)) {
          dropdown.classList.add('hidden');
        }
      });
    }

    dispose() {
      if (this._pingInterval) { clearInterval(this._pingInterval); this._pingInterval = null; }
      if (this.resizeObserver) this.resizeObserver.disconnect();
      if (this._windowResizeHandler) {
        window.removeEventListener('resize', this._windowResizeHandler);
        this._windowResizeHandler = null;
      }
      if (this.ws) this.ws.close();
      if (this.term) this.term.dispose();
      // Clean up all capture-phase drag listeners and the overlay element
      if (this._dragHandlers && this._dragBody) {
        const b = this._dragBody;
        const { onDragEnter, onDragOver, onDragLeave, onDrop } = this._dragHandlers;
        b.removeEventListener('dragenter', onDragEnter, true);
        b.removeEventListener('dragover',  onDragOver,  true);
        b.removeEventListener('dragleave', onDragLeave, true);
        b.removeEventListener('drop',      onDrop,      true);
      }
      if (this._dropOverlay) this._dropOverlay.remove();
      this.containerEl.remove();
    }
  }

  TerminalWidget.THEMES = {
    dark:      { background: '#0d0d17', foreground: '#e2e8f0', cursor: '#a78bfa', selectionBackground: '#a78bfa44' },
    dracula:   { background: '#282a36', foreground: '#f8f8f2', cursor: '#ff79c6', black: '#21222c', red: '#ff5555', green: '#50fa7b', yellow: '#f1fa8c', blue: '#bd93f9', magenta: '#ff79c6', cyan: '#8be9fd', white: '#f8f8f2', selectionBackground: '#44475a' },
    grass:     { background: '#0a1a0a', foreground: '#a8e6a3', cursor: '#57ff57', black: '#0d1f0d', red: '#ff6b6b', green: '#57ff57', yellow: '#ffd700', blue: '#87ceeb', magenta: '#da70d6', cyan: '#7fffd4', white: '#d0ffd0', selectionBackground: '#57ff5744' },
    ocean:     { background: '#0a1628', foreground: '#cdd6f4', cursor: '#89b4fa', black: '#1e2a3a', red: '#f38ba8', green: '#a6e3a1', yellow: '#f9e2af', blue: '#89b4fa', magenta: '#cba6f7', cyan: '#89dceb', white: '#cdd6f4', selectionBackground: '#89b4fa33' },
    solarized: { background: '#002b36', foreground: '#839496', cursor: '#93a1a1', black: '#073642', red: '#dc322f', green: '#859900', yellow: '#b58900', blue: '#268bd2', magenta: '#d33682', cyan: '#2aa198', white: '#eee8d5', selectionBackground: '#073642' },
    nord:      { background: '#2e3440', foreground: '#d8dee9', cursor: '#88c0d0', black: '#3b4252', red: '#bf616a', green: '#a3be8c', yellow: '#ebcb8b', blue: '#81a1c1', magenta: '#b48ead', cyan: '#88c0d0', white: '#e5e9f0', selectionBackground: '#4c566a' },
    monokai:   { background: '#272822', foreground: '#f8f8f2', cursor: '#f8f8f0', black: '#272822', red: '#f92672', green: '#a6e22e', yellow: '#f4bf75', blue: '#66d9ef', magenta: '#ae81ff', cyan: '#a1efe4', white: '#f8f8f2', selectionBackground: '#49483e' },
    light:     { background: '#fafafa', foreground: '#2d2d2d', cursor: '#4f46e5', black: '#000000', red: '#d73a49', green: '#22863a', yellow: '#e36209', blue: '#005cc5', magenta: '#6f42c1', cyan: '#1b7c83', white: '#6a737d', selectionBackground: '#c8e1ff' },
  };

  window.TerminalWidget = TerminalWidget;
})();
