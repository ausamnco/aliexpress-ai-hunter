import asyncio
import json
import logging
import random
import time
import urllib.parse
from typing import List, Dict, Any, Optional
from playwright.async_api import async_playwright, Page, BrowserContext

try:
    from playwright_stealth import Stealth
    async def apply_stealth(page):
        await Stealth().apply_stealth_async(page)
except Exception:
    try:
        from playwright_stealth import stealth_async
        async def apply_stealth(page):
            await stealth_async(page)
    except Exception:
        async def apply_stealth(page):
            pass

from app import database
from app import ai_evaluator
from app.models import ItemDetail

logger = logging.getLogger("aliexpress_scraper")

class ScraperSession:
    def __init__(self, search_id: str):
        self.search_id = search_id
        self.status = "pending"
        self.stage = "Initializing"
        self.progress_pct = 0
        self.total_candidates = 0
        self.evaluated_count = 0
        self.matched_count = 0
        self.event_queue = asyncio.Queue()
        self.active_page: Optional[Page] = None
        self.active_context: Optional[BrowserContext] = None
        self.challenge_url: Optional[str] = None
        self.current_search_url: Optional[str] = None
        self.captcha_event = asyncio.Event()
        self.captcha_resume_event = asyncio.Event()
        self.resume_action = "continue_remaining"
        self.is_cancelled = False
        self.remaining_terms: List[str] = []

    async def emit_event(self, event_type: str, data: Dict[str, Any] = None):
        payload = {
            "search_id": self.search_id,
            "type": event_type,
            "stage": self.stage,
            "progress_pct": self.progress_pct,
            "data": data or {}
        }
        await self.event_queue.put(payload)

sessions: Dict[str, ScraperSession] = {}

