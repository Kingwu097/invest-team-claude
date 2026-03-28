"""分析管道。将 Phase 1 的 CLI 逻辑重构为可复用的 pipeline，支持事件驱动。

核心流程：
1. 创建 session
2. 并行运行三个 Agent（发布 data_fetch / agent_analysis 事件）
3. 运行辩论（发布 debate 事件）
4. 生成共识报告（发布 consensus 事件）
"""

import asyncio
import logging
import time
import uuid
from datetime import datetime
from typing import Optional

from agents.fundamental import FundamentalAgent
from agents.macro import MacroAgent
from agents.sentiment import SentimentAgent
from agents.advisor import AdvisorAgent
from agents.quant import QuantAgent
from agents.risk_officer import RiskOfficerAgent
from config.llm_client import LLMClient, LLMError
from config.settings import settings
from core.event_bus import EventBus, event_bus
from core.event_store import EventStore
from core.events import AnalysisEvent, EventType
from data.market import get_stock_info
from debate.orchestrator import DebateOrchestrator
from models.report import AnalysisReport, ConsensusReport

logger = logging.getLogger(__name__)


class AnalysisPipeline:
    """分析管道。封装完整的分析+辩论流程，支持事件发布。"""

    def __init__(
        self,
        bus: Optional[EventBus] = None,
        store: Optional[EventStore] = None,
    ):
        self.bus = bus or event_bus
        self.store = store or EventStore()
        self._llm: Optional[LLMClient] = None

    async def run(self, stock_code: str) -> dict:
        """执行完整分析。返回结果字典。"""
        session_id = f"s_{uuid.uuid4().hex[:12]}"
        start_time = time.time()

        # 初始化 LLM
        try:
            self._llm = LLMClient()
        except LLMError as e:
            await self._emit(EventType.ANALYSIS_FAILED, session_id, stock_code,
                             data={"error": str(e)})
            raise

        # 获取股票名称
        stock_info = get_stock_info(stock_code)
        stock_name = stock_info.get("股票简称", stock_code) if stock_info else stock_code

        # 创建 session
        self.store.create_session(session_id, stock_code, stock_name)
        await self._emit(
            EventType.ANALYSIS_STARTED, session_id, stock_code,
            stock_name=stock_name,
            summary=f"开始分析 {stock_name} ({stock_code})",
        )

        try:
            # Phase 1: 三个 Agent 并行分析
            reports = await self._run_agents(session_id, stock_code, stock_name)

            if not reports:
                await self._emit(EventType.ANALYSIS_FAILED, session_id, stock_code,
                                 stock_name=stock_name,
                                 data={"error": "所有 Agent 均失败"})
                self.store.complete_session(session_id, "failed")
                raise RuntimeError("所有 Agent 均失败")

            # Phase 2: 辩论
            consensus, rounds_data = await self._run_debate(
                session_id, stock_code, stock_name, reports
            )

            # Phase 3: 决策层（理财顾问 + 量化研究员）
            proposal, quant_assessment = await self._run_decision(
                session_id, stock_code, stock_name, consensus, reports
            )

            # Phase 4: 审查层（风控总监）
            risk_review = await self._run_risk_review(
                session_id, stock_code, stock_name,
                proposal, quant_assessment, consensus
            )

            elapsed = time.time() - start_time
            total_tokens = self._llm.total_tokens if self._llm else 0

            # 完成
            self.store.complete_session(
                session_id, "completed",
                consensus.final_rating.value,
                consensus.consensus_confidence,
                total_tokens,
            )

            await self._emit(
                EventType.ANALYSIS_COMPLETED, session_id, stock_code,
                stock_name=stock_name,
                rating=consensus.final_rating.value,
                confidence=int(consensus.consensus_confidence),
                data={
                    "elapsed": round(elapsed, 1),
                    "total_tokens": total_tokens,
                    "is_high_divergence": consensus.is_high_divergence,
                    "is_deadlock": consensus.is_deadlock,
                    "has_proposal": proposal is not None,
                    "has_risk_review": risk_review is not None,
                    "risk_result": risk_review.result.value if risk_review else None,
                },
                summary=f"分析完成: {consensus.final_rating.value} ({consensus.consensus_confidence}%)",
            )

            return {
                "session_id": session_id,
                "stock_code": stock_code,
                "stock_name": stock_name,
                "reports": reports,
                "consensus": consensus,
                "rounds": rounds_data,
                "proposal": proposal,
                "quant_assessment": quant_assessment,
                "risk_review": risk_review,
                "elapsed": round(elapsed, 1),
                "total_tokens": total_tokens,
            }

        except Exception as e:
            await self._emit(EventType.ANALYSIS_FAILED, session_id, stock_code,
                             stock_name=stock_name, data={"error": str(e)})
            self.store.complete_session(session_id, "failed")
            raise

    async def _run_agents(
        self, session_id: str, stock_code: str, stock_name: str
    ) -> list[AnalysisReport]:
        """并行运行三个 Agent，发布事件。"""
        agents = [
            FundamentalAgent(self._llm),
            MacroAgent(self._llm),
            SentimentAgent(self._llm),
        ]

        reports: list[AnalysisReport] = []

        for agent in agents:
            await self._emit(
                EventType.DATA_FETCH_STARTED, session_id, stock_code,
                stock_name=stock_name, agent_role=agent.role.value,
                summary=f"{agent._role_name()} 开始获取数据",
            )

        # 自定义并行 —— 包装每个 agent 的 analyze，捕获前后事件
        async def run_agent(agent):
            try:
                await self._emit(
                    EventType.AGENT_ANALYSIS_STARTED, session_id, stock_code,
                    stock_name=stock_name, agent_role=agent.role.value,
                    summary=f"{agent._role_name()} 开始分析",
                )
                report = await agent.analyze(stock_code, stock_name)
                if report:
                    await self._emit(
                        EventType.AGENT_ANALYSIS_COMPLETED, session_id, stock_code,
                        stock_name=stock_name, agent_role=agent.role.value,
                        rating=report.rating.value,
                        confidence=report.confidence,
                        summary=report.summary,
                        data={
                            "key_metrics": report.key_metrics,
                            "risks": report.risks[:3],
                        },
                    )
                    return report
                else:
                    await self._emit(
                        EventType.AGENT_ANALYSIS_FAILED, session_id, stock_code,
                        stock_name=stock_name, agent_role=agent.role.value,
                        summary=f"{agent._role_name()} 分析失败",
                    )
                    return None
            except Exception as e:
                await self._emit(
                    EventType.AGENT_ANALYSIS_FAILED, session_id, stock_code,
                    stock_name=stock_name, agent_role=agent.role.value,
                    data={"error": str(e)},
                    summary=f"{agent._role_name()} 离线: {e}",
                )
                return None

        results = await asyncio.gather(
            *[run_agent(a) for a in agents], return_exceptions=True
        )

        for r in results:
            if isinstance(r, AnalysisReport):
                reports.append(r)

        self._agents = [a for a in agents if a.is_online]
        return reports

    async def _run_debate(
        self, session_id: str, stock_code: str, stock_name: str,
        reports: list[AnalysisReport],
    ) -> tuple[ConsensusReport, list]:
        """运行辩论，发布事件。"""
        await self._emit(
            EventType.DEBATE_STARTED, session_id, stock_code,
            stock_name=stock_name,
            data={"agent_count": len(self._agents)},
            summary=f"开始辩论: {len(self._agents)} 个 Agent 参与",
        )

        orchestrator = DebateOrchestrator(self._agents)

        # Hook into orchestrator rounds for event publishing
        consensus = await orchestrator.run_debate(reports)

        # 发布辩论轮次事件
        for rnd in orchestrator.rounds:
            await self._emit(
                EventType.DEBATE_ROUND_STARTED, session_id, stock_code,
                stock_name=stock_name, round_number=rnd.round_number,
                summary=f"Round {rnd.round_number}: {rnd.round_type.value}",
            )

            # Round 1 质疑事件
            for c in rnd.challenges:
                await self._emit(
                    EventType.DEBATE_CHALLENGE, session_id, stock_code,
                    stock_name=stock_name, round_number=1,
                    agent_role=c.challenger.value,
                    data={
                        "target": c.target.value,
                        "challenge": c.challenge,
                        "evidence": c.supporting_evidence,
                        "challenge_type": c.challenge_type.value,
                    },
                    confidence=c.confidence,
                    summary=f"{c.challenger.value}→{c.target.value}: {c.challenge[:80]}",
                )

            # Round 2 回应事件
            for r in rnd.responses:
                await self._emit(
                    EventType.DEBATE_RESPONSE, session_id, stock_code,
                    stock_name=stock_name, round_number=2,
                    agent_role=r.responder.value,
                    confidence=r.confidence_after,
                    data={
                        "response": r.response[:200],
                        "confidence_before": r.confidence_before,
                        "confidence_after": r.confidence_after,
                        "position_changed": r.position_changed,
                    },
                    summary=f"{r.responder.value}: {r.confidence_before}%→{r.confidence_after}%",
                )
                if r.position_changed:
                    await self._emit(
                        EventType.CONFIDENCE_CHANGED, session_id, stock_code,
                        stock_name=stock_name, round_number=2,
                        agent_role=r.responder.value,
                        confidence=r.confidence_after,
                        data={
                            "before": r.confidence_before,
                            "after": r.confidence_after,
                        },
                    )

            # Round 3 投票事件
            for v in rnd.votes:
                await self._emit(
                    EventType.DEBATE_VOTE, session_id, stock_code,
                    stock_name=stock_name, round_number=3,
                    agent_role=v.agent.value,
                    rating=v.rating.value,
                    confidence=v.confidence,
                    summary=f"{v.agent.value}: {v.rating.value} ({v.confidence}%)",
                )

            await self._emit(
                EventType.DEBATE_ROUND_COMPLETED, session_id, stock_code,
                stock_name=stock_name, round_number=rnd.round_number,
            )

        # 共识事件
        event_type = (
            EventType.CONSENSUS_DEADLOCK if consensus.is_deadlock
            else EventType.CONSENSUS_REACHED
        )
        await self._emit(
            event_type, session_id, stock_code,
            stock_name=stock_name,
            rating=consensus.final_rating.value,
            confidence=int(consensus.consensus_confidence),
            data={
                "is_high_divergence": consensus.is_high_divergence,
                "is_deadlock": consensus.is_deadlock,
                "votes": [
                    {"agent": v.agent.value, "rating": v.rating.value,
                     "confidence": v.confidence, "reasoning": v.reasoning}
                    for v in consensus.individual_votes
                ],
                "agreements": consensus.key_agreements,
                "disagreements": consensus.key_disagreements,
                "insights": consensus.actionable_insights,
            },
            summary=consensus.debate_summary,
        )

        await self._emit(
            EventType.DEBATE_COMPLETED, session_id, stock_code,
            stock_name=stock_name,
        )

        return consensus, orchestrator.rounds

    async def _run_decision(
        self, session_id: str, stock_code: str, stock_name: str,
        consensus: ConsensusReport, reports: list[AnalysisReport],
    ) -> tuple:
        """Phase 3: 决策层——理财顾问 + 量化研究员并行。"""
        # 理财顾问
        await self._emit(
            EventType.PROPOSAL_STARTED, session_id, stock_code,
            stock_name=stock_name, agent_role="advisor",
            summary="理财顾问开始制定投资建议",
        )

        advisor = AdvisorAgent(self._llm)
        quant_agent = QuantAgent(self._llm)

        # 量化研究员
        await self._emit(
            EventType.QUANT_STARTED, session_id, stock_code,
            stock_name=stock_name, agent_role="quant",
            summary="量化研究员开始定量评估",
        )

        # 并行执行
        proposal_task = advisor.generate_proposal(consensus, reports)
        quant_task = quant_agent.assess(stock_code, stock_name, reports)
        proposal, quant_assessment = await asyncio.gather(
            proposal_task, quant_task, return_exceptions=True
        )

        # 处理结果
        if isinstance(proposal, Exception):
            logger.error(f"理财顾问失败: {proposal}")
            proposal = None
        if isinstance(quant_assessment, Exception):
            logger.error(f"量化研究员失败: {quant_assessment}")
            quant_assessment = None

        if proposal:
            await self._emit(
                EventType.PROPOSAL_COMPLETED, session_id, stock_code,
                stock_name=stock_name, agent_role="advisor",
                rating=proposal.action.value,
                confidence=proposal.confidence,
                data={
                    "action": proposal.action.value,
                    "position_pct": proposal.target_position_pct,
                    "time_horizon": proposal.time_horizon,
                    "reasoning": proposal.reasoning[:200],
                    "stop_loss": proposal.stop_loss_pct,
                    "take_profit": proposal.take_profit_pct,
                },
                summary=f"理财顾问: {proposal.action.value} | 仓位 {proposal.target_position_pct}%",
            )

        if quant_assessment:
            await self._emit(
                EventType.QUANT_COMPLETED, session_id, stock_code,
                stock_name=stock_name, agent_role="quant",
                confidence=quant_assessment.composite_score,
                data={
                    "valuation_score": quant_assessment.valuation_score,
                    "momentum_score": quant_assessment.momentum_score,
                    "quality_score": quant_assessment.quality_score,
                    "composite_score": quant_assessment.composite_score,
                    "position_pct": quant_assessment.position_sizing_pct,
                    "volatility": quant_assessment.volatility_30d,
                    "max_drawdown": quant_assessment.max_drawdown_60d,
                    "sharpe": quant_assessment.sharpe_estimate,
                },
                summary=f"量化评分: {quant_assessment.composite_score}/100 | 仓位 {quant_assessment.position_sizing_pct}%",
            )

        return proposal, quant_assessment

    async def _run_risk_review(
        self, session_id: str, stock_code: str, stock_name: str,
        proposal, quant_assessment, consensus: ConsensusReport,
    ):
        """Phase 4: 审查层——风控总监审核。"""
        if not proposal:
            logger.warning("无投资建议，跳过风控审核")
            return None

        await self._emit(
            EventType.RISK_REVIEW_STARTED, session_id, stock_code,
            stock_name=stock_name, agent_role="risk_officer",
            summary="风控总监开始审核",
        )

        risk_officer = RiskOfficerAgent(self._llm)
        risk_review = await risk_officer.review(proposal, quant_assessment, consensus)

        if risk_review:
            await self._emit(
                EventType.RISK_REVIEW_COMPLETED, session_id, stock_code,
                stock_name=stock_name, agent_role="risk_officer",
                data={
                    "result": risk_review.result.value,
                    "risk_score": risk_review.risk_score,
                    "overall_risk": risk_review.overall_risk.value,
                    "approved_position_pct": risk_review.approved_position_pct,
                    "conditions": risk_review.conditions,
                    "warnings": risk_review.warnings,
                    "reasoning": risk_review.reasoning[:200],
                },
                summary=f"风控审核: {risk_review.result.value} | 风险 {risk_review.risk_score}/100 | 批准仓位 {risk_review.approved_position_pct}%",
            )

        return risk_review

    async def _emit(
        self,
        event_type: EventType,
        session_id: str,
        stock_code: str,
        stock_name: str = "",
        agent_role: Optional[str] = None,
        round_number: Optional[int] = None,
        confidence: Optional[int] = None,
        rating: Optional[str] = None,
        summary: Optional[str] = None,
        data: Optional[dict] = None,
    ):
        """创建并发布事件。"""
        event = AnalysisEvent(
            event_type=event_type,
            session_id=session_id,
            stock_code=stock_code,
            stock_name=stock_name,
            agent_role=agent_role,
            round_number=round_number,
            confidence=confidence,
            rating=rating,
            summary=summary,
            data=data or {},
        )
        await self.bus.publish(event)
        await self.store.save_event(event)
