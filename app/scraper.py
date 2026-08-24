import asyncio
import json
import logging
import math
import random
import re
import time
import urllib.parse
from typing import List, Dict, Any, Optional
from camoufox.async_api import AsyncCamoufox
from playwright.async_api import Page, BrowserContext

from app import database
from app import ai_evaluator
from app.models import ItemDetail, ProductEvaluation

logger = logging.getLogger("aliexpress_scraper")

class ScraperSession:
    def __init__(self, search_id: str):
        self.search_id = search_id
        self.status = "pending"  # pending, running, completed, cancelled, error
        self.stage = "Initializing"
        self.progress_pct = 0
        self.total_candidates = 0
        self.evaluated_items: List[Dict[str, Any]] = []
        self.matched_count = 0
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.active_page: Optional[Page] = None
        self.captcha_event = asyncio.Event()
        self.captcha_resume_event = asyncio.Event()
        self.resume_action = "continue_remaining"
        self.is_cancelled = False

    async def emit_event(self, event_type: str, data: Optional[Dict[str, Any]] = None):
        payload = {
            "search_id": self.search_id,
            "type": event_type,
            "stage": self.stage,
            "progress_pct": self.progress_pct,
            "data": data or {}
        }
        await self.event_queue.put(payload)

    async def cancel(self):
        self.is_cancelled = True
        self.status = "cancelled"
        self.stage = "Search stopped by user"
        self.captcha_resume_event.set()
        await self.emit_event("search_cancelled", {"message": "Search was stopped by user."})

sessions: Dict[str, ScraperSession] = {}

async def natural_mouse_move_and_drag(page: Page, start_x: float, start_y: float, end_x: float, end_y: float):
    """
    Simulates human-like mouse movement with acceleration, deceleration, and micro-jitter.
    """
    await page.mouse.move(start_x, start_y)
    await asyncio.sleep(random.uniform(0.05, 0.15))
    await page.mouse.down()
    await asyncio.sleep(random.uniform(0.05, 0.1))

    steps = random.randint(28, 42)
    for i in range(1, steps + 1):
        t = i / steps
        # Sinusoidal ease-in-out curve
        ease = 0.5 * (1 - math.cos(t * math.pi))
        curr_x = start_x + (end_x - start_x) * ease + random.uniform(-1.2, 1.2)
        curr_y = start_y + (end_y - start_y) * ease + random.uniform(-1.5, 1.5)
        await page.mouse.move(curr_x, curr_y)
        speed_delay = 0.008 + (1 - math.sin(t * math.pi)) * 0.012
        await asyncio.sleep(speed_delay)

    await page.mouse.move(end_x, end_y)
    await asyncio.sleep(random.uniform(0.1, 0.25))
    await page.mouse.up()
    await asyncio.sleep(0.5)

async def attempt_automated_slider_solve(page: Page) -> bool:
    """
    Attempts to automatically find and slide the verification puzzle on AliExpress.
    Returns True if successfully solved/cleared, False otherwise.
    """
    try:
        if "punish" not in page.url:
            return True

        logger.info("Attempting automated slider challenge solve...")
        await asyncio.sleep(1.0)

        slider_selectors = [
            "#nc_1_n1z",
            ".nc_iconfont.btn_slide",
            ".btn_slide",
            "#nc_1_wrapper .btn_slide",
            ".nc_scale span[id*='n1z']",
            "span[id*='nc_1_n1z']"
        ]

        slider_el = None
        for _ in range(12):
            for sel in slider_selectors:
                el = await page.query_selector(sel)
                if el and await el.is_visible():
                    slider_el = el
                    break
            if slider_el:
                break
            for frame in page.frames:
                for sel in slider_selectors:
                    el = await frame.query_selector(sel)
                    if el and await el.is_visible():
                        slider_el = el
                        break
                if slider_el:
                    break
            await asyncio.sleep(0.4)

        if not slider_el:
            logger.info("No visible slider button found for automated solve.")
            return False

        box = await slider_el.bounding_box()
        if not box:
            return False

        wrapper = await page.query_selector("#nc_1_wrapper, #nocaptcha")
        wrapper_box = await wrapper.bounding_box() if wrapper else None
        track_width = (wrapper_box["width"] - box["width"]) if wrapper_box else 260.0

        start_x = box["x"] + box["width"] / 2
        start_y = box["y"] + box["height"] / 2
        end_x = start_x + max(250.0, track_width)
        end_y = start_y

        logger.info(f"Sliding from ({start_x:.1f}, {start_y:.1f}) to ({end_x:.1f}, {end_y:.1f})...")
        await natural_mouse_move_and_drag(page, start_x, start_y, end_x, end_y)
        await asyncio.sleep(2.5)

        if "punish" not in page.url:
            logger.info("Slider challenge successfully solved!")
            return True

        return False
    except Exception as e:
        logger.warning(f"Error during slider solve: {e}")
        return False

