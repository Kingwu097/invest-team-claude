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
    description = "搜索互联网获取最新的行业研报、政策解读、市场分析（用于补充 akshare 数据不足的信息）"
    parameters_description = "query: 搜索关键词（会自动拼接股票代码）"

    def execute(self, stock_code: str, **kwargs) -> ToolResult:
        query = kwargs.get("query", "")
        if not query:
            # 自动构建搜索词
            from data.market import get_stock_info
            info = get_stock_info(stock_code)
            name = info.get("股票简称", stock_code) if info else stock_code
            query = f"{name} {stock_code} stock analysis investment outlook 2026"

        try:
            from ddgs import DDGS
            results = DDGS().text(query, max_results=5)

            if not results:
                return ToolResult(
                    tool_name=self.name, success=True,
                    data_text=f"[搜索 '{query}' 无结果]",
                    source="DuckDuckGo",
                )

            text_lines = [f"### Web 搜索: {query}", ""]
            for r in results:
                title = r.get("title", "")
                body = r.get("body", "")[:200]
                href = r.get("href", "")
                text_lines.append(f"**{title}**")
                text_lines.append(f"{body}")
                text_lines.append(f"[来源: {href}]")
                text_lines.append("")

            return ToolResult(
                tool_name=self.name, success=True,
                data_text="\n".join(text_lines),
                raw_data=results,
                data_date=datetime.now().strftime("%Y-%m-%d"),
                source="DuckDuckGo",
            )
        except Exception as e:
            logger.warning(f"Web 搜索失败: {e}")
            return ToolResult(
                tool_name=self.name, success=False,
                data_text=f"[Web 搜索失败: {e}]",
                error=str(e),
            )


class IndustryResearchTool(BaseTool):
    name = "industry_research"
    description = "搜索行业研究报告和政策动态，获取标的所在行业的最新分析"

    def execute(self, stock_code: str, **kwargs) -> ToolResult:
        from data.market import get_stock_info
        info = get_stock_info(stock_code)
        name = info.get("股票简称", stock_code) if info else stock_code
        industry = info.get("行业", "") if info else ""

        queries = [
            f"{industry or name} industry analysis outlook 2026",
            f"{name} {industry} policy regulation China",
        ]

        try:
            from ddgs import DDGS
            all_results = []
            for q in queries:
                results = DDGS().text(q, max_results=3)
                all_results.extend(results)

            if not all_results:
                return ToolResult(
                    tool_name=self.name, success=True,
                    data_text=f"[行业研究搜索无结果: {industry or name}]",
                    source="DuckDuckGo",
                )

            text_lines = [f"### 行业研究: {industry or name}", ""]
            for r in all_results[:6]:
                text_lines.append(f"**{r.get('title', '')}**")
                text_lines.append(f"{r.get('body', '')[:200]}")
                text_lines.append("")

            return ToolResult(
                tool_name=self.name, success=True,
                data_text="\n".join(text_lines),
                raw_data=all_results,
                data_date=datetime.now().strftime("%Y-%m-%d"),
                source="DuckDuckGo",
            )
        except Exception as e:
            return ToolResult(
                tool_name=self.name, success=False,
                data_text=f"[行业研究搜索失败: {e}]",
                error=str(e),
            )