async def handle_captcha_interaction(
    search_id: str,
    action: str,
    cookie_str: Optional[str] = None,
    redirect_url: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    session = sessions.get(search_id)
    if not session or not session.active_page or not session.active_context:
        return {"success": False, "message": "No active scraper session or page."}

    context = session.active_context
    page = session.active_page

    if action in ["resolve", "check", "done", "sync_cookie", "sync_url"]:
        cookies_to_add = []

        if cookie_str:
            clean_str = cookie_str.strip()
            pairs = [p.strip() for p in clean_str.split(";") if p.strip()]
            for p in pairs:
                if "=" in p:
                    k, v = p.split("=", 1)
                    k_clean = k.strip()
                    v_clean = v.strip()
                    if k_clean:
                        cookies_to_add.append({
                            "name": k_clean,
                            "value": v_clean,
                            "domain": ".aliexpress.com",
                            "path": "/"
                        })

        if redirect_url and "aliexpress.com" in redirect_url:
            parsed = urllib.parse.urlparse(redirect_url)
            params = urllib.parse.parse_qs(parsed.query)
            if "x5secdata" in params:
                cookies_to_add.append({
                    "name": "x5sec",
                    "value": params["x5secdata"][0],
                    "domain": ".aliexpress.com",
                    "path": "/"
                })

        if cookies_to_add:
            logger.info(f"Injecting {len(cookies_to_add)} cookies into Playwright context...")
            try:
                await context.add_cookies(cookies_to_add)
            except Exception as e:
                logger.warning(f"Error adding cookies to context: {e}")

        # Check page status by reloading or navigating to target search url
        try:
            target = session.current_search_url or page.url
            logger.info(f"Reloading Playwright page to check verification: {target}")
            await page.goto(target, wait_until="domcontentloaded", timeout=25000)
            await asyncio.sleep(2.0)
        except Exception as e:
            logger.warning(f"Error refreshing verification status: {e}")

        is_still_punish = "punish" in page.url or (await page.query_selector("#nc_1_n1z, .btn_slide") is not None)
        if not is_still_punish:
            session.captcha_event.set()
            await session.emit_event("captcha_cleared", {"message": "Verification passed!"})
            return {"success": True, "resolved": True}
        else:
            return {
                "success": True, 
                "resolved": False, 
                "message": "Verification is still showing on AliExpress. Please ensure you completed the slider in the tab."
            }

    elif action == "cancel":
        session.captcha_event.set()
        return {"success": True, "resolved": False}

    return {"success": False, "message": "Unknown action."}

async def resume_after_captcha_failure(search_id: str, action: str) -> Dict[str, Any]:
    session = sessions.get(search_id)
    if not session:
        return {"success": False, "message": "Session not found."}

    session.resume_action = action
    session.captcha_resume_event.set()
    return {"success": True, "action": action}

async def run_scraper_job(
    search_id: str,
    search_term: str,
    conditions: str,
    gemini_api_key: str,
    max_candidates: int = 30,
    ship_country: str = "AU",
    currency: str = "AUD",
    model_name: str = "gemini-2.5-flash",
    search_terms: Optional[List[str]] = None
):
    session = ScraperSession(search_id)
    sessions[search_id] = session

    try:
        session.status = "running"
        session.stage = "Parsing search terms and generating keyword variations..."
        session.progress_pct = 5
        await session.emit_event("search_started")

        # Compile list of search terms
        all_terms = []
        if search_terms:
            all_terms.extend([t.strip() for t in search_terms if t.strip()])
        if search_term and search_term.strip() and search_term.strip() not in all_terms:
            all_terms.insert(0, search_term.strip())
        if not all_terms:
            all_terms = [search_term.strip() or "Product"]

        # Generate variations for terms if needed
        search_queries = []
        for term in all_terms:
            variations = await ai_evaluator.generate_search_variations(
                search_term=term,
                conditions=conditions,
                api_key=gemini_api_key,
                model_name=model_name
            )
            for v in variations:
                if v not in search_queries:
                    search_queries.append(v)

        if not search_queries:
            search_queries = all_terms

        logger.info(f"Target search queries ({len(search_queries)}): {search_queries}")

        session.stage = "Launching browser..."
        session.progress_pct = 10
        await session.emit_event("browser_launching")

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                    "--window-size=1366,768"
                ]
            )

            context: BrowserContext = await browser.new_context(
                viewport={"width": 1366, "height": 768},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                locale="en-US",
                timezone_id="Australia/Sydney",
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
                    "Sec-Ch-Ua-Mobile": "?0",
                    "Sec-Ch-Ua-Platform": '"Windows"',
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                    "Upgrade-Insecure-Requests": "1"
                }
            )

            # Apply evasions
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.navigator.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            """)

            # Set AliExpress localization cookies
            cookie_domain = ".aliexpress.com"
            await context.add_cookies([
                {"name": "aep_usuc_f", "value": f"site=glo&c_tp={currency}&region={ship_country}&b_locale=en_US", "domain": cookie_domain, "path": "/"},
                {"name": "intl_locale", "value": "en_US", "domain": cookie_domain, "path": "/"},
            ])

            page: Page = await context.new_page()
            await apply_stealth(page)
            session.active_page = page
            session.active_context = context

            # Warmup session on AliExpress homepage to acquire valid tokens
            try:
                logger.info("Initializing session on AliExpress homepage...")
                await page.goto("https://www.aliexpress.com", wait_until="domcontentloaded", timeout=20000)
                await asyncio.sleep(1.5)
            except Exception as e:
                logger.warning(f"Error during homepage warmup: {e}")

            discovered_items: Dict[str, Dict[str, Any]] = {}
            query_index = 0

            while query_index < len(search_queries):
                query = search_queries[query_index]
                if len(discovered_items) >= max_candidates:
                    break

                session.stage = f"Searching AliExpress for: '{query}' ({query_index + 1}/{len(search_queries)})"
                session.progress_pct = 15 + int((query_index / len(search_queries)) * 25)
                await session.emit_event("query_started", {"query": query, "query_index": query_index + 1})

                search_url = f"https://www.aliexpress.com/wholesale?SearchText={urllib.parse.quote_plus(query)}&shipCountry={ship_country}"
                session.current_search_url = search_url

                try:
                    await page.goto(search_url, wait_until="domcontentloaded", timeout=25000)
                    await asyncio.sleep(2.0)
                except Exception as e:
                    logger.warning(f"Timeout loading search url '{search_url}': {e}")

                # Check for verification challenge
                is_punish = "punish" in page.url or (await page.query_selector("#nc_1_n1z, .btn_slide") is not None)
                if is_punish:
                    logger.info("Verification challenge detected! Prompting user to complete verification in tab...")
                    challenge_url = page.url
                    if "punish" not in challenge_url:
                        challenge_url = search_url

                    session.challenge_url = challenge_url
                    session.stage = "AliExpress Verification Required. Please complete the challenge in the opened tab."
                    session.captcha_event.clear()

                    await session.emit_event("captcha_required", {
                        "challenge_url": challenge_url,
                        "message": "AliExpress verification challenge required. Please click to open the challenge on AliExpress."
                    })

                    # Poll and wait up to 300s for user to complete verification
                    solved = False
                    start_wait = time.time()
                    while time.time() - start_wait < 300:
                        if session.captcha_event.is_set():
                            solved = True
                            break
                        if "punish" not in page.url:
                            solved = True
                            session.captcha_event.set()
                            break
                        await asyncio.sleep(1.5)

                    # Check if cleared
                    if solved or "punish" not in page.url:
                        logger.info("Verification successfully cleared!")
                        await session.emit_event("captcha_cleared")
                    else:
                        remaining = search_queries[query_index + 1:]
                        session.remaining_terms = remaining
                        session.captcha_resume_event.clear()

                        logger.warning(f"Verification challenge unresolved. Pausing search. Remaining queries: {remaining}")
                        await session.emit_event("captcha_failed", {
                            "failed_term": query,
                            "remaining_terms": remaining,
                            "message": f"Verification challenge was not completed for '{query}'."
                        })

                        try:
                            await asyncio.wait_for(session.captcha_resume_event.wait(), timeout=300.0)
                        except asyncio.TimeoutError:
                            session.resume_action = "continue_remaining"

                        if session.resume_action == "retry":
                            continue
                        else:
                            query_index += 1
                            continue

                # Scroll down smoothly to trigger lazy loading of product items
                for scroll_step in range(3):
                    await page.evaluate(f"window.scrollBy(0, {500 + scroll_step * 300});")
                    await asyncio.sleep(random.uniform(0.6, 1.2))

                # Extract product links and card information
                cards = await page.query_selector_all("a[href*='/item/']")
                logger.info(f"Found {len(cards)} item anchor tags on page for '{query}'.")

                for card in cards:
                    if len(discovered_items) >= max_candidates:
                        break

                    try:
                        href = await card.get_attribute("href")
                        if not href or "/item/" not in href:
                            continue

                        item_id = href.split("/item/")[-1].split(".html")[0].split("?")[0]
                        if not item_id.isdigit() or item_id in discovered_items:
                            continue

                        clean_url = f"https://www.aliexpress.com/item/{item_id}.html"
                        card_text = (await card.text_content() or "").strip()
                        
                        img_el = await card.query_selector("img")
                        img_src = await img_el.get_attribute("src") if img_el else None
                        if img_src and img_src.startswith("//"):
                            img_src = "https:" + img_src

                        lines = [line.strip() for line in card_text.split("\n") if line.strip()]
                        title_candidate = lines[0] if lines else f"AliExpress Product #{item_id}"
                        price_candidate = "N/A"
                        orig_price_candidate = None
                        
                        for line in lines:
                            if any(sym in line for sym in ["$", "AU", "US", "€", "£", "R$", "¥"]):
                                if price_candidate == "N/A":
                                    price_candidate = line
                                elif orig_price_candidate is None:
                                    orig_price_candidate = line

                        discovered_items[item_id] = {
                            "item_id": item_id,
                            "url": clean_url,
                            "title": title_candidate,
                            "price": price_candidate,
                            "original_price": orig_price_candidate,
                            "image_url": img_src,
                            "card_text": card_text,
                            "specs": []
                        }

                        session.total_candidates = len(discovered_items)
                        await session.emit_event("candidate_discovered", {
                            "item_id": item_id,
                            "total_candidates": len(discovered_items),
                            "title": title_candidate,
                            "price": price_candidate,
                            "image_url": img_src
                        })

                    except Exception as e:
                        continue

                query_index += 1

            session.stage = f"Evaluating {len(discovered_items)} product candidates with Gemini AI..."
            session.progress_pct = 45
            await session.emit_event("evaluation_phase_started", {"total_to_evaluate": len(discovered_items)})

            evaluated_items: List[ItemDetail] = []
            candidate_list = list(discovered_items.values())

            for i, cand in enumerate(candidate_list):
                session.stage = f"Evaluating product {i + 1}/{len(candidate_list)}: {cand['title'][:40]}..."
                session.progress_pct = 45 + int(((i + 1) / max(len(candidate_list), 1)) * 50)

                specs = []
                body_snippet = cand.get("card_text", "")

                try:
                    await page.goto(cand["url"], wait_until="domcontentloaded", timeout=20000)
                    await asyncio.sleep(random.uniform(0.8, 1.5))

                    spec_items = await page.query_selector_all("[class*='specification--item--'], [class*='spec--item--'], [class*='prop-item'], li[class*='spec']")
                    for s in spec_items[:25]:
                        txt = (await s.text_content() or "").strip()
                        if txt and ":" in txt:
                            specs.append(txt)

                    body_text = await page.evaluate("() => document.body.innerText")
                    if body_text:
                        body_snippet = body_text[:4000]

                    title_el = await page.query_selector("h1")
                    if title_el:
                        full_title = (await title_el.text_content() or "").strip()
                        if len(full_title) > len(cand["title"]):
                            cand["title"] = full_title

                except Exception as e:
                    logger.warning(f"Error fetching detail for item {cand['item_id']}: {e}")

                cand["specs"] = specs

                evaluation = await ai_evaluator.evaluate_product_criteria(
                    item_title=cand["title"],
                    item_price=cand["price"],
                    specs=specs,
                    body_snippet=body_snippet,
                    user_conditions=conditions,
                    api_key=gemini_api_key,
                    model_name=model_name
                )

                item_detail = ItemDetail(
                    item_id=cand["item_id"],
                    title=cand["title"],
                    price=cand["price"],
                    original_price=cand["original_price"],
                    url=cand["url"],
                    image_url=cand["image_url"],
                    specs=specs,
                    is_match=evaluation.is_match,
                    verdict_reason=evaluation.verdict_reason,
                    confidence=evaluation.confidence,
                    criteria_breakdown=[c.dict() for c in evaluation.criteria_evaluations]
                )

                evaluated_items.append(item_detail)
                if item_detail.is_match:
                    session.matched_count += 1

                session.evaluated_count = len(evaluated_items)

                await session.emit_event("item_evaluated", {
                    "index": len(evaluated_items),
                    "total": len(candidate_list),
                    "item": item_detail.dict(),
                    "matched_count": session.matched_count
                })

            await context.close()
            await browser.close()

        search_record = {
            "id": search_id,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "search_term": ", ".join(all_terms),
            "conditions": conditions,
            "ship_country": ship_country,
            "currency": currency,
            "total_found": len(discovered_items),
            "total_matched": session.matched_count,
            "status": "completed",
            "items": [item.dict() for item in evaluated_items]
        }

        await database.save_search(search_record)

        session.status = "completed"
        session.stage = f"Search completed! {session.matched_count} matching products verified."
        session.progress_pct = 100
        await session.emit_event("search_completed", search_record)

    except Exception as e:
        logger.error(f"Search failed for session {search_id}: {e}", exc_info=True)
        session.status = "failed"
        session.stage = f"Search failed: {str(e)[:150]}"
        await session.emit_event("search_failed", {"error": str(e)})
