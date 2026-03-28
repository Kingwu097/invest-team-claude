"""辩论协调器。管理三轮辩论流程，生成共识报告。

Round 1: 陈述与交叉审查 — 各 Agent 审查其他 Agent 的报告摘要
Round 2: 质疑与反驳 — Agent 回应针对自己的质疑
Round 3: 投票与共识生成 — 信心度加权投票，生成共识报告
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from agents.base import BaseAgent
from models.report import (
    AnalysisReport,
    Challenge,
    ChallengeResponse,
    ConsensusReport,
    DebateRound,
    RoundType,
    Vote,
)

logger = logging.getLogger(__name__)


class DebateOrchestrator:
    """辩论协调器。"""

    def __init__(self, agents: list[BaseAgent]):
        if len(agents) < 2:
            raise ValueError("辩论至少需要 2 个 Agent")
        self.agents = agents
        self.rounds: list[DebateRound] = []
        self._total_tokens = 0

    async def run_debate(
        self,
        reports: list[AnalysisReport],
    ) -> ConsensusReport:
        """执行完整辩论流程。"""
        online_agents = [a for a in self.agents if a.is_online]
        if not online_agents:
            raise RuntimeError("所有 Agent 均离线，无法进行辩论")

        if len(online_agents) == 1:
            logger.warning("仅 1 个 Agent 在线，跳过辩论直接出报告")
            report = reports[0]
            vote = Vote(
                agent=report.agent_role,
                rating=report.rating,
                confidence=report.confidence,
                reasoning=report.summary,
            )
            return ConsensusReport.from_votes(
                stock_code=report.stock_code,
                stock_name=report.stock_name,
                votes=[vote],
                agreements=[report.summary],
                disagreements=[],
                insights=[],
                debate_summary="仅一个 Agent 在线，未进行辩论。",
                total_tokens=0,
            )

        logger.info(f"开始辩论: {len(online_agents)} 个 Agent 参与")

        # Round 1: 交叉审查
        r1 = await self._round1_cross_review(online_agents, reports)
        self.rounds.append(r1)

        # Round 2: 质疑反驳
        r2 = await self._round2_challenge_response(
            online_agents, r1.challenges
        )
        self.rounds.append(r2)

        # Round 3: 投票共识
        r3, consensus = await self._round3_vote_consensus(
            online_agents, reports
        )
        self.rounds.append(r3)

        consensus.total_token_usage = sum(r.token_usage for r in self.rounds)
        return consensus

    async def _round1_cross_review(
        self,
        agents: list[BaseAgent],
        reports: list[AnalysisReport],
    ) -> DebateRound:
        """Round 1: 各 Agent 交叉审查其他 Agent 的报告摘要。"""
        logger.info("═══ Round 1: 陈述与交叉审查 ═══")

        summaries = {r.agent_role: r.to_summary_text() for r in reports}

        tasks = []
        for agent in agents:
            other_summaries = [
                s for role, s in summaries.items() if role != agent.role
            ]
            tasks.append(agent.cross_review(other_summaries))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_challenges = []
        for result in results:
            if isinstance(result, list):
                all_challenges.extend(result)
            elif isinstance(result, Exception):
                logger.warning(f"交叉审查出错: {result}")

        logger.info(f"Round 1 完成: {len(all_challenges)} 条质疑")

        return DebateRound(
            round_number=1,
            round_type=RoundType.CROSS_REVIEW,
            challenges=all_challenges,
            token_usage=0,
        )

    async def _round2_challenge_response(
        self,
        agents: list[BaseAgent],
        challenges: list[Challenge],
    ) -> DebateRound:
        """Round 2: Agent 回应针对自己的质疑。"""
        logger.info("═══ Round 2: 质疑与反驳 ═══")

        tasks = [agent.respond_to_challenges(challenges) for agent in agents]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_responses = []
        for result in results:
            if isinstance(result, list):
                all_responses.extend(result)
            elif isinstance(result, Exception):
                logger.warning(f"质疑回应出错: {result}")

        confidence_changes = [
            f"{r.responder.value}: {r.confidence_before}% → {r.confidence_after}%"
            for r in all_responses
            if r.position_changed
        ]
        if confidence_changes:
            logger.info(f"Round 2 信心度变化: {', '.join(confidence_changes)}")

        return DebateRound(
            round_number=2,
            round_type=RoundType.CHALLENGE_RESPONSE,
            responses=all_responses,
            token_usage=0,
        )

    async def _round3_vote_consensus(
        self,
        agents: list[BaseAgent],
        reports: list[AnalysisReport],
    ) -> tuple[DebateRound, ConsensusReport]:
        """Round 3: 投票与共识生成。"""
        logger.info("═══ Round 3: 投票与共识生成 ═══")

        tasks = [agent.vote() for agent in agents]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        votes = [r for r in results if isinstance(r, Vote)]
        if not votes:
            raise RuntimeError("所有 Agent 投票失败")

        for v in votes:
            logger.info(
                f"投票: {v.agent.value} → {v.rating.value} ({v.confidence}%)"
            )

        # 生成共识要点
        agreements, disagreements = self._analyze_consensus(reports, votes)
        insights = self._generate_insights(reports, votes)
        debate_summary = self._build_debate_summary()

        round3 = DebateRound(
            round_number=3,
            round_type=RoundType.VOTE_CONSENSUS,
            votes=votes,
            token_usage=0,
        )

        consensus = ConsensusReport.from_votes(
            stock_code=reports[0].stock_code,
            stock_name=reports[0].stock_name,
            votes=votes,
            agreements=agreements,
            disagreements=disagreements,
            insights=insights,
            debate_summary=debate_summary,
            total_tokens=0,
        )

        status = ""
        if consensus.is_deadlock:
            status = "⚠️ 未达成共识"
        elif consensus.is_high_divergence:
            status = "⚡ 高分歧"
        else:
            status = "✅ 共识达成"

        logger.info(
            f"Round 3 完成: {status} — "
            f"{consensus.final_rating.value} ({consensus.consensus_confidence}%)"
        )

        return round3, consensus

    def _analyze_consensus(
        self, reports: list[AnalysisReport], votes: list[Vote]
    ) -> tuple[list[str], list[str]]:
        """分析共识和分歧。"""
        agreements = []
        disagreements = []

        # 共同识别的风险
        all_risks = []
        for r in reports:
            all_risks.extend(r.risks)
        if all_risks:
            agreements.append(f"共同关注的风险领域: {', '.join(list(set(all_risks))[:3])}")

        # 评级一致性
        ratings = [v.rating for v in votes]
        if len(set(ratings)) == 1:
            agreements.append(f"三方一致看{ratings[0].value}")
        else:
            unique = set(ratings)
            disagreements.append(
                f"评级分歧: {', '.join(f'{v.agent.value}={v.rating.value}' for v in votes)}"
            )

        return agreements, disagreements

    def _generate_insights(
        self, reports: list[AnalysisReport], votes: list[Vote]
    ) -> list[str]:
        """生成可执行洞察。"""
        insights = []
        high_conf = [v for v in votes if v.confidence >= 75]
        if high_conf:
            strongest = max(high_conf, key=lambda v: v.confidence)
            insights.append(
                f"最高信心度来自{strongest.agent.value}分析师 "
                f"({strongest.confidence}%): {strongest.reasoning}"
            )

        # 高分歧提示
        confs = [v.confidence for v in votes]
        if max(confs) - min(confs) > 40:
            insights.append(
                "⚠️ 分析师之间信心度差距大，建议关注低信心度分析师的顾虑"
            )

        return insights

    def _build_debate_summary(self) -> str:
        """构建辩论过程摘要。"""
        lines = []
        for r in self.rounds:
            if r.round_type == RoundType.CROSS_REVIEW:
                lines.append(f"Round 1: {len(r.challenges)} 条质疑提出")
            elif r.round_type == RoundType.CHALLENGE_RESPONSE:
                changed = [
                    resp for resp in r.responses if resp.position_changed
                ]
                lines.append(
                    f"Round 2: {len(r.responses)} 条回应, "
                    f"{len(changed)} 次观点修正"
                )
            elif r.round_type == RoundType.VOTE_CONSENSUS:
                lines.append(f"Round 3: {len(r.votes)} 票投出")
        return " → ".join(lines)
