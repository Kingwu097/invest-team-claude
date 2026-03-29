"""绩效归因分析师 Agent。跟踪交易记录，评估 Agent 历史表现。

功能：
- 记录每次交易到 SQLite
- 统计各 Agent 的历史准确率
- 计算投资组合的模拟收益
"""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from models.report import AgentRole, ConsensusReport, Rating

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "data" / "performance.db"


class PerformanceRecord(BaseModel):
    """单次分析的绩效记录。"""
    session_id: str
    stock_code: str
    stock_name: str
    analysis_date: str
    rating: str  # 共识评级
    confidence: float
    entry_price: Optional[float] = None
    current_price: Optional[float] = None
    pnl_pct: Optional[float] = None  # 盈亏百分比
    days_held: int = 0
    is_correct: Optional[bool] = None  # 方向是否正确


class PerformanceSummary(BaseModel):
    """绩效汇总。"""
    total_analyses: int = 0
    tracked_trades: int = 0
    correct_predictions: int = 0
    accuracy_pct: Optional[float] = None
    avg_confidence: float = 0
    total_pnl_pct: float = 0
    best_trade: Optional[str] = None
    worst_trade: Optional[str] = None

    def to_markdown(self) -> str:
        lines = [
            "### 绩效归因报告",
            f"**总分析次数**: {self.total_analyses}",
            f"**有跟踪的交易**: {self.tracked_trades}",
        ]
        if self.accuracy_pct is not None:
            lines.append(f"**方向准确率**: {self.accuracy_pct:.1f}%")
        lines.append(f"**平均信心度**: {self.avg_confidence:.1f}%")
        if self.tracked_trades > 0:
            lines.append(f"**累计收益**: {self.total_pnl_pct:+.2f}%")
        if self.best_trade:
            lines.append(f"**最佳交易**: {self.best_trade}")
        if self.worst_trade:
            lines.append(f"**最差交易**: {self.worst_trade}")
        return "\n".join(lines)


class PerformanceTracker:
    """绩效跟踪器。持久化到 SQLite。"""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    stock_code TEXT NOT NULL,
                    stock_name TEXT,
                    analysis_date TEXT NOT NULL,
                    rating TEXT,
                    confidence REAL,
                    action TEXT,
                    position_pct REAL,
                    entry_price REAL,
                    current_price REAL,
                    pnl_pct REAL,
                    days_held INTEGER DEFAULT 0,
                    is_correct INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def record_trade(
        self,
        session_id: str,
        stock_code: str,
        stock_name: str,
        rating: str,
        confidence: float,
        action: str = "",
        position_pct: float = 0,
        entry_price: Optional[float] = None,
    ):
        """记录交易。"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """INSERT INTO trades
                   (session_id, stock_code, stock_name, analysis_date,
                    rating, confidence, action, position_pct, entry_price)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    session_id, stock_code, stock_name,
                    datetime.now().strftime("%Y-%m-%d"),
                    rating, confidence, action, position_pct, entry_price,
                ),
            )
            conn.commit()

    def update_price(self, stock_code: str, current_price: float):
        """更新持仓的当前价格并计算盈亏。"""
        with sqlite3.connect(str(self.db_path)) as conn:
            rows = conn.execute(
                "SELECT id, entry_price, analysis_date, rating FROM trades WHERE stock_code=? AND entry_price IS NOT NULL",
                (stock_code,),
            ).fetchall()
            for row in rows:
                tid, entry, date_str, rating = row
                if entry and entry > 0:
                    pnl = (current_price - entry) / entry * 100
                    days = (datetime.now() - datetime.strptime(date_str, "%Y-%m-%d")).days
                    # 判断方向是否正确
                    is_correct = None
                    if rating in ("strong_buy", "buy") and pnl > 0:
                        is_correct = 1
                    elif rating in ("sell", "strong_sell") and pnl < 0:
                        is_correct = 1
                    elif rating in ("strong_buy", "buy") and pnl < 0:
                        is_correct = 0
                    elif rating in ("sell", "strong_sell") and pnl > 0:
                        is_correct = 0

                    conn.execute(
                        "UPDATE trades SET current_price=?, pnl_pct=?, days_held=?, is_correct=? WHERE id=?",
                        (current_price, round(pnl, 2), days, is_correct, tid),
                    )
            conn.commit()

    def get_summary(self) -> PerformanceSummary:
        """获取绩效汇总。"""
        with sqlite3.connect(str(self.db_path)) as conn:
            total = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
            tracked = conn.execute(
                "SELECT COUNT(*) FROM trades WHERE entry_price IS NOT NULL"
            ).fetchone()[0]
            correct = conn.execute(
                "SELECT COUNT(*) FROM trades WHERE is_correct=1"
            ).fetchone()[0]
            evaluated = conn.execute(
                "SELECT COUNT(*) FROM trades WHERE is_correct IS NOT NULL"
            ).fetchone()[0]

            avg_conf = conn.execute(
                "SELECT AVG(confidence) FROM trades"
            ).fetchone()[0] or 0

            total_pnl = conn.execute(
                "SELECT SUM(pnl_pct) FROM trades WHERE pnl_pct IS NOT NULL"
            ).fetchone()[0] or 0

            best = conn.execute(
                "SELECT stock_name, pnl_pct FROM trades WHERE pnl_pct IS NOT NULL ORDER BY pnl_pct DESC LIMIT 1"
            ).fetchone()
            worst = conn.execute(
                "SELECT stock_name, pnl_pct FROM trades WHERE pnl_pct IS NOT NULL ORDER BY pnl_pct ASC LIMIT 1"
            ).fetchone()

            return PerformanceSummary(
                total_analyses=total,
                tracked_trades=tracked,
                correct_predictions=correct,
                accuracy_pct=(correct / evaluated * 100) if evaluated > 0 else None,
                avg_confidence=round(avg_conf, 1),
                total_pnl_pct=round(total_pnl, 2),
                best_trade=f"{best[0]} (+{best[1]}%)" if best and best[1] else None,
                worst_trade=f"{worst[0]} ({worst[1]}%)" if worst and worst[1] else None,
            )

    def list_trades(self, limit: int = 20) -> list[dict]:
        """列出最近的交易记录。"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM trades ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
