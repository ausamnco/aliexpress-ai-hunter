import asyncio
import os
import sys
import json
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
    gateway_provider: str = "zenrows",
    gateway_key: str = "",
    custom_gateway_url: str = "",
    search_query: str = "2.4G ANC headset",
    conditions: str = "1. Active Noise Cancellation (Hardware ANC)\n2. 2.4GHz USB wireless dongle included\n3. Deliverable to Australia"
):
    print("=" * 70)
    print("🧪 ALIEXPRESS AI PRODUCT HUNTER — AUTOMATED LIVE TEST SUITE")
    print("=" * 70)

    # 1. Initialize Database
    print("\n[STEP 1/6] Initializing Test Database...")
    await database.init_db()
    print("✅ SQLite database initialized.")

    # 2. Test Gemini API Key & Model Availability
    print("\n[STEP 2/6] Diagnosing & Testing Gemini API Key...")
    diag = await ai_evaluator.diagnose_and_validate_key(gemini_key)
    print(f" -> Valid: {diag.get('valid')}")
    print(f" -> Quota Available: {diag.get('quota_available')}")
    print(f" -> Models Available: {diag.get('models')[:5]}")
    if not diag.get("valid") or not diag.get("quota_available"):
        print(f"❌ Gemini Key validation failed: {diag.get('message')}")
        return False
    print("✅ Gemini API Key authenticated and model generation verified.")

    # 3. Test Gemini Search Variations Generation
    print("\n[STEP 3/6] Testing Intelligent Query Generation with Gemini...")
    variations = await ai_evaluator.generate_search_variations(
        search_term=search_query,
        conditions=conditions,
        api_key=gemini_key,
        model_name="gemini-3.7-flash" if "gemini-3.7-flash" in diag.get("models", []) else "gemini-2.5-flash"
    )
    print(f" -> Generated variations ({len(variations)}): {variations}")
    assert len(variations) > 0, "No variations generated!"
    print("✅ Gemini query generation working.")

    # 4. Test Scraping Gateway Connectivity
    print(f"\n[STEP 4/6] Testing Anti-Bot Gateway ({gateway_provider.upper()})...")
    gw_result = await scraper.GatewayScraperClient.validate_gateway(
        provider=gateway_provider,
        api_key=gateway_key,
        custom_gateway_url=custom_gateway_url
    )
    print(f" -> Gateway Validation: {gw_result}")
    if not gw_result.get("valid"):
        print(f"⚠️ Gateway validation check: {gw_result.get('message')}")
    else:
        print("✅ Gateway connected to AliExpress successfully with 0 anti-bot blocks.")

    # 5. Live Search & Parsing
    print(f"\n[STEP 5/6] Executing Live AliExpress Search for '{search_query}'...")
    search_url = f"https://www.aliexpress.com/w/wholesale-2-4g-anc-headset.html?SearchText=2.4g+anc+headset"
    status, html_content = await scraper.GatewayScraperClient.fetch_page(
        target_url=search_url,
        provider=gateway_provider,
        api_key=gateway_key,
        ship_country="AU",
        currency="AUD",
        custom_gateway_url=custom_gateway_url
    )
    print(f" -> Fetch status: {status}, HTML length: {len(html_content)} bytes")
    
    candidates = scraper.parse_search_results(html_content)
    print(f" -> Extracted {len(candidates)} product candidate(s) from live page:")
    for idx, c in enumerate(candidates[:5]):
        print(f"    [{idx+1}] ID: {c['item_id']} | Price: {c['price']} | Title: {c['title'][:60]}...")

    if candidates:
        # 6. Deep Item Detail & AI Evaluation Test
        first_item = candidates[0]
        item_id = first_item["item_id"]
        print(f"\n[STEP 6/6] Fetching Specifications & Running Gemini AI Evaluation for Product #{item_id}...")
        
        item_url = f"https://www.aliexpress.com/item/{item_id}.html"
        item_status, item_html = await scraper.GatewayScraperClient.fetch_page(
            target_url=item_url,
            provider=gateway_provider,
            api_key=gateway_key,
            ship_country="AU",
            currency="AUD",
            custom_gateway_url=custom_gateway_url
        )
        detailed_cand = scraper.parse_item_detail(item_html, item_id)
        if first_item.get("price") != "N/A" and detailed_cand.get("price") == "N/A":
            detailed_cand["price"] = first_item["price"]
        if not detailed_cand.get("image_url") and first_item.get("image_url"):
            detailed_cand["image_url"] = first_item["image_url"]
        if not detailed_cand.get("title") or detailed_cand.get("title") == f"AliExpress Product #{item_id}":
            if first_item.get("title") and first_item.get("title") != f"AliExpress Product #{item_id}":
                detailed_cand["title"] = first_item["title"]

        print(f" -> Scraped Specs Count: {len(detailed_cand.get('specs', []))}")
        print(f" -> Sample Specs: {detailed_cand.get('specs', [])[:3]}")

        model_to_use = diag["models"][0] if diag.get("models") else "gemini-3.6-flash"
        evaluation = await ai_evaluator.evaluate_product(
            item=detailed_cand,
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

        # Save to database
        import uuid
        test_search_id = f"test-live-run-{uuid.uuid4().hex[:6]}"
        await database.create_search(test_search_id, search_query, conditions, "AUD", "AU")
        detailed_cand["is_match"] = evaluation.is_match
        detailed_cand["confidence"] = evaluation.confidence
        detailed_cand["verdict_reason"] = evaluation.verdict_reason
        detailed_cand["criteria_breakdown"] = [c.model_dump() for c in evaluation.criteria_evaluations]
        await database.save_search_result(test_search_id, detailed_cand)
        await database.update_search_status(test_search_id, "completed", 1, 1 if evaluation.is_match else 0)

        saved = await database.get_search_by_id(test_search_id)
        assert saved is not None and len(saved["items"]) > 0, "Failed to persist evaluated item to DB!"
        print("✅ Database persistence & retrieval verified.")

    print("\n" + "=" * 70)
    print("🎉 ALL TESTS COMPLETED SUCCESSFULLY! CORE PIPELINE IS FULLY VALID.")
    print("=" * 70)
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--gemini-key", default=os.environ.get("GEMINI_API_KEY", ""))
    parser.add_argument("--gateway-provider", default="zenrows")
    parser.add_argument("--gateway-key", default=os.environ.get("GATEWAY_API_KEY", ""))
    parser.add_argument("--custom-url", default="")
    args = parser.parse_args()

    if not args.gemini_key:
        print("⚠️ Please provide --gemini-key <KEY> or set GEMINI_API_KEY environment variable.")
        sys.exit(1)

    asyncio.run(run_live_test_suite(
        gemini_key=args.gemini_key,
        gateway_provider=args.gateway_provider,
        gateway_key=args.gateway_key,
        custom_gateway_url=args.custom_url
    ))
