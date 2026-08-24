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

        if provider == "zenrows" and clean_key:
            return (
                f"https://api.zenrows.com/v1/?apikey={clean_key}&url={encoded_target}"
                f"&js_render=true&antibot=true&premium_proxy=true&proxy_country={country}&wait=2000"
            )
        elif provider == "scrapfly" and clean_key:
            return (
                f"https://api.scrapfly.io/scrape?key={clean_key}&url={encoded_target}"
                f"&render_js=true&asp=true&country={country}&wait_for_selector=body"
            )
        elif provider == "scraperapi" and clean_key:
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

def recursive_find_products(obj: Any, items: Dict[str, Dict[str, Any]]):
    """
    Recursively scans any arbitrary JSON data structure to extract AliExpress products.
    """
    if isinstance(obj, dict):
        pid = obj.get("productId") or obj.get("itemId") or obj.get("id") or obj.get("product_id")
        if pid:
            pid_str = str(pid)
            if re.match(r'^\d{8,25}$', pid_str) and pid_str not in items:
                # Title
                title = ""
                raw_title = obj.get("title") or obj.get("displayTitle") or obj.get("productTitle") or obj.get("subject") or obj.get("name")
                if isinstance(raw_title, dict):
                    title = raw_title.get("displayTitle") or raw_title.get("title") or ""
                elif isinstance(raw_title, str):
                    title = raw_title

                # Price
                price = "N/A"
                raw_price = obj.get("prices") or obj.get("price") or obj.get("salePrice") or obj.get("formattedPrice")
                if isinstance(raw_price, dict):
                    sale = raw_price.get("salePrice") or raw_price.get("currentPrice") or raw_price.get("minPrice") or raw_price
                    if isinstance(sale, dict):
                        price = sale.get("formattedPrice") or sale.get("minPrice") or "N/A"
                    elif isinstance(sale, (str, int, float)):
                        price = str(sale)
                elif isinstance(raw_price, (str, int, float)):
                    price = str(raw_price)

                # Image
                image_url = ""
                raw_img = obj.get("image") or obj.get("imageUrl") or obj.get("imgUrl") or obj.get("picPath") or obj.get("itemImg")
                if isinstance(raw_img, dict):
                    image_url = raw_img.get("imgUrl") or raw_img.get("imageUrl") or ""
                elif isinstance(raw_img, str):
                    image_url = raw_img
                if image_url.startswith("//"):
                    image_url = f"https:{image_url}"

                if len(title) > 3 or price != "N/A":
                    items[pid_str] = {
                        "item_id": pid_str,
                        "title": title or f"AliExpress Product #{pid_str}",
                        "price": str(price),
                        "original_price": None,
                        "url": f"https://www.aliexpress.com/item/{pid_str}.html",
                        "image_url": image_url or None,
                        "specs": []
                    }

        for v in obj.values():
            recursive_find_products(v, items)

    elif isinstance(obj, list):
        for elem in obj:
            recursive_find_products(elem, items)

