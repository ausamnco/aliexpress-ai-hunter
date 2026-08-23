#!/usr/bin/env python3
"""
AliExpress 2.4GHz + Hardware ANC Wireless Headphones Finder
Strict criteria:
1. Hardware ANC (Active Noise Cancellation) OR Transparency / Ambient Sound Mode (excludes ENC-only)
2. Dedicated 2.4GHz USB Dongle / Receiver (excludes Bluetooth-only)
3. Deliverable to Australia
"""

import asyncio
import json
import os
import re
import sys
import urllib.parse
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

OUTPUT_FILE = "aliexpress_anc_dongle_results.json"
TARGET_CANDIDATES = 50

SEARCH_QUERIES = [
    "2.4G ANC headset",
    "2.4ghz dongle active noise cancelling headphones",
    "tri-mode 2.4G wireless ANC headphones with USB adapter",
    "2.4G wireless active noise cancelling headphones PC PS5",
]

def check_captcha_needed(page_text: str, current_url: str) -> bool:
    blocked_keywords = [
        "_____tmd_____/punish",
        "sec-captcha",
        "baxia-dialog",
        "captcha verification",
    ]
    current_url_lower = current_url.lower()
    page_text_lower = page_text.lower()
    for kw in blocked_keywords:
        if kw in current_url_lower or kw in page_text_lower:
            return True
    return False

async def wait_for_user_verification(page, timeout_seconds=180):
    content = await page.content()
    url = page.url
    if check_captcha_needed(content, url):
        print("\n" + "=" * 76)
        print("🚨 [USER ACTION REQUIRED] ALIEXPRESS SECURITY VERIFICATION CHALLENGE DETECTED!")
        print("👉 A Chrome browser window is open on your screen.")
        print("👉 Please slide the verification slider / complete the challenge in that window.")
        print("👉 The script is actively waiting and will automatically proceed once completed.")
        print("=" * 76 + "\n")
        
        elapsed = 0
        while elapsed < timeout_seconds:
            await asyncio.sleep(2)
            elapsed += 2
            try:
                new_url = page.url
                new_content = await page.content()
                if not check_captcha_needed(new_content, new_url):
                    print("✅ Verification challenge successfully solved! Resuming scraping...\n")
                    await asyncio.sleep(2)
                    return True
                if elapsed % 10 == 0:
                    print(f"⏳ Still waiting for manual verification ({elapsed}s / {timeout_seconds}s)...")
            except Exception:
                pass
                
        print("⚠️ Verification challenge wait timed out. Continuing with available data...")
        return False
    return True

