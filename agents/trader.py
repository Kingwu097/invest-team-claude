"""交易执行员 Agent。记录模拟交易操作。

接收：RiskReview (审核通过的建议)
输出：TradeRecord（交易记录）
"""

import logging
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from models.report import (
    AgentRole, InvestmentProposal, PortfolioAction,
    RiskReview, RiskReviewResult,
)

logger = logging.getLogger(__name__)


class TradeRecord(BaseModel):
    """交易记录。"""
    stock_code: str
    stock_name: str
    timestamp: datetime = Field(default_factory=datetime.now)
    action: PortfolioAction
    position_pct: float
    entry_price: Optional[float] = None
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None
    reasoning: str = ""
    risk_review_result: str = ""
    executed: bool = True

    def to_markdown(self) -> str:
        action_names = {
            PortfolioAction.BUY: "买入", PortfolioAction.SELL: "卖出",
            PortfolioAction.HOLD: "持有", PortfolioAction.INCREASE: "加仓",
            PortfolioAction.DECREASE: "减仓",
        }
        lines = [
            f"### 交易执行: {self.stock_name} ({self.stock_code})",
            f"**操作**: {action_names.get(self.action, self.action.value)} | "
            f"**仓位**: {self.position_pct}%",
            f"**时间**: {self.timestamp.strftime('%Y-%m-%d %H:%M')}",
        ]
        if self.entry_price:
            lines.append(f"**执行价格**: {self.entry_price}")
        if self.stop_loss_price:
            lines.append(f"**止损价**: {self.stop_loss_price} | **止盈价**: {self.take_profit_price}")
        lines.append(f"**风控审核**: {self.risk_review_result}")
        lines.append(f"**执行备注**: {self.reasoning}")
        return "\n".join(lines)


class TraderAgent:
    """交易执行员。将审核通过的投资建议转化为模拟交易记录。"""

    def __init__(self):
        self.is_online = True

    @property
    def role(self) -> AgentRole:
        return AgentRole.FUNDAMENTAL  # 复用，不需要独立角色

    def _role_name(self) -> str:
        return "交易执行员"

    async def execute_trade(
        self,
        proposal: InvestmentProposal,
        risk_review: Optional[RiskReview],
        current_price: Optional[float] = None,
    ) -> Optional[TradeRecord]:
        """执行模拟交易。"""
        try:
            # 检查风控审核结果
            if risk_review and risk_review.result == RiskReviewResult.REJECTED:
                logger.info("[trader] 风控驳回，不执行交易")
                return TradeRecord(
                    stock_code=proposal.stock_code,
                    stock_name=proposal.stock_name,
                    action=PortfolioAction.HOLD,
                    position_pct=0,
                    reasoning="风控总监驳回投资建议",
                    risk_review_result="rejected",
                    executed=False,
                )

            # 使用风控批准的仓位（而非建议仓位）
            approved_pct = proposal.target_position_pct
            if risk_review and risk_review.approved_position_pct is not None:
                approved_pct = risk_review.approved_position_pct

            # 计算止损止盈价格
            entry_price = current_price
            stop_loss_price = None
            take_profit_price = None
            if current_price and proposal.stop_loss_pct:
                stop_loss_price = round(current_price * (1 - proposal.stop_loss_pct / 100), 2)
            if current_price and proposal.take_profit_pct:
                take_profit_price = round(current_price * (1 + proposal.take_profit_pct / 100), 2)

            record = TradeRecord(
                stock_code=proposal.stock_code,
                stock_name=proposal.stock_name,
                action=proposal.action,
                position_pct=approved_pct,
                entry_price=entry_price,
                stop_loss_price=stop_loss_price,
                take_profit_price=take_profit_price,
                reasoning=f"基于理财顾问建议（信心度{proposal.confidence}%），风控批准仓位{approved_pct}%",
                risk_review_result=risk_review.result.value if risk_review else "no_review",
                executed=True,
            )

            logger.info(
                f"[trader] 执行: {record.action.value} | "
                f"仓位 {record.position_pct}% | 价格 {entry_price}"
            )
            return record
        except Exception as e:
            logger.error(f"[trader] 执行失败: {e}")
            self.is_online = False
            return None
