"""数据模型定义。

核心数据结构：AnalysisReport / DebateRound / ConsensusReport
使用 Pydantic v2 实现序列化、校验和 JSON Schema 生成。
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class Rating(str, Enum):
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    NEUTRAL = "neutral"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


class AgentRole(str, Enum):
    FUNDAMENTAL = "fundamental"
    MACRO = "macro"
    SENTIMENT = "sentiment"


class RoundType(str, Enum):
    CROSS_REVIEW = "cross_review"
    CHALLENGE_RESPONSE = "challenge_response"
    VOTE_CONSENSUS = "vote_consensus"


class ChallengeType(str, Enum):
    EVIDENCE_CONFLICT = "evidence_conflict"
    MISSING_CONTEXT = "missing_context"
    LOGIC_FLAW = "logic_flaw"
    OUTDATED_DATA = "outdated_data"


class AnalysisSection(BaseModel):
    title: str
    content: str
    data_sources: list[str] = Field(default_factory=list)


class AnalysisReport(BaseModel):
    """单个 Agent 的分析报告。"""

    agent_role: AgentRole
    stock_code: str
    stock_name: str
    timestamp: datetime = Field(default_factory=datetime.now)
    rating: Rating
    confidence: int = Field(ge=0, le=100)
    summary: str
    key_metrics: dict = Field(default_factory=dict)
    analysis_sections: list[AnalysisSection] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    data_sources: list[str] = Field(default_factory=list)

    @field_validator("stock_code")
    @classmethod
    def validate_stock_code(cls, v: str) -> str:
        v = v.strip()
        if not v.isdigit() or len(v) != 6:
            raise ValueError(f"Invalid A-share stock code: {v}")
        if v[0] not in ("0", "3", "6"):
            raise ValueError(f"A-share code must start with 0/3/6, got: {v}")
        return v

    def to_summary_text(self) -> str:
        """生成用于辩论传递的结构化摘要（控制 token 消耗）。"""
        metrics_str = ", ".join(f"{k}: {v}" for k, v in self.key_metrics.items())
        risks_str = "; ".join(self.risks[:3]) if self.risks else "暂无"
        return (
            f"[{self.agent_role.value} 分析师]\n"
            f"评级: {self.rating.value} | 信心度: {self.confidence}%\n"
            f"核心结论: {self.summary}\n"
            f"关键指标: {metrics_str}\n"
            f"主要风险: {risks_str}"
        )

    def to_markdown(self) -> str:
        """生成 Markdown 格式报告。"""
        role_names = {
            AgentRole.FUNDAMENTAL: "基本面分析师",
            AgentRole.MACRO: "宏观分析师",
            AgentRole.SENTIMENT: "情绪分析师",
        }
        rating_names = {
            Rating.STRONG_BUY: "强烈看多",
            Rating.BUY: "看多",
            Rating.NEUTRAL: "中性",
            Rating.SELL: "看空",
            Rating.STRONG_SELL: "强烈看空",
        }
        lines = [
            f"### {role_names.get(self.agent_role, self.agent_role.value)}",
            f"**评级**: {rating_names.get(self.rating, self.rating.value)} | "
            f"**信心度**: {self.confidence}%",
            f"\n{self.summary}\n",
        ]
        if self.key_metrics:
            lines.append("**关键指标**:")
            for k, v in self.key_metrics.items():
                lines.append(f"- {k}: {v}")
            lines.append("")
        for section in self.analysis_sections:
            lines.append(f"**{section.title}**")
            lines.append(section.content)
            lines.append("")
        if self.risks:
            lines.append("**风险提示**:")
            for r in self.risks:
                lines.append(f"- {r}")
        return "\n".join(lines)


class Challenge(BaseModel):
    """辩论中的质疑记录。"""

    challenger: AgentRole
    target: AgentRole
    claim_challenged: str
    challenge_type: ChallengeType
    challenge: str
    supporting_evidence: str = ""
    confidence: int = Field(ge=0, le=100)


class ChallengeResponse(BaseModel):
    """对质疑的回应。"""

    responder: AgentRole
    original_challenge: Challenge
    response: str
    confidence_before: int = Field(ge=0, le=100)
    confidence_after: int = Field(ge=0, le=100)
    position_changed: bool = False


class Vote(BaseModel):
    """投票记录。"""

    agent: AgentRole
    rating: Rating
    confidence: int = Field(ge=0, le=100)
    reasoning: str = ""


class DebateRound(BaseModel):
    """辩论轮次记录。"""

    round_number: int = Field(ge=1, le=3)
    round_type: RoundType
    challenges: list[Challenge] = Field(default_factory=list)
    responses: list[ChallengeResponse] = Field(default_factory=list)
    votes: list[Vote] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.now)
    token_usage: int = 0


class ConsensusReport(BaseModel):
    """共识报告。"""

    stock_code: str
    stock_name: str
    timestamp: datetime = Field(default_factory=datetime.now)
    final_rating: Rating
    consensus_confidence: float = Field(ge=0, le=100)
    is_high_divergence: bool = False
    is_deadlock: bool = False
    individual_votes: list[Vote] = Field(default_factory=list)
    key_agreements: list[str] = Field(default_factory=list)
    key_disagreements: list[str] = Field(default_factory=list)
    actionable_insights: list[str] = Field(default_factory=list)
    debate_summary: str = ""
    total_token_usage: int = 0

    @classmethod
    def from_votes(
        cls,
        stock_code: str,
        stock_name: str,
        votes: list[Vote],
        agreements: list[str],
        disagreements: list[str],
        insights: list[str],
        debate_summary: str,
        total_tokens: int,
    ) -> "ConsensusReport":
        """从投票结果生成共识报告（信心度加权多数制）。"""
        if not votes:
            raise ValueError("No votes to build consensus from")

        rating_weights: dict[Rating, float] = {}
        for v in votes:
            rating_weights[v.rating] = rating_weights.get(v.rating, 0) + v.confidence

        final_rating = max(rating_weights, key=rating_weights.get)  # type: ignore
        consensus_conf = sum(v.confidence for v in votes) / len(votes)

        confidences = [v.confidence for v in votes]
        high_div = (max(confidences) - min(confidences)) > 40

        unique_ratings = set(v.rating for v in votes)
        deadlock = len(unique_ratings) == len(votes) and len(votes) >= 3

        return cls(
            stock_code=stock_code,
            stock_name=stock_name,
            final_rating=final_rating,
            consensus_confidence=round(consensus_conf, 1),
            is_high_divergence=high_div,
            is_deadlock=deadlock,
            individual_votes=votes,
            key_agreements=agreements,
            key_disagreements=disagreements,
            actionable_insights=insights,
            debate_summary=debate_summary,
            total_token_usage=total_tokens,
        )

    def to_markdown(self) -> str:
        """生成 Markdown 格式共识报告。"""
        rating_names = {
            Rating.STRONG_BUY: "强烈看多", Rating.BUY: "看多",
            Rating.NEUTRAL: "中性", Rating.SELL: "看空",
            Rating.STRONG_SELL: "强烈看空",
        }
        role_names = {
            AgentRole.FUNDAMENTAL: "基本面", AgentRole.MACRO: "宏观",
            AgentRole.SENTIMENT: "情绪",
        }

        status = ""
        if self.is_deadlock:
            status = " ⚠️ 未达成共识"
        elif self.is_high_divergence:
            status = " ⚡ 高分歧"

        lines = [
            f"## 共识报告: {self.stock_name} ({self.stock_code}){status}",
            f"\n**最终评级**: {rating_names.get(self.final_rating, self.final_rating.value)}",
            f"**共识信心度**: {self.consensus_confidence}%",
            f"**Token 消耗**: {self.total_token_usage:,}",
            "\n### 各方投票",
        ]
        for v in self.individual_votes:
            name = role_names.get(v.agent, v.agent.value)
            lines.append(
                f"- **{name}分析师**: {rating_names.get(v.rating, v.rating.value)} "
                f"({v.confidence}%) — {v.reasoning}"
            )
        if self.key_agreements:
            lines.append("\n### 共识要点")
            for a in self.key_agreements:
                lines.append(f"- {a}")
        if self.key_disagreements:
            lines.append("\n### 核心分歧")
            for d in self.key_disagreements:
                lines.append(f"- {d}")
        if self.actionable_insights:
            lines.append("\n### 可执行洞察")
            for i in self.actionable_insights:
                lines.append(f"- {i}")
        if self.debate_summary:
            lines.append(f"\n### 辩论过程摘要\n{self.debate_summary}")

        lines.append(
            "\n---\n*本报告由 AI 生成，仅供参考，不构成投资建议。投资有风险，入市需谨慎。*"
        )
        return "\n".join(lines)
