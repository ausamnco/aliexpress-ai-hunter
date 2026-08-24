import asyncio
import json
import logging
import os
import re
import urllib.parse
from typing import List, Dict, Any, Optional, AsyncGenerator, Tuple
import httpx

from app import database
from app import ai_evaluator
from app.models import ItemDetail, ProductEvaluation

logger = logging.getLogger(__name__)

class ScraperSession:
    def __init__(self, search_id: str):
        self.search_id = search_id
        self.status = "pending"  # pending, running, completed, error, stopped
        self.stage = "Initializing"
        self.progress_pct = 0
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.discovered_items: Dict[str, Dict[str, Any]] = {}
        self.evaluated_items: List[Dict[str, Any]] = []
        self.error_message: Optional[str] = None

    async def emit_event(self, event_type: str, data: Optional[Dict[str, Any]] = None):
        payload = {
            "search_id": self.search_id,
            "type": event_type,
            "stage": self.stage,
            "progress_pct": self.progress_pct,
            "data": data or {}
        }
        await self.event_queue.put(payload)

sessions: Dict[str, ScraperSession] = {}

class GatewayScraperClient:
    @staticmethod
    def build_gateway_url(
        target_url: str,
        provider: str,
        api_key: str,
        ship_country: str = "AU",
        custom_gateway_url: Optional[str] = None
    ) -> str:
        clean_key = (api_key or "").strip()
        encoded_target = urllib.parse.quote(target_url, safe="")
        country = (ship_country or "AU").lower()

        if provider == "zenrows":
            return (
                f"https://api.zenrows.com/v1/?apikey={clean_key}&url={encoded_target}"
                f"&js_render=true&antibot=true&premium_proxy=true&proxy_country={country}&wait=2000"
            )
        elif provider == "scrapfly":
            return (
                f"https://api.scrapfly.io/scrape?key={clean_key}&url={encoded_target}"
                f"&render_js=true&asp=true&country={country}&wait_for_selector=body"
            )
        elif provider == "scraperapi":
            return (
                f"https://api.scraperapi.com/?api_key={clean_key}&url={encoded_target}"
                f"&render=true&country_code={country}&premium=true"
            )
        elif provider == "custom" and custom_gateway_url:
            custom = custom_gateway_url.strip()
            if "{url}" in custom:
                return custom.replace("{url}", encoded_target)
            sep = "&" if "?" in custom else "?"
            return f"{custom}{sep}url={encoded_target}"
        else:
            return target_url

    @classmethod
    async def fetch_page(
        cls,
        target_url: str,
        provider: str,
        api_key: str,
        ship_country: str = "AU",
        currency: str = "AUD",
        custom_gateway_url: Optional[str] = None,
        timeout: float = 45.0
    ) -> Tuple[int, str]:
        gateway_url = cls.build_gateway_url(
            target_url=target_url,
            provider=provider,
            api_key=api_key,
            ship_country=ship_country,
            custom_gateway_url=custom_gateway_url
        )

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            try:
                resp = await client.get(gateway_url, headers=headers)
                return resp.status_code, resp.text
            except Exception as e:
                logger.warning(f"Gateway fetch error for {target_url}: {e}")
                return 500, str(e)

    @classmethod
    async def validate_gateway(
        cls,
        provider: str,
        api_key: str,
        custom_gateway_url: Optional[str] = None
    ) -> Dict[str, Any]:
        clean_key = (api_key or "").strip()
        if provider != "custom" and not clean_key:
            return {
                "valid": False,
                "message": f"API key for {provider.capitalize()} is required."
            }

        test_target = "https://www.aliexpress.com"
        status, content = await cls.fetch_page(
            target_url=test_target,
            provider=provider,
            api_key=clean_key,
            custom_gateway_url=custom_gateway_url,
            timeout=25.0
        )

        if status == 200 and len(content) > 1000:
            return {
                "valid": True,
                "provider": provider,
                "message": f"Successfully connected to {provider.capitalize()} scraping gateway!"
            }
        else:
            snippet = content[:200] if content else "Empty response"
            return {
                "valid": False,
                "provider": provider,
                "message": f"Gateway check failed (Status {status}): {snippet}"
            }

