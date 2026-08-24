// AliExpress AI Product Hunter - Background Service Worker (Manifest V3)

chrome.runtime.onInstalled.addListener(() => {
  console.log('AliExpress AI Product Hunter extension installed.');
});

// Helper for calling Gemini directly or through local Docker server
async function evaluateProducts(items, conditions, apiKey, modelName, localServerUrl = 'http://localhost:8000') {
  // 1. Try local AI Hunter server first (fastest batch processing)
  try {
    const res = await fetch(`${localServerUrl}/api/evaluate-batch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        items: items,
        conditions: conditions,
        gemini_api_key: apiKey,
        model_name: modelName || 'gemini-3.6-flash'
      })
    });
    if (res.ok) {
      const data = await res.json();
      return data.evaluated_items || [];
    }
  } catch (err) {
    console.log('Local AI Hunter server unavailable, falling back to direct Gemini API call:', err);
  }

  // 2. Direct Gemini Fallback
  const prompt = `You are an expert product analyst. Evaluate each product against the given conditions.
Conditions:
${conditions}

Products:
${JSON.stringify(items.map(i => ({ id: i.item_id, title: i.title, price: i.price })))}

Return a strict JSON object with this format:
{
  "evaluations": [
    {
      "item_id": "string",
      "is_match": true/false,
      "confidence": 0.0-1.0,
      "verdict_reason": "brief reason"
    }
  ]
}`;

  const selectedModel = modelName || 'gemini-3.6-flash';
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${selectedModel}:generateContent?key=${apiKey}`;

  const resp = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      contents: [{ parts: [{ text: prompt }] }],
      generationConfig: { responseMimeType: 'application/json', temperature: 0.1 }
    })
  });

  if (!resp.ok) {
    throw new Error(`Gemini API error: ${resp.status} ${resp.statusText}`);
  }

  const result = await resp.json();
  const text = result.candidates?.[0]?.content?.parts?.[0]?.text || '{}';
  const parsed = JSON.parse(text);
  const evalMap = new Map((parsed.evaluations || []).map(e => [String(e.item_id), e]));

  return items.map(item => {
    const ev = evalMap.get(String(item.item_id));
    return {
      ...item,
      is_match: ev ? Boolean(ev.is_match) : false,
      confidence: ev ? (ev.confidence || 0.8) : 0.5,
      verdict_reason: ev ? ev.verdict_reason : 'Evaluated by Gemini'
    };
  });
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'ANALYZE_PAGE_ITEMS') {
    evaluateProducts(
      request.items,
      request.conditions,
      request.apiKey,
      request.modelName,
      request.serverUrl
    )
      .then(evaluated => {
        sendResponse({ success: true, evaluated_items: evaluated });
      })
      .catch(err => {
        sendResponse({ success: false, error: err.message });
      });
    return true; // Keep channel open for async response
  }
});
