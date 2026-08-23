import asyncio
import base64
import json
import logging
import os
import re
import urllib.parse
from typing import Dict, List, Optional, Any, Callable
from playwright.async_api import async_playwright, Page, BrowserContext, Browser
from playwright_stealth import Stealth

from app import database
from app import ai_evaluator
from app.models import ProductEvaluation, CriteriaEvaluation

logger = logging.getLogger(__name__)

# Active scraping sessions
sessions: Dict[str, "ScraperSession"] = {}

class ScraperSession:
    def __init__(self, search_id: str):
        self.search_id = search_id
        self.status = "initializing"
        self.stage = "Starting..."
        self.progress_pct = 0
        self.is_captcha_active = False
        self.captcha_screenshot_b64: Optional[str] = None
        self.page: Optional[Page] = None
        self.context: Optional[BrowserContext] = None
        self.browser: Optional[Browser] = None
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.captcha_resolved_event = asyncio.Event()
        self.is_cancelled = False
        self.evaluated_items: List[Dict[str, Any]] = []

    async def emit_event(self, event_type: str, data: Dict[str, Any]):
        payload = {
            "type": event_type,
            "search_id": self.search_id,
            "status": self.status,
            "stage": self.stage,
            "progress_pct": self.progress_pct,
            "data": data
        }
        await self.event_queue.put(payload)

def check_captcha_needed(page_text: str, current_url: str) -> bool:
    blocked_keywords = [
        "_____tmd_____/punish",
        "sec-captcha",
        "baxia-dialog",
        "captcha verification",
        "please slide to verify",
        "please drag the slider",
    ]
    current_url_lower = current_url.lower()
    page_text_lower = page_text.lower()
    return any(kw in current_url_lower or kw in page_text_lower for kw in blocked_keywords)

async def capture_page_screenshot_b64(page: Page) -> str:
    try:
        screenshot_bytes = await page.screenshot(type="jpeg", quality=75)
        return base64.b64encode(screenshot_bytes).decode("utf-8")
    except Exception as e:
        logger.error(f"Error capturing screenshot: {e}")
        return ""