def parse_search_results(html_text: str) -> List[Dict[str, Any]]:
    """
    Extracts product candidates from search HTML, embedded runParams, or JSON scripts.
    """
    items: Dict[str, Dict[str, Any]] = {}

    # 1. Search for embedded window._init_data_ or window.runParams
    json_matches = re.findall(r'window\.runParams\s*=\s*(\{.*?\});', html_text, re.DOTALL)
    if not json_matches:
        json_matches = re.findall(r'window\._init_data_\s*=\s*(\{.*?\});', html_text, re.DOTALL)

    for jm in json_matches:
        try:
            data = json.loads(jm)
            # Traverse common AliExpress JSON response structures
            root = data.get("data", {}).get("root", {}) or data.get("mods", {})
            item_list = (
                root.get("itemList", {}).get("content", []) or
                data.get("items", []) or
                []
            )
            for raw_item in item_list:
                item_id = str(raw_item.get("productId") or raw_item.get("itemId") or "")
                if not item_id or item_id in items:
                    continue

                title = raw_item.get("title", {}).get("displayTitle") or raw_item.get("title") or ""
                price = raw_item.get("prices", {}).get("salePrice", {}).get("formattedPrice") or raw_item.get("price") or "N/A"
                orig_price = raw_item.get("prices", {}).get("originalPrice", {}).get("formattedPrice")
                img = raw_item.get("image", {}).get("imgUrl") or raw_item.get("imageUrl") or ""
                if img.startswith("//"):
                    img = f"https:{img}"

                if len(title) > 3:
                    items[item_id] = {
                        "item_id": item_id,
                        "title": title,
                        "price": price,
                        "original_price": orig_price,
                        "url": f"https://www.aliexpress.com/item/{item_id}.html",
                        "image_url": img,
                        "specs": []
                    }
        except Exception:
            pass

    # 2. HTML Anchor/DOM Fallback Extraction
    if len(items) < 5:
        # Find item links with regex
        link_matches = re.findall(r'href=[\"\']([^\"\']*aliexpress\.com/item/(\d+)\.html[^\"\']*)[\"\']', html_text)
        for full_url, item_id in link_matches:
            if item_id not in items:
                # Find title nearby if possible
                clean_url = f"https://www.aliexpress.com/item/{item_id}.html"
                items[item_id] = {
                    "item_id": item_id,
                    "title": f"AliExpress Product #{item_id}",
                    "price": "N/A",
                    "original_price": None,
                    "url": clean_url,
                    "image_url": None,
                    "specs": []
                }

    return list(items.values())

def parse_item_detail(html_text: str, item_id: str) -> Dict[str, Any]:
    """
    Extracts precise title, pricing, images, and technical specifications from an item page.
    """
    title = f"AliExpress Product #{item_id}"
    price = "N/A"
    orig_price = None
    image_url = None
    specs = []

    # 1. Parse JSON properties inside HTML
    data_match = re.search(r'window\.runParams\s*=\s*(\{.*?\});\s*</script>', html_text, re.DOTALL)
    if data_match:
        try:
            data = json.loads(data_match.group(1))
            root = data.get("data", {}) or data

            # Title
            title_module = root.get("titleModule", {}) or root.get("productInfoComponent", {})
            extracted_title = title_module.get("subject") or title_module.get("title")
            if extracted_title:
                title = extracted_title

            # Price
            price_module = root.get("priceModule", {}) or root.get("priceComponent", {})
            extracted_price = (
                price_module.get("formatedActivityPrice") or
                price_module.get("formatedPrice") or
                price_module.get("formattedPrice")
            )
            if extracted_price:
                price = extracted_price

            # Specs
            prop_module = root.get("specsModule", {}) or root.get("productPropComponent", {})
            props_list = prop_module.get("props", [])
            for prop in props_list:
                name = prop.get("attrName")
                val = prop.get("attrValue")
                if name and val:
                    specs.append(f"{name}: {val}")

            # Images
            image_module = root.get("imageModule", {}) or root.get("imageComponent", {})
            img_list = image_module.get("imagePathList", [])
            if img_list:
                image_url = img_list[0]
                if image_url.startswith("//"):
                    image_url = f"https:{image_url}"
        except Exception:
            pass

    # 2. HTML Fallback Extraction if JSON parsing was partial
    if not specs:
        spec_items = re.findall(
            r'<(?:li|div|span)[^>]*class=[\"\'][^\"\']*(?:specification--item|prop-item|spec--item)[^\"\']*[\"\'][^>]*>(.*?)</(?:li|div|span)>',
            html_text,
            re.DOTALL | re.IGNORECASE
        )
        for s in spec_items:
            clean_s = re.sub(r'<[^>]+>', ' ', s).strip()
            clean_s = re.sub(r'\s+', ' ', clean_s)
            if len(clean_s) > 3 and clean_s not in specs:
                specs.append(clean_s)

    if title == f"AliExpress Product #{item_id}":
        title_h1 = re.search(r'<h1[^>]*>(.*?)</h1>', html_text, re.DOTALL | re.IGNORECASE)
        if title_h1:
            clean_h1 = re.sub(r'<[^>]+>', '', title_h1.group(1)).strip()
            if clean_h1:
                title = clean_h1

    if price == "N/A":
        price_match = re.search(r'([A-Z]{0,3}\s*\$\s*[\d\.,]+)', html_text)
        if price_match:
            price = price_match.group(1)

    return {
        "item_id": item_id,
        "title": title,
        "price": price,
        "original_price": orig_price,
        "url": f"https://www.aliexpress.com/item/{item_id}.html",
        "image_url": image_url,
        "specs": specs
    }

