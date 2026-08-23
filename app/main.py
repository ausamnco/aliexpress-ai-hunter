import asyncio
import json
import logging
import os
import uuid
import httpx
from typing import AsyncGenerator
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Query
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app import database
from app import scraper
from app import ai_evaluator
from app.models import SearchRequest, ValidateKeyRequest, CaptchaActionRequest, CaptchaResumeRequest

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("aliexpress_ai_hunter")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.init_db()
    logger.info("Database initialized successfully.")
    yield

app = FastAPI(title="AliExpress AI Product Hunter", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

@app.get("/api/suggestions")
async def get_search_suggestions(q: str = Query("", min_length=1)):
    if not q.strip():
        return {"suggestions": []}
    
    clean_q = q.strip()
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            # Query Google Search Suggestions (ultra-fast, generic spelling & product autocompletion)
            url = f"https://suggestqueries.google.com/complete/search?client=firefox&q={httpx.URL(clean_q)}"
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and len(data) > 1 and isinstance(data[1], list):
                    return {"suggestions": data[1][:8]}
    except Exception as e:
        logger.warning(f"Error fetching suggestions for '{clean_q}': {e}")
        
    return {"suggestions": []}

@app.post("/api/search")
async def start_search(req: SearchRequest, background_tasks: BackgroundTasks):
    # Support either single search_term or list of search_terms
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

@app.post("/api/captcha/resume")
async def resume_captcha_failure(req: CaptchaResumeRequest):
    result = await scraper.resume_after_captcha_failure(req.search_id, req.action)
    return result

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
                    
                    if event.get("type") in ["search_completed", "search_failed"]:
                        break
                except asyncio.TimeoutError:
                    yield f": keepalive\n\n"
                    if session.status in ["completed", "failed"]:
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

@app.post("/api/captcha/action")
async def perform_captcha_action(req: CaptchaActionRequest):
    result = await scraper.handle_captcha_interaction(
        search_id=req.search_id,
        action=req.action,
        cookie_str=req.cookie_str,
        redirect_url=req.redirect_url
    )
    return result

@app.get("/api/captcha/live/{search_id}", response_class=HTMLResponse)
async def get_live_captcha_page(search_id: str):
    session = scraper.sessions.get(search_id)
    if not session or not session.active_page:
        raise HTTPException(status_code=404, detail="Active search session or browser page not found.")

    try:
        page = session.active_page
        content = await page.content()
        
        base_tag = f'<base href="{page.url}">'
        inject_script = """
        <script>
            // Relay verification completion to parent app
            setInterval(function() {
                var el = document.querySelector('.nc-lang-cnt, #nc_1__scale_text, .btn_slide');
                if (el && (el.innerText.toLowerCase().indexOf('pass') !== -1 || el.innerText.toLowerCase().indexOf('success') !== -1)) {
                    if (window.parent) window.parent.postMessage({ type: 'aliexpress_captcha_passed' }, '*');
                }
            }, 1000);
        </script>
        """
        
        if "<head>" in content:
            content = content.replace("<head>", f"<head>\n{base_tag}\n{inject_script}", 1)
        elif "<html" in content:
            content = content.replace(">", f">\n<head>{base_tag}\n{inject_script}</head>", 1)
            
        return HTMLResponse(
            content=content,
            headers={
                "X-Frame-Options": "ALLOWALL",
                "Content-Security-Policy": "default-src * 'unsafe-inline' 'unsafe-eval' data: blob:;"
            }
        )
    except Exception as e:
        logger.error(f"Error serving live AliExpress challenge page: {e}")
        return HTMLResponse(content=f"<h3>Error loading AliExpress challenge:</h3><p>{str(e)}</p>")

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
