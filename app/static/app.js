// AliExpress AI Product Hunter - Frontend Application

document.addEventListener('DOMContentLoaded', () => {
  // Initialize Lucide icons
  if (window.lucide) {
    lucide.createIcons();
  }

  // State
  let currentApiKey = localStorage.getItem('gemini_api_key') || '';
  let activeEventSource = null;
  let currentSearchId = null;
  let activeProducts = [];
  let activeFilter = 'all'; // 'all', 'matches', 'excluded'
  let isDraggingCaptcha = false;
  let captchaDragStart = { x: 0, y: 0 };
  let activeCaptchaImage = new Image();

  // Helper to prevent XSS from scraped content
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
  const conditionsInput = document.getElementById('conditions-input');
  const maxCandidatesSelect = document.getElementById('max-candidates-select');
  const shipCountryInput = document.getElementById('ship-country-input');
  const currencyInput = document.getElementById('currency-input');
  const modelSelect = document.getElementById('model-select');
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

  // Filter Buttons
  const filterTabBtns = document.querySelectorAll('.filter-tab-btn');

  // CAPTCHA Modal Elements
  const captchaModal = document.getElementById('captcha-modal');
  const closeCaptchaModal = document.getElementById('close-captcha-modal');
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

  // History Grid
  const historyGrid = document.getElementById('history-grid');
  const historyEmptyState = document.getElementById('history-empty-state');
  const refreshHistoryBtn = document.getElementById('refresh-history-btn');

  // 1. Initialize API Key Status
  function updateApiKeyUI() {
    if (currentApiKey) {
      apiKeyIndicator.className = 'w-2 h-2 rounded-full bg-emerald-400';
      apiKeyBtnText.textContent = 'Gemini Key Configured';
      geminiKeyInput.value = currentApiKey;
    } else {
      apiKeyIndicator.className = 'w-2 h-2 rounded-full bg-amber-400 animate-pulse';
      apiKeyBtnText.textContent = 'Set Gemini API Key';
      geminiKeyInput.value = '';
    }
  }
  updateApiKeyUI();

  // Navigation Logic
  navSearchTab.addEventListener('click', () => {
    navSearchTab.classList.add('active', 'text-brand-500');
    navSearchTab.classList.remove('text-slate-400');
    navHistoryTab.classList.remove('active', 'text-brand-500');
    navHistoryTab.classList.add('text-slate-400');
    searchSection.classList.remove('hidden');
    historySection.classList.add('hidden');
  });

  navHistoryTab.addEventListener('click', () => {
    navHistoryTab.classList.add('active', 'text-brand-500');
    navHistoryTab.classList.remove('text-slate-400');
    navSearchTab.classList.remove('active', 'text-brand-500');
    navSearchTab.classList.add('text-slate-400');
    historySection.classList.remove('hidden');
    searchSection.classList.add('hidden');
    loadHistory();
  });

  // Preset Chips
  document.querySelectorAll('.preset-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      searchTermInput.value = chip.dataset.product || '';
      conditionsInput.value = chip.dataset.conditions || '';
      searchTermInput.focus();
    });
  });

  // API Key Modal Handlers
  openApiKeyBtn.addEventListener('click', () => {
    keyValidationMessage.classList.add('hidden');
    apiKeyModal.classList.remove('hidden');
    apiKeyModal.classList.add('flex');
    geminiKeyInput.focus();
  });

  function closeKeyModal() {
    apiKeyModal.classList.add('hidden');
    apiKeyModal.classList.remove('flex');
  }

  closeApiKeyModal.addEventListener('click', closeKeyModal);
  cancelApiKeyBtn.addEventListener('click', closeKeyModal);

  apiKeyForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const key = geminiKeyInput.value.trim();
    if (!key) return;

    keyValidationMessage.classList.remove('hidden', 'bg-emerald-500/10', 'text-emerald-400', 'border-emerald-500/20', 'bg-red-500/10', 'text-red-400', 'border-red-500/20');
    keyValidationMessage.classList.add('bg-slate-800', 'text-slate-300', 'border', 'border-slate-700');
    keyValidationMessage.textContent = 'Validating key with Gemini API...';

    try {
      const res = await fetch('/api/validate-key', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: key })
      });
      const data = await res.json();

      if (data.valid) {
        currentApiKey = key;
        localStorage.setItem('gemini_api_key', key);
        updateApiKeyUI();
        keyValidationMessage.className = 'text-xs p-2.5 rounded-lg border bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
        keyValidationMessage.textContent = '✅ Key validated successfully! Saved to browser.';
        setTimeout(closeKeyModal, 1200);
      } else {
        keyValidationMessage.className = 'text-xs p-2.5 rounded-lg border bg-red-500/10 text-red-400 border-red-500/20';
        keyValidationMessage.textContent = `❌ ${data.message || 'Invalid API Key'}`;
      }
    } catch (err) {
      keyValidationMessage.className = 'text-xs p-2.5 rounded-lg border bg-red-500/10 text-red-400 border-red-500/20';
      keyValidationMessage.textContent = '❌ Error connecting to server.';
    }
  });

  // Filter Buttons
  filterTabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      filterTabBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      activeFilter = btn.dataset.filter;
      renderProducts();
    });
  });

  // Search Form Submission
  searchForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!currentApiKey) {
      openApiKeyBtn.click();
      return;
    }

    const searchTerm = searchTermInput.value.trim();
    const conditions = conditionsInput.value.trim();
    if (!searchTerm || !conditions) return;

    // Reset UI
    activeProducts = [];
    renderProducts();
    liveStatusCard.classList.remove('hidden');
    liveStageTitle.textContent = 'Starting AI Search...';
    liveProgressBadge.textContent = '0%';
    liveProgressBar.style.width = '0%';
    liveStatDiscovered.textContent = '0';
    liveStatEvaluated.textContent = '0';
    liveStatMatches.textContent = '0';
    resultsEmptyState.classList.add('hidden');
    productsList.classList.remove('hidden');
    startSearchBtn.disabled = true;
    startSearchBtn.classList.add('opacity-70', 'cursor-not-allowed');

    try {
      const res = await fetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          search_term: searchTerm,
          conditions: conditions,
          gemini_api_key: currentApiKey,
          max_candidates: parseInt(maxCandidatesSelect.value, 10),
          ship_country: shipCountryInput.value.trim(),
          currency: currencyInput.value.trim(),
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
        startSearchBtn.classList.remove('opacity-70', 'cursor-not-allowed');
      }
    } catch (err) {
      alert('Error initiating search: ' + err.message);
      startSearchBtn.disabled = false;
      startSearchBtn.classList.remove('opacity-70', 'cursor-not-allowed');
    }
  });

  // SSE Stream Listener
  function connectSSEStream(searchId) {
    if (activeEventSource) {
      activeEventSource.close();
    }

    activeEventSource = new EventSource(`/api/search/stream/${searchId}`);

    activeEventSource.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        handleStreamEvent(payload);
      } catch (err) {
        console.error('Error parsing SSE event:', err);
      }
    };

    activeEventSource.onerror = (err) => {
      console.warn('SSE connection closed or interrupted:', err);
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

      case 'search_completed':
        if (data.items && data.items.length > 0) {
          activeProducts = data.items;
        }
        renderProducts();
        liveStageTitle.textContent = `Completed! ${data.total_matched} matching products found.`;
        liveProgressBadge.textContent = '100%';
        liveProgressBar.style.width = '100%';
        startSearchBtn.disabled = false;
        startSearchBtn.classList.remove('opacity-70', 'cursor-not-allowed');
        if (activeEventSource) activeEventSource.close();
        loadHistoryCount();
        break;

      case 'search_failed':
        liveStageTitle.textContent = `Error: ${data.error || 'Search encountered an issue.'}`;
        startSearchBtn.disabled = false;
        startSearchBtn.classList.remove('opacity-70', 'cursor-not-allowed');
        if (activeEventSource) activeEventSource.close();
        break;
    }
  }

  // Render Product Items
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
      card.className = `p-4 rounded-xl border transition-all ${
        item.is_match 
          ? 'bg-emerald-950/20 border-emerald-500/30 hover:border-emerald-500/50' 
          : 'bg-dark-card border-dark-border/80 hover:border-slate-700'
      } flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between`;

      const matchBadge = item.is_match 
        ? `<span class="badge-match text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider flex items-center gap-1"><i data-lucide="check-circle-2" class="w-3 h-3"></i> Verified Match</span>`
        : `<span class="badge-fail text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider flex items-center gap-1"><i data-lucide="x-circle" class="w-3 h-3"></i> Filtered Out</span>`;

      card.innerHTML = `
        <div class="flex items-center gap-3.5 flex-1 min-w-0">
          <div class="w-14 h-14 rounded-lg bg-slate-900 border border-dark-border flex-shrink-0 overflow-hidden flex items-center justify-center">
            ${item.image_url 
              ? `<img src="${escapeHTML(item.image_url)}" alt="Product" class="w-full h-full object-cover">` 
              : `<i data-lucide="headphones" class="w-6 h-6 text-slate-600"></i>`
            }
          </div>
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2 mb-1 flex-wrap">
              ${matchBadge}
              <span class="text-xs font-mono font-bold text-emerald-400">${escapeHTML(item.price || 'N/A')}</span>
              ${item.original_price ? `<span class="text-[10px] text-slate-500 line-through font-mono">${escapeHTML(item.original_price)}</span>` : ''}
            </div>
            <a href="${escapeHTML(item.url)}" target="_blank" class="text-sm font-semibold text-slate-100 hover:text-brand-500 transition line-clamp-1 block">
              ${escapeHTML(item.title)}
            </a>
            <p class="text-xs text-slate-400 mt-1 line-clamp-1">
              ${escapeHTML(item.verdict_reason || 'AI evaluation complete.')}
            </p>
          </div>
        </div>

        <div class="flex items-center gap-2 self-end sm:self-center flex-shrink-0">
          <button class="view-detail-btn px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 transition flex items-center gap-1.5" data-index="${index}">
            <i data-lucide="sparkles" class="w-3.5 h-3.5 text-brand-500"></i>
            <span>AI Breakdown</span>
          </button>
          <a href="${escapeHTML(item.url)}" target="_blank" class="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition" title="Open Link">
            <i data-lucide="external-link" class="w-4 h-4"></i>
          </a>
        </div>
      `;

      productsList.appendChild(card);
    });

    // Reinitialize icons in new cards
    if (window.lucide) lucide.createIcons();

    // Attach click listeners to view detail
    document.querySelectorAll('.view-detail-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const item = filtered[parseInt(btn.dataset.index, 10)];
        showProductDetail(item);
      });
    });
  }

  // Show Product Detail Modal
  function showProductDetail(item) {
    if (!item) return;

    modalProductTitle.textContent = item.title;
    modalProductPrice.textContent = item.price || 'N/A';
    modalProductLink.href = item.url;

    // Verdict Box
    modalVerdictBox.className = `p-3.5 rounded-xl border ${
      item.is_match 
        ? 'bg-emerald-950/30 border-emerald-500/40 text-emerald-300' 
        : 'bg-red-950/30 border-red-500/40 text-red-300'
    }`;
    modalVerdictBox.innerHTML = `
      <div class="font-bold flex items-center gap-2 mb-1">
        <i data-lucide="${item.is_match ? 'check-circle-2' : 'x-circle'}" class="w-4 h-4"></i>
        <span>${item.is_match ? 'Product Matches All User Criteria' : 'Product Excluded'}</span>
      </div>
      <p class="text-xs text-slate-300 leading-relaxed">${item.verdict_reason || 'No detailed verdict summary provided.'}</p>
    `;

    // Criteria Breakdown List
    modalCriteriaList.innerHTML = '';
    const breakdown = item.criteria_breakdown || [];
    if (breakdown.length === 0) {
      modalCriteriaList.innerHTML = '<p class="text-slate-500 text-xs">No individual criteria breakdown items.</p>';
    } else {
      breakdown.forEach(crit => {
        const critDiv = document.createElement('div');
        critDiv.className = `p-2.5 rounded-lg border ${
          crit.met 
            ? 'bg-emerald-950/20 border-emerald-500/30 text-slate-200' 
            : 'bg-red-950/20 border-red-500/30 text-slate-300'
        }`;
        critDiv.innerHTML = `
          <div class="flex items-center justify-between font-semibold text-xs mb-1">
            <span class="flex items-center gap-1.5">
              <i data-lucide="${crit.met ? 'check' : 'x'}" class="w-3.5 h-3.5 ${crit.met ? 'text-emerald-400' : 'text-red-400'}"></i>
              ${crit.condition}
            </span>
            <span class="text-[10px] uppercase px-1.5 py-0.5 rounded ${crit.met ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'}">${crit.met ? 'MET' : 'UNMET'}</span>
          </div>
          <p class="text-[11px] text-slate-400 pl-5">${crit.evidence || 'No specific evidence string.'}</p>
        `;
        modalCriteriaList.appendChild(critDiv);
      });
    }

    // Specs List
    modalSpecsList.innerHTML = '';
    const specs = item.specs || [];
    if (specs.length === 0) {
      modalSpecsList.innerHTML = '<p class="text-slate-500 text-xs col-span-2">No structured specs table items parsed.</p>';
    } else {
      specs.forEach(s => {
        const specItem = document.createElement('div');
        specItem.className = 'text-slate-300 truncate';
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

  // CAPTCHA Modal & Interactive Drag Solver
  function showCaptchaModal(screenshotB64, message) {
    if (!screenshotB64) return;
    captchaModal.classList.remove('hidden');
    captchaModal.classList.add('flex');

    activeCaptchaImage.onload = () => {
      captchaCanvas.width = activeCaptchaImage.naturalWidth || 800;
      captchaCanvas.height = activeCaptchaImage.naturalHeight || 450;
      const ctx = captchaCanvas.getContext('2d');
      ctx.drawImage(activeCaptchaImage, 0, 0);
    };
    activeCaptchaImage.src = `data:image/jpeg;base64,${screenshotB64}`;
  }

  function hideCaptchaModal() {
    captchaModal.classList.add('hidden');
    captchaModal.classList.remove('flex');
  }

  closeCaptchaModal.addEventListener('click', hideCaptchaModal);

  // Mouse interaction on CAPTCHA Canvas
  captchaCanvas.addEventListener('mousedown', (e) => {
    const rect = captchaCanvas.getBoundingClientRect();
    const scaleX = captchaCanvas.width / rect.width;
    const scaleY = captchaCanvas.height / rect.height;

    captchaDragStart = {
      x: (e.clientX - rect.left) * scaleX,
      y: (e.clientY - rect.top) * scaleY
    };
    isDraggingCaptcha = true;
  });

  captchaCanvas.addEventListener('mouseup', async (e) => {
    if (!isDraggingCaptcha || !currentSearchId) return;
    isDraggingCaptcha = false;

    const rect = captchaCanvas.getBoundingClientRect();
    const scaleX = captchaCanvas.width / rect.width;
    const scaleY = captchaCanvas.height / rect.height;

    const endX = (e.clientX - rect.left) * scaleX;
    const endY = (e.clientY - rect.top) * scaleY;

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

      if (data.screenshot) {
        activeCaptchaImage.src = `data:image/jpeg;base64,${data.screenshot}`;
      }

      if (data.resolved) {
        setTimeout(hideCaptchaModal, 800);
      }
    } catch (err) {
      captchaLoadingOverlay.classList.add('hidden');
      console.error('Error submitting captcha action:', err);
    }
  });

  resumeCaptchaBtn.addEventListener('click', async () => {
    if (!currentSearchId) return;
    try {
      await fetch('/api/captcha/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          search_id: currentSearchId,
          action: 'resolve'
        })
      });
      hideCaptchaModal();
    } catch (err) {
      hideCaptchaModal();
    }
  });

  // History Functions
  async function loadHistoryCount() {
    try {
      const res = await fetch('/api/history');
      const data = await res.json();
      const count = (data.searches || []).length;
      historyBadgeCount.textContent = count;
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
        card.className = 'bg-dark-card border border-dark-border rounded-2xl p-5 shadow-lg flex flex-col justify-between hover:border-slate-700 transition relative';

        const dateStr = new Date(search.timestamp).toLocaleString();
        
        card.innerHTML = `
          <div>
            <div class="flex items-center justify-between mb-2">
              <span class="text-[11px] font-mono text-slate-400">${dateStr}</span>
              <span class="text-xs font-bold px-2 py-0.5 rounded-full ${
                search.status === 'completed' 
                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' 
                  : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
              }">${search.status}</span>
            </div>

            <h3 class="font-bold text-white text-base mb-1.5 line-clamp-1">${search.search_term}</h3>
            
            <p class="text-xs text-slate-400 font-mono line-clamp-2 bg-slate-900/60 p-2 rounded-lg border border-dark-border mb-4">
              ${search.conditions}
            </p>

            <div class="flex items-center gap-3 text-xs mb-4">
              <span class="text-slate-400">Found: <strong class="text-white font-mono">${search.total_found}</strong></span>
              <span class="text-slate-400">Matches: <strong class="text-emerald-400 font-mono">${search.total_matched}</strong></span>
              <span class="text-slate-500 font-mono uppercase">${search.currency} (${search.ship_country})</span>
            </div>
          </div>

          <div class="flex items-center justify-between pt-3 border-t border-dark-border gap-2">
            <button class="delete-history-btn text-xs px-2.5 py-1.5 rounded-lg text-red-400 hover:bg-red-500/10 transition border border-red-500/20 flex items-center gap-1" data-id="${search.id}">
              <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
              <span>Delete</span>
            </button>
            <button class="view-history-btn text-xs px-3 py-1.5 rounded-lg bg-brand-600 hover:bg-brand-500 text-white font-medium transition flex items-center gap-1 shadow-md shadow-brand-500/10" data-id="${search.id}">
              <i data-lucide="eye" class="w-3.5 h-3.5"></i>
              <span>View Results</span>
            </button>
          </div>
        `;

        historyGrid.appendChild(card);
      });

      if (window.lucide) lucide.createIcons();

      // Attach history listeners
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

      // Populate Search Form with past inputs
      searchTermInput.value = search.search_term || '';
      conditionsInput.value = search.conditions || '';
      shipCountryInput.value = search.ship_country || 'AU';
      currencyInput.value = search.currency || 'AUD';

      // Switch to Search tab & populate products
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
