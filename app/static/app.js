// AliExpress AI Product Hunter - Frontend Application (Nord Theme, Multi-Term Chips & Smart Verification)

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
  let currentTheme = localStorage.getItem('app_theme') || 'dark';
  let activeEventSource = null;
  let currentSearchId = null;
  let activeProducts = [];
  let activeFilter = 'all';
  let searchTermsList = [];
  let conditionsList = [''];
  let suggestDebounceTimeout = null;
  let activeSuggestIndex = -1;

  // CAPTCHA drag state
  let isDraggingCaptcha = false;
  let captchaDragStart = { x: 0, y: 0 };
  let captchaDragCurrent = { x: 0, y: 0 };
  let activeCaptchaImage = new Image();

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

  // CAPTCHA Modal Elements
  const captchaModal = document.getElementById('captcha-modal');
  const captchaSolveView = document.getElementById('captcha-solve-view');
  const captchaFailureView = document.getElementById('captcha-failure-view');
  const captchaFailureMessage = document.getElementById('captcha-failure-message');
  const remainingTermsList = document.getElementById('remaining-terms-list');
  const retryCaptchaBtn = document.getElementById('retry-captcha-btn');
  const continueRemainingBtn = document.getElementById('continue-remaining-btn');
  const closeCaptchaModal = document.getElementById('close-captcha-modal');
  const cancelCaptchaBtn = document.getElementById('cancel-captcha-btn');
  const captchaCanvas = document.getElementById('captcha-canvas');
  const captchaLoadingOverlay = document.getElementById('captcha-loading-overlay');
  const resumeCaptchaBtn = document.getElementById('resume-captcha-btn');

  // Detail Modal Elements
  const productDetailModal = document.getElementById('product-detail-modal');
  const closeDetailModal = document.getElementById('close-detail-modal');
  const modalProductTitle = document.getElementById('modal-product-title');
  const modalProductPrice = document.getElementById('modal-product-price');
  const modalProductLink = document.getElementById('modal-product-link');
  const modalVerdictBox = document.getElementById('modal-verdict-box');
  const modalCriteriaList = document.getElementById('modal-criteria-list');
  const modalSpecsList = document.getElementById('modal-specs-list');

  // History Grid Elements
  const historyGrid = document.getElementById('history-grid');
  const historyEmptyState = document.getElementById('history-empty-state');
  const refreshHistoryBtn = document.getElementById('refresh-history-btn');

  // 1. Theme Management (Nord Dark & Light)
  function applyTheme(theme) {
    currentTheme = theme;
    localStorage.setItem('app_theme', theme);
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
      themeIconDark.classList.remove('hidden');
      themeIconLight.classList.add('hidden');
    } else {
      document.documentElement.classList.remove('dark');
      themeIconDark.classList.add('hidden');
      themeIconLight.classList.remove('hidden');
    }
  }
  applyTheme(currentTheme);

  themeToggleBtn.addEventListener('click', () => {
    applyTheme(currentTheme === 'dark' ? 'light' : 'dark');
  });

  // 2. Navigation Tabs
  navSearchTab.addEventListener('click', () => {
    navSearchTab.classList.add('active');
    navSearchTab.classList.remove('opacity-70');
    navHistoryTab.classList.remove('active');
    navHistoryTab.classList.add('opacity-70');
    searchSection.classList.remove('hidden');
    historySection.classList.add('hidden');
  });

  navHistoryTab.addEventListener('click', () => {
    navHistoryTab.classList.add('active');
    navHistoryTab.classList.remove('opacity-70');
    navSearchTab.classList.remove('active');
    navSearchTab.classList.add('opacity-70');
    historySection.classList.remove('hidden');
    searchSection.classList.add('hidden');
    loadHistory();
  });

  // 3. Gmail-Style Search Term(s) Chips Box
  function renderSearchChips() {
    searchChipsContainer.innerHTML = '';
    if (searchTermsList.length === 0) {
      searchChipsContainer.innerHTML = `<span id="chips-empty-hint" class="text-xs text-nord-3 italic px-1 py-0.5">No search terms confirmed yet. Type above and press Enter.</span>`;
      return;
    }

    searchTermsList.forEach((term, idx) => {
      const chip = document.createElement('div');
      chip.className = 'flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-nord-8/15 border border-nord-8/30 text-nord-8 text-xs font-semibold animate-in fade-in zoom-in-95 duration-100';
      chip.innerHTML = `
        <span class="chip-text cursor-pointer hover:underline" title="Click to edit">${escapeHTML(term)}</span>
        <button type="button" class="remove-chip-btn text-nord-8/70 hover:text-nord-11 transition" data-index="${idx}">
          <i data-lucide="x" class="w-3 h-3"></i>
        </button>
      `;
      searchChipsContainer.appendChild(chip);
    });

    if (window.lucide) lucide.createIcons();

    // Attach Remove Listeners
    searchChipsContainer.querySelectorAll('.remove-chip-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const index = parseInt(btn.dataset.index, 10);
        searchTermsList.splice(index, 1);
        renderSearchChips();
      });
    });

    // Attach Edit Listeners
    searchChipsContainer.querySelectorAll('.chip-text').forEach((el, idx) => {
      el.addEventListener('click', () => {
        const term = searchTermsList[idx];
        searchTermInput.value = term;
        searchTermsList.splice(idx, 1);
        renderSearchChips();
        searchTermInput.focus();
      });
    });
  }

  function addSearchTerm(rawTerm) {
    if (!rawTerm) return;
    const clean = rawTerm.replace(/,/g, '').trim();
    if (clean && !searchTermsList.includes(clean)) {
      searchTermsList.push(clean);
      renderSearchChips();
    }
  }

  searchTermInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ',') {
      if (activeSuggestIndex >= 0 && suggestionsDropdown.children[activeSuggestIndex]) {
        // Handled by suggestions dropdown
        return;
      }
      e.preventDefault();
      addSearchTerm(searchTermInput.value);
      searchTermInput.value = '';
      suggestionsDropdown.classList.add('hidden');
    }
  });

  searchTermInput.addEventListener('blur', () => {
    setTimeout(() => {
      if (searchTermInput.value.trim()) {
        addSearchTerm(searchTermInput.value);
        searchTermInput.value = '';
      }
    }, 200);
  });

  // 4. Dynamic Numbered Criteria Fields (Max 10)
  function renderConditions() {
    conditionsContainer.innerHTML = '';
    conditionCountBadge.textContent = `${conditionsList.length} / 10`;

    conditionsList.forEach((condText, idx) => {
      const row = document.createElement('div');
      row.className = 'flex items-center gap-2';

      row.innerHTML = `
        <div class="w-7 h-9 rounded-xl theme-bg-input border theme-border flex items-center justify-center text-xs font-mono font-bold text-nord-8 flex-shrink-0">
          ${idx + 1}
        </div>
        <input type="text" value="${escapeHTML(condText)}" placeholder="e.g. Must have hardware ANC, not ENC" class="condition-input flex-1 theme-bg-input border theme-border rounded-xl px-3.5 py-2 text-xs text-nord-5 placeholder-nord-3 focus:outline-none focus:border-nord-8" data-index="${idx}">
        ${idx > 0 ? `
          <button type="button" class="remove-cond-btn p-2 rounded-xl text-nord-11 hover:bg-nord-11/10 transition border border-nord-11/20 flex-shrink-0" data-index="${idx}" title="Remove condition">
            <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
          </button>
        ` : ''}
      `;

      conditionsContainer.appendChild(row);
    });

    if (window.lucide) lucide.createIcons();

    // Attach Input Listeners
    document.querySelectorAll('.condition-input').forEach(input => {
      input.addEventListener('input', (e) => {
        const index = parseInt(e.target.dataset.index, 10);
        conditionsList[index] = e.target.value;
      });
    });

    // Attach Remove Listeners
    document.querySelectorAll('.remove-cond-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const index = parseInt(btn.dataset.index, 10);
        conditionsList.splice(index, 1);
        renderConditions();
      });
    });

    if (conditionsList.length >= 10) {
      addConditionBtn.disabled = true;
      addConditionBtn.classList.add('opacity-50', 'cursor-not-allowed');
    } else {
      addConditionBtn.disabled = false;
      addConditionBtn.classList.remove('opacity-50', 'cursor-not-allowed');
    }
  }

  addConditionBtn.addEventListener('click', () => {
    if (conditionsList.length < 10) {
      conditionsList.push('');
      renderConditions();
      const inputs = document.querySelectorAll('.condition-input');
      if (inputs.length > 0) inputs[inputs.length - 1].focus();
    }
  });

  renderConditions();

  // 5. Destination Country & Currency Auto-Sync
  shipCountrySelect.addEventListener('change', () => {
    const selectedCountry = shipCountrySelect.value;
    const autoCurrency = COUNTRY_CURRENCY_MAP[selectedCountry] || 'USD';
    const matchingOption = currencySelect.querySelector(`option[value="${autoCurrency}"]`);
    if (matchingOption) {
      currencySelect.value = autoCurrency;
    } else {
      currencySelect.value = 'USD';
    }
  });

  // 6. Generic Search Term Live Autofill / Spell Suggestion
  searchTermInput.addEventListener('input', () => {
    const query = searchTermInput.value.trim();
    if (suggestDebounceTimeout) clearTimeout(suggestDebounceTimeout);

    if (query.length < 2) {
      suggestionsDropdown.classList.add('hidden');
      return;
    }

    suggestDebounceTimeout = setTimeout(async () => {
      try {
        const res = await fetch(`/api/suggestions?q=${encodeURIComponent(query)}`);
        const data = await res.json();
        const suggestions = data.suggestions || [];

        if (suggestions.length === 0) {
          suggestionsDropdown.classList.add('hidden');
          return;
        }

        suggestionsDropdown.innerHTML = '';
        activeSuggestIndex = -1;

        suggestions.forEach((term) => {
          const item = document.createElement('div');
          item.className = 'suggestion-item px-3.5 py-2 text-xs text-nord-5 cursor-pointer flex items-center gap-2';
          item.innerHTML = `<i data-lucide="search" class="w-3.5 h-3.5 text-nord-3"></i><span>${escapeHTML(term)}</span>`;
          item.addEventListener('click', () => {
            addSearchTerm(term);
            searchTermInput.value = '';
            suggestionsDropdown.classList.add('hidden');
          });
          suggestionsDropdown.appendChild(item);
        });

        if (window.lucide) lucide.createIcons();
        suggestionsDropdown.classList.remove('hidden');
      } catch (err) {
        suggestionsDropdown.classList.add('hidden');
      }
    }, 180);
  });

  // Keyboard navigation for suggestions
  searchTermInput.addEventListener('keydown', (e) => {
    const items = suggestionsDropdown.querySelectorAll('.suggestion-item');
    if (suggestionsDropdown.classList.contains('hidden') || items.length === 0) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      activeSuggestIndex = (activeSuggestIndex + 1) % items.length;
      updateSuggestionHighlight(items);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      activeSuggestIndex = (activeSuggestIndex - 1 + items.length) % items.length;
      updateSuggestionHighlight(items);
    } else if (e.key === 'Enter' && activeSuggestIndex >= 0) {
      e.preventDefault();
      items[activeSuggestIndex].click();
    } else if (e.key === 'Escape') {
      suggestionsDropdown.classList.add('hidden');
    }
  });

  function updateSuggestionHighlight(items) {
    items.forEach((it, idx) => {
      if (idx === activeSuggestIndex) {
        it.classList.add('selected');
      } else {
        it.classList.remove('selected');
      }
    });
  }

  document.addEventListener('click', (e) => {
    if (!searchTermInput.contains(e.target) && !suggestionsDropdown.contains(e.target)) {
      suggestionsDropdown.classList.add('hidden');
    }
  });

  // 7. Mandatory Entrance Gate & Gemini API Key
  async function fetchAvailableModels(apiKey) {
    try {
      const res = await fetch('/api/models', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: apiKey })
      });
      const data = await res.json();
      if (data.models && data.models.length > 0) {
        modelSelect.innerHTML = '';
        data.models.forEach((m, idx) => {
          const opt = document.createElement('option');
          opt.value = m;
          opt.textContent = idx === 0 ? `${m} (Recommended)` : m;
          if (idx === 0) opt.selected = true;
          modelSelect.appendChild(opt);
        });
      }
    } catch (e) {
      console.warn('Error fetching dynamic models:', e);
    }
  }

  function checkApiKeyEntranceGate() {
    if (!currentApiKey) {
      closeApiKeyModal.classList.add('hidden');
      cancelApiKeyBtn.classList.add('hidden');
      apiKeyModal.classList.remove('hidden');
      apiKeyModal.classList.add('flex');
      apiKeyIndicator.className = 'w-2 h-2 rounded-full bg-nord-11 animate-pulse';
      apiKeyBtnText.textContent = 'API Key Required';
    } else {
      apiKeyIndicator.className = 'w-2 h-2 rounded-full bg-nord-14';
      apiKeyBtnText.textContent = 'Gemini Connected';
      geminiKeyInput.value = currentApiKey;
      fetchAvailableModels(currentApiKey);
    }
  }
  checkApiKeyEntranceGate();

  openApiKeyBtn.addEventListener('click', () => {
    keyValidationMessage.classList.add('hidden');
    closeApiKeyModal.classList.remove('hidden');
    cancelApiKeyBtn.classList.remove('hidden');
    apiKeyModal.classList.remove('hidden');
    apiKeyModal.classList.add('flex');
    geminiKeyInput.focus();
  });

  function closeKeyModal() {
    if (!currentApiKey) return;
    apiKeyModal.classList.add('hidden');
    apiKeyModal.classList.remove('flex');
  }

  closeApiKeyModal.addEventListener('click', closeKeyModal);
  cancelApiKeyBtn.addEventListener('click', closeKeyModal);

  apiKeyForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const key = geminiKeyInput.value.trim();
    if (!key) return;

    keyValidationMessage.className = 'text-xs p-3 rounded-xl border bg-nord-0 text-nord-4 border-nord-2 block';
    keyValidationMessage.textContent = 'Diagnosing and validating key with Google Gemini API...';

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
        apiKeyIndicator.className = 'w-2 h-2 rounded-full bg-nord-14';
        apiKeyBtnText.textContent = 'Gemini Connected';
        
        if (data.models && data.models.length > 0) {
          modelSelect.innerHTML = '';
          data.models.forEach((m, idx) => {
            const opt = document.createElement('option');
            opt.value = m;
            opt.textContent = idx === 0 ? `${m} (Recommended)` : m;
            if (idx === 0) opt.selected = true;
            modelSelect.appendChild(opt);
          });
        }

        keyValidationMessage.className = 'text-xs p-3 rounded-xl border bg-nord-14/15 text-nord-14 border-nord-14/30 block';
        keyValidationMessage.textContent = '✅ ' + (data.message || 'Gemini API key validated and active! App unlocked.');
        setTimeout(closeKeyModal, 1200);
      } else if (data.valid && !data.quota_available) {
        currentApiKey = key;
        keyValidationMessage.className = 'text-xs p-3 rounded-xl border bg-nord-13/15 text-nord-13 border-nord-13/30 block leading-relaxed';
        keyValidationMessage.innerHTML = `
          <div class="font-bold mb-1 flex items-center gap-1.5 text-nord-13">
            <i data-lucide="alert-triangle" class="w-4 h-4"></i>
            <span>Key Authenticated, but Quota is Unavailable</span>
          </div>
          <p class="opacity-90 mb-1.5">${escapeHTML(data.message)}</p>
          <div class="text-[11px] bg-nord-0/60 p-2 rounded-lg border theme-border space-y-1">
            <p>• <strong>Free Tier Quota</strong>: Ensure you generated your key under a standard Google AI Studio project with Gemini API enabled.</p>
            <p>• <strong>Rate Limit</strong>: If you recently ran multiple requests, wait 60 seconds for the free tier per-minute quota to reset.</p>
            <p>• Check your quota dashboard at <a href="https://aistudio.google.com/" target="_blank" class="text-nord-8 underline font-semibold">Google AI Studio</a>.</p>
          </div>
        `;
        if (window.lucide) lucide.createIcons();
      } else {
        keyValidationMessage.className = 'text-xs p-3 rounded-xl border bg-nord-11/15 text-nord-11 border-nord-11/30 block leading-relaxed';
        keyValidationMessage.innerHTML = `
          <div class="font-bold mb-1 flex items-center gap-1.5 text-nord-11">
            <i data-lucide="x-circle" class="w-4 h-4"></i>
            <span>Validation Failed: ${escapeHTML(data.error_type || 'AUTH_ERROR')}</span>
          </div>
          <p class="opacity-90">${escapeHTML(data.message || 'Invalid Gemini API key.')}</p>
        `;
        if (window.lucide) lucide.createIcons();
      }
    } catch (err) {
      keyValidationMessage.className = 'text-xs p-3 rounded-xl border bg-nord-11/15 text-nord-11 border-nord-11/30 block';
      keyValidationMessage.textContent = '❌ Error connecting to validation server.';
    }
  });

  // 8. Filter Buttons
  filterTabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      filterTabBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      activeFilter = btn.dataset.filter;
      renderProducts();
    });
  });

  // 9. Search Form Submission
  searchForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!currentApiKey) {
      checkApiKeyEntranceGate();
      return;
    }

    // Flush any pending term in input box into chips
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
    liveStageTitle.textContent = 'Initiating AI Search Pipeline...';
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

  // 10. SSE Stream Listener
  function connectSSEStream(searchId) {
    if (activeEventSource) activeEventSource.close();
    activeEventSource = new EventSource(`/api/search/stream/${searchId}`);

    activeEventSource.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        handleStreamEvent(payload);
      } catch (err) {}
    };

    activeEventSource.onerror = (err) => {
      console.warn('SSE connection interrupted:', err);
    };
  }

  function handleStreamEvent(event) {
    const { type, stage, progress_pct, data } = event;

    if (stage) liveStageTitle.textContent = stage;
    if (progress_pct !== undefined) {
      liveProgressBadge.textContent = `${progress_pct}%`;
      liveProgressBar.style.width = `${progress_pct}%`;
    }

    switch (type) {
      case 'candidate_discovered':
        liveStatDiscovered.textContent = data.total_candidates || activeProducts.length;
        break;

      case 'item_evaluated':
        activeProducts.push(data.item);
        liveStatEvaluated.textContent = data.index;
        liveStatMatches.textContent = data.matched_count;
        renderProducts();
        break;

      case 'captcha_required':
        showCaptchaModal(data.screenshot, data.message);
        break;

      case 'captcha_cleared':
        hideCaptchaModal();
        break;

      case 'captcha_failed':
        showCaptchaFailureModal(data.message, data.remaining_terms || []);
        break;

      case 'search_completed':
        if (data.items && data.items.length > 0) {
          activeProducts = data.items;
        }
        renderProducts();
        liveStageTitle.textContent = `Completed! ${data.total_matched} matching products verified.`;
        liveProgressBadge.textContent = '100%';
        liveProgressBar.style.width = '100%';
        startSearchBtn.disabled = false;
        startSearchBtn.classList.remove('opacity-60', 'cursor-not-allowed');
        if (activeEventSource) activeEventSource.close();
        loadHistoryCount();
        break;

      case 'search_failed':
        liveStageTitle.textContent = `Error: ${data.error || 'Search encountered an issue.'}`;
        startSearchBtn.disabled = false;
        startSearchBtn.classList.remove('opacity-60', 'cursor-not-allowed');
        if (activeEventSource) activeEventSource.close();
        break;
    }
  }

  // 11. Render Product Cards
  function renderProducts() {
    countAll.textContent = activeProducts.length;
    const matchesCount = activeProducts.filter(p => p.is_match).length;
    countMatches.textContent = matchesCount;
    countExcluded.textContent = activeProducts.length - matchesCount;

    let filtered = activeProducts;
    if (activeFilter === 'matches') {
      filtered = activeProducts.filter(p => p.is_match);
    } else if (activeFilter === 'excluded') {
      filtered = activeProducts.filter(p => !p.is_match);
    }

    if (activeProducts.length === 0) {
      resultsEmptyState.classList.remove('hidden');
      productsList.classList.add('hidden');
      resultsCountLabel.textContent = 'No items found yet.';
      return;
    }

    resultsEmptyState.classList.add('hidden');
    productsList.classList.remove('hidden');
    resultsCountLabel.textContent = `Showing ${filtered.length} of ${activeProducts.length} candidate products (${matchesCount} matching).`;

    productsList.innerHTML = '';

    filtered.forEach((item, index) => {
      const card = document.createElement('div');
      card.className = `p-4 rounded-2xl border transition-all ${
        item.is_match 
          ? 'bg-nord-14/10 border-nord-14/30 hover:border-nord-14/50' 
          : 'theme-bg-card theme-border hover:border-nord-3'
      } flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between`;

      const matchBadge = item.is_match 
        ? `<span class="badge-match text-[10px] font-bold px-2.5 py-0.5 rounded-full uppercase tracking-wider flex items-center gap-1"><i data-lucide="check-circle-2" class="w-3 h-3"></i> Verified Match</span>`
        : `<span class="badge-fail text-[10px] font-bold px-2.5 py-0.5 rounded-full uppercase tracking-wider flex items-center gap-1"><i data-lucide="x-circle" class="w-3 h-3"></i> Filtered Out</span>`;

      card.innerHTML = `
        <div class="flex items-center gap-3.5 flex-1 min-w-0">
          <div class="w-14 h-14 rounded-xl bg-nord-0/70 border theme-border flex-shrink-0 overflow-hidden flex items-center justify-center">
            ${item.image_url 
              ? `<img src="${escapeHTML(item.image_url)}" alt="Product" class="w-full h-full object-cover">` 
              : `<i data-lucide="package" class="w-6 h-6 text-nord-3"></i>`
            }
          </div>
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2 mb-1 flex-wrap">
              ${matchBadge}
              <span class="text-xs font-mono font-bold text-nord-14">${escapeHTML(item.price || 'N/A')}</span>
              ${item.original_price ? `<span class="text-[10px] text-nord-3 line-through font-mono">${escapeHTML(item.original_price)}</span>` : ''}
            </div>
            <a href="${escapeHTML(item.url)}" target="_blank" class="text-sm font-bold text-nord-6 hover:text-nord-8 transition line-clamp-1 block">
              ${escapeHTML(item.title)}
            </a>
            <p class="text-xs text-nord-4 opacity-80 mt-1 line-clamp-1">
              ${escapeHTML(item.verdict_reason || 'AI evaluation complete.')}
            </p>
          </div>
        </div>

        <div class="flex items-center gap-2 self-end sm:self-center flex-shrink-0">
          <button class="view-detail-btn px-3.5 py-2 rounded-xl theme-bg-input hover:border-nord-8 text-nord-5 text-xs font-semibold border theme-border transition flex items-center gap-1.5" data-index="${index}">
            <i data-lucide="sparkles" class="w-3.5 h-3.5 text-nord-8"></i>
            <span>AI Breakdown</span>
          </button>
          <a href="${escapeHTML(item.url)}" target="_blank" class="p-2 rounded-xl theme-bg-input hover:border-nord-8 text-nord-4 border theme-border transition" title="Open Product Page">
            <i data-lucide="external-link" class="w-4 h-4"></i>
          </a>
        </div>
      `;

      productsList.appendChild(card);
    });

    if (window.lucide) lucide.createIcons();

    document.querySelectorAll('.view-detail-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const item = filtered[parseInt(btn.dataset.index, 10)];
        showProductDetail(item);
      });
    });
  }

  // 12. Show Product Detail Modal
  function showProductDetail(item) {
    if (!item) return;

    modalProductTitle.textContent = item.title;
    modalProductPrice.textContent = item.price || 'N/A';
    modalProductLink.href = item.url;

    modalVerdictBox.className = `p-3.5 rounded-2xl border ${
      item.is_match 
        ? 'bg-nord-14/15 border-nord-14/35 text-nord-14' 
        : 'bg-nord-11/15 border-nord-11/35 text-nord-11'
    }`;
    modalVerdictBox.innerHTML = `
      <div class="font-bold flex items-center gap-2 mb-1 text-sm">
        <i data-lucide="${item.is_match ? 'check-circle-2' : 'x-circle'}" class="w-4 h-4"></i>
        <span>${item.is_match ? 'Product Matches All User Criteria' : 'Product Excluded'}</span>
      </div>
      <p class="text-xs opacity-90 leading-relaxed">${escapeHTML(item.verdict_reason || 'No detailed verdict summary.')}</p>
    `;

    modalCriteriaList.innerHTML = '';
    const breakdown = item.criteria_breakdown || [];
    if (breakdown.length === 0) {
      modalCriteriaList.innerHTML = '<p class="text-nord-3 text-xs">No criteria breakdown items.</p>';
    } else {
      breakdown.forEach(crit => {
        const critDiv = document.createElement('div');
        critDiv.className = `p-3 rounded-xl border ${
          crit.met 
            ? 'bg-nord-14/10 border-nord-14/25 text-nord-5' 
            : 'bg-nord-11/10 border-nord-11/25 text-nord-4'
        }`;
        critDiv.innerHTML = `
          <div class="flex items-center justify-between font-bold text-xs mb-1">
            <span class="flex items-center gap-1.5">
              <i data-lucide="${crit.met ? 'check' : 'x'}" class="w-3.5 h-3.5 ${crit.met ? 'text-nord-14' : 'text-nord-11'}"></i>
              ${escapeHTML(crit.condition)}
            </span>
            <span class="text-[10px] uppercase font-mono px-2 py-0.5 rounded ${crit.met ? 'bg-nord-14/20 text-nord-14' : 'bg-nord-11/20 text-nord-11'}">${crit.met ? 'MET' : 'UNMET'}</span>
          </div>
          <p class="text-[11px] opacity-80 pl-5 leading-relaxed">${escapeHTML(crit.evidence || 'No specific evidence string.')}</p>
        `;
        modalCriteriaList.appendChild(critDiv);
      });
    }

    modalSpecsList.innerHTML = '';
    const specs = item.specs || [];
    if (specs.length === 0) {
      modalSpecsList.innerHTML = '<p class="text-nord-3 text-xs col-span-2">No specs parsed.</p>';
    } else {
      specs.forEach(s => {
        const specItem = document.createElement('div');
        specItem.className = 'text-nord-4 truncate';
        specItem.textContent = `• ${s}`;
        specItem.title = s;
        modalSpecsList.appendChild(specItem);
      });
    }

    if (window.lucide) lucide.createIcons();

    productDetailModal.classList.remove('hidden');
    productDetailModal.classList.add('flex');
  }

  closeDetailModal.addEventListener('click', () => {
    productDetailModal.classList.add('hidden');
    productDetailModal.classList.remove('flex');
  });

  // 13. Interactive CAPTCHA Canvas Drag Solver
  function redrawCaptchaCanvas(showDragLine = false) {
    if (!activeCaptchaImage.src) return;
    const ctx = captchaCanvas.getContext('2d');
    ctx.clearRect(0, 0, captchaCanvas.width, captchaCanvas.height);
    ctx.drawImage(activeCaptchaImage, 0, 0, captchaCanvas.width, captchaCanvas.height);

    if (showDragLine && isDraggingCaptcha) {
      ctx.strokeStyle = '#88C0D0';
      ctx.lineWidth = 4;
      ctx.beginPath();
      ctx.moveTo(captchaDragStart.x, captchaDragStart.y);
      ctx.lineTo(captchaDragCurrent.x, captchaDragCurrent.y);
      ctx.stroke();

      ctx.fillStyle = '#88C0D0';
      ctx.beginPath();
      ctx.arc(captchaDragCurrent.x, captchaDragCurrent.y, 8, 0, 2 * Math.PI);
      ctx.fill();
    }
  }

  function showCaptchaModal(screenshotB64, message) {
    if (!screenshotB64) return;
    captchaSolveView.classList.remove('hidden');
    captchaFailureView.classList.add('hidden');
    captchaModal.classList.remove('hidden');
    captchaModal.classList.add('flex');

    activeCaptchaImage.onload = () => {
      captchaCanvas.width = activeCaptchaImage.naturalWidth || 800;
      captchaCanvas.height = activeCaptchaImage.naturalHeight || 450;
      redrawCaptchaCanvas(false);
    };
    activeCaptchaImage.src = `data:image/jpeg;base64,${screenshotB64}`;
  }

  function showCaptchaFailureModal(message, remainingTerms) {
    captchaSolveView.classList.add('hidden');
    captchaFailureView.classList.remove('hidden');
    captchaFailureMessage.textContent = message || 'AliExpress verification challenge failed.';

    remainingTermsList.innerHTML = '';
    if (!remainingTerms || remainingTerms.length === 0) {
      remainingTermsList.innerHTML = '<span class="text-xs text-nord-3 italic">No remaining terms left in queue.</span>';
    } else {
      remainingTerms.forEach(t => {
        const chip = document.createElement('span');
        chip.className = 'px-2.5 py-1 rounded-lg bg-nord-2 text-nord-4 text-xs font-mono font-medium';
        chip.textContent = t;
        remainingTermsList.appendChild(chip);
      });
    }

    captchaModal.classList.remove('hidden');
    captchaModal.classList.add('flex');
    if (window.lucide) lucide.createIcons();
  }

  function hideCaptchaModal() {
    captchaModal.classList.add('hidden');
    captchaModal.classList.remove('flex');
  }

  closeCaptchaModal.addEventListener('click', hideCaptchaModal);

  cancelCaptchaBtn.addEventListener('click', async () => {
    if (!currentSearchId) return;
    try {
      await fetch('/api/captcha/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ search_id: currentSearchId, action: 'cancel' })
      });
    } catch (e) {}
    hideCaptchaModal();
  });

  retryCaptchaBtn.addEventListener('click', async () => {
    if (!currentSearchId) return;
    try {
      await fetch('/api/captcha/resume', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ search_id: currentSearchId, action: 'retry' })
      });
    } catch (e) {}
    hideCaptchaModal();
  });

  continueRemainingBtn.addEventListener('click', async () => {
    if (!currentSearchId) return;
    try {
      await fetch('/api/captcha/resume', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ search_id: currentSearchId, action: 'continue_remaining' })
      });
    } catch (e) {}
    hideCaptchaModal();
  });

  captchaCanvas.addEventListener('mousedown', (e) => {
    const rect = captchaCanvas.getBoundingClientRect();
    const scaleX = captchaCanvas.width / rect.width;
    const scaleY = captchaCanvas.height / rect.height;

    captchaDragStart = {
      x: (e.clientX - rect.left) * scaleX,
      y: (e.clientY - rect.top) * scaleY
    };
    captchaDragCurrent = { ...captchaDragStart };
    isDraggingCaptcha = true;
  });

  captchaCanvas.addEventListener('mousemove', (e) => {
    if (!isDraggingCaptcha) return;
    const rect = captchaCanvas.getBoundingClientRect();
    const scaleX = captchaCanvas.width / rect.width;
    const scaleY = captchaCanvas.height / rect.height;

    captchaDragCurrent = {
      x: (e.clientX - rect.left) * scaleX,
      y: (e.clientY - rect.top) * scaleY
    };
    redrawCaptchaCanvas(true);
  });

  captchaCanvas.addEventListener('mouseup', async (e) => {
    if (!isDraggingCaptcha || !currentSearchId) return;
    isDraggingCaptcha = false;

    const rect = captchaCanvas.getBoundingClientRect();
    const scaleX = captchaCanvas.width / rect.width;
    const scaleY = captchaCanvas.height / rect.height;

    const endX = (e.clientX - rect.left) * scaleX;
    const endY = (e.clientY - rect.top) * scaleY;

    // Check if genuinely dragged (prevent accidental single click triggers)
    const dragDistance = Math.abs(endX - captchaDragStart.x);
    if (dragDistance < 25) {
      redrawCaptchaCanvas(false);
      return;
    }

    captchaLoadingOverlay.classList.remove('hidden');

    try {
      const res = await fetch('/api/captcha/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          search_id: currentSearchId,
          action: 'drag',
          start_x: captchaDragStart.x,
          start_y: captchaDragStart.y,
          end_x: endX,
          end_y: endY
        })
      });
      const data = await res.json();
      captchaLoadingOverlay.classList.add('hidden');

      if (data.resolved) {
        setTimeout(hideCaptchaModal, 600);
      } else if (data.screenshot) {
        activeCaptchaImage.src = `data:image/jpeg;base64,${data.screenshot}`;
      }
    } catch (err) {
      captchaLoadingOverlay.classList.add('hidden');
    }
  });

  resumeCaptchaBtn.addEventListener('click', async () => {
    if (!currentSearchId) return;
    try {
      await fetch('/api/captcha/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ search_id: currentSearchId, action: 'resolve' })
      });
      hideCaptchaModal();
    } catch (err) {
      hideCaptchaModal();
    }
  });

  // 14. History Management
  async function loadHistoryCount() {
    try {
      const res = await fetch('/api/history');
      const data = await res.json();
      historyBadgeCount.textContent = (data.searches || []).length;
    } catch (e) {}
  }
  loadHistoryCount();

  async function loadHistory() {
    try {
      const res = await fetch('/api/history');
      const data = await res.json();
      const searches = data.searches || [];

      historyBadgeCount.textContent = searches.length;
      historyGrid.innerHTML = '';

      if (searches.length === 0) {
        historyEmptyState.classList.remove('hidden');
        return;
      }

      historyEmptyState.classList.add('hidden');

      searches.forEach(search => {
        const card = document.createElement('div');
        card.className = 'theme-bg-card border theme-border rounded-3xl p-5 shadow-lg flex flex-col justify-between hover:border-nord-8 transition relative';

        const dateStr = new Date(search.timestamp).toLocaleString();
        
        card.innerHTML = `
          <div>
            <div class="flex items-center justify-between mb-2">
              <span class="text-[11px] font-mono text-nord-3">${dateStr}</span>
              <span class="text-xs font-bold px-2 py-0.5 rounded-full ${
                search.status === 'completed' 
                  ? 'bg-nord-14/15 text-nord-14 border border-nord-14/30' 
                  : 'bg-nord-13/15 text-nord-13 border border-nord-13/30'
              }">${search.status}</span>
            </div>

            <h3 class="font-extrabold text-nord-6 text-base mb-1.5 line-clamp-1">${escapeHTML(search.search_term)}</h3>
            
            <p class="text-xs text-nord-4 opacity-80 font-mono line-clamp-2 bg-nord-0/60 p-2.5 rounded-xl border theme-border mb-4">
              ${escapeHTML(search.conditions)}
            </p>

            <div class="flex items-center gap-3 text-xs mb-4">
              <span class="text-nord-4">Found: <strong class="text-nord-6 font-mono">${search.total_found}</strong></span>
              <span class="text-nord-4">Matches: <strong class="text-nord-14 font-mono">${search.total_matched}</strong></span>
              <span class="text-nord-3 font-mono uppercase">${search.currency} (${search.ship_country})</span>
            </div>
          </div>

          <div class="flex items-center justify-between pt-3 border-t theme-border gap-2">
            <button class="delete-history-btn text-xs px-3 py-1.5 rounded-xl text-nord-11 hover:bg-nord-11/10 transition border border-nord-11/25 flex items-center gap-1" data-id="${search.id}">
              <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
              <span>Delete</span>
            </button>
            <button class="view-history-btn text-xs px-3.5 py-1.5 rounded-xl bg-gradient-to-r from-nord-10 to-nord-8 text-nord-0 font-bold transition flex items-center gap-1 shadow-md shadow-nord-8/15" data-id="${search.id}">
              <i data-lucide="eye" class="w-3.5 h-3.5"></i>
              <span>View Results</span>
            </button>
          </div>
        `;

        historyGrid.appendChild(card);
      });

      if (window.lucide) lucide.createIcons();

      document.querySelectorAll('.view-history-btn').forEach(btn => {
        btn.addEventListener('click', () => viewHistorySearch(btn.dataset.id));
      });

      document.querySelectorAll('.delete-history-btn').forEach(btn => {
        btn.addEventListener('click', () => deleteHistorySearch(btn.dataset.id));
      });

    } catch (err) {
      console.error('Error loading history:', err);
    }
  }

  refreshHistoryBtn.addEventListener('click', loadHistory);

  async function viewHistorySearch(searchId) {
    try {
      const res = await fetch(`/api/history/${searchId}`);
      const search = await res.json();
      if (!search) return;

      searchTermsList = (search.search_term || '').split(',').map(t => t.trim()).filter(Boolean);
      renderSearchChips();

      shipCountrySelect.value = search.ship_country || 'AU';
      currencySelect.value = search.currency || 'AUD';

      if (search.conditions) {
        const rawLines = search.conditions.split('\n').map(l => l.replace(/^\d+\.\s*/, '').trim()).filter(Boolean);
        conditionsList = rawLines.length > 0 ? rawLines : [''];
        renderConditions();
      }

      navSearchTab.click();
      activeProducts = search.items || [];
      renderProducts();
      liveStatusCard.classList.remove('hidden');
      liveStageTitle.textContent = `Viewing Saved Search: "${search.search_term}" (${new Date(search.timestamp).toLocaleString()})`;
      liveProgressBadge.textContent = '100%';
      liveProgressBar.style.width = '100%';
      liveStatDiscovered.textContent = search.total_found;
      liveStatEvaluated.textContent = activeProducts.length;
      liveStatMatches.textContent = search.total_matched;
    } catch (err) {
      alert('Error fetching search record: ' + err.message);
    }
  }

  async function deleteHistorySearch(searchId) {
    if (!confirm('Are you sure you want to delete this saved search and all its product records from the database?')) {
      return;
    }

    try {
      const res = await fetch(`/api/history/${searchId}`, { method: 'DELETE' });
      if (res.ok) {
        loadHistory();
      } else {
        alert('Failed to delete record.');
      }
    } catch (err) {
      alert('Error deleting search: ' + err.message);
    }
  }

});
