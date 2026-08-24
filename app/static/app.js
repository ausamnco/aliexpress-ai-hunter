// AliExpress AI Product Hunter - Frontend Application

document.addEventListener("DOMContentLoaded", () => {
  lucide.createIcons();

  // --- STATE ---
  let state = {
    apiKey: localStorage.getItem("gemini_api_key") || "",
    shipCountry: localStorage.getItem("ship_country") || "AU",
    currency: localStorage.getItem("currency") || "AUD",
    modelName: localStorage.getItem("model_name") || "gemini-2.5-flash",
    activeSearchId: null,
    searchTerms: [],
    conditions: [
      "1. Active Noise Cancellation (Hardware ANC)",
      "2. 2.4GHz USB wireless dongle included",
      "3. Deliverable to Australia"
    ],
    items: [],
    activeFilter: "all",
    activeTab: "search",
    eventSource: null
  };

  // --- POPULAR SUGGESTIONS DICTIONARY (Instant 0ms Keystroke Matching) ---
  const INSTANT_SUGGESTIONS = [
    "2.4G ANC headset", "2.4G wireless headphones", "ANC gaming headset with mic", "active noise cancelling headphones",
    "bluetooth 5.4 earbuds", "mechanical keyboard wireless", "hall effect magnetic switch keyboard",
    "4k 144hz portable monitor", "oled portable gaming monitor", "gan 140w fast charger", "magnetic power bank 10000mah",
    "smart watch amoled display", "nvme m.2 enclosure 40gbps", "usb-c hub 10 in 1", "ergonomic wireless mouse",
    "rgb desk mat led", "aluminum laptop stand", "dac amp headphone amplifier", "tws wireless earbuds anc",
    "drawing tablet with screen", "smart led strip light rgbic", "action camera 4k 60fps", "retro handheld gaming console"
  ];

  // --- DOM ELEMENTS ---
  const searchSection = document.getElementById("search-section");
  const historySection = document.getElementById("history-section");
  const navSearchTab = document.getElementById("nav-search-tab");
  const navHistoryTab = document.getElementById("nav-history-tab");
  const historyBadgeCount = document.getElementById("history-badge-count");
  const themeToggleBtn = document.getElementById("theme-toggle-btn");
  const themeIconDark = document.getElementById("theme-icon-dark");
  const themeIconLight = document.getElementById("theme-icon-light");

  const openApiKeyBtn = document.getElementById("open-api-key-btn");
  const apiKeyIndicator = document.getElementById("api-key-indicator");
  const apiKeyBtnText = document.getElementById("api-key-btn-text");
  const apiKeyModal = document.getElementById("api-key-modal");
  const closeApiKeyModal = document.getElementById("close-api-key-modal");
  const cancelApiKeyBtn = document.getElementById("cancel-api-key-btn");
  const apiKeyForm = document.getElementById("api-key-form");
  const geminiKeyInput = document.getElementById("gemini-key-input");
  const keyValidationMessage = document.getElementById("key-validation-message");
  const modelSelect = document.getElementById("model-select");

  const searchTermInput = document.getElementById("search-term-input");
  const searchChipsContainer = document.getElementById("search-chips-container");
  const suggestionsDropdown = document.getElementById("suggestions-dropdown");
  const conditionsContainer = document.getElementById("conditions-container");
  const addConditionBtn = document.getElementById("add-condition-btn");
  const conditionCountBadge = document.getElementById("condition-count-badge");
  const shipCountrySelect = document.getElementById("ship-country-select");
  const currencySelect = document.getElementById("currency-select");
  const maxCandidatesSelect = document.getElementById("max-candidates-select");
  const searchForm = document.getElementById("search-form");
  const startSearchBtn = document.getElementById("start-search-btn");

  const liveStatusCard = document.getElementById("live-status-card");
  const liveStageTitle = document.getElementById("live-stage-title");
  const liveProgressBadge = document.getElementById("live-progress-badge");
  const liveProgressBar = document.getElementById("live-progress-bar");
  const liveStatDiscovered = document.getElementById("live-stat-discovered");
  const liveStatEvaluated = document.getElementById("live-stat-evaluated");
  const liveStatMatches = document.getElementById("live-stat-matches");
  const stopSearchBtn = document.getElementById("stop-search-btn");

  const resultsEmptyState = document.getElementById("results-empty-state");
  const productsList = document.getElementById("products-list");
  const resultsCountLabel = document.getElementById("results-count-label");
  const countAll = document.getElementById("count-all");
  const countMatches = document.getElementById("count-matches");
  const countExcluded = document.getElementById("count-excluded");
  const filterTabBtns = document.querySelectorAll(".filter-tab-btn");

  const captchaModal = document.getElementById("captcha-modal");
  const resumeCaptchaBtn = document.getElementById("resume-captcha-btn");
  const skipCaptchaBtn = document.getElementById("skip-captcha-btn");

  const productDetailModal = document.getElementById("product-detail-modal");
  const closeDetailModal = document.getElementById("close-detail-modal");
  const modalProductTitle = document.getElementById("modal-product-title");
  const modalVerdictBox = document.getElementById("modal-verdict-box");
  const modalCriteriaList = document.getElementById("modal-criteria-list");
  const modalSpecsList = document.getElementById("modal-specs-list");
  const modalProductPrice = document.getElementById("modal-product-price");
  const modalProductLink = document.getElementById("modal-product-link");

  const historyEmptyState = document.getElementById("history-empty-state");
  const historyGrid = document.getElementById("history-grid");

  // --- INITIALIZATION ---
  function init() {
    initTheme();
    initSettings();
    renderChips();
    renderConditions();
    updateApiKeyStatusUI();
    loadHistoryCount();
  }

  function initTheme() {
    const savedTheme = localStorage.getItem("theme") || "dark";
    if (savedTheme === "light") {
      document.body.classList.add("light-theme");
      themeIconDark.classList.remove("hidden");
      themeIconLight.classList.add("hidden");
    } else {
      document.body.classList.remove("light-theme");
      themeIconDark.classList.add("hidden");
      themeIconLight.classList.remove("hidden");
    }
  }

  themeToggleBtn.addEventListener("click", () => {
    const isLight = document.body.classList.toggle("light-theme");
    localStorage.setItem("theme", isLight ? "light" : "dark");
    themeIconDark.classList.toggle("hidden", !isLight);
    themeIconLight.classList.toggle("hidden", isLight);
  });

  function initSettings() {
    if (state.shipCountry) shipCountrySelect.value = state.shipCountry;
    if (state.currency) currencySelect.value = state.currency;
    if (state.modelName) modelSelect.value = state.modelName;

    shipCountrySelect.addEventListener("change", (e) => {
      state.shipCountry = e.target.value;
      localStorage.setItem("ship_country", e.target.value);
    });

    currencySelect.addEventListener("change", (e) => {
      state.currency = e.target.value;
      localStorage.setItem("currency", e.target.value);
    });

    modelSelect.addEventListener("change", (e) => {
      state.modelName = e.target.value;
      localStorage.setItem("model_name", e.target.value);
    });
  }

  // --- GEMINI API KEY HANDLING ---
  function updateApiKeyStatusUI() {
    if (state.apiKey && state.apiKey.length > 10) {
      apiKeyIndicator.className = "w-2 h-2 rounded-full bg-nord-14";
      apiKeyBtnText.textContent = "Gemini Connected";
    } else {
      apiKeyIndicator.className = "w-2 h-2 rounded-full bg-nord-11 animate-pulse";
      apiKeyBtnText.textContent = "Set Gemini Key";
    }
  }

  openApiKeyBtn.addEventListener("click", () => {
    geminiKeyInput.value = state.apiKey;
    keyValidationMessage.classList.add("hidden");
    apiKeyModal.classList.remove("hidden");
    apiKeyModal.classList.add("flex");
    geminiKeyInput.focus();
  });

  function closeApiKeyModalFunc() {
    apiKeyModal.classList.add("hidden");
    apiKeyModal.classList.remove("flex");
  }

  closeApiKeyModal.addEventListener("click", closeApiKeyModalFunc);
  cancelApiKeyBtn.addEventListener("click", closeApiKeyModalFunc);

  apiKeyForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const key = geminiKeyInput.value.trim();
    if (!key) {
      showKeyMessage("Please enter a valid API key.", "error");
      return;
    }

    showKeyMessage("Validating key with Google Gemini...", "info");
    try {
      const resp = await fetch("/api/validate-key", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: key })
      });
      const data = await resp.json();

      if (data.valid) {
        state.apiKey = key;
        localStorage.setItem("gemini_api_key", key);
        updateApiKeyStatusUI();
        showKeyMessage("✅ Key validated and connected successfully!", "success");
        setTimeout(closeApiKeyModalFunc, 1200);
      } else {
        showKeyMessage(`❌ ${data.message || "Invalid API key."}`, "error");
      }
    } catch (err) {
      showKeyMessage(`Connection error: ${err.message}`, "error");
    }
  });

  function showKeyMessage(msg, type) {
    keyValidationMessage.classList.remove("hidden", "bg-nord-11/20", "border-nord-11", "text-nord-11", "bg-nord-14/20", "border-nord-14", "text-nord-14", "bg-nord-8/20", "border-nord-8", "text-nord-8");
    if (type === "error") {
      keyValidationMessage.classList.add("bg-nord-11/20", "border-nord-11", "text-nord-11");
    } else if (type === "success") {
      keyValidationMessage.classList.add("bg-nord-14/20", "border-nord-14", "text-nord-14");
    } else {
      keyValidationMessage.classList.add("bg-nord-8/20", "border-nord-8", "text-nord-8");
    }
    keyValidationMessage.textContent = msg;
  }

  // --- SEARCH CHIPS & INSTANT SUGGESTIONS ---
  function renderChips() {
    searchChipsContainer.innerHTML = "";
    if (state.searchTerms.length === 0) {
      searchChipsContainer.innerHTML = '<span id="chips-empty-hint" class="text-xs text-nord-3 italic px-1 py-0.5">No search terms confirmed yet. Type above and press Enter.</span>';
      return;
    }

    state.searchTerms.forEach((term, index) => {
      const chip = document.createElement("span");
      chip.className = "inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold bg-nord-8/15 text-nord-8 border border-nord-8/30 animate-fadeIn";
      chip.innerHTML = `
        <span>${escapeHtml(term)}</span>
        <button type="button" class="text-nord-8/60 hover:text-nord-11 transition" data-index="${index}">
          <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
        </button>
      `;
      chip.querySelector("button").addEventListener("click", () => {
        state.searchTerms.splice(index, 1);
        renderChips();
      });
      searchChipsContainer.appendChild(chip);
    });
  }

  function addSearchTerm(term) {
    const clean = term.trim().replace(/^[,;\s]+|[,;\s]+$/g, '');
    if (clean && !state.searchTerms.includes(clean)) {
      state.searchTerms.push(clean);
      renderChips();
    }
    searchTermInput.value = "";
    hideSuggestions();
  }

  searchTermInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      addSearchTerm(searchTermInput.value);
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      navigateSuggestions(1);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      navigateSuggestions(-1);
    } else if (e.key === "Escape") {
      hideSuggestions();
    }
  });

  searchTermInput.addEventListener("blur", () => {
    setTimeout(() => {
      if (searchTermInput.value.trim()) {
        addSearchTerm(searchTermInput.value);
      }
      hideSuggestions();
    }, 200);
  });

  // 0ms Instant Suggestion Matching
  let suggestionDebounceTimer = null;
  searchTermInput.addEventListener("input", () => {
    const q = searchTermInput.value.trim().toLowerCase();
    if (!q) {
      hideSuggestions();
      return;
    }

    // Immediate local match in 0ms
    const localMatches = INSTANT_SUGGESTIONS.filter(s => s.toLowerCase().includes(q)).slice(0, 6);
    if (localMatches.length > 0) {
      renderSuggestions(localMatches);
    }

    // Debounced Google suggestion merge
    clearTimeout(suggestionDebounceTimer);
    suggestionDebounceTimer = setTimeout(async () => {
      try {
        const resp = await fetch(`/api/suggestions?q=${encodeURIComponent(q)}`);
        if (resp.ok) {
          const data = await resp.json();
          if (data.suggestions && data.suggestions.length > 0) {
            const combined = Array.from(new Set([...localMatches, ...data.suggestions])).slice(0, 7);
            renderSuggestions(combined);
          }
        }
      } catch (err) {}
    }, 150);
  });

  let activeSuggestionIndex = -1;
  function renderSuggestions(list) {
    if (!list || list.length === 0) {
      hideSuggestions();
      return;
    }
    suggestionsDropdown.innerHTML = "";
    activeSuggestionIndex = -1;

    list.forEach((s, idx) => {
      const item = document.createElement("div");
      item.className = "px-3.5 py-2 text-xs text-nord-5 hover:bg-nord-8/15 hover:text-nord-8 cursor-pointer flex items-center gap-2 transition";
      item.innerHTML = `<i data-lucide="search" class="w-3 h-3 text-nord-3"></i><span>${escapeHtml(s)}</span>`;
      item.addEventListener("mousedown", (e) => {
        e.preventDefault();
        addSearchTerm(s);
      });
      suggestionsDropdown.appendChild(item);
    });

    lucide.createIcons({ root: suggestionsDropdown });
    suggestionsDropdown.classList.remove("hidden");
  }

  function hideSuggestions() {
    suggestionsDropdown.classList.add("hidden");
    activeSuggestionIndex = -1;
  }

  function navigateSuggestions(direction) {
    const items = suggestionsDropdown.querySelectorAll("div");
    if (!items.length || suggestionsDropdown.classList.contains("hidden")) return;

    items.forEach(i => i.classList.remove("bg-nord-8/20", "text-nord-8"));
    activeSuggestionIndex += direction;
    if (activeSuggestionIndex < 0) activeSuggestionIndex = items.length - 1;
    if (activeSuggestionIndex >= items.length) activeSuggestionIndex = 0;

    const current = items[activeSuggestionIndex];
    if (current) {
      current.classList.add("bg-nord-8/20", "text-nord-8");
      searchTermInput.value = current.textContent.trim();
    }
  }

  // --- DYNAMIC NUMBERED CONDITIONS WITH ENTER-KEY CEMENTATION ---
  function renderConditions() {
    conditionsContainer.innerHTML = "";
    conditionCountBadge.textContent = `${state.conditions.length} / 10`;

    state.conditions.forEach((condText, index) => {
      const row = document.createElement("div");
      row.className = "flex items-center gap-2 group";
      
      const numSpan = document.createElement("span");
      numSpan.className = "w-5 text-right text-xs font-mono font-bold text-nord-8 opacity-70 flex-shrink-0";
      numSpan.textContent = `${index + 1}.`;

      const input = document.createElement("input");
      input.type = "text";
      input.className = "condition-input flex-1 theme-bg-input border theme-border rounded-xl px-3 py-2 text-xs text-nord-5 placeholder-nord-3 focus:outline-none focus:border-nord-8 focus:ring-1 focus:ring-nord-8 transition-all";
      input.placeholder = `Condition ${index + 1}...`;
      
      // Strip leading number if already formatted
      input.value = condText.replace(/^\d+\.\s*/, '');

      input.addEventListener("input", () => {
        state.conditions[index] = `${index + 1}. ${input.value.trim()}`;
      });

      // Cement condition on Enter key and advance to next row
      input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          state.conditions[index] = `${index + 1}. ${input.value.trim()}`;
          if (index === state.conditions.length - 1 && state.conditions.length < 10) {
            addCondition();
          } else {
            const nextInput = conditionsContainer.querySelectorAll(".condition-input")[index + 1];
            if (nextInput) nextInput.focus();
          }
        }
      });

      const removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.className = "p-1.5 rounded-lg text-nord-3 hover:text-nord-11 hover:bg-nord-11/10 transition opacity-60 hover:opacity-100 flex-shrink-0";
      removeBtn.innerHTML = '<i data-lucide="trash-2" class="w-3.5 h-3.5"></i>';
      removeBtn.title = "Remove Condition";
      removeBtn.addEventListener("click", () => {
        if (state.conditions.length > 1) {
          state.conditions.splice(index, 1);
          renderConditions();
        }
      });

      row.appendChild(numSpan);
      row.appendChild(input);
      if (state.conditions.length > 1) {
        row.appendChild(removeBtn);
      }
      conditionsContainer.appendChild(row);
    });

    lucide.createIcons({ root: conditionsContainer });
  }

  function addCondition() {
    if (state.conditions.length >= 10) return;
    state.conditions.push(`${state.conditions.length + 1}. `);
    renderConditions();
    const inputs = conditionsContainer.querySelectorAll(".condition-input");
    const lastInput = inputs[inputs.length - 1];
    if (lastInput) lastInput.focus();
  }

  addConditionBtn.addEventListener("click", addCondition);

  // --- SEARCH SUBMISSION & STREAMING ---
  searchForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    if (searchTermInput.value.trim()) {
      addSearchTerm(searchTermInput.value);
    }

    if (state.searchTerms.length === 0) {
      alert("Please enter at least one search term.");
      searchTermInput.focus();
      return;
    }

    if (!state.apiKey) {
      apiKeyModal.classList.remove("hidden");
      apiKeyModal.classList.add("flex");
      showKeyMessage("A Gemini API Key is required to evaluate product criteria.", "error");
      return;
    }

    // Format all conditions
    const formattedConditions = state.conditions
      .map((c, i) => `${i + 1}. ${c.replace(/^\d+\.\s*/, '').trim()}`)
      .filter(c => c.replace(/^\d+\.\s*/, '').length > 0)
      .join("\n");

    if (!formattedConditions) {
      alert("Please specify at least one strict evaluation condition.");
      return;
    }

    const payload = {
      search_terms: state.searchTerms,
      conditions: formattedConditions,
      gemini_api_key: state.apiKey,
      ship_country: state.shipCountry,
      currency: state.currency,
      model_name: state.modelName,
      max_candidates: parseInt(maxCandidatesSelect.value) || 30
    };

    // Reset UI for live run
    state.items = [];
    renderResults();
    startSearchBtn.disabled = true;
    startSearchBtn.classList.add("opacity-50", "cursor-not-allowed");
    liveStatusCard.classList.remove("hidden");
    liveStageTitle.textContent = "Initializing search...";
    liveProgressBar.style.width = "5%";
    liveProgressBadge.textContent = "5%";
    liveStatDiscovered.textContent = "0";
    liveStatEvaluated.textContent = "0";
    liveStatMatches.textContent = "0";

    try {
      const resp = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail || "Failed to initiate search.");
      }

      const data = await resp.json();
      state.activeSearchId = data.search_id;
      listenToSearchStream(data.search_id);
    } catch (err) {
      alert(`Search error: ${err.message}`);
      resetSearchButton();
    }
  });

  // Stop Search Handler
  stopSearchBtn.addEventListener("click", async () => {
    if (!state.activeSearchId) return;
    stopSearchBtn.disabled = true;
    stopSearchBtn.classList.add("opacity-50");
    try {
      await fetch(`/api/search/${state.activeSearchId}/stop`, { method: "POST" });
    } catch (e) {
      console.warn("Stop request failed:", e);
    }
  });

  function listenToSearchStream(searchId) {
    if (state.eventSource) {
      state.eventSource.close();
    }

    state.eventSource = new EventSource(`/api/search/stream/${searchId}`);

    state.eventSource.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        handleStreamEvent(msg);
      } catch (err) {
        console.error("Stream parse error:", err);
      }
    };

    state.eventSource.onerror = (err) => {
      console.warn("SSE connection closed or interrupted.", err);
      state.eventSource.close();
      resetSearchButton();
    };
  }

  function handleStreamEvent(event) {
    const type = event.type;
    const data = event.data || {};

    if (event.stage) liveStageTitle.textContent = event.stage;
    if (event.progress_pct !== undefined) {
      liveProgressBar.style.width = `${event.progress_pct}%`;
      liveProgressBadge.textContent = `${event.progress_pct}%`;
    }

    if (type === "candidate_discovered") {
      const count = parseInt(liveStatDiscovered.textContent) + 1;
      liveStatDiscovered.textContent = count;
    } else if (type === "item_evaluated") {
      const item = data;
      state.items.push(item);
      liveStatEvaluated.textContent = state.items.length;
      const matchCount = state.items.filter(i => i.is_match).length;
      liveStatMatches.textContent = matchCount;
      renderResults();
    } else if (type === "captcha_detected" || type === "captcha_required") {
      captchaModal.classList.remove("hidden");
      captchaModal.classList.add("flex");
    } else if (type === "search_completed" || type === "search_cancelled" || type === "search_error") {
      if (state.eventSource) state.eventSource.close();
      captchaModal.classList.add("hidden");
      captchaModal.classList.remove("flex");
      resetSearchButton();
      loadHistoryCount();
      renderResults();
    }
  }

  resumeCaptchaBtn.addEventListener("click", async () => {
    if (!state.activeSearchId) return;
    try {
      await fetch("/api/captcha/resume", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ search_id: state.activeSearchId, action: "continue_remaining" })
      });
      captchaModal.classList.add("hidden");
      captchaModal.classList.remove("flex");
    } catch (err) {}
  });

  skipCaptchaBtn.addEventListener("click", async () => {
    captchaModal.classList.add("hidden");
    captchaModal.classList.remove("flex");
  });

  function resetSearchButton() {
    startSearchBtn.disabled = false;
    startSearchBtn.classList.remove("opacity-50", "cursor-not-allowed");
    stopSearchBtn.disabled = false;
    stopSearchBtn.classList.remove("opacity-50");
  }

  // --- RESULTS RENDERING & FILTERING ---
  function renderResults() {
    const total = state.items.length;
    const matches = state.items.filter(i => i.is_match).length;
    const excluded = total - matches;

    countAll.textContent = total;
    countMatches.textContent = matches;
    countExcluded.textContent = excluded;
    resultsCountLabel.textContent = `${total} product(s) evaluated`;

    let filtered = state.items;
    if (state.activeFilter === "matches") {
      filtered = state.items.filter(i => i.is_match);
    } else if (state.activeFilter === "excluded") {
      filtered = state.items.filter(i => !i.is_match);
    }

    if (filtered.length === 0) {
      productsList.classList.add("hidden");
      resultsEmptyState.classList.remove("hidden");
    } else {
      resultsEmptyState.classList.add("hidden");
      productsList.classList.remove("hidden");
      productsList.innerHTML = "";

      filtered.forEach((item) => {
        const card = createProductCard(item);
        productsList.appendChild(card);
      });
    }

    lucide.createIcons({ root: productsList });
  }

  filterTabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      filterTabBtns.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      state.activeFilter = btn.getAttribute("data-filter");
      renderResults();
    });
  });

  function createProductCard(item) {
    const card = document.createElement("div");
    card.className = "theme-bg-input border theme-border rounded-2xl p-4 flex flex-col justify-between shadow-md hover:border-nord-8 transition-all group";

    const isMatch = item.is_match;
    const badgeClass = isMatch ? "bg-nord-14/15 text-nord-14 border-nord-14/30" : "bg-nord-11/15 text-nord-11 border-nord-11/30";
    const badgeIcon = isMatch ? "check-circle-2" : "x-circle";
    const badgeText = isMatch ? `MATCH (${Math.round((item.confidence || 1) * 100)}%)` : "EXCLUDED";

    const imgUrl = item.image_url || "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=400&q=80";

    card.innerHTML = `
      <div>
        <div class="relative w-full h-40 bg-nord-0 rounded-xl overflow-hidden mb-3">
          <img src="${imgUrl}" alt="${escapeHtml(item.title)}" class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" onerror="this.src='https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=400&q=80'">
          <div class="absolute top-2.5 left-2.5">
            <span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-bold border ${badgeClass} backdrop-blur-md">
              <i data-lucide="${badgeIcon}" class="w-3.5 h-3.5"></i>
              <span>${badgeText}</span>
            </span>
          </div>
        </div>

        <h4 class="font-bold text-xs text-nord-6 line-clamp-2 mb-1.5 group-hover:text-nord-8 transition-colors">${escapeHtml(item.title)}</h4>
        <div class="text-sm font-extrabold font-mono text-nord-14 mb-2">${escapeHtml(item.price)}</div>
        <p class="text-[11px] text-nord-4 opacity-75 line-clamp-2 leading-relaxed mb-3">${escapeHtml(item.verdict_reason || "No evaluation explanation available.")}</p>
      </div>

      <div class="flex items-center justify-between pt-3 border-t theme-border gap-2">
        <button type="button" class="view-details-btn text-xs font-bold text-nord-8 hover:text-nord-7 flex items-center gap-1 transition">
          <i data-lucide="file-text" class="w-3.5 h-3.5"></i>
          <span>Evaluation Details</span>
        </button>
        <a href="${item.url}" target="_blank" class="p-1.5 rounded-lg bg-nord-2 hover:bg-nord-8 hover:text-nord-0 transition text-nord-4">
          <i data-lucide="external-link" class="w-3.5 h-3.5"></i>
        </a>
      </div>
    `;

    card.querySelector(".view-details-btn").addEventListener("click", () => openProductDetailModal(item));
    return card;
  }

  function openProductDetailModal(item) {
    modalProductTitle.textContent = item.title;
    modalProductPrice.textContent = item.price;
    modalProductLink.href = item.url;

    const isMatch = item.is_match;
    modalVerdictBox.className = `p-3.5 rounded-xl border ${isMatch ? 'bg-nord-14/15 border-nord-14/30 text-nord-14' : 'bg-nord-11/15 border-nord-11/30 text-nord-11'}`;
    modalVerdictBox.innerHTML = `
      <div class="font-bold text-xs flex items-center gap-1.5 mb-1">
        <i data-lucide="${isMatch ? 'check-circle-2' : 'x-circle'}" class="w-4 h-4"></i>
        <span>AI Verdict: ${isMatch ? 'MATCH (Verified All Conditions)' : 'EXCLUDED (Unmet Criteria)'}</span>
      </div>
      <p class="text-xs opacity-90 leading-relaxed">${escapeHtml(item.verdict_reason || '')}</p>
    `;

    modalCriteriaList.innerHTML = "";
    const breakdown = item.criteria_breakdown || [];
    if (breakdown.length === 0) {
      modalCriteriaList.innerHTML = '<p class="text-nord-3 italic">No detailed criteria breakdown available.</p>';
    } else {
      breakdown.forEach(crit => {
        const critEl = document.createElement("div");
        critEl.className = "p-2.5 rounded-xl bg-nord-0/50 border theme-border space-y-1";
        critEl.innerHTML = `
          <div class="flex items-center justify-between font-semibold text-xs">
            <span class="text-nord-5">${escapeHtml(crit.condition)}</span>
            <span class="px-2 py-0.5 rounded-md text-[10px] font-bold ${crit.met ? 'bg-nord-14/20 text-nord-14' : 'bg-nord-11/20 text-nord-11'}">
              ${crit.met ? 'PASS' : 'FAIL'}
            </span>
          </div>
          <p class="text-[11px] text-nord-4 opacity-80">${escapeHtml(crit.evidence || '')}</p>
        `;
        modalCriteriaList.appendChild(critEl);
      });
    }

    modalSpecsList.innerHTML = "";
    const specs = item.specs || [];
    if (specs.length === 0) {
      modalSpecsList.innerHTML = '<span class="text-nord-3 italic col-span-2">No direct specification items scraped.</span>';
    } else {
      specs.forEach(s => {
        const specSpan = document.createElement("div");
        specSpan.className = "truncate text-nord-4";
        specSpan.textContent = `• ${s}`;
        modalSpecsList.appendChild(specSpan);
      });
    }

    productDetailModal.classList.remove("hidden");
    productDetailModal.classList.add("flex");
    lucide.createIcons({ root: productDetailModal });
  }

  closeDetailModal.addEventListener("click", () => {
    productDetailModal.classList.add("hidden");
    productDetailModal.classList.remove("flex");
  });

  // --- HISTORY TAB ---
  navSearchTab.addEventListener("click", () => {
    state.activeTab = "search";
    navSearchTab.classList.add("active");
    navHistoryTab.classList.remove("active");
    searchSection.classList.remove("hidden");
    historySection.classList.add("hidden");
  });

  navHistoryTab.addEventListener("click", () => {
    state.activeTab = "history";
    navHistoryTab.classList.add("active");
    navSearchTab.classList.remove("active");
    historySection.classList.remove("hidden");
    searchSection.classList.add("hidden");
    loadSearchHistory();
  });

  async function loadHistoryCount() {
    try {
      const resp = await fetch("/api/history");
      if (resp.ok) {
        const data = await resp.json();
        historyBadgeCount.textContent = (data.searches || []).length;
      }
    } catch (err) {}
  }

  async function loadSearchHistory() {
    try {
      const resp = await fetch("/api/history");
      if (!resp.ok) return;
      const data = await resp.json();
      const list = data.searches || [];

      if (list.length === 0) {
        historyEmptyState.classList.remove("hidden");
        historyGrid.innerHTML = "";
      } else {
        historyEmptyState.classList.add("hidden");
        historyGrid.innerHTML = "";

        list.forEach(rec => {
          const card = document.createElement("div");
          card.className = "theme-bg-card border theme-border rounded-2xl p-5 shadow-lg flex flex-col justify-between gap-4";
          card.innerHTML = `
            <div>
              <div class="flex items-center justify-between mb-2">
                <span class="text-xs font-mono text-nord-3">${new Date(rec.created_at).toLocaleString()}</span>
                <span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${rec.status === 'completed' ? 'bg-nord-14/15 text-nord-14' : 'bg-nord-13/15 text-nord-13'} uppercase">
                  ${rec.status}
                </span>
              </div>
              <h3 class="font-bold text-sm text-nord-6 mb-1">${escapeHtml(rec.search_term)}</h3>
              <p class="text-xs text-nord-4 opacity-75 line-clamp-2 mb-3">${escapeHtml(rec.conditions)}</p>
              <div class="flex items-center gap-3 text-xs font-mono">
                <span class="text-nord-5">Found: <strong>${rec.total_found}</strong></span>
                <span class="text-nord-14">Matches: <strong>${rec.total_matched}</strong></span>
              </div>
            </div>

            <div class="flex items-center justify-between pt-3 border-t theme-border">
              <button type="button" class="load-history-btn px-3 py-1.5 rounded-xl bg-nord-8/15 text-nord-8 hover:bg-nord-8 hover:text-nord-0 font-bold text-xs transition">
                View Results
              </button>
              <button type="button" class="delete-history-btn p-1.5 rounded-lg text-nord-3 hover:text-nord-11 hover:bg-nord-11/10 transition" title="Delete Search">
                <i data-lucide="trash-2" class="w-4 h-4"></i>
              </button>
            </div>
          `;

          card.querySelector(".load-history-btn").addEventListener("click", () => openHistoricalSearch(rec.id));
          card.querySelector(".delete-history-btn").addEventListener("click", async () => {
            if (confirm("Delete this saved search?")) {
              await fetch(`/api/history/${rec.id}`, { method: "DELETE" });
              loadSearchHistory();
              loadHistoryCount();
            }
          });

          historyGrid.appendChild(card);
        });

        lucide.createIcons({ root: historyGrid });
      }
    } catch (err) {
      console.error("Failed to load history:", err);
    }
  }

  async function openHistoricalSearch(searchId) {
    try {
      const resp = await fetch(`/api/history/${searchId}`);
      if (!resp.ok) return;
      const data = await resp.json();

      state.items = data.items || [];
      state.activeFilter = "all";
      renderResults();

      navSearchTab.click();
      liveStatusCard.classList.add("hidden");
    } catch (err) {}
  }

  function escapeHtml(text) {
    if (!text) return "";
    return text.toString()
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  init();
});
