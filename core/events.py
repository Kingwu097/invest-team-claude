"""事件数据模型。所有 Agent 交互产出的事件类型定义。"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """事件类型。"""
    # 分析生命周期
    ANALYSIS_STARTED = "analysis_started"
    ANALYSIS_COMPLETED = "analysis_completed"
    ANALYSIS_FAILED = "analysis_failed"

    # 数据获取
    DATA_FETCH_STARTED = "data_fetch_started"
    DATA_FETCH_COMPLETED = "data_fetch_completed"
    DATA_FETCH_FAILED = "data_fetch_failed"

    # Agent 分析
    AGENT_ANALYSIS_STARTED = "agent_analysis_started"
    AGENT_ANALYSIS_COMPLETED = "agent_analysis_completed"
    AGENT_ANALYSIS_FAILED = "agent_analysis_failed"

    # 辩论
    DEBATE_STARTED = "debate_started"
    DEBATE_ROUND_STARTED = "debate_round_started"
    DEBATE_CHALLENGE = "debate_challenge"
    DEBATE_RESPONSE = "debate_response"
    DEBATE_VOTE = "debate_vote"
    DEBATE_ROUND_COMPLETED = "debate_round_completed"
    DEBATE_COMPLETED = "debate_completed"

    # 共识
    CONSENSUS_REACHED = "consensus_reached"
    CONSENSUS_DEADLOCK = "consensus_deadlock"

    # 信心度
    CONFIDENCE_CHANGED = "confidence_changed"

    # 决策层
    PROPOSAL_STARTED = "proposal_started"
    PROPOSAL_COMPLETED = "proposal_completed"
    QUANT_STARTED = "quant_started"
    QUANT_COMPLETED = "quant_completed"

    # 审查层
    RISK_REVIEW_STARTED = "risk_review_started"
    RISK_REVIEW_COMPLETED = "risk_review_completed"


class AnalysisEvent(BaseModel):
    """分析事件。所有事件的统一结构。"""

    id: str = Field(default_factory=lambda: f"evt_{datetime.now().strftime('%H%M%S%f')}")
    event_type: EventType
    timestamp: datetime = Field(default_factory=datetime.now)
    agent_role: Optional[str] = None
    stock_code: Optional[str] = None
    stock_name: Optional[str] = None

    # 事件数据（不同事件类型携带不同数据）
    data: dict[str, Any] = Field(default_factory=dict)

    # 元数据
    round_number: Optional[int] = None
    confidence: Optional[int] = None
    rating: Optional[str] = None
    summary: Optional[str] = None
    token_usage: int = 0

    # 关联的分析 session
    session_id: str = ""

    def to_sse_data(self) -> dict:
        """转换为 SSE 推送格式。"""
        return {
            "id": self.id,
            "type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "agent": self.agent_role,
            "stock_code": self.stock_code,
            "stock_name": self.stock_name,
            "data": self.data,
            "round": self.round_number,
            "confidence": self.confidence,
            "rating": self.rating,
            "summary": self.summary,
            "session_id": self.session_id,
        }
