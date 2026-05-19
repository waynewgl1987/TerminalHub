(function () {
  const storageKey = 'terminalhub-ai-config';

  const AIConfigPanel = {
    providers: [],
    async init() {
      this.panel = document.getElementById('aiPanel');
      this.providerEl = document.getElementById('aiProvider');
      this.modelEl = document.getElementById('aiModel');
      this.baseUrlEl = document.getElementById('aiBaseUrl');
      this.apiKeyEl = document.getElementById('aiApiKey');
      this.statusDot = document.getElementById('aiStatusDot');
      this.statusText = document.getElementById('aiStatusText');
      document.getElementById('openAIPanel').addEventListener('click', () => this.open());
      document.getElementById('closeAIPanel').addEventListener('click', () => this.close());
      document.getElementById('saveAIConfig').addEventListener('click', () => this.save());
      document.getElementById('testAIConnection').addEventListener('click', () => this.testConnection());
      this.providerEl.addEventListener('change', () => this.loadModels(this.providerEl.value));
      this.providers = await fetch('/api/ai/providers').then((r) => r.json());
      this.renderProviders();
      this.restore();
    },
    renderProviders() {
      this.providerEl.innerHTML = this.providers.map((item) => `<option value="${item.id}">${item.name}</option>`).join('');
    },
    open() {
      this.panel.classList.remove('hidden');
    },
    close() {
      this.panel.classList.add('hidden');
    },
    getConfig() {
      return {
        provider: this.providerEl.value,
        model: this.modelEl.value,
        base_url: this.baseUrlEl.value.trim(),
        api_key: this.apiKeyEl.value.trim()
      };
    },
    async loadModels(provider, preferred = '') {
      const data = await fetch(`/api/ai/models?provider=${encodeURIComponent(provider)}`).then((r) => r.json());
      this.modelEl.innerHTML = (data.models || []).map((item) => `<option value="${item}">${item}</option>`).join('');
      if (preferred) this.modelEl.value = preferred;
      if (!this.modelEl.value && this.modelEl.options.length) this.modelEl.selectedIndex = 0;
      this.toggleCredentialInputs(provider);
    },
    toggleCredentialInputs(provider) {
      const requiresKey = !['copilot', 'ollama'].includes(provider);
      this.apiKeyEl.closest('label').style.display = requiresKey ? '' : '';
      this.baseUrlEl.closest('label').style.display = ['ollama', 'custom'].includes(provider) ? '' : '';
    },
    async restore() {
      const saved = JSON.parse(localStorage.getItem(storageKey) || '{}');
      const provider = saved.provider || 'copilot';
      this.providerEl.value = provider;
      await this.loadModels(provider, saved.model || '');
      this.baseUrlEl.value = saved.base_url || '';
      this.apiKeyEl.value = saved.api_key || '';
    },
    save() {
      localStorage.setItem(storageKey, JSON.stringify(this.getConfig()));
      this.statusText.textContent = i18n.t('saving');
      setTimeout(() => {
        this.statusText.textContent = i18n.t('connectionOk');
      }, 400);
      window.dispatchEvent(new CustomEvent('terminalhub:ai-config-changed', { detail: this.getConfig() }));
    },
    async testConnection() {
      this.statusDot.classList.remove('online');
      this.statusText.textContent = i18n.t('testing');
      const payload = this.getConfig();
      const result = await fetch('/api/ai/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      }).then((r) => r.json());
      this.statusDot.classList.toggle('online', !!result.ok);
      this.statusText.textContent = result.message || (result.ok ? i18n.t('connectionOk') : i18n.t('connectionFailed'));
    }
  };

  window.AIConfigPanel = AIConfigPanel;
})();