def analyze_features(title: str, specs: list, body_text: str):
    combined_text = f"{title} {' '.join(specs)} {body_text}".lower()
    
    # 1. Hardware ANC / Transparency Mode Check
    anc_patterns = [
        r'\bactive\s+noise\s+cancell?ing\b',
        r'\bactive\s+noise\s+cancellation\b',
        r'\bhybrid\s+anc\b',
        r'\b-\d+\s*db\s*(anc|noise|reduction)\b',
        r'\b\d+\s*db\s*anc\b',
        r'\btransparency\s+mode\b',
        r'\bambient\s+(sound|mode)\b',
        r'\bdual-mic\s+anc\b',
        r'\banc\s+mode\b',
        r'\banc\s+active\b',
        r'\banc\s+headphone\b',
        r'\banc\s+headset\b',
        r'\bactive\s+noise-cancellation:\s*yes\b',
    ]
    
    has_anc = False
    for pat in anc_patterns:
        if re.search(pat, combined_text, re.I):
            has_anc = True
            break
            
    for s in specs:
        if "active noise-cancellation" in s.lower() and "yes" in s.lower():
            has_anc = True
            break

    # Check for ENC-only (Microphone/Call noise reduction only)
    enc_only = False
    enc_indicators = [
        r'\benc\s+call\s+noise\s+reduction\b',
        r'\bcall\s+noise\s+reduction\b',
        r'\benvironmental\s+noise\s+cancellation\b',
        r'\bcvc\s*8\.0\b',
        r'\benc\s+mic\b',
        r'\bmic\s+noise\s+cancellation\b',
    ]
    has_enc_mention = any(re.search(pat, combined_text, re.I) for pat in enc_indicators)
    if has_enc_mention and not has_anc:
        enc_only = True

    # 2. Dedicated 2.4GHz USB Dongle / Receiver Check
    dongle_patterns = [
        r'\b2\.4\s*g\s*(dongle|receiver|adapter|usb|transmitter|wireless)\b',
        r'\b2\.4ghz\s*(dongle|receiver|adapter|usb|transmitter|wireless)\b',
        r'\btri-mode\b',
        r'\bthree-mode\b',
        r'\b3-mode\b',
        r'\b4-mode\b',
        r'\b5-mode\b',
        r'\busb\s+dongle\b',
        r'\busb\s+receiver\b',
        r'\busb\s+adapter\b',
        r'\btype-c\s+receiver\b',
        r'\btype-c\s+dongle\b',
        r'\btype-c\s+adapter\b',
        r'\b2\.4g/bluetooth\b',
        r'\b2\.4g\+bt\b',
        r'\b2\.4g\+bluetooth\b',
        r'\b2\.4g\s+and\s+bluetooth\b',
    ]
    has_dongle = any(re.search(pat, combined_text, re.I) for pat in dongle_patterns)
    is_bluetooth_only = not has_dongle

    # 3. Delivery to Australia Check
    undeliverable_patterns = [
        r'can\s*not\s*be\s*delivered\s*to\s*australia',
        r'cannot\s*be\s*shipped\s*to\s*your\s*address',
        r'this\s*item\s*cannot\s*be\s*shipped\s*to\s*australia',
        r'out\s*of\s*stock',
    ]
    undeliverable = any(re.search(pat, combined_text, re.I) for pat in undeliverable_patterns)
    deliverable_to_au = not undeliverable

    is_match = has_anc and not enc_only and has_dongle and not is_bluetooth_only and deliverable_to_au

    reasons = []
    if not has_anc:
        reasons.append("No hardware ANC / Transparency mode detected")
    if enc_only:
        reasons.append("Only ENC (microphone call noise reduction), no active ear-cup ANC")
    if not has_dongle or is_bluetooth_only:
        reasons.append("Bluetooth/wired only, no dedicated 2.4GHz USB dongle/receiver")
    if not deliverable_to_au:
        reasons.append("Not deliverable to Australia")

    return {
        "is_match": is_match,
        "has_anc": has_anc,
        "enc_only": enc_only,
        "has_dongle": has_dongle,
        "deliverable_to_au": deliverable_to_au,
        "reasons": reasons,
    }