def parse_search_results(html_text: str) -> List[Dict[str, Any]]:
    """
    Extracts product candidates from search HTML, embedded runParams, or JSON scripts.
    """
    items: Dict[str, Dict[str, Any]] = {}

    # 1. Parse JSON from scripts
    script_patterns = [
        r'window\.runParams\s*=\s*(\{.*?\});\s*(?:</script>|\n)',
        r'window\._init_data_\s*=\s*(\{.*?\});\s*(?:</script>|\n)',
        r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});\s*(?:</script>|\n)',
        r'<script[^>]*id=[\"\']__AER_DATA__[\"\'][^>]*>(.*?)</script>',
        r'<script[^>]*type=[\"\']application/json[\"\'][^>]*>(.*?)</script>',
        r'runParams\s*:\s*(\{.*?\})\s*,\s*\w+\s*:'
    ]

    for pat in script_patterns:
        matches = re.findall(pat, html_text, re.DOTALL)
        for m in matches:
            try:
                data = json.loads(m)
                recursive_find_products(data, items)
            except Exception:
                try:
                    trimmed = m.strip()
                    if trimmed.endswith(';'):
                        trimmed = trimmed[:-1]
                    data = json.loads(trimmed)
                    recursive_find_products(data, items)
                except Exception:
                    pass

    # 2. Extract item links from HTML regex
    link_matches = re.findall(r'(?:href=[\"\'])?(?:https?:)?(?://(?:www\.)?aliexpress\.com)?/item/(\d{8,25})\.html', html_text)
    for pid in link_matches:
        if pid not in items:
            items[pid] = {
                "item_id": pid,
                "title": f"AliExpress Product #{pid}",
                "price": "N/A",
                "original_price": None,
                "url": f"https://www.aliexpress.com/item/{pid}.html",
                "image_url": None,
                "specs": []
            }

    # 3. Extract productId pattern matches directly
    pid_matches = re.findall(r'\"productId\"\s*:\s*[\"\']?(\d{8,25})[\"\']?', html_text)
    for pid in pid_matches:
        if pid not in items:
            items[pid] = {
                "item_id": pid,
                "title": f"AliExpress Product #{pid}",
                "price": "N/A",
                "original_price": None,
                "url": f"https://www.aliexpress.com/item/{pid}.html",
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
    specs: List[str] = []

    # 1. Parse JSON properties inside HTML
    data_matches = re.findall(r'(?:window\.)?(?:runParams|_init_data_)\s*=\s*(\{.*?\});\s*(?:</script>|\n)', html_text, re.DOTALL)
    for dm in data_matches:
        try:
            data = json.loads(dm)
            root = data.get("data", {}) or data

            # Title
            title_module = root.get("titleModule", {}) or root.get("productInfoComponent", {})
            extracted_title = title_module.get("subject") or title_module.get("title") or title_module.get("productTitle")
            if extracted_title:
                title = str(extracted_title)

            # Price
            price_module = root.get("priceModule", {}) or root.get("priceComponent", {})
            extracted_price = (
                price_module.get("formatedActivityPrice") or
                price_module.get("formatedPrice") or
                price_module.get("formattedPrice") or
                price_module.get("minPrice")
            )
            if extracted_price:
                price = str(extracted_price)

            # Specs
            prop_module = root.get("specsModule", {}) or root.get("productPropComponent", {}) or root.get("skuModule", {})
            props_list = prop_module.get("props", []) or prop_module.get("productProperties", []) or []
            for prop in props_list:
                if isinstance(prop, dict):
                    name = prop.get("attrName") or prop.get("name") or prop.get("propName")
                    val = prop.get("attrValue") or prop.get("value") or prop.get("propValue")
                    if name and val:
                        spec_str = f"{name}: {val}"
                        if spec_str not in specs:
                            specs.append(spec_str)

            # Images
            image_module = root.get("imageModule", {}) or root.get("imageComponent", {})
            img_list = image_module.get("imagePathList", []) or image_module.get("images", [])
            if img_list and isinstance(img_list, list):
                image_url = str(img_list[0])
                if image_url.startswith("//"):
                    image_url = f"https:{image_url}"
        except Exception:
            pass

    # 2. HTML Fallback Extraction if JSON parsing was partial
    if not specs:
        spec_patterns = [
            r'<(?:li|div|span|td)[^>]*class=[\"\'][^\"\']*(?:specification--item|prop-item|spec--item|property-item|specification-item)[^\"\']*[\"\'][^>]*>(.*?)</(?:li|div|span|td)>',
            r'<span class=[\"\']title[\"\']>([^<]+)</span>\s*<span class=[\"\']value[\"\']>([^<]+)</span>'
        ]
        for pat in spec_patterns:
            matches = re.findall(pat, html_text, re.DOTALL | re.IGNORECASE)
            for m in matches:
                if isinstance(m, tuple):
                    k, v = m
                    clean_k = re.sub(r'<[^>]+>', ' ', k).strip()
                    clean_v = re.sub(r'<[^>]+>', ' ', v).strip()
                    if clean_k and clean_v:
                        spec_str = f"{clean_k}: {clean_v}"
                        if spec_str not in specs:
                            specs.append(spec_str)
                elif isinstance(m, str):
                    clean_s = re.sub(r'<[^>]+>', ' ', m).strip()
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

    if not image_url:
        img_match = re.search(r'<meta property=[\"\']og:image[\"\'] content=[\"\']([^\"\']+)[\"\']', html_text)
        if img_match:
            image_url = img_match.group(1)
            if image_url.startswith("//"):
                image_url = f"https:{image_url}"

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
        # Create search in DB
        await database.create_search(
            search_id=search_id,
            search_term=search_term,
            conditions=conditions,
            currency=currency,
            ship_country=ship_country
        )

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

            provider_label = scraping_provider.capitalize() if scraping_api_key or scraping_provider == "custom" else "Direct Web"
            session.stage = f"Searching AliExpress for '{query}' ({provider_label})..."
            session.progress_pct = 10 + int((q_idx / len(search_queries)) * 30)
            await session.emit_event("query_started", {"query": query, "query_index": q_idx + 1})

            slug = re.sub(r'[^a-z0-9]+', '-', query.lower()).strip('-')
            encoded_query = urllib.parse.quote_plus(query)

            # Try primary search URL format
            search_urls = [
                f"https://www.aliexpress.com/w/wholesale-{slug}.html?SearchText={encoded_query}",
                f"https://www.aliexpress.com/wholesale?SearchText={encoded_query}"
            ]

            for search_url in search_urls:
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
                    if candidates:
                        break
                else:
                    logger.warning(f"Gateway returned status {status} for query '{query}' at {search_url}")

        if not discovered_candidates:
            msg = (
                "No products could be extracted. "
                "Make sure your Scraping Gateway Key (ZenRows / ScrapFly / ScraperAPI) is active to bypass AliExpress security challenges."
                if not scraping_api_key and scraping_provider != "custom" else
                "AliExpress search returned 0 items for this query. Try a broader search keyword."
            )
            session.stage = msg
            await session.emit_event("progress_update", {"message": msg})

        # 2. Evaluate candidate products with Gemini AI
        candidate_list = list(discovered_candidates.values())[:max_candidates]
        if candidate_list:
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
        logger.error(f"Error during scraping job {search_id}: {e}", exc_info=True)
        session.status = "error"
        session.error_message = str(e)
        session.stage = f"Error: {str(e)}"
        await session.emit_event("search_error", {"error": str(e)})

    finally:
        await session.emit_event("stream_end")
