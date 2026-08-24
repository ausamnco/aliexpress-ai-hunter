import asyncio
import json
import logging
import os
import uuid
import httpx
from typing import AsyncGenerator, Optional, Dict, Any, List
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Query
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel

from app import database
from app import scraper
from app import ai_evaluator
from app.models import SearchRequest, ValidateKeyRequest, ValidateGatewayRequest

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("aliexpress_ai_hunter")

# Shared HTTP client for suggestions & background API calls
http_client: Optional[httpx.AsyncClient] = None
SUGGESTIONS_CACHE: Dict[str, List[str]] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client
    http_client = httpx.AsyncClient(timeout=5.0, headers={"User-Agent": "Mozilla/5.0"})
    await database.init_db()
    logger.info("Database & persistent HTTP client initialized successfully.")
    yield
    if http_client:
        await http_client.aclose()

app = FastAPI(title="AliExpress AI Product Hunter", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models for Batch Evaluation from Extension
class BatchEvaluateRequest(BaseModel):
    items: List[Dict[str, Any]]
    conditions: str
    gemini_api_key: str
    model_name: Optional[str] = "gemini-3.6-flash"

# API Endpoints

@app.post("/api/validate-key")
async def validate_gemini_key(req: ValidateKeyRequest):
    if not req.api_key or len(req.api_key.strip()) < 10:
        return {
            "valid": False,
            "quota_available": False,
            "error_type": "TOO_SHORT",
            "message": "API key is too short or empty.",
            "models": []
        }
    
    diag = await ai_evaluator.diagnose_and_validate_key(req.api_key.strip())
    return diag

@app.post("/api/models")
async def get_gemini_models(req: ValidateKeyRequest):
    if not req.api_key:
        raise HTTPException(status_code=400, detail="API Key required.")
    models = await ai_evaluator.list_available_models(req.api_key.strip())
    return {"models": models}

@app.post("/api/validate-gateway")
async def validate_scraping_gateway(req: ValidateGatewayRequest):
    result = await scraper.GatewayScraperClient.validate_gateway(
        provider=req.provider,
        api_key=req.api_key,
        custom_gateway_url=req.custom_gateway_url
    )
    return result

@app.get("/api/suggestions")
async def get_search_suggestions(q: str = Query("", min_length=1)):
    clean_q = q.strip().lower()
    if not clean_q:
        return {"suggestions": []}
    
    # Check in-memory cache first for instant sub-millisecond response
    if clean_q in SUGGESTIONS_CACHE:
        return {"suggestions": SUGGESTIONS_CACHE[clean_q]}
    
    global http_client
    try:
        if not http_client or http_client.is_closed:
            http_client = httpx.AsyncClient(timeout=3.0, headers={"User-Agent": "Mozilla/5.0"})
            
        url = f"https://suggestqueries.google.com/complete/search?client=firefox&q={httpx.URL(clean_q)}"
        resp = await http_client.get(url)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and len(data) > 1 and isinstance(data[1], list):
                suggestions = data[1][:8]
                SUGGESTIONS_CACHE[clean_q] = suggestions
                return {"suggestions": suggestions}
    except Exception as e:
        logger.warning(f"Error fetching suggestions for '{clean_q}': {e}")
        
    return {"suggestions": []}

@app.post("/api/search")
async def start_search(req: SearchRequest, background_tasks: BackgroundTasks):
    terms = req.search_terms or []
    if req.search_term and req.search_term.strip() and req.search_term.strip() not in terms:
        terms.insert(0, req.search_term.strip())
        
    if not terms or not any(t.strip() for t in terms):
        raise HTTPException(status_code=400, detail="At least one search term is required.")
    if not req.conditions.strip():
        raise HTTPException(status_code=400, detail="Conditions cannot be empty.")
    if not req.gemini_api_key.strip():
        raise HTTPException(status_code=400, detail="Gemini API Key is required.")

    search_id = str(uuid.uuid4())
    primary_term = terms[0].strip()
    
    background_tasks.add_task(
        scraper.run_scraper_job,
        search_id=search_id,
        search_term=primary_term,
        search_terms=terms,
        conditions=req.conditions.strip(),
        gemini_api_key=req.gemini_api_key.strip(),
        scraping_provider=req.scraping_provider.strip().lower(),
        scraping_api_key=(req.scraping_api_key or "").strip(),
        custom_gateway_url=(req.custom_gateway_url or "").strip(),
        max_candidates=req.max_candidates,
        ship_country=req.ship_country.strip().upper(),
        currency=req.currency.strip().upper(),
        model_name=req.model_name
    )

    return {
        "search_id": search_id,
        "status": "started",
        "message": f"Search started for {len(terms)} search term(s) with {req.max_candidates} max candidates."
    }

@app.post("/api/search/{search_id}/stop")
async def stop_search(search_id: str):
    session = scraper.sessions.get(search_id)
    if not session:
        raise HTTPException(status_code=404, detail="Search session not found or already completed.")
    
    await session.cancel()
    await database.update_search_status(search_id, "cancelled", len(session.evaluated_items), sum(1 for i in session.evaluated_items if i.get("is_match")))
    return {"status": "cancelled", "search_id": search_id, "message": "Search cancelled successfully."}

@app.post("/api/evaluate-batch")
async def evaluate_items_batch(req: BatchEvaluateRequest):
    """
    Direct concurrent batch evaluation endpoint for Chrome Extension or API clients.
    Evaluates up to 60 items in parallel within ~3 seconds!
    """
    if not req.items:
        return {"evaluated_items": []}
    if not req.conditions.strip():
        raise HTTPException(status_code=400, detail="Conditions cannot be empty.")
    if not req.gemini_api_key.strip():
        raise HTTPException(status_code=400, detail="Gemini API Key is required.")

    async def eval_single(item: Dict[str, Any]):
        try:
            ev = await ai_evaluator.evaluate_product(
                item=item,
                conditions=req.conditions,
                api_key=req.gemini_api_key,
                model_name=req.model_name or "gemini-3.6-flash"
            )
            item_copy = dict(item)
            item_copy["is_match"] = ev.is_match
            item_copy["confidence"] = ev.confidence
            item_copy["verdict_reason"] = ev.verdict_reason
            item_copy["criteria_breakdown"] = [c.model_dump() for c in ev.criteria_evaluations]
            return item_copy
        except Exception as e:
            item_copy = dict(item)
            item_copy["is_match"] = False
            item_copy["confidence"] = 0.0
            item_copy["verdict_reason"] = f"Evaluation failed: {str(e)[:80]}"
            return item_copy

    results = await asyncio.gather(*(eval_single(it) for it in req.items), return_exceptions=True)
    clean_results = [r for r in results if isinstance(r, dict)]
    return {"evaluated_items": clean_results}

@app.get("/api/search/stream/{search_id}")
async def stream_search_events(search_id: str):
    session = scraper.sessions.get(search_id)
    if not session:
        db_record = await database.get_search_by_id(search_id)
        if db_record:
            async def single_event_gen():
                yield f"data: {json.dumps({'type': 'search_completed', 'data': db_record})}\n\n"
            return StreamingResponse(single_event_gen(), media_type="text/event-stream")
        raise HTTPException(status_code=404, detail="Search session not found.")

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            yield f"data: {json.dumps({'type': 'initial_state', 'status': session.status, 'stage': session.stage, 'progress_pct': session.progress_pct})}\n\n"
            
            while True:
                try:
                    event = await asyncio.wait_for(session.event_queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(event)}\n\n"
                    
                    if event.get("type") in ["search_completed", "search_error", "search_cancelled", "stream_end"]:
                        break
                except asyncio.TimeoutError:
                    yield f": keepalive\n\n"
                    if session.status in ["completed", "error", "cancelled"]:
                        break
        except asyncio.CancelledError:
            logger.info(f"Client disconnected from SSE stream for {search_id}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )

@app.get("/api/history")
async def get_search_history():
    history = await database.get_all_searches()
    return {"searches": history}

@app.get("/api/history/{search_id}")
async def get_search_details(search_id: str):
    details = await database.get_search_by_id(search_id)
    if not details:
        raise HTTPException(status_code=404, detail="Search record not found.")
    return details

@app.delete("/api/history/{search_id}")
async def delete_search_record(search_id: str):
    success = await database.delete_search(search_id)
    if not success:
        raise HTTPException(status_code=404, detail="Search record not found.")
    return {"success": True, "message": "Search record and associated items deleted."}

# Static Files & SPA Route
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", response_class=HTMLResponse)
@app.head("/", response_class=HTMLResponse)
async def serve_index():
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>AliExpress AI Hunter</h1><p>Frontend static files not found.</p>")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
