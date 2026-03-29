"""宏观分析师 Agent。关注宏观环境、行业景气度、政策面。

修复：使用 LPR/PMI/CPI 替代过时的 GDP 接口。
"""

from typing import Any

from agents.base import BaseAgent
from agents.tools import ToolRegistry
from agents.tools.registry import create_macro_tools
from config.llm_client import LLMClient
from models.report import AgentRole


class MacroAgent(BaseAgent):

    def __init__(self, llm: LLMClient, tools: ToolRegistry = None):
        super().__init__(llm)
        self._tools = tools or create_macro_tools()

    @property
    def role(self) -> AgentRole:
        return AgentRole.MACRO

    @property
    def tools(self) -> ToolRegistry:
        return self._tools

    @property
    def focus_metrics(self) -> list[str]:
        return [
            "LPR利率趋势", "CPI通胀水平", "PMI景气度",
            "行业板块涨跌", "政策动向", "流动性环境",
        ]

    def get_system_prompt(self) -> str:
        tools_desc = self._tools.get_tools_prompt()
        return (
            "你是一位资深的宏观分析师，专注于从宏观经济和行业趋势角度评估投资标的。\n\n"
            "你的分析框架:\n"
            "1. 货币政策: LPR 利率趋势、降息/加息周期判断\n"
            "2. 经济景气: PMI 扩张/收缩、CPI 通胀水平\n"
            "3. 行业景气: 标的所在行业的板块排名、资金流入方向\n"
            "4. 政策分析: 相关产业政策、监管变化对标的的影响\n\n"
            f"{tools_desc}\n\n"
            "输出要求:\n"
            "- 给出明确的评级 (strong_buy/buy/neutral/sell/strong_sell)\n"
            "- 给出信心度 (0-100)\n"
            "- 从自上而下的视角分析，关注系统性风险\n"
            "- 引用具体宏观数据和数据截止日期\n"
            "- 判断当前市场周期位置"
        )

    def fetch_data(self, stock_code: str) -> dict[str, Any]:
        tool_names = [
            "stock_info", "stock_history", "key_metrics",
            "china_lpr", "china_pmi", "industry_boards", "china_cpi",
            "industry_research",
        ]
        results = self._tools.execute_tools(tool_names, stock_code)
        context = self._tools.build_context(results)
        return {"_tool_context": context}