async def run_scraper_job(
    search_id: str,
    search_term: str,
    conditions: str,
    gemini_api_key: str,
    max_candidates: int = 30,
    ship_country: str = "AU",
    currency: str = "AUD",
    model_name: str = "gemini-2.5-flash"
):
    session = ScraperSession(search_id)
    sessions[search_id] = session
    
    await database.create_search(search_id, search_term, conditions, currency, ship_country)
    
    stealth = Stealth()
    session.status = "running"
    session.stage = "Initializing browser session..."
    session.progress_pct = 5
    await session.emit_event("status_update", {"message": "Starting Playwright browser..."})

    try:
        async with async_playwright() as p:
            session.browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-infobars',
                    '--disable-dev-shm-usage',
                    '--window-size=1920,1080',
                ]
            )
            
            session.context = await session.browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                }
            )
            
            # Add localization cookies
            await session.context.add_cookies([
                {"name": "aep_usuc_f", "value": f"site=glo&c_tp={currency}&region={ship_country}&b_locale=en_US", "domain": ".aliexpress.com", "path": "/"},
                {"name": "intl_locale", "value": "en_US", "domain": ".aliexpress.com", "path": "/"},
                {"name": "xman_us_f", "value": f"x_locale=en_US&x_c_chrg={currency}&x_chrg_r={currency}", "domain": ".aliexpress.com", "path": "/"},
            ])
            
            session.page = await session.context.new_page()
            await stealth.apply_stealth_async(session.page)

            # Step 1: Generate Search Query Variations using Gemini
            session.stage = "Generating optimized search queries with Gemini AI..."
            session.progress_pct = 10
            await session.emit_event("status_update", {"message": "Asking Gemini for search keyword variations..."})
            
            search_queries = await ai_evaluator.generate_search_variations(search_term, conditions, gemini_api_key, model_name)
            if search_term not in search_queries:
                search_queries.insert(0, search_term)
                
            await session.emit_event("search_queries_ready", {"queries": search_queries})

            # Step 2: Multi-Query Search Crawl
            collected_candidates: Dict[str, Dict[str, Any]] = {}
            
            for q_idx, query in enumerate(search_queries):
                if session.is_cancelled or len(collected_candidates) >= max_candidates:
                    break
                    
                session.stage = f"Searching AliExpress for: '{query}'"
                session.progress_pct = 15 + int((q_idx / len(search_queries)) * 25)
                await session.emit_event("search_query_progress", {"query": query, "index": q_idx + 1, "total": len(search_queries)})
                
                encoded = urllib.parse.quote_plus(query)
                search_url = f"https://www.aliexpress.com/wholesale?SearchText={encoded}&shipCountry={ship_country}"
                
                try:
                    await session.page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
                    await session.page.wait_for_timeout(2000)
                    
                    # Check for CAPTCHA
                    page_content = await session.page.content()
                    if check_captcha_needed(page_content, session.page.url):
                        session.is_captcha_active = True
                        session.captcha_screenshot_b64 = await capture_page_screenshot_b64(session.page)
                        session.captcha_resolved_event.clear()
                        
                        await session.emit_event("captcha_required", {
                            "message": "AliExpress verification challenge detected! Please solve it in the modal.",
                            "screenshot": session.captcha_screenshot_b64,
                            "url": session.page.url
                        })
                        
                        # Wait for user resolution or timeout
                        try:
                            await asyncio.wait_for(session.captcha_resolved_event.wait(), timeout=120)
                        except asyncio.TimeoutError:
                            logger.warning(f"Search {search_id} CAPTCHA timeout.")
                            
                        session.is_captcha_active = False
                        session.captcha_screenshot_b64 = None
                        await session.emit_event("captcha_cleared", {"message": "Verification cleared. Resuming..."})
                        await session.page.wait_for_timeout(2000)
                        
                    # Scroll down to load product cards
                    for _ in range(5):
                        await session.page.evaluate("window.scrollBy(0, 900)")
                        await session.page.wait_for_timeout(800)
                        
                    item_links = await session.page.locator("a[href*='/item/']").all()
                    
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
                        lines = [l.strip() for l in card_text.split("\n") if l.strip()]
                        title = lines[0] if lines else "AliExpress Product"
                        
                        # Extract price
                        price = "N/A"
                        orig_price = None
                        for l in lines:
                            if currency in l or "$" in l:
                                if price == "N/A":
                                    price = l
                                elif orig_price is None:
                                    orig_price = l
                                    
                        # Extract image if available
                        img_elem = link.locator("img").first
                        img_src = await img_elem.get_attribute("src") if await img_elem.count() > 0 else None
                        
                        # Clean canonical URL
                        canonical_url = f"https://www.aliexpress.com/item/{item_id}.html"
                        
                        candidate = {
                            "item_id": item_id,
                            "title": title,
                            "price": price,
                            "original_price": orig_price,
                            "image_url": img_src,
                            "url": canonical_url,
                            "card_text": " | ".join(lines),
                            "specs": [],
                            "body_snippet": "",
                        }
                        collected_candidates[item_id] = candidate
                        
                        await session.emit_event("candidate_discovered", {
                            "total_candidates": len(collected_candidates),
                            "candidate": candidate
                        })
                        
                        if len(collected_candidates) >= max_candidates:
                            break
                            
                except Exception as e:
                    logger.error(f"Error scraping search query '{query}': {e}")
                    await session.emit_event("log", {"level": "warn", "message": f"Search error for '{query}': {str(e)}"})

            total_discovered = len(collected_candidates)
            session.stage = f"Discovered {total_discovered} candidates. Starting Gemini AI deep evaluation..."
            session.progress_pct = 40
            await session.emit_event("status_update", {"message": f"Starting deep AI evaluation for {total_discovered} products..."})

            # Step 3: Deep Inspection & Gemini AI Criteria Evaluation
            matched_count = 0
            candidate_list = list(collected_candidates.values())
            
            for idx, item in enumerate(candidate_list, 1):
                if session.is_cancelled:
                    break
                    
                session.stage = f"Evaluating product {idx}/{total_discovered}: {item['title'][:45]}..."
                session.progress_pct = 40 + int((idx / max(1, total_discovered)) * 55)
                
                # Fetch product detail page
                specs = []
                body_text = item["card_text"]
                try:
                    await session.page.goto(item["url"], wait_until="domcontentloaded", timeout=25000)
                    await session.page.wait_for_timeout(1000)
                    await session.page.evaluate("window.scrollBy(0, 1000)")
                    await session.page.wait_for_timeout(1000)
                    
                    # Full title if present
                    title_elem = await session.page.locator("h1").first.inner_text() if await session.page.locator("h1").count() > 0 else ""
                    if title_elem and len(title_elem.strip()) > 5:
                        item["title"] = title_elem.strip()
                        
                    # Spec table items
                    spec_elems = await session.page.locator("[class*='specification--prop'], [class*='specification-item'], [class*='property-item'], [class*='pdp-info-item']").all()
                    for se in spec_elems:
                        txt = await se.inner_text()
                        if txt.strip():
                            specs.append(txt.strip().replace('\n', ': '))
                    item["specs"] = specs
                    
                    # Body text
                    body_elem = await session.page.locator("body").inner_text()
                    body_text = f"{item['card_text']} {body_elem[:4000]}"
                    item["body_snippet"] = body_text[:2000]
                    
                except Exception as e:
                    logger.warning(f"Error fetching detail for item {item['item_id']}: {e}")

                # Call Gemini for strict conditions evaluation
                evaluation: ProductEvaluation = await ai_evaluator.evaluate_product_criteria(
                    item_title=item["title"],
                    item_price=item["price"],
                    specs=item["specs"],
                    body_snippet=body_text,
                    user_conditions=conditions,
                    api_key=gemini_api_key,
                    model_name=model_name
                )
                
                item["is_match"] = evaluation.is_match
                item["verdict_reason"] = evaluation.verdict_reason
                item["criteria_breakdown"] = [c.model_dump() for c in evaluation.criteria_evaluations]
                
                if item["is_match"]:
                    matched_count += 1
                    
                session.evaluated_items.append(item)
                
                # Emit real-time item evaluation event
                await session.emit_event("item_evaluated", {
                    "index": idx,
                    "total": total_discovered,
                    "item": item,
                    "matched_count": matched_count
                })

            # Step 4: Save all items and complete
            session.stage = "Saving results to database..."
            session.progress_pct = 98
            await database.save_items(search_id, session.evaluated_items)
            await database.update_search_status(search_id, "completed", total_found=total_discovered, total_matched=matched_count)

            session.status = "completed"
            session.stage = f"Search completed! Found {matched_count} matching products out of {total_discovered} candidates."
            session.progress_pct = 100
            
            await session.emit_event("search_completed", {
                "total_found": total_discovered,
                "total_matched": matched_count,
                "items": session.evaluated_items
            })

    except Exception as e:
        logger.error(f"Search {search_id} failed with error: {e}", exc_info=True)
        session.status = "failed"
        session.stage = f"Failed: {str(e)}"
        await database.update_search_status(search_id, "failed")
        await session.emit_event("search_failed", {"error": str(e)})

    finally:
        if session.context:
            try:
                await session.context.close()
            except Exception:
                pass
        if session.browser:
            try:
                await session.browser.close()
            except Exception:
                pass