async def scrape_aliexpress():
    stealth = Stealth()
    print("🚀 Initializing Playwright Chromium Browser...")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-infobars',
                '--disable-dev-shm-usage',
            ]
        )
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 900},
            locale="en-US",
        )
        
        page = await context.new_page()
        await stealth.apply_stealth_async(page)

        collected_candidates = {} # item_id -> dict

        print("\n🔍 Step 1: Performing Multi-Query Search across AliExpress...")
        for q_idx, query in enumerate(SEARCH_QUERIES, 1):
            if len(collected_candidates) >= TARGET_CANDIDATES:
                break
                
            encoded_query = urllib.parse.quote_plus(query)
            search_url = f"https://www.aliexpress.com/wholesale?SearchText={encoded_query}"
            print(f"\n[Query {q_idx}/{len(SEARCH_QUERIES)}] Searching for: \"{query}\"")
            
            try:
                await page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
                await wait_for_user_verification(page)
                await page.wait_for_timeout(3000)
                
                # Scroll down progressively to load infinite scroll / lazy loaded products
                for s in range(5):
                    await page.evaluate("window.scrollBy(0, 900)")
                    await page.wait_for_timeout(1000)
                    
                # Extract search cards
                item_links = await page.locator("a[href*='/item/']").all()
                print(f"Found {len(item_links)} product card elements on page.")
                
                for link in item_links:
                    href = await link.get_attribute("href")
                    if not href:
                        continue
                        
                    id_match = re.search(r'/item/(\d+)\.html', href)
                    if not id_match:
                        continue
                    item_id = id_match.group(1)
                    
                    if item_id in collected_candidates:
                        continue
                        
                    card_text = await link.inner_text()
                    lines = [line.strip() for line in card_text.split("\n") if line.strip()]
                    
                    title = lines[0] if lines else "Unknown Headphone"
                    price = "N/A"
                    for line in lines:
                        if "AU$" in line or "$" in line:
                            price = line
                            break
                            
                    canonical_url = f"https://www.aliexpress.com/item/{item_id}.html"
                    
                    collected_candidates[item_id] = {
                        "item_id": item_id,
                        "title": title,
                        "price": price,
                        "card_text": " | ".join(lines),
                        "url": canonical_url,
                        "query_source": query,
                        "specs": [],
                        "body_snippet": "",
                    }
                    
                    if len(collected_candidates) >= TARGET_CANDIDATES:
                        break
                        
            except Exception as e:
                print(f"Error while searching for '{query}': {e}")
                
        print(f"\n📊 Total unique candidate listings collected: {len(collected_candidates)}")
        
        # Step 2: Deep Inspection & Spec Extraction
        print("\n🔍 Step 2: Extracting detailed specifications & checking hardware criteria...")
        
        verified_results = []
        all_parsed_items = []
        
        for idx, (item_id, item) in enumerate(collected_candidates.items(), 1):
            print(f"[{idx}/{len(collected_candidates)}] Inspecting: {item['title'][:55]}... ({item['price']})")
            
            specs = []
            body_text = item["card_text"]
            
            try:
                await page.goto(item["url"], wait_until="domcontentloaded", timeout=30000)
                await wait_for_user_verification(page, timeout_seconds=30)
                await page.wait_for_timeout(1500)
                
                # Scroll to load specification section
                await page.evaluate("window.scrollBy(0, 1000)")
                await page.wait_for_timeout(1000)
                
                title_elem = await page.locator("h1").first.inner_text() if await page.locator("h1").count() > 0 else ""
                if title_elem and len(title_elem.strip()) > 5:
                    item["title"] = title_elem.strip()
                    
                # Extract specs
                spec_elems = await page.locator("[class*='specification--prop'], [class*='specification-item'], [class*='property-item'], [class*='pdp-info-item']").all()
                for se in spec_elems:
                    txt = await se.inner_text()
                    if txt.strip():
                        specs.append(txt.strip().replace('\n', ': '))
                item["specs"] = specs
                
                # Extract body snippet
                body_elem = await page.locator("body").inner_text()
                body_text = f"{item['card_text']} {body_elem[:4000]}"
                item["body_snippet"] = body_text[:2000]
                
            except Exception:
                pass

            # Perform strict criteria analysis
            analysis = analyze_features(item["title"], item["specs"], body_text)
            item.update(analysis)
            all_parsed_items.append(item)
            
            if analysis["is_match"]:
                print(f"  🌟 [MATCH VERIFIED]: {item['title'][:65]}")
                verified_results.append(item)
            else:
                print(f"  ❌ Filtered out: {', '.join(analysis['reasons'])}")

        await browser.close()

    # Step 3: Save results
    output_data = {
        "total_parsed": len(all_parsed_items),
        "total_verified_matches": len(verified_results),
        "strict_criteria": {
            "hardware_anc_or_transparency": True,
            "dedicated_2_4ghz_usb_dongle": True,
            "deliverable_to_australia": True,
            "enc_only_excluded": True,
            "bluetooth_only_excluded": True,
        },
        "verified_matches": verified_results,
        "all_candidates": all_parsed_items,
    }

    output_path = os.path.join(os.getcwd(), OUTPUT_FILE)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 70)
    print(f"🎉 Scraping and filtering complete!")
    print(f"Total candidates analyzed: {len(all_parsed_items)}")
    print(f"Verified matches meeting all criteria: {len(verified_results)}")
    print(f"Saved results to: {output_path}")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(scrape_aliexpress())
