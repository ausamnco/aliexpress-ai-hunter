import os
import json
import datetime
import aiosqlite
from typing import List, Optional, Dict, Any

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "searches.db"))

def get_db_path() -> str:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return DB_PATH

async def init_db():
    db_file = get_db_path()
    async with aiosqlite.connect(db_file) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("""
            CREATE TABLE IF NOT EXISTS searches (
                id TEXT PRIMARY KEY,
                search_term TEXT NOT NULL,
                conditions TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                status TEXT NOT NULL,
                total_found INTEGER DEFAULT 0,
                total_matched INTEGER DEFAULT 0,
                currency TEXT DEFAULT 'AUD',
                ship_country TEXT DEFAULT 'AU'
            );
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                search_id TEXT NOT NULL,
                item_id TEXT NOT NULL,
                title TEXT NOT NULL,
                price TEXT NOT NULL,
                original_price TEXT,
                image_url TEXT,
                url TEXT NOT NULL,
                rating TEXT,
                sales TEXT,
                is_match BOOLEAN NOT NULL DEFAULT 0,
                verdict_reason TEXT,
                criteria_breakdown TEXT,
                specs TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (search_id) REFERENCES searches(id) ON DELETE CASCADE
            );
        """)
        
        await db.execute("CREATE INDEX IF NOT EXISTS idx_items_search_id ON items(search_id);")
        await db.commit()

async def create_search(search_id: str, search_term: str, conditions: str, currency: str = "AUD", ship_country: str = "AU") -> Dict[str, Any]:
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db_file = get_db_path()
    async with aiosqlite.connect(db_file) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            """
            INSERT INTO searches (id, search_term, conditions, timestamp, status, total_found, total_matched, currency, ship_country)
            VALUES (?, ?, ?, ?, 'running', 0, 0, ?, ?)
            """,
            (search_id, search_term, conditions, timestamp, currency, ship_country)
        )
        await db.commit()
    return {
        "id": search_id,
        "search_term": search_term,
        "conditions": conditions,
        "timestamp": timestamp,
        "status": "running",
        "total_found": 0,
        "total_matched": 0,
        "currency": currency,
        "ship_country": ship_country
    }

async def update_search_status(search_id: str, status: str, total_found: int = 0, total_matched: int = 0):
    db_file = get_db_path()
    async with aiosqlite.connect(db_file) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            """
            UPDATE searches 
            SET status = ?, total_found = ?, total_matched = ?
            WHERE id = ?
            """,
            (status, total_found, total_matched, search_id)
        )
        await db.commit()

async def save_search_result(search_id: str, item: Dict[str, Any]):
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db_file = get_db_path()
    async with aiosqlite.connect(db_file) as db:
        db.row_factory = aiosqlite.Row
        criteria_str = json.dumps(item.get("criteria_breakdown", []), ensure_ascii=False)
        specs_str = json.dumps(item.get("specs", []), ensure_ascii=False)
        
        await db.execute(
            """
            INSERT INTO items (
                search_id, item_id, title, price, original_price, image_url, 
                url, rating, sales, is_match, verdict_reason, criteria_breakdown, specs, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                search_id,
                str(item.get("item_id", "")),
                item.get("title", ""),
                item.get("price", ""),
                item.get("original_price"),
                item.get("image_url"),
                item.get("url", ""),
                item.get("rating"),
                item.get("sales"),
                1 if item.get("is_match") else 0,
                item.get("verdict_reason", ""),
                criteria_str,
                specs_str,
                now
            )
        )
        await db.commit()

async def save_items(search_id: str, items: List[Dict[str, Any]]):
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db_file = get_db_path()
    async with aiosqlite.connect(db_file) as db:
        db.row_factory = aiosqlite.Row
        for item in items:
            criteria_str = json.dumps(item.get("criteria_breakdown", []), ensure_ascii=False)
            specs_str = json.dumps(item.get("specs", []), ensure_ascii=False)
            
            await db.execute(
                """
                INSERT INTO items (
                    search_id, item_id, title, price, original_price, image_url, 
                    url, rating, sales, is_match, verdict_reason, criteria_breakdown, specs, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    search_id,
                    str(item.get("item_id", "")),
                    item.get("title", ""),
                    item.get("price", ""),
                    item.get("original_price"),
                    item.get("image_url"),
                    item.get("url", ""),
                    item.get("rating"),
                    item.get("sales"),
                    1 if item.get("is_match") else 0,
                    item.get("verdict_reason", ""),
                    criteria_str,
                    specs_str,
                    now
                )
            )
        await db.commit()

async def get_all_searches() -> List[Dict[str, Any]]:
    db_file = get_db_path()
    async with aiosqlite.connect(db_file) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM searches ORDER BY timestamp DESC")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def get_search_by_id(search_id: str) -> Optional[Dict[str, Any]]:
    db_file = get_db_path()
    async with aiosqlite.connect(db_file) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM searches WHERE id = ?", (search_id,))
        search_row = await cursor.fetchone()
        if not search_row:
            return None
            
        search_dict = dict(search_row)
        
        cursor = await db.execute("SELECT * FROM items WHERE search_id = ? ORDER BY is_match DESC, id ASC", (search_id,))
        item_rows = await cursor.fetchall()
        
        items = []
        for r in item_rows:
            d = dict(r)
            d["is_match"] = bool(d["is_match"])
            try:
                d["criteria_breakdown"] = json.loads(d["criteria_breakdown"]) if d["criteria_breakdown"] else []
            except Exception:
                d["criteria_breakdown"] = []
            try:
                d["specs"] = json.loads(d["specs"]) if d["specs"] else []
            except Exception:
                d["specs"] = []
            items.append(d)
            
        search_dict["items"] = items
        return search_dict

async def delete_search(search_id: str) -> bool:
    db_file = get_db_path()
    async with aiosqlite.connect(db_file) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("DELETE FROM items WHERE search_id = ?", (search_id,))
        cursor = await db.execute("DELETE FROM searches WHERE id = ?", (search_id,))
        await db.commit()
        return cursor.rowcount > 0
