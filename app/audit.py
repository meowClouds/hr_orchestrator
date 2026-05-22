import sqlite3
import aiosqlite
from datetime import datetime
from typing import Optional, List, Dict
import logging

logger = logging.getLogger(__name__)

class AuditLogger:
    def __init__(self, db_path: str = "audit.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Create audit_log table if not exists (synchronous for startup)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    message TEXT NOT NULL,
                    intent TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    agent_used TEXT NOT NULL,
                    response TEXT NOT NULL,
                    latency_ms INTEGER NOT NULL
                )
            """)
            # Append-only triggers: prevent updates and deletes
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS prevent_audit_update
                AFTER UPDATE ON audit_log
                BEGIN
                    SELECT RAISE(FAIL, 'Audit log is append-only');
                END
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS prevent_audit_delete
                AFTER DELETE ON audit_log
                BEGIN
                    SELECT RAISE(FAIL, 'Audit log is append-only');
                END
            """)
            conn.commit()

    async def log(self, request_id: str, user_id: str, message: str,
                  intent: str, confidence: float, agent_used: str,
                  response: str, latency_ms: int) -> None:
        """Insert a new audit entry (append-only)."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO audit_log
                (timestamp, request_id, user_id, message, intent, confidence,
                 agent_used, response, latency_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.utcnow().isoformat(),
                request_id, user_id, message, intent, confidence,
                agent_used, response, latency_ms
            ))
            await db.commit()

    async def get_entries(self, limit: int = 100, user_id: Optional[str] = None) -> List[Dict]:
        """Retrieve recent audit entries (read-only)."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if user_id:
                cursor = await db.execute(
                    "SELECT * FROM audit_log WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
                    (user_id, limit)
                )
            else:
                cursor = await db.execute(
                    "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?",
                    (limit,)
                )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def ping(self) -> bool:
        """Check database connectivity."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Audit DB ping failed: {e}")
            return False