async def run_scraper_job(
    search_id: str,
    search_term: str,
    conditions: str,
    gemini_api_key: str,
    max_candidates: int = 30,
    ship_country: str = "AU",
    currency: str = "AUD",
    model_name: str = "gemini-3.5-flash",
    search_terms: Optional[List[str]] = None
):
    session = ScraperSession(search_id)
    sessions[search_id] = session

    try:
        # Create search in DB
        await database.create_search(
            search_id=search_id,
            search_term=search_term,
            conditions=conditions,
            currency=currency,
            ship_country=ship_country
        )

        session.status = "running"
        session.stage = "Generating intelligent search queries with Gemini AI..."
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

        # Generate intelligent variations
        search_queries = []
        for term in all_terms:
            if session.is_cancelled:
                return
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

        if session.is_cancelled:
            return

        session.stage = "Launching Camoufox stealth browser engine..."
        session.progress_pct = 10
        await session.emit_event("progress_update", {"message": session.stage})

        discovered_candidates: Dict[str, Dict[str, Any]] = {}

        # Launch Camoufox Stealth Firefox Browser
        async with AsyncCamoufox(
            headless=True,
            geoip=True,
            humanize=True,
            os="windows"
        ) as browser:
            page = await browser.new_page()
            session.active_page = page

            # Set localization cookie
            try:
                await page.context.add_cookies([
                    {
                        "name": "aep_usuc_f",
                        "value": f"site=glo&province=&city=&c_tp={currency}&region={ship_country}&b_locale=en_US&ae_u_p_s=2",
                        "domain": ".aliexpress.com",
                        "path": "/"
                    }
                ])
            except Exception as e:
                logger.warning(f"Could not set preliminary cookies: {e}")

            for q_idx, query in enumerate(search_queries):
                if len(discovered_candidates) >= max_candidates or session.is_cancelled:
                    break

                session.stage = f"Searching AliExpress for '{query}' (Camoufox Stealth)..."
                session.progress_pct = 12 + int((q_idx / len(search_queries)) * 30)
                await session.emit_event("query_started", {"query": query, "query_index": q_idx + 1})

                slug = re.sub(r'[^a-z0-9]+', '-', query.lower()).strip('-')
                encoded_query = urllib.parse.quote_plus(query)
                search_url = f"https://www.aliexpress.com/w/wholesale-{slug}.html?SearchText={encoded_query}"

                try:
                    await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(random.uniform(1.0, 1.8))

                    # Check if CAPTCHA challenge appeared
                    if "punish" in page.url:
                        logger.info(f"Verification challenge detected on '{query}'.")
                        session.stage = "AliExpress challenge detected. Solving automatically..."
                        await session.emit_event("captcha_detected", {"url": page.url, "query": query})

                        solved = await attempt_automated_slider_solve(page)
                        if not solved:
                            session.stage = "Awaiting manual verification slider in modal..."
                            await session.emit_event("captcha_required", {"url": page.url})
                            try:
                                await asyncio.wait_for(session.captcha_resume_event.wait(), timeout=90.0)
                            except asyncio.TimeoutError:
                                logger.warning("Verification modal timed out, skipping to next query.")
                            session.captcha_resume_event.clear()

                    # Scroll down to trigger lazy loading of products
                    for _ in range(3):
                        if session.is_cancelled:
                            break
                        await page.evaluate("window.scrollBy(0, 1000);")
                        await asyncio.sleep(0.4)

                    # Extract products directly from DOM
                    extracted = await page.evaluate('''() => {
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

                    for item in extracted:
                        cid = item["item_id"]
                        if cid not in discovered_candidates:
                            discovered_candidates[cid] = item
                            await session.emit_event("candidate_discovered", item)
                            if len(discovered_candidates) >= max_candidates:
                                break

                except Exception as e:
                    logger.warning(f"Error scraping '{query}': {e}")
                    continue

        if session.is_cancelled:
            logger.info(f"Search {search_id} cancelled.")
            return

        candidate_list = list(discovered_candidates.values())[:max_candidates]
        if not candidate_list:
            session.stage = "No products found for this search. Try a broader search keyword."
            await session.emit_event("progress_update", {"message": session.stage})
        else:
            session.stage = f"Discovered {len(candidate_list)} products. Running parallel AI evaluation with {model_name}..."
            session.progress_pct = 45
            await session.emit_event("evaluation_phase_started", {"total_candidates": len(candidate_list)})

            sem = asyncio.Semaphore(10)  # Evaluate up to 10 products concurrently

            async def evaluate_single_candidate(cand: Dict[str, Any], idx: int):
                if session.is_cancelled:
                    return None

                async with sem:
                    if session.is_cancelled:
                        return None

                    item_id = cand["item_id"]
                    detailed_cand = dict(cand)
                    detailed_cand.setdefault("specs", [])

                    try:
                        evaluation: ProductEvaluation = await ai_evaluator.evaluate_product(
                            item=detailed_cand,
                            conditions=conditions,
                            api_key=gemini_api_key,
                            model_name=model_name
                        )
                        detailed_cand["is_match"] = evaluation.is_match
                        detailed_cand["confidence"] = evaluation.confidence
                        detailed_cand["verdict_reason"] = evaluation.verdict_reason
                        detailed_cand["criteria_breakdown"] = [c.model_dump() for c in evaluation.criteria_evaluations]
                    except Exception as e:
                        logger.warning(f"Evaluation note for item {item_id}: {e}")
                        detailed_cand["is_match"] = False
                        detailed_cand["confidence"] = 0.0
                        detailed_cand["verdict_reason"] = f"Evaluation note: {str(e)[:80]}"
                        detailed_cand["criteria_breakdown"] = []

                    if session.is_cancelled:
                        return None

                    await database.save_search_result(search_id, detailed_cand)
                    session.evaluated_items.append(detailed_cand)

                    completed_count = len(session.evaluated_items)
                    session.progress_pct = min(95, 45 + int((completed_count / max(1, len(candidate_list))) * 50))
                    session.stage = f"Evaluated {completed_count}/{len(candidate_list)} products with {model_name}..."
                    await session.emit_event("item_evaluated", detailed_cand)
                    return detailed_cand

            await asyncio.gather(*(evaluate_single_candidate(c, i) for i, c in enumerate(candidate_list)), return_exceptions=True)

        if session.is_cancelled:
            return

        session.status = "completed"
        match_count = sum(1 for item in session.evaluated_items if item.get("is_match"))
        await database.update_search_status(
            search_id=search_id,
            status="completed",
            total_found=len(session.evaluated_items),
            total_matched=match_count
        )

        session.stage = f"Search & AI evaluation completed! ({match_count} matches / {len(session.evaluated_items)} evaluated)"
        session.progress_pct = 100
        await session.emit_event("search_completed", {
            "total_evaluated": len(session.evaluated_items),
            "matches_found": match_count
        })

    except Exception as e:
        logger.error(f"Scraping job failed for {search_id}: {e}", exc_info=True)
        session.status = "error"
        session.stage = f"Error: {str(e)[:150]}"
        await session.emit_event("search_error", {"error": str(e)})
