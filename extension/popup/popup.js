// AliExpress AI Product Hunter - Popup Logic

document.addEventListener('DOMContentLoaded', async () => {
  const geminiKeyInput = document.getElementById('gemini-key');
  const conditionsInput = document.getElementById('conditions');
  const modelSelect = document.getElementById('model-select');
  const serverUrlInput = document.getElementById('server-url');
  const analyzeBtn = document.getElementById('analyze-btn');
  const statusBox = document.getElementById('status-box');
  const statusText = document.getElementById('status-text');
  const resultsSummary = document.getElementById('results-summary');
  const statMatches = document.getElementById('stat-matches');
  const statTotal = document.getElementById('stat-total');

  // Load saved settings from chrome.storage.local
  const saved = await chrome.storage.local.get(['gemini_api_key', 'conditions', 'model_name', 'server_url']);
  if (saved.gemini_api_key) geminiKeyInput.value = saved.gemini_api_key;
  if (saved.conditions) conditionsInput.value = saved.conditions;
  if (saved.model_name) modelSelect.value = saved.model_name;
  if (saved.server_url) serverUrlInput.value = saved.server_url;

  function saveSettings() {
    chrome.storage.local.set({
      gemini_api_key: geminiKeyInput.value.trim(),
      conditions: conditionsInput.value.trim(),
      model_name: modelSelect.value,
      server_url: serverUrlInput.value.trim()
    });
  }

  geminiKeyInput.addEventListener('change', saveSettings);
  conditionsInput.addEventListener('change', saveSettings);
  modelSelect.addEventListener('change', saveSettings);
  serverUrlInput.addEventListener('change', saveSettings);

  analyzeBtn.addEventListener('click', async () => {
    const key = geminiKeyInput.value.trim();
    const conditions = conditionsInput.value.trim();
    const model = modelSelect.value;
    const serverUrl = serverUrlInput.value.trim() || 'http://localhost:8000';

    if (!key) {
      statusBox.classList.remove('hidden');
      statusText.textContent = '❌ Please enter your Gemini API key.';
      geminiKeyInput.focus();
      return;
    }

    if (!conditions) {
      statusBox.classList.remove('hidden');
      statusText.textContent = '❌ Please specify at least one condition.';
      conditionsInput.focus();
      return;
    }

    saveSettings();

    // Query active tab
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab || !tab.id) {
      statusBox.classList.remove('hidden');
      statusText.textContent = '❌ Could not access the active browser tab.';
      return;
    }

    if (!tab.url || (!tab.url.includes('aliexpress.com') && !tab.url.includes('aliexpress.us'))) {
      statusBox.classList.remove('hidden');
      statusText.textContent = '⚠️ Please navigate to an AliExpress search or category page first.';
      return;
    }

    statusBox.classList.remove('hidden');
    statusText.textContent = '🔍 Extracting products from page DOM (<100ms)...';
    analyzeBtn.disabled = true;
    analyzeBtn.style.opacity = '0.7';

    try {
      // 1. Extract products via content script
      let response;
      try {
        response = await chrome.tabs.sendMessage(tab.id, { action: 'EXTRACT_PRODUCTS' });
      } catch (err) {
        // Content script might not be injected yet, inject it manually
        await chrome.scripting.executeScript({
          target: { tabId: tab.id },
          files: ['content.js']
        });
        response = await chrome.tabs.sendMessage(tab.id, { action: 'EXTRACT_PRODUCTS' });
      }

      const products = response?.products || [];
      if (products.length === 0) {
        statusText.textContent = '⚠️ No AliExpress product cards detected on this page.';
        analyzeBtn.disabled = false;
        analyzeBtn.style.opacity = '1';
        return;
      }

      statusText.textContent = `⚡ Running AI evaluation on ${products.length} products with ${model}...`;

      // 2. Send to background worker for batch evaluation
      const evalResp = await chrome.runtime.sendMessage({
        action: 'ANALYZE_PAGE_ITEMS',
        items: products,
        conditions: conditions,
        apiKey: key,
        modelName: model,
        serverUrl: serverUrl
      });

      if (!evalResp || !evalResp.success) {
        throw new Error(evalResp?.error || 'AI Evaluation failed');
      }

      const evaluatedItems = evalResp.evaluated_items || [];
      const matchCount = evaluatedItems.filter(i => i.is_match).length;

      // 3. Inject visual match badges onto AliExpress product cards
      await chrome.tabs.sendMessage(tab.id, {
        action: 'INJECT_BADGES',
        evaluated_items: evaluatedItems
      });

      statusText.textContent = `✅ Analysis complete! Found ${matchCount} matches. Badges rendered on AliExpress!`;
      statMatches.textContent = matchCount;
      statTotal.textContent = evaluatedItems.length;
      resultsSummary.classList.remove('hidden');

    } catch (err) {
      statusText.textContent = `❌ Error: ${err.message}`;
    } finally {
      analyzeBtn.disabled = false;
      analyzeBtn.style.opacity = '1';
    }
  });
});
