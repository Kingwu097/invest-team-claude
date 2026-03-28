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
    # 决策层
    ADVISOR = "advisor"
    QUANT = "quant"
    # 审查层
    RISK_OFFICER = "risk_officer"


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


# === 决策层模型 ===


class PortfolioAction(str, Enum):
    """投资组合操作。"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    INCREASE = "increase"
    DECREASE = "decrease"


class InvestmentProposal(BaseModel):
    """理财顾问的投资建议。"""
    stock_code: str
    stock_name: str
    timestamp: datetime = Field(default_factory=datetime.now)
    action: PortfolioAction
    target_position_pct: float = Field(ge=0, le=100, description="建议仓位占比%")
    reasoning: str
    bull_case: str = ""
    bear_case: str = ""
    confidence: int = Field(ge=0, le=100)
    time_horizon: str = ""  # "短期1-2周" / "中期1-3月" / "长期6月+"
    key_catalysts: list[str] = Field(default_factory=list)
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None

    def to_markdown(self) -> str:
        action_names = {
            PortfolioAction.BUY: "买入", PortfolioAction.SELL: "卖出",
            PortfolioAction.HOLD: "持有", PortfolioAction.INCREASE: "加仓",
            PortfolioAction.DECREASE: "减仓",
        }
        lines = [
            f"### 理财顾问建议: {self.stock_name} ({self.stock_code})",
            f"**操作**: {action_names.get(self.action, self.action.value)} | "
            f"**建议仓位**: {self.target_position_pct}% | "
            f"**信心度**: {self.confidence}%",
            f"**投资周期**: {self.time_horizon}",
            f"\n**核心逻辑**: {self.reasoning}",
        ]
        if self.bull_case:
            lines.append(f"\n**看多论据**: {self.bull_case}")
        if self.bear_case:
            lines.append(f"**看空论据**: {self.bear_case}")
        if self.key_catalysts:
            lines.append("\n**关键催化剂**:")
            for c in self.key_catalysts:
                lines.append(f"- {c}")
        if self.stop_loss_pct is not None:
            lines.append(f"\n**止损**: -{self.stop_loss_pct}% | **止盈**: +{self.take_profit_pct}%")
        return "\n".join(lines)


class QuantAssessment(BaseModel):
    """量化研究员的定量评估。"""
    stock_code: str
    stock_name: str
    timestamp: datetime = Field(default_factory=datetime.now)
    # 量化信号
    valuation_score: int = Field(ge=0, le=100, description="估值评分")
    momentum_score: int = Field(ge=0, le=100, description="动量评分")
    quality_score: int = Field(ge=0, le=100, description="质量评分")
    composite_score: int = Field(ge=0, le=100, description="综合评分")
    # 风险度量
    volatility_30d: Optional[float] = None  # 30日波动率
    max_drawdown_60d: Optional[float] = None  # 60日最大回撤
    sharpe_estimate: Optional[float] = None  # 夏普比率估算
    # 建议
    position_sizing_pct: float = Field(ge=0, le=100, description="建议仓位%")
    reasoning: str = ""

    def to_markdown(self) -> str:
        lines = [
            f"### 量化研究员评估: {self.stock_name} ({self.stock_code})",
            f"**综合评分**: {self.composite_score}/100",
            f"- 估值: {self.valuation_score} | 动量: {self.momentum_score} | 质量: {self.quality_score}",
        ]
        if self.volatility_30d is not None:
            lines.append(f"- 30日波动率: {self.volatility_30d:.1f}%")
        if self.max_drawdown_60d is not None:
            lines.append(f"- 60日最大回撤: {self.max_drawdown_60d:.1f}%")
        if self.sharpe_estimate is not None:
            lines.append(f"- 夏普比率估算: {self.sharpe_estimate:.2f}")
        lines.append(f"\n**建议仓位**: {self.position_sizing_pct}%")
        lines.append(f"**分析**: {self.reasoning}")
        return "\n".join(lines)


# === 审查层模型 ===


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskReviewResult(str, Enum):
    APPROVED = "approved"
    APPROVED_WITH_CONDITIONS = "approved_with_conditions"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"


class RiskReview(BaseModel):
    """风控总监的审核报告。"""
    stock_code: str
    stock_name: str
    timestamp: datetime = Field(default_factory=datetime.now)
    result: RiskReviewResult
    overall_risk: RiskLevel
    risk_score: int = Field(ge=0, le=100, description="风险评分，越高越危险")
    # 具体风险评估
    concentration_risk: str = ""  # 集中度风险
    liquidity_risk: str = ""  # 流动性风险
    drawdown_risk: str = ""  # 回撤风险
    event_risk: str = ""  # 事件风险
    # 审核意见
    conditions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    approved_position_pct: Optional[float] = None  # 批准的仓位上限
    reasoning: str = ""

    def to_markdown(self) -> str:
        result_names = {
            RiskReviewResult.APPROVED: "✅ 通过",
            RiskReviewResult.APPROVED_WITH_CONDITIONS: "⚠️ 有条件通过",
            RiskReviewResult.REJECTED: "❌ 驳回",
            RiskReviewResult.NEEDS_REVISION: "🔄 需修改",
        }
        risk_names = {
            RiskLevel.LOW: "🟢 低", RiskLevel.MEDIUM: "🟡 中",
            RiskLevel.HIGH: "🟠 高", RiskLevel.CRITICAL: "🔴 极高",
        }
        lines = [
            f"### 风控总监审核: {self.stock_name} ({self.stock_code})",
            f"**审核结果**: {result_names.get(self.result, self.result.value)}",
            f"**综合风险**: {risk_names.get(self.overall_risk, self.overall_risk.value)} (评分: {self.risk_score}/100)",
        ]
        if self.approved_position_pct is not None:
            lines.append(f"**批准仓位上限**: {self.approved_position_pct}%")
        lines.append(f"\n**风险评估**:")
        if self.concentration_risk:
            lines.append(f"- 集中度: {self.concentration_risk}")
        if self.liquidity_risk:
            lines.append(f"- 流动性: {self.liquidity_risk}")
        if self.drawdown_risk:
            lines.append(f"- 回撤: {self.drawdown_risk}")
        if self.event_risk:
            lines.append(f"- 事件: {self.event_risk}")
        if self.conditions:
            lines.append("\n**附加条件**:")
            for c in self.conditions:
                lines.append(f"- {c}")
        if self.warnings:
            lines.append("\n**风险警告**:")
            for w in self.warnings:
                lines.append(f"- ⚠️ {w}")
        lines.append(f"\n**审核意见**: {self.reasoning}")
        return "\n".join(lines)
