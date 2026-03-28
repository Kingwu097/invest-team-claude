"""新闻和情绪相关工具。"""

import logging
from datetime import datetime
from typing import Optional

from agents.tools import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class StockNewsTool(BaseTool):
    name = "stock_news"
    description = "获取个股最新新闻（标题、来源、发布时间），用于判断近期舆情方向"

    def execute(self, stock_code: str, **kwargs) -> ToolResult:
        import akshare as ak
        df = ak.stock_news_em(symbol=stock_code)
        if df is None or df.empty:
            return ToolResult(
                tool_name=self.name, success=False,
                data_text="[新闻数据不可用]", error="Empty",
            )
        news = df.head(10)
        text_lines = [f"### {stock_code} 最新新闻 (共 {len(df)} 条)"]
        for _, row in news.iterrows():
            title = row.get("新闻标题", "")
            time_str = row.get("发布时间", "")
            source = row.get("文章来源", "")
            content = str(row.get("新闻内容", ""))[:150]
            text_lines.append(f"\n**[{time_str}] {title}** ({source})")
            if content:
                text_lines.append(f"  {content}...")

        latest_time = str(news.iloc[0].get("发布时间", ""))
        return ToolResult(
            tool_name=self.name, success=True,
            data_text="\n".join(text_lines),
            raw_data=news,
            data_date=latest_time[:10] if latest_time else None,
            source="东方财富",
        )


class NorthFlowTool(BaseTool):
    name = "north_flow"
    description = "获取北向资金（沪股通）历史净买入数据，反映外资动向"

    def execute(self, stock_code: str = "", **kwargs) -> ToolResult:
        import akshare as ak
        df = ak.stock_hsgt_hist_em(symbol="沪股通")
        if df is None or df.empty:
            return ToolResult(
                tool_name=self.name, success=False,
                data_text="[北向资金数据不可用]", error="Empty",
            )
        recent = df.tail(10)
        text_lines = ["### 近 10 个交易日北向资金（沪股通）"]
        for _, row in recent.iterrows():
            items = [f"{k}: {v}" for k, v in row.items() if str(v).strip()]
            text_lines.append(f"- {' | '.join(items[:5])}")
        return ToolResult(
            tool_name=self.name, success=True,
            data_text="\n".join(text_lines),
            raw_data=recent,
            data_date=str(recent.iloc[-1].iloc[0]) if len(recent) > 0 else None,
            source="东方财富",
        )


class MarginDataTool(BaseTool):
    name = "margin_data"
    description = "获取两市融资融券汇总数据，反映杠杆资金动向"

    def execute(self, stock_code: str = "", **kwargs) -> ToolResult:
        import akshare as ak
        df = ak.stock_margin_account_info()
        if df is None or df.empty:
            return ToolResult(
                tool_name=self.name, success=False,
                data_text="[融资融券数据不可用]", error="Empty",
            )
        recent = df.head(5)
        text_lines = ["### 近 5 个交易日融资融券汇总"]
        for _, row in recent.iterrows():
            items = [f"{k}: {v}" for k, v in row.items() if str(v).strip()]
            text_lines.append(f"- {' | '.join(items[:6])}")
        return ToolResult(
            tool_name=self.name, success=True,
            data_text="\n".join(text_lines),
            raw_data=recent,
            source="东方财富",
        )


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "搜索互联网获取最新的行业研报、政策解读、市场分析等信息（当 akshare 数据不足时使用）"
    parameters_description = "query: 搜索关键词"

    def execute(self, stock_code: str, **kwargs) -> ToolResult:
        query = kwargs.get("query", f"{stock_code} 最新分析")
        return ToolResult(
            tool_name=self.name, success=False,
            data_text=f"[Web 搜索暂未实现 — 搜索词: {query}]",
            error="Not implemented yet — Phase 3 将通过 MCP 或 SerpAPI 接入",
        )
