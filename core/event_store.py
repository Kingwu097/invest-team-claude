"""事件持久化存储（SQLite）。

支持：
- 事件写入和查询
- 按 session_id 检索完整分析记录
- 历史分析列表
"""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.events import AnalysisEvent, EventType

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "data" / "events.db"


class EventStore:
    """事件持久化存储。"""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    agent_role TEXT,
                    stock_code TEXT,
                    stock_name TEXT,
                    round_number INTEGER,
                    confidence INTEGER,
                    rating TEXT,
                    summary TEXT,
                    data_json TEXT,
                    token_usage INTEGER DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_id ON events(session_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_event_type ON events(event_type)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS analysis_sessions (
                    session_id TEXT PRIMARY KEY,
                    stock_code TEXT NOT NULL,
                    stock_name TEXT,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    status TEXT DEFAULT 'running',
                    final_rating TEXT,
                    consensus_confidence REAL,
                    total_tokens INTEGER DEFAULT 0
                )
            """)
            conn.commit()

    async def save_event(self, event: AnalysisEvent):
        """保存事件到 SQLite。"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO events
                   (id, session_id, event_type, timestamp, agent_role,
                    stock_code, stock_name, round_number, confidence,
                    rating, summary, data_json, token_usage)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event.id,
                    event.session_id,
                    event.event_type.value,
                    event.timestamp.isoformat(),
                    event.agent_role,
                    event.stock_code,
                    event.stock_name,
                    event.round_number,
                    event.confidence,
                    event.rating,
                    event.summary,
                    json.dumps(event.data, ensure_ascii=False, default=str),
                    event.token_usage,
                ),
            )
            conn.commit()

    def create_session(self, session_id: str, stock_code: str, stock_name: str = ""):
        """创建分析 session。"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO analysis_sessions
                   (session_id, stock_code, stock_name, started_at, status)
                   VALUES (?, ?, ?, ?, 'running')""",
                (session_id, stock_code, stock_name, datetime.now().isoformat()),
            )
            conn.commit()

    def complete_session(
        self,
        session_id: str,
        status: str = "completed",
        final_rating: str = "",
        consensus_confidence: float = 0,
        total_tokens: int = 0,
    ):
        """完成分析 session。"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """UPDATE analysis_sessions
                   SET completed_at=?, status=?, final_rating=?,
                       consensus_confidence=?, total_tokens=?
                   WHERE session_id=?""",
                (
                    datetime.now().isoformat(),
                    status,
                    final_rating,
                    consensus_confidence,
                    total_tokens,
                    session_id,
                ),
            )
            conn.commit()

    def get_session_events(self, session_id: str) -> list[dict]:
        """获取某个 session 的所有事件。"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM events WHERE session_id=? ORDER BY timestamp",
                (session_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def list_sessions(self, limit: int = 20) -> list[dict]:
        """列出最近的分析 session。"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT * FROM analysis_sessions
                   ORDER BY started_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_session(self, session_id: str) -> Optional[dict]:
        """获取单个 session 信息。"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM analysis_sessions WHERE session_id=?",
                (session_id,),
            ).fetchone()
            return dict(row) if row else None
