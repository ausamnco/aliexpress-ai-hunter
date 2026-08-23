import asyncio
import json
import httpx
import sys

LAN_BASE = "http://192.168.20.100:8000"

async def monitor_stream(search_id: str):
    print(f"\n=======================================================")
    print(f"📡 Attaching SSE listener to search_id: {search_id}")
    print(f"=======================================================\n")
    
    url = f"{LAN_BASE}/api/search/stream/{search_id}"
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("GET", url) as response:
            print(f"Connected to stream. Status: {response.status_code}\n")
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
                                    print("⚠️  VERIFICATION CHALLENGE TRIGGERED ON LAN INSTANCE!")
                                    print(f"Challenge URL: {data.get('challenge_url')}")
                                    print(f"Search ID: {search_id}")
                                    print("!" * 60 + "\n")
                                    
                                elif event_type == "captcha_cleared":
                                    print("\n🎉 VERIFICATION CLEARED SUCCESSFULLY!\n")
                                    
                                elif event_type == "captcha_failed":
                                    print(f"\n❌ VERIFICATION FAILED: {data.get('message')}\n")
                                    
                                elif event_type == "item_evaluated":
                                    item = data.get("item", {})
                                    match_str = "✅ MATCH" if item.get("is_match") else "❌ EXCLUDED"
                                    print(f"   -> Item #{data.get('index')}: {item.get('title')[:50]}... | {item.get('price')} | {match_str}")
                                    
                                elif event_type in ["search_completed", "search_failed"]:
                                    print(f"\n🏁 Search stream finished with event: {event_type}\n")
                                    return
                            except Exception as e:
                                print("Raw message:", raw_data)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        search_id = sys.argv[1]
        asyncio.run(monitor_stream(search_id))
    else:
        print("Usage: python monitor_lan.py <search_id>")