async def run_scraper_job(
    search_id: str,
    search_term: str,
    conditions: str,
    gemini_api_key: str,
    scraping_provider: str = "zenrows",
    scraping_api_key: str = "",
    custom_gateway_url: str = "",
    max_candidates: int = 30,
    ship_country: str = "AU",
    currency: str = "AUD",
    model_name: str = "gemini-3.7-flash",
    search_terms: Optional[List[str]] = None
):
    session = ScraperSession(search_id)
    sessions[search_id] = session

    try:
        session.status = "running"
        session.stage = "Generating intelligent search variations with Gemini AI..."
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

        logger.info(f"Target queries ({len(search_queries)}): {search_queries}")
        discovered_candidates: Dict[str, Dict[str, Any]] = {}

        # 1. Fetch search pages via Gateway
        for q_idx, query in enumerate(search_queries):
            if len(discovered_candidates) >= max_candidates:
                break

            session.stage = f"Searching AliExpress for '{query}' via {scraping_provider.capitalize()} Gateway..."
            session.progress_pct = 10 + int((q_idx / len(search_queries)) * 30)
            await session.emit_event("query_started", {"query": query, "query_index": q_idx + 1})

            slug = re.sub(r'[^a-z0-9]+', '-', query.lower()).strip('-')
            search_url = f"https://www.aliexpress.com/w/wholesale-{slug}.html"

            status, html = await GatewayScraperClient.fetch_page(
                target_url=search_url,
                provider=scraping_provider,
                api_key=scraping_api_key,
                ship_country=ship_country,
                currency=currency,
                custom_gateway_url=custom_gateway_url
            )

            if status == 200:
                candidates = parse_search_results(html)
                for cand in candidates:
                    cid = cand["item_id"]
                    if cid not in discovered_candidates:
                        discovered_candidates[cid] = cand
                        await session.emit_event("candidate_discovered", cand)
                        if len(discovered_candidates) >= max_candidates:
                            break
            else:
                logger.warning(f"Gateway returned status {status} for query '{query}'")

        if not discovered_candidates:
            session.stage = "No candidates found. Trying broad query fallback..."
            await session.emit_event("progress_update", {"message": "No candidates found on initial queries. Trying direct fallback..."})

        # 2. Evaluate candidate products with Gemini AI
        candidate_list = list(discovered_candidates.values())[:max_candidates]
        session.stage = f"Found {len(candidate_list)} candidate products. Evaluating specifications with {model_name}..."
        session.progress_pct = 45
        await session.emit_event("evaluation_phase_started", {"total_candidates": len(candidate_list)})

        for idx, cand in enumerate(candidate_list):
            item_id = cand["item_id"]
            session.stage = f"Evaluating product {idx + 1}/{len(candidate_list)}: '{cand['title'][:45]}...'"
            session.progress_pct = 45 + int((idx / max(1, len(candidate_list))) * 50)
            await session.emit_event("item_evaluating", {"item_id": item_id, "title": cand["title"]})

            # Fetch deep item details and specifications via Gateway
            item_url = f"https://www.aliexpress.com/item/{item_id}.html"
            item_status, item_html = await GatewayScraperClient.fetch_page(
                target_url=item_url,
                provider=scraping_provider,
                api_key=scraping_api_key,
                ship_country=ship_country,
                currency=currency,
                custom_gateway_url=custom_gateway_url
            )

            if item_status == 200:
                detailed_cand = parse_item_detail(item_html, item_id)
                # Keep original price/image if detailed page was missing them
                if cand.get("price") != "N/A" and detailed_cand.get("price") == "N/A":
                    detailed_cand["price"] = cand["price"]
                if not detailed_cand.get("image_url") and cand.get("image_url"):
                    detailed_cand["image_url"] = cand["image_url"]
            else:
                detailed_cand = cand

            # Evaluate against user conditions using Gemini
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

            # Save in database
            await database.save_search_result(search_id, detailed_cand)
            session.evaluated_items.append(detailed_cand)

            await session.emit_event("item_evaluated", detailed_cand)

        session.status = "completed"
        session.stage = "Search and AI evaluation completed successfully!"
        session.progress_pct = 100
        match_count = sum(1 for item in session.evaluated_items if item.get("is_match"))
        await session.emit_event("search_completed", {
            "total_evaluated": len(session.evaluated_items),
            "matches_found": match_count
        })

    except Exception as e:
        logger.error(f"Error during scraping job {search_id}: {e}", exc_info=True)
        session.status = "error"
        session.error_message = str(e)
        session.stage = f"Error: {str(e)}"
        await session.emit_event("search_error", {"error": str(e)})

    finally:
        await session.emit_event("stream_end")

async def get_session_events(search_id: str) -> AsyncGenerator[str, None]:
    session = sessions.get(search_id)
    if not session:
        yield f"data: {json.dumps({'type': 'error', 'message': 'Session not found'})}\n\n"
        return

    while True:
        try:
            event = await asyncio.wait_for(session.event_queue.get(), timeout=30.0)
            yield f"data: {json.dumps(event)}\n\n"
            if event.get("type") == "stream_end":
                break
        except asyncio.TimeoutError:
            yield f": keepalive\n\n"
        except asyncio.CancelledError:
            break
