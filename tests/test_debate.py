"""P0 测试: 辩论/共识算法。"""

import pytest
from models.report import (
    AgentRole, ConsensusReport, Rating, Vote,
    Challenge, ChallengeType, DebateRound, RoundType,
)


class TestConsensusAlgorithm:
    def test_consensus_majority_reached(self):
        """2/3 看多 → 共识 = 看多。"""
        votes = [
            Vote(agent=AgentRole.FUNDAMENTAL, rating=Rating.BUY, confidence=80, reasoning=""),
            Vote(agent=AgentRole.MACRO, rating=Rating.BUY, confidence=70, reasoning=""),
            Vote(agent=AgentRole.SENTIMENT, rating=Rating.SELL, confidence=50, reasoning=""),
        ]
        cr = ConsensusReport.from_votes(
            "600519", "贵州茅台", votes, [], [], [], "", 0
        )
        assert cr.final_rating == Rating.BUY
        assert not cr.is_deadlock
        assert not cr.is_high_divergence

    def test_consensus_high_divergence(self):
        """信心度差距 > 40 → is_high_divergence。"""
        votes = [
            Vote(agent=AgentRole.FUNDAMENTAL, rating=Rating.BUY, confidence=95, reasoning=""),
            Vote(agent=AgentRole.MACRO, rating=Rating.BUY, confidence=50, reasoning=""),
            Vote(agent=AgentRole.SENTIMENT, rating=Rating.NEUTRAL, confidence=40, reasoning=""),
        ]
        cr = ConsensusReport.from_votes(
            "600519", "贵州茅台", votes, [], [], [], "", 0
        )
        assert cr.is_high_divergence  # 95 - 40 = 55 > 40

    def test_consensus_deadlock(self):
        """三方各持不同评级 → 僵局。"""
        votes = [
            Vote(agent=AgentRole.FUNDAMENTAL, rating=Rating.BUY, confidence=60, reasoning=""),
            Vote(agent=AgentRole.MACRO, rating=Rating.SELL, confidence=60, reasoning=""),
            Vote(agent=AgentRole.SENTIMENT, rating=Rating.NEUTRAL, confidence=60, reasoning=""),
        ]
        cr = ConsensusReport.from_votes(
            "600519", "贵州茅台", votes, [], [], [], "", 0
        )
        assert cr.is_deadlock

    def test_consensus_weighted_majority(self):
        """信心度加权：高信心度的 BUY 胜过低信心度的 SELL。"""
        votes = [
            Vote(agent=AgentRole.FUNDAMENTAL, rating=Rating.BUY, confidence=90, reasoning=""),
            Vote(agent=AgentRole.MACRO, rating=Rating.SELL, confidence=30, reasoning=""),
            Vote(agent=AgentRole.SENTIMENT, rating=Rating.BUY, confidence=70, reasoning=""),
        ]
        cr = ConsensusReport.from_votes(
            "600519", "贵州茅台", votes, [], [], [], "", 0
        )
        # BUY: 90+70=160, SELL: 30 → BUY wins
        assert cr.final_rating == Rating.BUY

    def test_no_votes_raises(self):
        with pytest.raises(ValueError, match="No votes"):
            ConsensusReport.from_votes(
                "600519", "贵州茅台", [], [], [], [], "", 0
            )


class TestDebateRound:
    def test_round_creation(self):
        r = DebateRound(
            round_number=1,
            round_type=RoundType.CROSS_REVIEW,
            challenges=[
                Challenge(
                    challenger=AgentRole.MACRO,
                    target=AgentRole.FUNDAMENTAL,
                    claim_challenged="PE偏低",
                    challenge_type=ChallengeType.MISSING_CONTEXT,
                    challenge="未考虑行业下行",
                    confidence=72,
                )
            ],
        )
        assert r.round_number == 1
        assert len(r.challenges) == 1
        assert r.challenges[0].challenger == AgentRole.MACRO
