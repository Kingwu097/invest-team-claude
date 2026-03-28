"""情绪分析师 Agent。关注市场情绪、资金流向、舆情。"""

from typing import Any

from agents.base import BaseAgent
from config.llm_client import LLMClient
from data import market, news as news_mod
from models.report import AgentRole


class SentimentAgent(BaseAgent):

    @property
    def role(self) -> AgentRole:
        return AgentRole.SENTIMENT

    @property
    def focus_metrics(self) -> list[str]:
        return [
            "北向资金流向", "融资融券余额", "新闻情绪倾向",
            "社交媒体热度", "成交量变化", "换手率",
        ]

    def get_system_prompt(self) -> str:
        return (
            "你是一位资深的情绪分析师，专注于通过市场情绪和资金面信号评估投资标的。\n\n"
            "你的分析框架:\n"
            "1. 资金面: 北向资金净流入/流出趋势，融资融券余额变化\n"
            "2. 新闻情绪: 近期新闻的正面/负面倾向，重大事件影响\n"
            "3. 交易信号: 成交量异动、换手率变化、量价关系\n"
            "4. 市场热度: 标的被关注程度，是否有过度乐观/悲观\n\n"
            "输出要求:\n"
            "- 给出明确的评级 (strong_buy/buy/neutral/sell/strong_sell)\n"
            "- 给出信心度 (0-100)\n"
            "- 区分短期情绪波动和中期趋势\n"
            "- 识别市场可能过度反应的风险\n"
            "- 关注反转信号"
        )

    def fetch_data(self, stock_code: str) -> dict[str, Any]:
        return {
            "stock_info": market.get_stock_info(stock_code),
            "history": market.get_stock_history(stock_code, days=60),
            "news": news_mod.get_stock_news(stock_code),
            "north_flow": news_mod.get_north_flow(),
            "margin": news_mod.get_margin_data(stock_code),
        }
