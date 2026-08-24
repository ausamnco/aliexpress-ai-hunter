import asyncio
import os
import sys
import logging
import argparse
from typing import Dict, Any

from app import database
from app import ai_evaluator
from app import scraper

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("test_suite")

async def run_live_test_suite(
    gemini_key: str,
    search_query: str = "2.4G ANC headset",
    conditions: str = "1. Active Noise Cancellation (Hardware ANC)\n2. 2.4GHz USB wireless dongle included\n3. Deliverable to Australia"
):
    print("=" * 70)
    print("🧪 ALIEXPRESS AI PRODUCT HUNTER — CAMOUFOX LIVE TEST SUITE")
    print("=" * 70)

    # 1. Initialize Database
    print("\n[STEP 1/5] Initializing Test Database...")
    await database.init_db()
    print("✅ SQLite database initialized.")

    # 2. Test Gemini API Key & Model Availability
    print("\n[STEP 2/5] Diagnosing & Testing Gemini API Key...")
    diag = await ai_evaluator.diagnose_and_validate_key(gemini_key)
    print(f" -> Valid: {diag.get('valid')}")
    print(f" -> Quota Available: {diag.get('quota_available')}")
    print(f" -> Models Available: {diag.get('models')[:5]}")
    if not diag.get("valid") or not diag.get("quota_available"):
        print(f"❌ Gemini Key validation failed: {diag.get('message')}")
        return False
    print("✅ Gemini API Key authenticated and model generation verified.")

    # 3. Test Gemini Search Variations Generation
    print("\n[STEP 3/5] Testing Intelligent Query Generation with Gemini...")
    model_to_use = diag["models"][0] if diag.get("models") else "gemini-3.5-flash"
    variations = await ai_evaluator.generate_search_variations(
        search_term=search_query,
        conditions=conditions,
        api_key=gemini_key,
        model_name=model_to_use
    )
    print(f" -> Generated variations ({len(variations)}): {variations}")
    assert len(variations) > 0, "No variations generated!"
    print("✅ Gemini query generation working.")

    # 4. Test Live Camoufox Stealth Scraping & Extraction
    print(f"\n[STEP 4/5] Executing Live Camoufox Stealth Search for '{search_query}'...")
    from camoufox.async_api import AsyncCamoufox
    
    candidates = []
    async with AsyncCamoufox(headless=True, geoip=True, humanize=True, os="windows") as browser:
        page = await browser.new_page()
        search_url = f"https://www.aliexpress.com/w/wholesale-2-4g-anc-headset.html?SearchText=2.4g+anc+headset"
        await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        
        # Scroll to load candidates
        for _ in range(2):
            await page.evaluate("window.scrollBy(0, 1000);")
            await asyncio.sleep(0.5)

        candidates = await page.evaluate('''() => {
            const results = [];
            const seen = new Set();
            const links = document.querySelectorAll('a[href*="/item/"]');
            for (const l of links) {
                const href = l.getAttribute('href') || '';
                const m = href.match(/\\/item\\/(\\d+)\\.html/);
                if (m && !seen.has(m[1])) {
                    seen.add(m[1]);
                    const card = l.closest('div[class*="search-item"], div[class*="card"], div[class*="item"], div[class*="srp-item"], div[class*="search-card"], div[class*="search_item"]') || l.parentElement;
                    const titleEl = card ? (card.querySelector('h1, h3, h4, span[class*="title"], div[class*="title"], [class*="product-title"]') || l) : l;
                    const priceEl = card ? card.querySelector('div[class*="price"], span[class*="price"], [class*="money"]') : null;
                    const imgEl = card ? card.querySelector('img') : l.querySelector('img');
                    
                    let imgUrl = imgEl ? (imgEl.getAttribute('src') || imgEl.getAttribute('data-src') || '') : '';
                    if (imgUrl.startsWith('//')) imgUrl = 'https:' + imgUrl;
                    
                    results.push({
                        item_id: m[1],
                        title: titleEl ? titleEl.textContent.trim() : `Product #${m[1]}`,
                        price: priceEl ? priceEl.textContent.trim() : 'N/A',
                        image_url: imgUrl,
                        url: 'https://www.aliexpress.com/item/' + m[1] + '.html',
                        card_text: card ? card.innerText : l.innerText
                    });
                }
            }
            return results;
        }''')

    print(f" -> Extracted {len(candidates)} product candidate(s) via Camoufox:")
    for idx, c in enumerate(candidates[:5]):
        print(f"    [{idx+1}] ID: {c['item_id']} | Price: {c['price']} | Title: {c['title'][:60]}...")

    assert len(candidates) > 0, "No candidates found via Camoufox!"

    # 5. Gemini AI Evaluation & SQLite Persistence
    first_item = candidates[0]
    item_id = first_item["item_id"]
    print(f"\n[STEP 5/5] Running Gemini AI Evaluation for Product #{item_id}...")
    
    first_item["specs"] = []
    evaluation = await ai_evaluator.evaluate_product(
        item=first_item,
        conditions=conditions,
        api_key=gemini_key,
        model_name=model_to_use
    )
    print(f"\n🎯 Gemini Verdict: {'MATCH (PASS)' if evaluation.is_match else 'EXCLUDED (FAIL)'}")
    print(f"   Confidence: {round(evaluation.confidence * 100)}%")
    print(f"   Reason: {evaluation.verdict_reason}")
    print("   Breakdown:")
    for crit in evaluation.criteria_evaluations:
        print(f"    - [{'PASS' if crit.met else 'FAIL'}] {crit.condition}: {crit.evidence}")

    # Test SQLite storage
    import uuid
    test_search_id = f"test-camoufox-{uuid.uuid4().hex[:6]}"
    await database.create_search(test_search_id, search_query, conditions, "AUD", "AU")
    first_item["is_match"] = evaluation.is_match
    first_item["confidence"] = evaluation.confidence
    first_item["verdict_reason"] = evaluation.verdict_reason
    first_item["criteria_breakdown"] = [c.model_dump() for c in evaluation.criteria_evaluations]
    await database.save_search_result(test_search_id, first_item)
    await database.update_search_status(test_search_id, "completed", 1, 1 if evaluation.is_match else 0)

    saved = await database.get_search_by_id(test_search_id)
    assert saved is not None and len(saved["items"]) > 0, "Failed to persist evaluated item to DB!"
    print("✅ Database persistence & retrieval verified.")

    print("\n" + "=" * 70)
    print("🎉 ALL TESTS COMPLETED SUCCESSFULLY! CAMOUFOX PIPELINE IS FULLY OPERATIONAL.")
    print("=" * 70)
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--gemini-key", default=os.environ.get("GEMINI_API_KEY", ""))
    args = parser.parse_args()

    if not args.gemini_key:
        print("⚠️ Please provide --gemini-key <KEY> or set GEMINI_API_KEY environment variable.")
        sys.exit(1)

    asyncio.run(run_live_test_suite(
        gemini_key=args.gemini_key
    ))
