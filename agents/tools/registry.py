"""Agent 工具集注册工厂。为每个 Agent 角色配置默认工具。"""

from agents.tools import ToolRegistry
from agents.tools.market_tools import (
    StockInfoTool, StockHistoryTool,
    FinancialSummaryTool, KeyMetricsTool,
)
from agents.tools.macro_tools import (
    LPRTool, PMITool, IndustryBoardsTool, ChinaCPITool,
)
from agents.tools.sentiment_tools import (
    StockNewsTool, NorthFlowTool, MarginDataTool, WebSearchTool,
)


def create_fundamental_tools() -> ToolRegistry:
    """基本面分析师的工具集。"""
    registry = ToolRegistry()
    registry.register(StockInfoTool())
    registry.register(StockHistoryTool())
    registry.register(FinancialSummaryTool())
    registry.register(KeyMetricsTool())
    return registry


def create_macro_tools() -> ToolRegistry:
    """宏观分析师的工具集。"""
    registry = ToolRegistry()
    registry.register(StockInfoTool())
    registry.register(StockHistoryTool())
    registry.register(KeyMetricsTool())
    registry.register(LPRTool())
    registry.register(PMITool())
    registry.register(IndustryBoardsTool())
    registry.register(ChinaCPITool())
    return registry


def create_sentiment_tools() -> ToolRegistry:
    """情绪分析师的工具集。"""
    registry = ToolRegistry()
    registry.register(StockInfoTool())
    registry.register(StockHistoryTool())
    registry.register(StockNewsTool())
    registry.register(NorthFlowTool())
    registry.register(MarginDataTool())
    registry.register(WebSearchTool())
    return registry
