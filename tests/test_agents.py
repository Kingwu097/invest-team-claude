"""P1 测试: Agent 基类模板方法。"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any

from agents.base import BaseAgent
from config.llm_client import LLMClient
from models.report import AgentRole, AnalysisReport, Rating


class MockAgent(BaseAgent):
    """测试用 Agent 子类。"""

    @property
    def role(self) -> AgentRole:
        return AgentRole.FUNDAMENTAL

    @property
    def focus_metrics(self) -> list[str]:
        return ["PE", "ROE"]

    def get_system_prompt(self) -> str:
        return "You are a test agent."

    def fetch_data(self, stock_code: str) -> dict[str, Any]:
        return {"stock_info": {"股票简称": "测试"}}


class TestAgentAnalyze:
    @pytest.mark.asyncio
    async def test_full_pipeline_success(self):
        mock_llm = MagicMock(spec=LLMClient)
        mock_report = AnalysisReport(
            agent_role=AgentRole.FUNDAMENTAL,
            stock_code="600519",
            stock_name="贵州茅台",
            rating=Rating.BUY,
            confidence=85,
            summary="估值偏低",
        )
        mock_llm.call_structured = AsyncMock(return_value=mock_report)

        agent = MockAgent(mock_llm)
        result = await agent.analyze("600519", "贵州茅台")

        assert result is not None
        assert result.rating == Rating.BUY
        assert result.confidence == 85
        assert agent.is_online

    @pytest.mark.asyncio
    async def test_llm_failure_marks_offline(self):
        mock_llm = MagicMock(spec=LLMClient)
        mock_llm.call_structured = AsyncMock(side_effect=Exception("API Error"))

        agent = MockAgent(mock_llm)
        result = await agent.analyze("600519", "贵州茅台")

        assert result is None
        assert not agent.is_online

    @pytest.mark.asyncio
    async def test_vote_parsing(self):
        mock_llm = MagicMock(spec=LLMClient)
        mock_llm.call_text = AsyncMock(
            return_value="最终评级: buy\n信心度: 78\n理由: 估值合理偏低"
        )

        agent = MockAgent(mock_llm)
        agent._last_report = AnalysisReport(
            agent_role=AgentRole.FUNDAMENTAL,
            stock_code="600519",
            stock_name="贵州茅台",
            rating=Rating.BUY,
            confidence=85,
            summary="test",
        )

        vote = await agent.vote()
        assert vote is not None
        assert vote.rating == Rating.BUY
        assert vote.confidence == 78
        assert "估值" in vote.reasoning
