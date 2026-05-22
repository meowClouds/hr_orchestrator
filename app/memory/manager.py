import sqlite3
import json
import aiosqlite
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

class MemoryManager:
    """
    Two-tier memory:
    - STM: In-memory dict with TTL (short-term)
    - LTM: SQLite persistent storage with significance scoring
    """
    def __init__(self, stm_ttl_seconds: int = 300, ltm_db_path: str = "long_term_memory.db"):
        self.stm_ttl = stm_ttl_seconds
        self.ltm_path = ltm_db_path
        # STM storage: {user_id: {key: (value, significance, expiry_timestamp)}}
        self.stm: Dict[str, Dict[str, tuple]] = defaultdict(dict)
        self._init_ltm()

    def _init_ltm(self):
        with sqlite3.connect(self.ltm_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ltm (
                    user_id TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    significance REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    last_accessed TEXT NOT NULL,
                    PRIMARY KEY (user_id, key)
                )
            """)
            conn.commit()

    # ---------- Store Memory ----------
    async def store(self, user_id: str, key: str, value: Any, significance: float):
        if significance > 0.7:
            await self._store_ltm(user_id, key, value, significance)
        else:
            self._store_stm(user_id, key, value, significance)

    def _store_stm(self, user_id: str, key: str, value: Any, significance: float):
        expiry = datetime.utcnow() + timedelta(seconds=self.stm_ttl)
        self.stm[user_id][key] = (value, significance, expiry.timestamp())
        logger.debug(f"STM stored: {user_id}/{key}")

    async def _store_ltm(self, user_id: str, key: str, value: Any, significance: float):
        async with aiosqlite.connect(self.ltm_path) as db:
            serialised = json.dumps(value, default=str)
            now = datetime.utcnow().isoformat()
            await db.execute("""
                INSERT OR REPLACE INTO ltm (user_id, key, value, significance, created_at, last_accessed)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, key, serialised, significance, now, now))
            await db.commit()
        logger.debug(f"LTM stored: {user_id}/{key} (sig={significance})")

    # ---------- Retrieve Memory ----------
    async def get(self, user_id: str, key: str) -> Optional[Dict]:
        """Retrieve a single memory by key (checks STM first, then LTM)."""
        # Check STM
        if user_id in self.stm and key in self.stm[user_id]:
            value, sig, expiry_ts = self.stm[user_id][key]
            if datetime.utcnow().timestamp() < expiry_ts:
                return {"value": value, "significance": sig, "source": "STM"}
            else:
                del self.stm[user_id][key]

        # Check LTM
        async with aiosqlite.connect(self.ltm_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT value, significance FROM ltm WHERE user_id = ? AND key = ?",
                (user_id, key)
            )
            row = await cursor.fetchone()
            if row:
                # Update last_accessed
                await db.execute(
                    "UPDATE ltm SET last_accessed = ? WHERE user_id = ? AND key = ?",
                    (datetime.utcnow().isoformat(), user_id, key)
                )
                await db.commit()
                return {
                    "value": json.loads(row["value"]),
                    "significance": row["significance"],
                    "source": "LTM"
                }
        return None

    async def get_all(self, user_id: str, memory_type: Optional[str] = None) -> List[Dict]:
        """Retrieve all memories for a user (STM, LTM, or both)."""
        results = []
        # STM
        if memory_type in (None, "STM"):
            if user_id in self.stm:
                for key, (value, sig, expiry_ts) in self.stm[user_id].items():
                    if datetime.utcnow().timestamp() < expiry_ts:
                        results.append({
                            "key": key,
                            "value": value,
                            "significance": sig,
                            "type": "STM"
                        })
        # LTM
        if memory_type in (None, "LTM"):
            async with aiosqlite.connect(self.ltm_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    "SELECT key, value, significance FROM ltm WHERE user_id = ?",
                    (user_id,)
                )
                rows = await cursor.fetchall()
                for row in rows:
                    results.append({
                        "key": row["key"],
                        "value": json.loads(row["value"]),
                        "significance": row["significance"],
                        "type": "LTM"
                    })
        return results

    async def delete_entry(self, user_id: str, key: str) -> bool:
        """Delete from both tiers."""
        deleted = False
        if user_id in self.stm and key in self.stm[user_id]:
            del self.stm[user_id][key]
            deleted = True
        async with aiosqlite.connect(self.ltm_path) as db:
            cursor = await db.execute(
                "DELETE FROM ltm WHERE user_id = ? AND key = ?",
                (user_id, key)
            )
            await db.commit()
            if cursor.rowcount > 0:
                deleted = True
        return deleted

    async def cleanup_stm(self):
        """Remove expired STM entries."""
        now_ts = datetime.utcnow().timestamp()
        for user_id in list(self.stm.keys()):
            expired_keys = [k for k, (_, _, exp_ts) in self.stm[user_id].items() if exp_ts < now_ts]
            for k in expired_keys:
                del self.stm[user_id][k]
            if not self.stm[user_id]:
                del self.stm[user_id]