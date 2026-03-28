"""基本面分析师 Agent。关注估值、盈利质量、财务健康度。"""

from typing import Any

from agents.base import BaseAgent
from config.llm_client import LLMClient
from data import market, financial
from models.report import AgentRole


class FundamentalAgent(BaseAgent):

    @property
    def role(self) -> AgentRole:
        return AgentRole.FUNDAMENTAL

    @property
    def focus_metrics(self) -> list[str]:
        return [
            "PE/PB/PS", "ROE/ROA", "营收增速", "净利润增速",
            "毛利率", "净利率", "资产负债率", "自由现金流",
        ]

    def get_system_prompt(self) -> str:
        return (
            "你是一位资深的基本面分析师，专注于通过财务数据评估公司内在价值。\n\n"
            "你的分析框架:\n"
            "1. 估值分析: PE/PB/PS 的历史分位和同行对比，判断当前估值水平\n"
            "2. 盈利质量: ROE/ROA 趋势，毛利率和净利率变化，判断盈利可持续性\n"
            "3. 财务健康: 资产负债率、现金流状况，判断财务风险\n"
            "4. 成长性: 营收和利润增速趋势，判断增长动力\n\n"
            "输出要求:\n"
            "- 给出明确的评级 (strong_buy/buy/neutral/sell/strong_sell)\n"
            "- 给出信心度 (0-100)\n"
            "- 用数据说话，引用具体指标数值\n"
            "- 识别 2-3 个关键风险点\n"
            "- 保持客观，避免情绪化判断"
        )

    def fetch_data(self, stock_code: str) -> dict[str, Any]:
        return {
            "stock_info": market.get_stock_info(stock_code),
            "history": market.get_stock_history(stock_code, days=120),
            "financial": financial.get_financial_summary(stock_code),
            "key_metrics": financial.get_key_metrics(stock_code),
        }
