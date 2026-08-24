// AliExpress AI Product Hunter - Frontend Application (Nord Theme, Scraping Gateway & Gemini AI Architecture)

document.addEventListener('DOMContentLoaded', () => {
  if (window.lucide) {
    lucide.createIcons();
  }

  // Country to Currency Mapping
  const COUNTRY_CURRENCY_MAP = {
    AU: 'AUD', US: 'USD', GB: 'GBP', CA: 'CAD', NZ: 'NZD',
    DE: 'EUR', FR: 'EUR', IT: 'EUR', ES: 'EUR', NL: 'EUR',
    AT: 'EUR', BE: 'EUR', FI: 'EUR', GR: 'EUR', IE: 'EUR', PT: 'EUR',
    JP: 'JPY', SG: 'SGD', BR: 'BRL', MX: 'MXN', KR: 'KRW',
    CH: 'CHF', SE: 'SEK', NO: 'NOK', DK: 'DKK', PL: 'PLN',
    IN: 'INR', PH: 'PHP', TH: 'THB', MY: 'MYR', ID: 'IDR',
    VN: 'VND', SA: 'SAR', AE: 'AED', ZA: 'ZAR', TR: 'TRY'
  };

  // State
  let currentApiKey = localStorage.getItem('gemini_api_key') || '';
  let currentGatewayProvider = localStorage.getItem('scraping_provider') || 'zenrows';
  let currentGatewayKey = localStorage.getItem('scraping_api_key') || '';
  let currentCustomGatewayUrl = localStorage.getItem('custom_gateway_url') || '';
  let currentTheme = localStorage.getItem('app_theme') || 'dark';
  let activeEventSource = null;
  let currentSearchId = null;
  let activeProducts = [];
  let activeFilter = 'all';
  let searchTermsList = [];
  let conditionsList = [''];
  let suggestDebounceTimeout = null;
  let activeSuggestIndex = -1;

  // Helper to prevent XSS
  function escapeHTML(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // DOM Elements
  const themeToggleBtn = document.getElementById('theme-toggle-btn');
  const themeIconDark = document.getElementById('theme-icon-dark');
  const themeIconLight = document.getElementById('theme-icon-light');

  const navSearchTab = document.getElementById('nav-search-tab');
  const navHistoryTab = document.getElementById('nav-history-tab');
  const searchSection = document.getElementById('search-section');
  const historySection = document.getElementById('history-section');
  const historyBadgeCount = document.getElementById('history-badge-count');

  // Key Modal Elements
  const openApiKeyBtn = document.getElementById('open-api-key-btn');
  const apiKeyModal = document.getElementById('api-key-modal');
  const closeApiKeyModal = document.getElementById('close-api-key-modal');
  const cancelApiKeyBtn = document.getElementById('cancel-api-key-btn');
  const apiKeyForm = document.getElementById('api-key-form');
  const geminiKeyInput = document.getElementById('gemini-key-input');
  const apiKeyIndicator = document.getElementById('api-key-indicator');
  const apiKeyBtnText = document.getElementById('api-key-btn-text');
  const keyValidationMessage = document.getElementById('key-validation-message');

  // Gateway Modal Elements
  const openGatewayBtn = document.getElementById('open-gateway-btn');
  const gatewayModal = document.getElementById('gateway-modal');
  const closeGatewayModal = document.getElementById('close-gateway-modal');
  const gatewayForm = document.getElementById('gateway-form');
  const gatewayProviderSelect = document.getElementById('gateway-provider-select');
  const gatewayKeyInput = document.getElementById('gateway-key-input');
  const customGatewayUrlGroup = document.getElementById('custom-gateway-url-group');
  const customGatewayUrlInput = document.getElementById('custom-gateway-url-input');
  const testGatewayBtn = document.getElementById('test-gateway-btn');
  const gatewayIndicator = document.getElementById('gateway-indicator');
  const gatewayValidationMessage = document.getElementById('gateway-validation-message');

  // Search Form Elements
  const searchForm = document.getElementById('search-form');
  const searchTermInput = document.getElementById('search-term-input');
  const searchChipsContainer = document.getElementById('search-chips-container');
  const suggestionsDropdown = document.getElementById('suggestions-dropdown');
  const conditionsContainer = document.getElementById('conditions-container');
  const addConditionBtn = document.getElementById('add-condition-btn');
  const conditionCountBadge = document.getElementById('condition-count-badge');
  const shipCountrySelect = document.getElementById('ship-country-select');
  const currencySelect = document.getElementById('currency-select');
  const modelSelect = document.getElementById('model-select');
  const maxCandidatesSelect = document.getElementById('max-candidates-select');
  const startSearchBtn = document.getElementById('start-search-btn');

  // Live Status & Results Elements
  const liveStatusCard = document.getElementById('live-status-card');
  const liveStageTitle = document.getElementById('live-stage-title');
  const liveProgressBadge = document.getElementById('live-progress-badge');
  const liveProgressBar = document.getElementById('live-progress-bar');
  const liveStatDiscovered = document.getElementById('live-stat-discovered');
  const liveStatEvaluated = document.getElementById('live-stat-evaluated');
  const liveStatMatches = document.getElementById('live-stat-matches');
  const resultsCountLabel = document.getElementById('results-count-label');
  const resultsEmptyState = document.getElementById('results-empty-state');
  const productsList = document.getElementById('products-list');
  const countAll = document.getElementById('count-all');
  const countMatches = document.getElementById('count-matches');
  const countExcluded = document.getElementById('count-excluded');
  const filterTabBtns = document.querySelectorAll('.filter-tab-btn');

  // Detail Modal Elements
  const productDetailModal = document.getElementById('product-detail-modal');
  const closeDetailModal = document.getElementById('close-detail-modal');
  const modalProductTitle = document.getElementById('modal-product-title');
  const modalProductPrice = document.getElementById('modal-product-price');
  const modalProductLink = document.getElementById('modal-product-link');
  const modalVerdictBox = document.getElementById('modal-verdict-box');
  const modalCriteriaList = document.getElementById('modal-criteria-list');
  const modalSpecsList = document.getElementById('modal-specs-list');

  // History Elements
  const historyGrid = document.getElementById('history-grid');
  const historyEmptyState = document.getElementById('history-empty-state');

  // 1. Theme Management
  function applyTheme(theme) {
    currentTheme = theme;
    localStorage.setItem('app_theme', theme);
    if (theme === 'light') {
      document.documentElement.classList.add('light-theme');
      if (themeIconDark) themeIconDark.classList.remove('hidden');
      if (themeIconLight) themeIconLight.classList.add('hidden');
    } else {
      document.documentElement.classList.remove('light-theme');
      if (themeIconDark) themeIconDark.classList.add('hidden');
      if (themeIconLight) themeIconLight.classList.remove('hidden');
    }
  }

  applyTheme(currentTheme);

  if (themeToggleBtn) {
    themeToggleBtn.addEventListener('click', () => {
      applyTheme(currentTheme === 'dark' ? 'light' : 'dark');
    });
  }

  // 2. Navigation Tabs
  navSearchTab.addEventListener('click', () => {
    navSearchTab.classList.add('active');
    navHistoryTab.classList.remove('active');
    searchSection.classList.remove('hidden');
    historySection.classList.add('hidden');
  });

  navHistoryTab.addEventListener('click', () => {
    navHistoryTab.classList.add('active');
    navSearchTab.classList.remove('active');
    historySection.classList.remove('hidden');
    searchSection.classList.add('hidden');
    loadHistory();
  });

  // 3. Country & Currency Synchronization
  shipCountrySelect.addEventListener('change', () => {
    const country = shipCountrySelect.value;
    const recommendedCurrency = COUNTRY_CURRENCY_MAP[country] || 'USD';
    currencySelect.value = recommendedCurrency;
  });

  // 4. Scraping Gateway Settings Management
  function updateGatewayIndicator() {
    if (gatewayIndicator) {
      if (currentGatewayKey || currentGatewayProvider === 'custom') {
        gatewayIndicator.className = 'w-2 h-2 rounded-full bg-emerald-400';
      } else {
        gatewayIndicator.className = 'w-2 h-2 rounded-full bg-nord-13';
      }
    }
  }

  function openGatewaySettings() {
    if (gatewayProviderSelect) gatewayProviderSelect.value = currentGatewayProvider;
    if (gatewayKeyInput) gatewayKeyInput.value = currentGatewayKey;
    if (customGatewayUrlInput) customGatewayUrlInput.value = currentCustomGatewayUrl;
    toggleCustomUrlGroup();
    if (gatewayValidationMessage) gatewayValidationMessage.classList.add('hidden');
    gatewayModal.classList.remove('hidden');
    gatewayModal.classList.add('flex');
    if (window.lucide) lucide.createIcons();
  }

  function closeGatewaySettings() {
    gatewayModal.classList.add('hidden');
    gatewayModal.classList.remove('flex');
  }

  function toggleCustomUrlGroup() {
    if (gatewayProviderSelect && customGatewayUrlGroup) {
      if (gatewayProviderSelect.value === 'custom') {
        customGatewayUrlGroup.classList.remove('hidden');
      } else {
        customGatewayUrlGroup.classList.add('hidden');
      }
    }
  }

  if (gatewayProviderSelect) {
    gatewayProviderSelect.addEventListener('change', toggleCustomUrlGroup);
  }

  if (openGatewayBtn) openGatewayBtn.addEventListener('click', openGatewaySettings);
  if (closeGatewayModal) closeGatewayModal.addEventListener('click', closeGatewaySettings);

  if (gatewayForm) {
    gatewayForm.addEventListener('submit', (e) => {
      e.preventDefault();
      currentGatewayProvider = gatewayProviderSelect.value;
      currentGatewayKey = gatewayKeyInput.value.trim();
      currentCustomGatewayUrl = customGatewayUrlInput.value.trim();

      localStorage.setItem('scraping_provider', currentGatewayProvider);
      localStorage.setItem('scraping_api_key', currentGatewayKey);
      localStorage.setItem('custom_gateway_url', currentCustomGatewayUrl);

      updateGatewayIndicator();
      closeGatewaySettings();
    });
  }

  if (testGatewayBtn) {
    testGatewayBtn.addEventListener('click', async () => {
      const provider = gatewayProviderSelect.value;
      const key = gatewayKeyInput.value.trim();
      const customUrl = customGatewayUrlInput.value.trim();

      testGatewayBtn.disabled = true;
      testGatewayBtn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin text-nord-8"></i><span>Testing...</span>`;
      if (window.lucide) lucide.createIcons();

      gatewayValidationMessage.className = 'text-xs p-3 rounded-xl border bg-nord-8/10 text-nord-8 border-nord-8/30 block';
      gatewayValidationMessage.textContent = 'Testing connection to AliExpress through gateway...';
      gatewayValidationMessage.classList.remove('hidden');

      try {
        const res = await fetch('/api/validate-gateway', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            provider: provider,
            api_key: key,
            custom_gateway_url: customUrl
          })
        });
        const data = await res.json();

        if (data.valid) {
          gatewayValidationMessage.className = 'text-xs p-3 rounded-xl border bg-nord-14/15 text-nord-14 border-nord-14/30 block';
          gatewayValidationMessage.innerHTML = `<strong>✅ Success!</strong> ${escapeHTML(data.message)}`;
        } else {
          gatewayValidationMessage.className = 'text-xs p-3 rounded-xl border bg-nord-11/15 text-nord-11 border-nord-11/30 block';
          gatewayValidationMessage.innerHTML = `<strong>❌ Connection Failed:</strong> ${escapeHTML(data.message)}`;
        }
      } catch (err) {
        gatewayValidationMessage.className = 'text-xs p-3 rounded-xl border bg-nord-11/15 text-nord-11 border-nord-11/30 block';
        gatewayValidationMessage.textContent = 'Error connecting to validation server: ' + err.message;
      } finally {
        testGatewayBtn.disabled = false;
        testGatewayBtn.innerHTML = `<i data-lucide="activity" class="w-4 h-4 text-nord-8"></i><span>Test Connection</span>`;
        if (window.lucide) lucide.createIcons();
      }
    });
  }

  updateGatewayIndicator();

  // 5. Gemini API Key & Model Validation
  function updateApiKeyStatus(hasKey) {
    if (hasKey) {
      apiKeyIndicator.className = 'w-2 h-2 rounded-full bg-emerald-400';
      apiKeyBtnText.textContent = 'Gemini Key Active';
      closeApiKeyModal.classList.remove('hidden');
      cancelApiKeyBtn.classList.remove('hidden');
    } else {
      apiKeyIndicator.className = 'w-2 h-2 rounded-full bg-amber-400';
      apiKeyBtnText.textContent = 'Set Gemini Key';
      closeApiKeyModal.classList.add('hidden');
      cancelApiKeyBtn.classList.add('hidden');
    }
  }

  function checkApiKeyEntranceGate() {
    if (!currentApiKey) {
      geminiKeyInput.value = '';
      keyValidationMessage.classList.add('hidden');
      apiKeyModal.classList.remove('hidden');
      apiKeyModal.classList.add('flex');
      geminiKeyInput.focus();
    } else {
      updateApiKeyStatus(true);
      fetchModels(currentApiKey);
    }
  }

  openApiKeyBtn.addEventListener('click', () => {
    geminiKeyInput.value = currentApiKey;
    keyValidationMessage.classList.add('hidden');
    apiKeyModal.classList.remove('hidden');
    apiKeyModal.classList.add('flex');
    geminiKeyInput.focus();
  });

  closeApiKeyModal.addEventListener('click', () => {
    apiKeyModal.classList.add('hidden');
    apiKeyModal.classList.remove('flex');
  });

  cancelApiKeyBtn.addEventListener('click', () => {
    apiKeyModal.classList.add('hidden');
    apiKeyModal.classList.remove('flex');
  });

  async function fetchModels(key) {
    try {
      const res = await fetch('/api/models', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: key })
      });
      const data = await res.json();
      if (data.models && data.models.length > 0) {
        populateModelDropdown(data.models);
      }
    } catch (e) {}
  }

  function populateModelDropdown(models) {
    const currentVal = modelSelect.value;
    modelSelect.innerHTML = '';
    models.forEach((m, idx) => {
      const opt = document.createElement('option');
      opt.value = m;
      opt.textContent = m + (idx === 0 ? ' (Recommended)' : '');
      modelSelect.appendChild(opt);
    });

    if (models.includes(currentVal)) {
      modelSelect.value = currentVal;
    } else {
      modelSelect.value = models[0];
    }
  }

  apiKeyForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const key = geminiKeyInput.value.trim();
    if (!key) return;

    keyValidationMessage.className = 'text-xs p-3 rounded-xl border bg-nord-8/10 text-nord-8 border-nord-8/30 block';
    keyValidationMessage.textContent = 'Verifying API key & testing generation quota...';
    keyValidationMessage.classList.remove('hidden');

    try {
      const res = await fetch('/api/validate-key', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: key })
      });
      const data = await res.json();

      if (data.valid && data.quota_available) {
        currentApiKey = key;
        localStorage.setItem('gemini_api_key', key);
        updateApiKeyStatus(true);
        if (data.models && data.models.length > 0) {
          populateModelDropdown(data.models);
        }
        apiKeyModal.classList.add('hidden');
        apiKeyModal.classList.remove('flex');
      } else {
        keyValidationMessage.className = 'text-xs p-3 rounded-xl border bg-nord-11/15 text-nord-11 border-nord-11/30 block';
        keyValidationMessage.innerHTML = `<strong>Validation Failed:</strong> ${escapeHTML(data.message || 'Invalid Gemini API key.')}`;
      }
    } catch (err) {
      keyValidationMessage.className = 'text-xs p-3 rounded-xl border bg-nord-11/15 text-nord-11 border-nord-11/30 block';
      keyValidationMessage.textContent = 'Error connecting to validation server.';
    }
  });

  // 6. Search Terms Chips
  function renderSearchChips() {
    searchChipsContainer.innerHTML = '';
    if (searchTermsList.length === 0) {
      searchChipsContainer.innerHTML = '<span id="chips-empty-hint" class="text-xs text-nord-3 italic px-1 py-0.5">No search terms confirmed yet. Type above and press Enter.</span>';
      return;
    }

    searchTermsList.forEach((term, index) => {
      const chip = document.createElement('span');
      chip.className = 'inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-nord-8/15 text-nord-8 border border-nord-8/30 text-xs font-semibold';
      chip.innerHTML = `
        <span>${escapeHTML(term)}</span>
        <button type="button" data-index="${index}" class="remove-chip-btn hover:text-nord-11 transition focus:outline-none">
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
        </button>
      `;
      searchChipsContainer.appendChild(chip);
    });

    searchChipsContainer.querySelectorAll('.remove-chip-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const idx = parseInt(btn.dataset.index, 10);
        searchTermsList.splice(idx, 1);
        renderSearchChips();
      });
    });
  }

  function addSearchTerm(term) {
    const clean = term.trim();
    if (clean && !searchTermsList.includes(clean)) {
      searchTermsList.push(clean);
      renderSearchChips();
    }
  }

  searchTermInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      if (searchTermInput.value.trim()) {
        addSearchTerm(searchTermInput.value);
        searchTermInput.value = '';
        suggestionsDropdown.classList.add('hidden');
      }
    }
  });

  // 7. Dynamic Numbered Conditions
  function renderConditions() {
    conditionsContainer.innerHTML = '';
    conditionsList.forEach((cond, index) => {
      const row = document.createElement('div');
      row.className = 'flex items-center gap-2 relative';
      row.innerHTML = `
        <span class="w-6 h-6 rounded-lg bg-nord-2 text-nord-4 font-mono font-bold text-xs flex items-center justify-center flex-shrink-0">${index + 1}</span>
        <input type="text" data-index="${index}" value="${escapeHTML(cond)}" placeholder="Condition ${index + 1} (e.g. Under $80 AUD)" class="condition-input flex-1 theme-bg-input border theme-border rounded-xl px-3.5 py-2 text-xs text-nord-5 focus:outline-none focus:border-nord-8">
        ${conditionsList.length > 1 ? `
          <button type="button" data-index="${index}" class="remove-condition-btn text-nord-3 hover:text-nord-11 p-1 transition" title="Remove condition">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
          </button>
        ` : ''}
      `;
      conditionsContainer.appendChild(row);
    });

    conditionCountBadge.textContent = `${conditionsList.length} / 10`;

    conditionsContainer.querySelectorAll('.condition-input').forEach(input => {
      input.addEventListener('input', (e) => {
        const idx = parseInt(e.target.dataset.index, 10);
        conditionsList[idx] = e.target.value;
      });
    });

    conditionsContainer.querySelectorAll('.remove-condition-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const idx = parseInt(btn.dataset.index, 10);
        conditionsList.splice(idx, 1);
        renderConditions();
      });
    });
  }

  addConditionBtn.addEventListener('click', () => {
    if (conditionsList.length < 10) {
      conditionsList.push('');
      renderConditions();
      const inputs = conditionsContainer.querySelectorAll('.condition-input');
      inputs[inputs.length - 1].focus();
    }
  });

  renderConditions();

  // 8. Product Rendering & Filter Tabs
  filterTabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      filterTabBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      activeFilter = btn.dataset.filter;
      renderProducts();
    });
  });

  function renderProducts() {
    productsList.innerHTML = '';
    const filtered = activeProducts.filter(p => {
      if (activeFilter === 'matches') return p.is_match;
      if (activeFilter === 'excluded') return !p.is_match;
      return true;
    });

    const matchCount = activeProducts.filter(p => p.is_match).length;
    const excludedCount = activeProducts.length - matchCount;

    countAll.textContent = activeProducts.length;
    countMatches.textContent = matchCount;
    countExcluded.textContent = excludedCount;
    resultsCountLabel.textContent = `${filtered.length} of ${activeProducts.length} items`;

    if (filtered.length === 0) {
      resultsEmptyState.classList.remove('hidden');
    } else {
      resultsEmptyState.classList.add('hidden');
    }

    filtered.forEach(p => {
      const card = document.createElement('div');
      card.className = `theme-bg-card border ${p.is_match ? 'border-nord-14/40 hover:border-nord-14' : 'border-nord-11/30 opacity-75 hover:opacity-100'} rounded-2xl p-4 transition shadow-lg flex flex-col justify-between`;

      const imgPlaceholder = p.image_url ? `
        <img src="${escapeHTML(p.image_url)}" alt="${escapeHTML(p.title)}" class="w-full h-44 object-cover rounded-xl mb-3 bg-nord-0">
      ` : `
        <div class="w-full h-44 rounded-xl mb-3 bg-nord-0 flex items-center justify-center text-nord-3 text-xs">No image preview</div>
      `;

      card.innerHTML = `
        <div>
          ${imgPlaceholder}
          <div class="flex items-center justify-between mb-1.5">
            <span class="text-xs font-bold font-mono text-nord-14">${escapeHTML(p.price || 'N/A')}</span>
            <span class="px-2.5 py-0.5 rounded-full text-[10px] font-bold ${p.is_match ? 'bg-nord-14/20 text-nord-14 border border-nord-14/30' : 'bg-nord-11/20 text-nord-11 border border-nord-11/30'}">
              ${p.is_match ? 'MATCH' : 'EXCLUDED'}
            </span>
          </div>
          <h4 class="text-xs font-bold text-nord-6 line-clamp-2 mb-2 leading-relaxed" title="${escapeHTML(p.title)}">${escapeHTML(p.title)}</h4>
          <p class="text-[11px] text-nord-4 opacity-90 line-clamp-2 mb-3 leading-relaxed">${escapeHTML(p.verdict_reason || 'Evaluated by Gemini AI')}</p>
        </div>

        <div class="flex items-center gap-2 pt-3 border-t theme-border">
          <button type="button" class="view-detail-btn flex-1 py-1.5 rounded-lg bg-nord-2 hover:bg-nord-3 text-nord-5 text-xs font-semibold transition" data-id="${p.item_id}">
            View Evaluation
          </button>
          <a href="${escapeHTML(p.url)}" target="_blank" class="p-1.5 rounded-lg bg-nord-8/15 text-nord-8 hover:bg-nord-8/25 transition" title="Open on AliExpress">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path></svg>
          </a>
        </div>
      `;

      card.querySelector('.view-detail-btn').addEventListener('click', () => {
        openProductModal(p);
      });

      productsList.appendChild(card);
    });
  }

  function openProductModal(product) {
    modalProductTitle.textContent = product.title;
    modalProductPrice.textContent = product.price || 'N/A';
    modalProductLink.href = product.url;

    modalVerdictBox.className = `p-3.5 rounded-xl border ${product.is_match ? 'bg-nord-14/10 border-nord-14/30 text-nord-14' : 'bg-nord-11/10 border-nord-11/30 text-nord-11'}`;
    modalVerdictBox.innerHTML = `
      <div class="font-bold mb-1 flex items-center gap-1.5">
        <span>${product.is_match ? '✅ ALL CRITERIA MET' : '❌ CRITERIA FAILED'}</span>
        ${product.confidence ? `<span class="text-[10px] font-mono opacity-80">(${Math.round(product.confidence * 100)}% confidence)</span>` : ''}
      </div>
      <p class="text-xs opacity-95 leading-relaxed">${escapeHTML(product.verdict_reason || '')}</p>
    `;

    modalCriteriaList.innerHTML = '';
    if (product.criteria_breakdown && product.criteria_breakdown.length > 0) {
      product.criteria_breakdown.forEach(c => {
        const item = document.createElement('div');
        item.className = 'p-2.5 rounded-xl bg-nord-0/50 border theme-border space-y-1';
        item.innerHTML = `
          <div class="flex items-center justify-between font-bold text-xs">
            <span class="text-nord-5">${escapeHTML(c.condition)}</span>
            <span class="${c.met ? 'text-nord-14' : 'text-nord-11'}">${c.met ? 'PASS' : 'FAIL'}</span>
          </div>
          <p class="text-[11px] text-nord-4 opacity-80">${escapeHTML(c.evidence || 'Evaluated from listing')}</p>
        `;
        modalCriteriaList.appendChild(item);
      });
    } else {
      modalCriteriaList.innerHTML = '<span class="text-xs text-nord-3 italic">No granular criteria breakdown available.</span>';
    }

    modalSpecsList.innerHTML = '';
    if (product.specs && product.specs.length > 0) {
      product.specs.forEach(s => {
        const specEl = document.createElement('div');
        specEl.className = 'p-1.5 bg-nord-1/60 rounded-lg text-[11px] text-nord-4';
        specEl.textContent = s;
        modalSpecsList.appendChild(specEl);
      });
    } else {
      modalSpecsList.innerHTML = '<span class="text-xs text-nord-3 italic col-span-2">No structured specs found on page.</span>';
    }

    productDetailModal.classList.remove('hidden');
    productDetailModal.classList.add('flex');
  }

  closeDetailModal.addEventListener('click', () => {
    productDetailModal.classList.add('hidden');
    productDetailModal.classList.remove('flex');
  });

  // 9. Search Submission
  searchForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!currentApiKey) {
      checkApiKeyEntranceGate();
      return;
    }

    if (searchTermInput.value.trim()) {
      addSearchTerm(searchTermInput.value);
      searchTermInput.value = '';
    }

    if (searchTermsList.length === 0) {
      searchTermInput.focus();
      return;
    }

    const validConditions = conditionsList.map(c => c.trim()).filter(Boolean);
    const selectedCountryText = shipCountrySelect.options[shipCountrySelect.selectedIndex].text;
    const countryCriteriaText = `Deliverable and shippable to ${selectedCountryText}`;
    if (!validConditions.some(c => c.toLowerCase().includes('deliverable') || c.toLowerCase().includes('shipping'))) {
      validConditions.push(countryCriteriaText);
    }

    const joinedConditions = validConditions.map((c, i) => `${i + 1}. ${c}`).join('\n');

    activeProducts = [];
    renderProducts();
    liveStatusCard.classList.remove('hidden');
    liveStageTitle.textContent = 'Starting Scraping Gateway & AI Evaluation Pipeline...';
    liveProgressBadge.textContent = '0%';
    liveProgressBar.style.width = '0%';
    liveStatDiscovered.textContent = '0';
    liveStatEvaluated.textContent = '0';
    liveStatMatches.textContent = '0';
    resultsEmptyState.classList.add('hidden');
    productsList.classList.remove('hidden');
    startSearchBtn.disabled = true;
    startSearchBtn.classList.add('opacity-60', 'cursor-not-allowed');

    try {
      const res = await fetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          search_term: searchTermsList[0],
          search_terms: searchTermsList,
          conditions: joinedConditions,
          gemini_api_key: currentApiKey,
          scraping_provider: currentGatewayProvider,
          scraping_api_key: currentGatewayKey,
          custom_gateway_url: currentCustomGatewayUrl,
          max_candidates: parseInt(maxCandidatesSelect.value, 10),
          ship_country: shipCountrySelect.value,
          currency: currencySelect.value,
          model_name: modelSelect.value
        })
      });

      const data = await res.json();
      if (data.search_id) {
        currentSearchId = data.search_id;
        connectSSEStream(currentSearchId);
      } else {
        alert('Failed to start search: ' + (data.detail || 'Unknown error'));
        startSearchBtn.disabled = false;
        startSearchBtn.classList.remove('opacity-60', 'cursor-not-allowed');
      }
    } catch (err) {
      alert('Error initiating search: ' + err.message);
      startSearchBtn.disabled = false;
      startSearchBtn.classList.remove('opacity-60', 'cursor-not-allowed');
    }
  });

  // 10. SSE Stream Connection
  function connectSSEStream(searchId) {
    if (activeEventSource) {
      activeEventSource.close();
    }

    activeEventSource = new EventSource(`/api/search/stream/${searchId}`);

    activeEventSource.onmessage = (e) => {
      try {
        const payload = JSON.parse(e.data);
        handleSSEEvent(payload);
      } catch (err) {}
    };

    activeEventSource.onerror = () => {
      if (activeEventSource) activeEventSource.close();
      startSearchBtn.disabled = false;
      startSearchBtn.classList.remove('opacity-60', 'cursor-not-allowed');
    };
  }

  function handleSSEEvent(event) {
    if (event.stage) liveStageTitle.textContent = event.stage;
    if (typeof event.progress_pct === 'number') {
      liveProgressBadge.textContent = `${event.progress_pct}%`;
      liveProgressBar.style.width = `${event.progress_pct}%`;
    }

    switch (event.type) {
      case 'candidate_discovered':
        const discovered = parseInt(liveStatDiscovered.textContent, 10) || 0;
        liveStatDiscovered.textContent = discovered + 1;
        break;

      case 'item_evaluated':
        const evaluated = parseInt(liveStatEvaluated.textContent, 10) || 0;
        liveStatEvaluated.textContent = evaluated + 1;
        const item = event.data || event;
        const existingIdx = activeProducts.findIndex(p => p.item_id === item.item_id);
        if (existingIdx !== -1) {
          activeProducts[existingIdx] = item;
        } else {
          activeProducts.push(item);
        }
        const matches = activeProducts.filter(p => p.is_match).length;
        liveStatMatches.textContent = matches;
        renderProducts();
        break;

      case 'search_completed':
        liveStageTitle.textContent = 'Search & AI Evaluation Complete!';
        liveProgressBadge.textContent = '100%';
        liveProgressBar.style.width = '100%';
        startSearchBtn.disabled = false;
        startSearchBtn.classList.remove('opacity-60', 'cursor-not-allowed');
        if (activeEventSource) activeEventSource.close();
        break;

      case 'search_error':
        liveStageTitle.textContent = `Error: ${event.data?.error || 'Search encountered an error'}`;
        startSearchBtn.disabled = false;
        startSearchBtn.classList.remove('opacity-60', 'cursor-not-allowed');
        if (activeEventSource) activeEventSource.close();
        break;

      case 'stream_end':
        startSearchBtn.disabled = false;
        startSearchBtn.classList.remove('opacity-60', 'cursor-not-allowed');
        if (activeEventSource) activeEventSource.close();
        break;
    }
  }

  // 11. History Management
  async function loadHistory() {
    try {
      const res = await fetch('/api/history');
      const data = await res.json();
      const searches = data.searches || [];

      if (historyBadgeCount) historyBadgeCount.textContent = searches.length;

      if (searches.length === 0) {
        historyEmptyState.classList.remove('hidden');
        historyGrid.innerHTML = '';
        return;
      }

      historyEmptyState.classList.add('hidden');
      historyGrid.innerHTML = '';

      searches.forEach(s => {
        const card = document.createElement('div');
        card.className = 'theme-bg-card border theme-border rounded-2xl p-5 shadow-lg flex flex-col justify-between hover:border-nord-8 transition';
        card.innerHTML = `
          <div>
            <div class="flex items-center justify-between mb-2">
              <span class="text-xs font-mono text-nord-3">${new Date(s.created_at || Date.now()).toLocaleDateString()}</span>
              <span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-nord-8/20 text-nord-8 font-mono">${s.match_count || 0} Matches</span>
            </div>
            <h4 class="font-bold text-sm text-nord-6 mb-1">${escapeHTML(s.search_term)}</h4>
            <p class="text-xs text-nord-4 opacity-80 line-clamp-2 mb-3">${escapeHTML(s.conditions)}</p>
          </div>
          <div class="flex items-center justify-between pt-3 border-t theme-border">
            <span class="text-xs font-mono text-nord-4">${s.total_candidates || 0} Evaluated</span>
            <div class="flex items-center gap-2">
              <button class="delete-history-btn text-nord-3 hover:text-nord-11 p-1 transition" data-id="${s.search_id}" title="Delete Record">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
              </button>
            </div>
          </div>
        `;

        card.querySelector('.delete-history-btn').addEventListener('click', async (e) => {
          e.stopPropagation();
          if (confirm('Delete this search record?')) {
            await fetch(`/api/history/${s.search_id}`, { method: 'DELETE' });
            loadHistory();
          }
        });

        historyGrid.appendChild(card);
      });
    } catch (e) {}
  }

  // Initialize
  checkApiKeyEntranceGate();
});
