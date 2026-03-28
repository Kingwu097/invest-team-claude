"""Agent 基类。模板方法模式：子类只需 override 3 个钩子。

流程: analyze() → fetch_data() → format_context() → LLM 分析 → 解析 AnalysisReport
辩论: participate_round1/2/3() — 被 DebateOrchestrator 调用
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

from config.llm_client import LLMClient
from data.formatter import DataFormatter
from models.report import (
    AgentRole,
    AnalysisReport,
    AnalysisSection,
    Challenge,
    ChallengeResponse,
    ChallengeType,
    Rating,
    Vote,
)

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """投资分析 Agent 基类。"""

    def __init__(self, llm: LLMClient):
        self.llm = llm
        self.is_online = True
        self._last_report: Optional[AnalysisReport] = None

    @property
    @abstractmethod
    def role(self) -> AgentRole:
        """Agent 角色。"""
        ...

    @abstractmethod
    def get_system_prompt(self) -> str:
        """返回该 Agent 的 system prompt。"""
        ...

    @abstractmethod
    def fetch_data(self, stock_code: str) -> dict[str, Any]:
        """获取该 Agent 需要的数据。返回 {section_name: raw_data}。"""
        ...

    @property
    @abstractmethod
    def focus_metrics(self) -> list[str]:
        """该 Agent 关注的核心指标列表。"""
        ...

    async def analyze(self, stock_code: str, stock_name: str) -> Optional[AnalysisReport]:
        """执行完整分析流程（模板方法）。"""
        try:
            # 1. 获取数据
            logger.info(f"[{self.role.value}] 获取数据: {stock_code}")
            raw_data = self.fetch_data(stock_code)

            # 2. 格式化上下文
            # 如果使用工具系统，raw_data 包含 _tool_context
            if "_tool_context" in raw_data:
                context = raw_data["_tool_context"]
                incomplete = "[不可用" in context or "[数据获取失败" in context
            else:
                context = DataFormatter.build_context(raw_data)
                incomplete = any(
                    "数据不可用" in DataFormatter.build_context({k: v})
                    for k, v in raw_data.items()
                    if v is None
                )

            # 3. 调用 LLM 分析
            logger.info(f"[{self.role.value}] 开始分析...")
            user_msg = (
                f"请对 {stock_name}({stock_code}) 进行深度分析。\n\n"
                f"以下是相关数据:\n{context}\n\n"
                f"请重点关注以下指标: {', '.join(self.focus_metrics)}\n"
                f"{'⚠️ 注意: 部分数据不可用，请基于可用数据分析并标注数据局限性。' if incomplete else ''}"
            )

            report = await self.llm.call_structured(
                system_prompt=self.get_system_prompt(),
                user_message=user_msg,
                response_model=AnalysisReport,
            )
            # 覆盖自动填充字段
            report.agent_role = self.role
            report.stock_code = stock_code
            report.stock_name = stock_name
            self._last_report = report
            logger.info(
                f"[{self.role.value}] 分析完成: "
                f"{report.rating.value} ({report.confidence}%)"
            )
            return report

        except Exception as e:
            logger.error(f"[{self.role.value}] 分析失败: {e}")
            self.is_online = False
            return None

    async def cross_review(
        self, other_summaries: list[str]
    ) -> list[Challenge]:
        """Round 1: 交叉审查其他 Agent 的报告摘要，输出质疑。"""
        if not self.is_online or not self._last_report:
            return []

        prompt = (
            f"你是{self._role_name()}。以下是其他分析师的报告摘要:\n\n"
            + "\n\n---\n\n".join(other_summaries)
            + f"\n\n你自己的分析结论: {self._last_report.to_summary_text()}\n\n"
            f"请识别其他分析师报告中的潜在问题，包括: 证据冲突、遗漏背景、逻辑缺陷、数据过时。\n"
            f"输出 1-2 条最重要的质疑。"
        )
        try:
            text = await self.llm.call_text(
                system_prompt=self._debate_system_prompt(),
                user_message=prompt,
            )
            return self._parse_challenges(text)
        except Exception as e:
            logger.warning(f"[{self.role.value}] 交叉审查失败: {e}")
            return []

    async def respond_to_challenges(
        self, challenges: list[Challenge]
    ) -> list[ChallengeResponse]:
        """Round 2: 回应针对自己的质疑。"""
        if not self.is_online or not self._last_report or not challenges:
            return []

        my_challenges = [c for c in challenges if c.target == self.role]
        if not my_challenges:
            return []

        challenges_text = "\n".join(
            f"- [{c.challenger.value}] 质疑: {c.challenge} (依据: {c.supporting_evidence})"
            for c in my_challenges
        )
        prompt = (
            f"你是{self._role_name()}。以下是其他分析师对你报告的质疑:\n\n"
            f"{challenges_text}\n\n"
            f"你的原始结论: {self._last_report.to_summary_text()}\n\n"
            f"请逐一回应这些质疑。如果质疑合理，请调整你的信心度和观点。"
            f"如果质疑不成立，请给出反驳证据。\n"
            f"请明确标注回应后你的新信心度（0-100）。"
        )
        try:
            text = await self.llm.call_text(
                system_prompt=self._debate_system_prompt(),
                user_message=prompt,
            )
            return self._parse_responses(text, my_challenges)
        except Exception as e:
            logger.warning(f"[{self.role.value}] 回应质疑失败: {e}")
            return []

    async def vote(self) -> Optional[Vote]:
        """Round 3: 投票。"""
        if not self.is_online or not self._last_report:
            return None

        prompt = (
            f"你是{self._role_name()}。经过交叉审查和辩论后，\n"
            f"请给出你的最终评级和信心度。\n\n"
            f"你的当前结论: {self._last_report.to_summary_text()}\n\n"
            f"请输出:\n"
            f"1. 最终评级: strong_buy / buy / neutral / sell / strong_sell\n"
            f"2. 最终信心度: 0-100\n"
            f"3. 一句话理由"
        )
        try:
            text = await self.llm.call_text(
                system_prompt=self._debate_system_prompt(),
                user_message=prompt,
            )
            return self._parse_vote(text)
        except Exception as e:
            logger.warning(f"[{self.role.value}] 投票失败: {e}")
            return None

    # === 内部方法 ===

    def _role_name(self) -> str:
        names = {
            AgentRole.FUNDAMENTAL: "基本面分析师",
            AgentRole.MACRO: "宏观分析师",
            AgentRole.SENTIMENT: "情绪分析师",
        }
        return names.get(self.role, self.role.value)

    def _debate_system_prompt(self) -> str:
        return (
            f"你是一位专业的{self._role_name()}，正在参与投资分析辩论。"
            f"请保持专业、客观、有理有据。"
            f"当有充分理由时，应该修改自己的观点和信心度。"
        )

    def _parse_challenges(self, text: str) -> list[Challenge]:
        """从 LLM 文本中解析质疑（尽力解析，不强求完美格式）。"""
        challenges = []
        lines = text.strip().split("\n")
        current = {}
        for line in lines:
            line = line.strip()
            if not line:
                if current.get("challenge"):
                    challenges.append(self._build_challenge(current))
                    current = {}
                continue
            if "质疑" in line or "问题" in line or line.startswith("-") or line.startswith("1") or line.startswith("2"):
                if current.get("challenge"):
                    challenges.append(self._build_challenge(current))
                current = {"challenge": line.lstrip("-0123456789.、 ")}
            elif "依据" in line or "证据" in line or "原因" in line:
                current["evidence"] = line.split(":", 1)[-1].strip() if ":" in line else line
            else:
                current.setdefault("challenge", "")
                current["challenge"] += " " + line

        if current.get("challenge"):
            challenges.append(self._build_challenge(current))

        return challenges[:2]

    def _build_challenge(self, data: dict) -> Challenge:
        target_roles = [r for r in AgentRole if r != self.role]
        return Challenge(
            challenger=self.role,
            target=target_roles[0] if target_roles else self.role,
            claim_challenged=data.get("challenge", "")[:100],
            challenge_type=ChallengeType.MISSING_CONTEXT,
            challenge=data.get("challenge", ""),
            supporting_evidence=data.get("evidence", ""),
            confidence=self._last_report.confidence if self._last_report else 50,
        )

    def _parse_responses(
        self, text: str, challenges: list[Challenge]
    ) -> list[ChallengeResponse]:
        """从 LLM 文本中解析质疑回应。"""
        import re

        conf_match = re.search(r"信心度[：:]\s*(\d+)", text)
        new_conf = int(conf_match.group(1)) if conf_match else (
            self._last_report.confidence if self._last_report else 50
        )
        old_conf = self._last_report.confidence if self._last_report else 50

        responses = []
        for c in challenges:
            responses.append(ChallengeResponse(
                responder=self.role,
                original_challenge=c,
                response=text[:500],
                confidence_before=old_conf,
                confidence_after=min(max(new_conf, 0), 100),
                position_changed=abs(new_conf - old_conf) >= 10,
            ))

        if self._last_report:
            self._last_report.confidence = min(max(new_conf, 0), 100)

        return responses

    def _parse_vote(self, text: str) -> Vote:
        """从 LLM 文本中解析投票。"""
        import re

        text_lower = text.lower()
        rating = Rating.NEUTRAL
        for r in Rating:
            if r.value in text_lower:
                rating = r
                break

        conf_match = re.search(r"信心度[：:]\s*(\d+)", text)
        if not conf_match:
            conf_match = re.search(r"(\d+)\s*%", text)
        confidence = int(conf_match.group(1)) if conf_match else (
            self._last_report.confidence if self._last_report else 50
        )

        reasoning_match = re.search(r"理由[：:]\s*(.+)", text)
        reasoning = reasoning_match.group(1).strip() if reasoning_match else text[:100]

        return Vote(
            agent=self.role,
            rating=rating,
            confidence=min(max(confidence, 0), 100),
            reasoning=reasoning,
        )
