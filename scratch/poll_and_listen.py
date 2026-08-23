import asyncio
import json
import httpx
import time

LAN_BASE = "http://192.168.20.100:8000"

async def monitor_stream(search_id: str):
    print(f"\n=======================================================")
    print(f"📡 Attached SSE listener to search_id: {search_id}")
    print(f"=======================================================\n")
    
    url = f"{LAN_BASE}/api/search/stream/{search_id}"
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("GET", url) as response:
            buffer = ""
            async for chunk in response.aiter_text():
                buffer += chunk
                while "\n\n" in buffer:
                    message, buffer = buffer.split("\n\n", 1)
                    for line in message.splitlines():
                        if line.startswith("data: "):
                            raw_data = line[6:].strip()
                            try:
                                payload = json.loads(raw_data)
                                event_type = payload.get("type")
                                stage = payload.get("stage")
                                progress = payload.get("progress_pct")
                                data = payload.get("data", {})
                                
                                print(f"[{progress}%] [STAGE: {stage}] EVENT: {event_type}")
                                
                                if event_type == "captcha_required":
                                    print("\n" + "!" * 60)
                                    print("⚠️  VERIFICATION CHALLENGE TRIGGERED!")
                                    print(f"Challenge URL: {data.get('challenge_url')}")
                                    print(f"Search ID: {search_id}")
                                    print("!" * 60 + "\n")
                                    
                                elif event_type == "captcha_cleared":
                                    print("\n🎉 VERIFICATION CLEARED!\n")
                                    
                                elif event_type == "captcha_failed":
                                    print(f"\n❌ VERIFICATION FAILED: {data.get('message')}\n")
                                    
                                elif event_type == "item_evaluated":
                                    item = data.get("item", {})
                                    match_str = "✅ MATCH" if item.get("is_match") else "❌ EXCLUDED"
                                    print(f"   -> Item #{data.get('index')}: {item.get('title')[:40]}... | {item.get('price')} | {match_str}")
                                    
                                elif event_type in ["search_completed", "search_failed"]:
                                    print(f"\n🏁 Search stream finished: {event_type}\n")
                                    return
                            except Exception:
                                pass

async def main():
    print(f"Connecting to LAN instance at {LAN_BASE}...")
    try:
        r = httpx.get(f"{LAN_BASE}/api/history", timeout=5.0)
        print("Connected! Initial history count:", len(r.json().get("searches", [])))
    except Exception as e:
        print(f"Failed to connect to {LAN_BASE}: {e}")
        return

    print("\n🎧 Listener is active and waiting for a search to start on http://192.168.20.100:8000...")
    print("Ready for user input.")

if __name__ == "__main__":
    asyncio.run(main())
