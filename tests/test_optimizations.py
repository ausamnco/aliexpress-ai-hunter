import asyncio
import time
import httpx
from app import main, scraper, ai_evaluator, database


async def test_fast_suggestions():
    # Warmup and test suggestion speed
    await database.init_db()
    
    # Test cold & cached suggestions
    t0 = time.time()
    res1 = await main.get_search_suggestions("headset")
    dur1 = (time.time() - t0) * 1000
    
    t1 = time.time()
    res2 = await main.get_search_suggestions("headset")
    dur2 = (time.time() - t1) * 1000
    
    assert "suggestions" in res1
    assert len(res1["suggestions"]) > 0
    assert "suggestions" in res2
    assert dur2 < 5.0 # Cached response should be < 5ms
    print(f"Suggestions test passed: first={dur1:.1f}ms, cached={dur2:.2f}ms, count={len(res1['suggestions'])}")


async def test_stop_search_session():
    search_id = "test-stop-session-1"
    session = scraper.ScraperSession(search_id)
    scraper.sessions[search_id] = session
    
    assert session.is_cancelled is False
    assert session.status == "pending"
    
    await session.cancel()
    
    assert session.is_cancelled is True
    assert session.status == "cancelled"
    assert session.stage == "Search stopped by user"
    print("Stop search session test passed.")


async def test_evaluate_batch_endpoint():
    req = main.BatchEvaluateRequest(
        items=[
            {
                "item_id": "1001",
                "title": "Wireless 2.4G Gaming Headset with Active Noise Cancellation ANC",
                "price": "AU $45.00"
            },
            {
                "item_id": "1002",
                "title": "Cotton T-Shirt Short Sleeve Casual",
                "price": "AU $15.00"
            }
        ],
        conditions="1. Must be an audio headset with ANC\n2. Must have 2.4G wireless",
        gemini_api_key=os.environ.get("GEMINI_API_KEY", "MOCK_KEY"),
        model_name="gemini-3.5-flash"
    )
    
    t0 = time.time()
    res = await main.evaluate_items_batch(req)
    dur = time.time() - t0
    
    assert "evaluated_items" in res
    assert len(res["evaluated_items"]) == 2
    item1 = res["evaluated_items"][0]
    item2 = res["evaluated_items"][1]
    
    assert item1["is_match"] is True
    assert item2["is_match"] is False
    print(f"Batch evaluation endpoint test passed in {dur:.2f}s: Item 1 Match={item1['is_match']}, Item 2 Match={item2['is_match']}")

if __name__ == "__main__":
    asyncio.run(test_fast_suggestions())
    asyncio.run(test_stop_search_session())
    asyncio.run(test_evaluate_batch_endpoint())
