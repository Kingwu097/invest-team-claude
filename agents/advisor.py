"""理财顾问 Agent。汇总情报层分析，生成投资建议。

接收：ConsensusReport + 三份 AnalysisReport
输出：InvestmentProposal（操作建议 + 仓位 + 止损止盈）
"""

import logging
from typing import Optional

from config.llm_client import LLMClient
from models.report import (
    AgentRole, AnalysisReport, ConsensusReport,
    InvestmentProposal,
)

logger = logging.getLogger(__name__)


class AdvisorAgent:
    """理财顾问。汇总情报层共识，生成投资建议。"""

    def __init__(self, llm: LLMClient):
        self.llm = llm
        self.is_online = True

    @property
    def role(self) -> AgentRole:
        return AgentRole.ADVISOR

    def _role_name(self) -> str:
        return "理财顾问"

    async def generate_proposal(
        self,
        consensus: ConsensusReport,
        reports: list[AnalysisReport],
    ) -> Optional[InvestmentProposal]:
        """基于共识报告生成投资建议。"""
        try:
            context = self._build_context(consensus, reports)
            system_prompt = (
                "你是一位资深的理财顾问，负责将分析团队的研究成果转化为可执行的投资建议。\n\n"
                "你的职责：\n"
                "1. 综合三位分析师的观点和辩论结论\n"
                "2. 制定具体的投资操作建议（买入/卖出/持有/加仓/减仓）\n"
                "3. 给出建议仓位比例（占总资产的百分比）\n"
                "4. 设定止损和止盈水平\n"
                "5. 明确投资周期（短期/中期/长期）\n\n"
                "原则：\n"
                "- 当分析师存在高分歧时，建议保守操作\n"
                "- 仓位不超过单只股票 20%（除非信心度极高）\n"
                "- 必须同时考虑看多和看空论据\n"
                "- 止损幅度根据波动率动态调整"
            )

            proposal = await self.llm.call_structured(
                system_prompt=system_prompt,
                user_message=context,
                response_model=InvestmentProposal,
            )
            proposal.stock_code = consensus.stock_code
            proposal.stock_name = consensus.stock_name
            logger.info(
                f"[advisor] 建议: {proposal.action.value} | "
                f"仓位 {proposal.target_position_pct}% | 信心度 {proposal.confidence}%"
            )
            return proposal
        except Exception as e:
            logger.error(f"[advisor] 生成建议失败: {e}")
            self.is_online = False
            return None

    def _build_context(
        self, consensus: ConsensusReport, reports: list[AnalysisReport]
    ) -> str:
        lines = [
            f"请为 {consensus.stock_name} ({consensus.stock_code}) 制定投资建议。\n",
            "## 分析团队共识",
            consensus.to_markdown(),
            "\n## 各分析师详细报告摘要",
        ]
        for r in reports:
            lines.append(r.to_summary_text())
            lines.append("")
        return "\n".join(lines)
