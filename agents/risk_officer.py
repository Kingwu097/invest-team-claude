"""风控总监 Agent。审核投资建议，控制风险。

接收：InvestmentProposal + QuantAssessment + ConsensusReport
输出：RiskReview（审核结果 + 风险评估 + 条件/警告）

设计文档规定：风控总监兼任「裁判 Agent」角色，基于风险预算裁决。
"""

import logging
from typing import Optional

from config.llm_client import LLMClient
from models.report import (
    AgentRole, ConsensusReport, InvestmentProposal,
    QuantAssessment, RiskReview,
)

logger = logging.getLogger(__name__)


class RiskOfficerAgent:
    """风控总监。审核投资建议，设定风险边界。"""

    def __init__(self, llm: LLMClient):
        self.llm = llm
        self.is_online = True

    @property
    def role(self) -> AgentRole:
        return AgentRole.RISK_OFFICER

    def _role_name(self) -> str:
        return "风控总监"

    async def review(
        self,
        proposal: InvestmentProposal,
        quant: Optional[QuantAssessment],
        consensus: ConsensusReport,
    ) -> Optional[RiskReview]:
        """审核投资建议。"""
        try:
            context = self._build_context(proposal, quant, consensus)
            system_prompt = (
                "你是投资团队的风控总监，负责审核所有投资建议的风险合规性。\n\n"
                "你的审核框架：\n"
                "1. **集中度风险**：单只股票仓位不得超过总资产 20%\n"
                "2. **流动性风险**：评估标的的日成交额是否足以支撑建议的仓位规模\n"
                "3. **回撤风险**：基于波动率和最大回撤，评估潜在亏损\n"
                "4. **事件风险**：近期是否有可能导致大幅波动的事件（财报、政策等）\n\n"
                "审核规则：\n"
                "- 高分歧 + 高仓位 → 必须降低仓位或驳回\n"
                "- 波动率 > 40% → 仓位上限 10%\n"
                "- 最大回撤 > 20% → 必须设置止损\n"
                "- 信心度 < 50% → 驳回或要求修改\n\n"
                "输出审核结果、风险评分（0-100，越高越危险）、条件和警告。"
            )

            review = await self.llm.call_structured(
                system_prompt=system_prompt,
                user_message=context,
                response_model=RiskReview,
            )
            review.stock_code = proposal.stock_code
            review.stock_name = proposal.stock_name

            # 硬性规则检查
            self._apply_hard_rules(review, proposal, quant, consensus)

            result_str = review.result.value
            logger.info(
                f"[risk_officer] 审核: {result_str} | "
                f"风险评分: {review.risk_score}/100 | "
                f"批准仓位: {review.approved_position_pct}%"
            )
            return review
        except Exception as e:
            logger.error(f"[risk_officer] 审核失败: {e}")
            self.is_online = False
            return None

    def _apply_hard_rules(
        self,
        review: RiskReview,
        proposal: InvestmentProposal,
        quant: Optional[QuantAssessment],
        consensus: ConsensusReport,
    ):
        """应用硬性风控规则（覆盖 LLM 输出）。"""
        from models.report import RiskReviewResult, RiskLevel

        # 规则 1: 单只仓位不超过 20%
        if proposal.target_position_pct > 20:
            if review.approved_position_pct is None or review.approved_position_pct > 20:
                review.approved_position_pct = 20.0
                review.conditions.append("单只股票仓位不得超过 20%")

        # 规则 2: 高波动率 → 仓位上限 10%
        if quant and quant.volatility_30d and quant.volatility_30d > 40:
            if review.approved_position_pct is None or review.approved_position_pct > 10:
                review.approved_position_pct = 10.0
                review.warnings.append(
                    f"30日波动率 {quant.volatility_30d:.1f}% 超过 40%，仓位限制至 10%"
                )
                review.overall_risk = RiskLevel.HIGH

        # 规则 3: 高分歧 + 高仓位 → 降仓
        if consensus.is_high_divergence and proposal.target_position_pct > 10:
            if review.approved_position_pct is None or review.approved_position_pct > 10:
                review.approved_position_pct = 10.0
                review.warnings.append("分析师存在高分歧，建议降低仓位")

        # 规则 4: 未达共识 → 仓位限制至 5%
        if consensus.is_deadlock:
            if review.approved_position_pct is None or review.approved_position_pct > 5:
                review.approved_position_pct = 5.0
                review.result = RiskReviewResult.APPROVED_WITH_CONDITIONS
                review.warnings.append("分析师未达成共识，仓位限制至 5%")

        # 确保有批准仓位
        if review.approved_position_pct is None:
            review.approved_position_pct = min(proposal.target_position_pct, 15.0)

    def _build_context(
        self,
        proposal: InvestmentProposal,
        quant: Optional[QuantAssessment],
        consensus: ConsensusReport,
    ) -> str:
        lines = [
            f"请审核以下投资建议：\n",
            "## 理财顾问建议",
            proposal.to_markdown(),
            "\n## 分析团队共识",
            consensus.to_markdown(),
        ]
        if quant:
            lines.append("\n## 量化评估")
            lines.append(quant.to_markdown())
        return "\n".join(lines)
