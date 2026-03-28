"""宏观分析师 Agent。关注宏观环境、行业景气度、政策面。"""

from typing import Any

from agents.base import BaseAgent
from config.llm_client import LLMClient
from data import market, financial
from models.report import AgentRole

import akshare as ak
from data._retry import retry_fetch


@retry_fetch
def _get_macro_gdp():
    return ak.macro_china_gdp()


@retry_fetch
def _get_industry_boards():
    return ak.stock_board_industry_name_em()


class MacroAgent(BaseAgent):

    @property
    def role(self) -> AgentRole:
        return AgentRole.MACRO

    @property
    def focus_metrics(self) -> list[str]:
        return [
            "GDP增速", "CPI/PPI", "PMI", "M2增速",
            "LPR", "行业板块涨跌", "政策动向",
        ]

    def get_system_prompt(self) -> str:
        return (
            "你是一位资深的宏观分析师，专注于从宏观经济和行业趋势角度评估投资标的。\n\n"
            "你的分析框架:\n"
            "1. 宏观环境: GDP/CPI/PMI/M2 等核心宏观指标趋势\n"
            "2. 货币政策: LPR、国债收益率变化，流动性判断\n"
            "3. 行业景气: 标的所在行业的景气度、板块轮动位置\n"
            "4. 政策分析: 相关产业政策、监管变化对标的的影响\n\n"
            "输出要求:\n"
            "- 给出明确的评级 (strong_buy/buy/neutral/sell/strong_sell)\n"
            "- 给出信心度 (0-100)\n"
            "- 从自上而下的视角分析，关注系统性风险\n"
            "- 识别政策面的利好和利空因素\n"
            "- 判断当前市场周期位置"
        )

    def fetch_data(self, stock_code: str) -> dict[str, Any]:
        return {
            "stock_info": market.get_stock_info(stock_code),
            "history": market.get_stock_history(stock_code, days=250),
            "key_metrics": financial.get_key_metrics(stock_code),
            "macro_gdp": _get_macro_gdp(),
            "industry_boards": _get_industry_boards(),
        }