async def handle_captcha_interaction(search_id: str, action: str, start_x: Optional[float] = None, start_y: Optional[float] = None, end_x: Optional[float] = None, end_y: Optional[float] = None) -> Dict[str, Any]:
    session = sessions.get(search_id)
    if not session or not session.page:
        return {"success": False, "message": "No active session or browser page found."}

    page = session.page
    try:
        if action == "drag" and start_x is not None and start_y is not None and end_x is not None and end_y is not None:
            await page.mouse.move(start_x, start_y)
            await page.mouse.down()
            
            steps = 25
            for i in range(1, steps + 1):
                cur_x = start_x + (end_x - start_x) * (i / steps)
                cur_y = start_y + (end_y - start_y) * (i / steps)
                await page.mouse.move(cur_x, cur_y)
                await asyncio.sleep(0.015)
                
            await page.mouse.up()
            await page.wait_for_timeout(2000)
            
        elif action == "click" and start_x is not None and start_y is not None:
            await page.mouse.click(start_x, start_y)
            await page.wait_for_timeout(1500)
            
        elif action == "resolve":
            session.captcha_resolved_event.set()
            return {"success": True, "resolved": True, "message": "Resuming scraper..."}

        # Check if CAPTCHA cleared
        content = await page.content()
        url = page.url
        is_still_blocked = check_captcha_needed(content, url)
        
        fresh_screenshot = await capture_page_screenshot_b64(page)
        session.captcha_screenshot_b64 = fresh_screenshot

        if not is_still_blocked:
            session.is_captcha_active = False
            session.captcha_resolved_event.set()
            return {
                "success": True,
                "resolved": True,
                "screenshot": fresh_screenshot,
                "message": "Challenge solved successfully! Resuming..."
            }
        else:
            return {
                "success": True,
                "resolved": False,
                "screenshot": fresh_screenshot,
                "message": "Challenge still active. Please try dragging further."
            }

    except Exception as e:
        logger.error(f"Error handling captcha interaction: {e}")
        return {"success": False, "message": str(e)}
