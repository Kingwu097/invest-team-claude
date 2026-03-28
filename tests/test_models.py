"""P0 测试: 数据模型序列化/校验。"""

import pytest
from datetime import datetime

from models.report import (
    AgentRole,
    AnalysisReport,
    AnalysisSection,
    ConsensusReport,
    Rating,
    Vote,
)


class TestAnalysisReport:
    def test_serialization_json_roundtrip(self):
        report = AnalysisReport(
            agent_role=AgentRole.FUNDAMENTAL,
            stock_code="600519",
            stock_name="贵州茅台",
            rating=Rating.BUY,
            confidence=85,
            summary="估值偏低，盈利质量高",
            key_metrics={"pe_ratio": 25.3, "roe": 30.1},
            risks=["行业增速放缓"],
            data_sources=["akshare"],
        )
        json_str = report.model_dump_json()
        restored = AnalysisReport.model_validate_json(json_str)
        assert restored.rating == Rating.BUY
        assert restored.confidence == 85
        assert restored.stock_code == "600519"
        assert restored.key_metrics["pe_ratio"] == 25.3

    def test_serialization_markdown(self):
        report = AnalysisReport(
            agent_role=AgentRole.MACRO,
            stock_code="600519",
            stock_name="贵州茅台",
            rating=Rating.SELL,
            confidence=72,
            summary="宏观环境不利",
            key_metrics={"gdp_growth": 5.2},
            risks=["利率上升"],
        )
        md = report.to_markdown()
        assert "宏观分析师" in md
        assert "看空" in md
        assert "72%" in md

    def test_validation_confidence_range(self):
        with pytest.raises(Exception):
            AnalysisReport(
                agent_role=AgentRole.FUNDAMENTAL,
                stock_code="600519",
                stock_name="test",
                rating=Rating.BUY,
                confidence=101,
                summary="test",
            )
        with pytest.raises(Exception):
            AnalysisReport(
                agent_role=AgentRole.FUNDAMENTAL,
                stock_code="600519",
                stock_name="test",
                rating=Rating.BUY,
                confidence=-1,
                summary="test",
            )

    def test_validation_stock_code(self):
        with pytest.raises(Exception):
            AnalysisReport(
                agent_role=AgentRole.FUNDAMENTAL,
                stock_code="abc",
                stock_name="test",
                rating=Rating.BUY,
                confidence=50,
                summary="test",
            )
        with pytest.raises(Exception):
            AnalysisReport(
                agent_role=AgentRole.FUNDAMENTAL,
                stock_code="100000",
                stock_name="test",
                rating=Rating.BUY,
                confidence=50,
                summary="test",
            )

    def test_to_summary_text(self):
        report = AnalysisReport(
            agent_role=AgentRole.SENTIMENT,
            stock_code="000001",
            stock_name="平安银行",
            rating=Rating.NEUTRAL,
            confidence=60,
            summary="情绪中性",
            key_metrics={"north_flow": "净流入"},
            risks=["成交量萎缩"],
        )
        summary = report.to_summary_text()
        assert "sentiment" in summary
        assert "60%" in summary
        assert "情绪中性" in summary


class TestConsensusReport:
    def test_from_votes_majority(self):
        votes = [
            Vote(agent=AgentRole.FUNDAMENTAL, rating=Rating.BUY, confidence=85, reasoning="估值低"),
            Vote(agent=AgentRole.MACRO, rating=Rating.BUY, confidence=70, reasoning="政策利好"),
            Vote(agent=AgentRole.SENTIMENT, rating=Rating.NEUTRAL, confidence=60, reasoning="情绪中性"),
        ]
        cr = ConsensusReport.from_votes(
            stock_code="600519", stock_name="贵州茅台",
            votes=votes, agreements=[], disagreements=[],
            insights=[], debate_summary="", total_tokens=0,
        )
        assert cr.final_rating == Rating.BUY
        assert not cr.is_deadlock

    def test_high_divergence(self):
        votes = [
            Vote(agent=AgentRole.FUNDAMENTAL, rating=Rating.STRONG_BUY, confidence=95, reasoning=""),
            Vote(agent=AgentRole.MACRO, rating=Rating.SELL, confidence=50, reasoning=""),
            Vote(agent=AgentRole.SENTIMENT, rating=Rating.BUY, confidence=70, reasoning=""),
        ]
        cr = ConsensusReport.from_votes(
            stock_code="600519", stock_name="贵州茅台",
            votes=votes, agreements=[], disagreements=[],
            insights=[], debate_summary="", total_tokens=0,
        )
        assert cr.is_high_divergence

    def test_deadlock(self):
        votes = [
            Vote(agent=AgentRole.FUNDAMENTAL, rating=Rating.BUY, confidence=60, reasoning=""),
            Vote(agent=AgentRole.MACRO, rating=Rating.SELL, confidence=60, reasoning=""),
            Vote(agent=AgentRole.SENTIMENT, rating=Rating.NEUTRAL, confidence=60, reasoning=""),
        ]
        cr = ConsensusReport.from_votes(
            stock_code="600519", stock_name="贵州茅台",
            votes=votes, agreements=[], disagreements=[],
            insights=[], debate_summary="", total_tokens=0,
        )
        assert cr.is_deadlock

    def test_weighted_confidence(self):
        votes = [
            Vote(agent=AgentRole.FUNDAMENTAL, rating=Rating.BUY, confidence=90, reasoning=""),
            Vote(agent=AgentRole.MACRO, rating=Rating.BUY, confidence=60, reasoning=""),
            Vote(agent=AgentRole.SENTIMENT, rating=Rating.BUY, confidence=30, reasoning=""),
        ]
        cr = ConsensusReport.from_votes(
            stock_code="600519", stock_name="贵州茅台",
            votes=votes, agreements=[], disagreements=[],
            insights=[], debate_summary="", total_tokens=0,
        )
        assert cr.consensus_confidence == 60.0  # (90+60+30)/3
