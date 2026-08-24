// AliExpress AI Product Hunter - Content Script
// Extracts live rendered products with 0 lag and renders AI match badges on product cards.

(function() {
  'use strict';

  function extractPageProducts() {
    const products = [];
    const seenIds = new Set();

    // 1. Try script data tags if present in DOM
    const scripts = document.querySelectorAll('script');
    for (const s of scripts) {
      const text = s.textContent || '';
      if (text.includes('_init_data_') && text.includes('itemList')) {
        try {
          const match = text.match(/_init_data_\s*=\s*\{(?:\s*data:\s*)?(\{.+?\})\s*\}(?:;|\n|$)/s);
          if (match) {
            const data = JSON.parse(match[1]);
            const root = data.data?.root?.fields || data.root?.fields || data;
            const items = root.mods?.itemList?.content || [];
            for (const item of items) {
              const pid = String(item.productId || item.itemCardId || item.targetId || '');
              if (pid && !seenIds.has(pid)) {
                seenIds.add(pid);
                const title = item.title?.displayTitle || item.title?.title || `Product #${pid}`;
                const price = item.prices?.salePrice?.formattedPrice || item.prices?.originalPrice?.formattedPrice || 'N/A';
                let img = item.image?.imgUrl || '';
                if (img.startsWith('//')) img = 'https:' + img;
                products.push({
                  item_id: pid,
                  title: title,
                  price: price,
                  image_url: img,
                  url: `https://www.aliexpress.com/item/${pid}.html`
                });
              }
            }
          }
        } catch (e) {}
      }
    }

    // 2. DOM Fallback: Scan product card anchor elements
    const itemLinks = document.querySelectorAll('a[href*="/item/"]');
    for (const link of itemLinks) {
      const href = link.getAttribute('href') || '';
      const idMatch = href.match(/\/item\/(\d+)\.html/);
      if (!idMatch) continue;
      const pid = idMatch[1];
      if (seenIds.has(pid)) continue;
      seenIds.add(pid);

      const card = link.closest('div[class*="search-item"], div[class*="card"], div[class*="item"], div[class*="srp-item"]') || link.parentElement;
      const titleEl = card ? (card.querySelector('h1, h3, h4, span[class*="title"], div[class*="title"]') || link) : link;
      const title = titleEl ? titleEl.textContent.trim() : `Product #${pid}`;

      const priceEl = card ? card.querySelector('div[class*="price"], span[class*="price"]') : null;
      const price = priceEl ? priceEl.textContent.trim() : 'N/A';

      const imgEl = card ? card.querySelector('img') : link.querySelector('img');
      let imgUrl = imgEl ? (imgEl.getAttribute('src') || imgEl.getAttribute('data-src') || '') : '';
      if (imgUrl.startsWith('//')) imgUrl = 'https:' + imgUrl;

      products.push({
        item_id: pid,
        title: title,
        price: price,
        image_url: imgUrl,
        url: href.startsWith('http') ? href : `https://www.aliexpress.com${href}`
      });

      if (products.length >= 60) break;
    }

    return products;
  }

  function injectBadges(evaluatedItems) {
    if (!evaluatedItems || evaluatedItems.length === 0) return;

    const itemMap = new Map();
    for (const item of evaluatedItems) {
      itemMap.set(String(item.item_id), item);
    }

    const itemLinks = document.querySelectorAll('a[href*="/item/"]');
    for (const link of itemLinks) {
      const href = link.getAttribute('href') || '';
      const idMatch = href.match(/\/item\/(\d+)\.html/);
      if (!idMatch) continue;
      const pid = idMatch[1];
      const evalData = itemMap.get(pid);
      if (!evalData) continue;

      const card = link.closest('div[class*="search-item"], div[class*="card"], div[class*="item"], div[class*="srp-item"]') || link.parentElement;
      if (!card || card.querySelector('.ai-hunter-badge')) continue;

      card.style.position = 'relative';

      const badge = document.createElement('div');
      badge.className = 'ai-hunter-badge';
      const isMatch = evalData.is_match;
      const conf = evalData.confidence ? Math.round(evalData.confidence * 100) : 90;

      badge.style.cssText = `
        position: absolute;
        top: 8px;
        left: 8px;
        z-index: 999;
        padding: 4px 8px;
        border-radius: 8px;
        font-size: 11px;
        font-weight: bold;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        color: white;
        background: ${isMatch ? '#2e7d32' : '#c62828'};
        box-shadow: 0 4px 10px rgba(0,0,0,0.3);
        cursor: pointer;
        display: flex;
        align-items: center;
        gap: 4px;
      `;

      badge.innerHTML = `
        <span>${isMatch ? '✓ MATCH' : '✕ EXCLUDED'}</span>
        <span style="opacity: 0.85; font-size: 9px;">(${conf}%)</span>
      `;

      badge.title = evalData.verdict_reason || (isMatch ? 'All criteria satisfied' : 'Criteria failed');

      card.appendChild(badge);
    }

    injectFloatingFilterBar(evaluatedItems);
  }

  function injectFloatingFilterBar(evaluatedItems) {
    if (document.getElementById('ai-hunter-floating-bar')) return;

    const matchesCount = evaluatedItems.filter(i => i.is_match).length;
    const excludedCount = evaluatedItems.length - matchesCount;

    const bar = document.createElement('div');
    bar.id = 'ai-hunter-floating-bar';
    bar.style.cssText = `
      position: fixed;
      bottom: 24px;
      right: 24px;
      z-index: 999999;
      background: #2e3440;
      color: #eceff4;
      border: 1px solid #4c566a;
      border-radius: 16px;
      padding: 10px 16px;
      display: flex;
      align-items: center;
      gap: 12px;
      box-shadow: 0 8px 24px rgba(0,0,0,0.4);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      font-size: 12px;
    `;

    bar.innerHTML = `
      <div style="font-weight: bold; color: #88c0d0;">🎯 AI Hunter (${matchesCount} Matches)</div>
      <button id="ai-filter-matches-btn" style="background: #a3be8c; color: #2e3440; border: none; border-radius: 8px; padding: 4px 10px; font-weight: bold; cursor: pointer;">Show Matches (${matchesCount})</button>
      <button id="ai-filter-all-btn" style="background: #4c566a; color: white; border: none; border-radius: 8px; padding: 4px 10px; font-weight: bold; cursor: pointer;">Show All (${evaluatedItems.length})</button>
    `;

    document.body.appendChild(bar);

    document.getElementById('ai-filter-matches-btn')?.addEventListener('click', () => {
      filterVisibleCards(true, evaluatedItems);
    });
    document.getElementById('ai-filter-all-btn')?.addEventListener('click', () => {
      filterVisibleCards(null, evaluatedItems);
    });
  }

  function filterVisibleCards(onlyMatches, evaluatedItems) {
    const itemMap = new Map(evaluatedItems.map(i => [String(i.item_id), i]));
    const itemLinks = document.querySelectorAll('a[href*="/item/"]');
    for (const link of itemLinks) {
      const idMatch = (link.getAttribute('href') || '').match(/\/item\/(\d+)\.html/);
      if (!idMatch) continue;
      const pid = idMatch[1];
      const data = itemMap.get(pid);
      const card = link.closest('div[class*="search-item"], div[class*="card"], div[class*="item"], div[class*="srp-item"]') || link.parentElement;
      if (!card) continue;

      if (onlyMatches === true) {
        card.style.display = (data && data.is_match) ? '' : 'none';
      } else {
        card.style.display = '';
      }
    }
  }

  // Message passing listener
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'EXTRACT_PRODUCTS') {
      const products = extractPageProducts();
      sendResponse({ products: products });
    } else if (request.action === 'INJECT_BADGES') {
      injectBadges(request.evaluated_items);
      sendResponse({ status: 'ok' });
    }
    return true;
  });

})();
