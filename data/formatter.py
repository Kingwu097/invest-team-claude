"""DataFormatter：将原始数据格式化为 LLM 可读的文本上下文。

Agent 通过选择不同的 section 来控制注入 prompt 的数据内容，
但格式化逻辑集中在这里，避免 DRY 违反。
"""

import logging
from typing import Any, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class DataFormatter:
    """将结构化数据格式化为 LLM 上下文文本。"""

    @staticmethod
    def format_stock_info(info: Optional[dict]) -> str:
        if not info:
            return "[个股信息: 数据不可用]"
        lines = ["### 个股基本信息"]
        for k, v in info.items():
            lines.append(f"- {k}: {v}")
        return "\n".join(lines)

    @staticmethod
    def format_history(df: Optional[pd.DataFrame], last_n: int = 10) -> str:
        if df is None or df.empty:
            return "[历史行情: 数据不可用]"
        recent = df.tail(last_n)
        lines = [f"### 近 {last_n} 个交易日行情"]
        for _, row in recent.iterrows():
            date = row.get("日期", row.get("date", ""))
            close = row.get("收盘", row.get("close", ""))
            change = row.get("涨跌幅", row.get("change_pct", ""))
            volume = row.get("成交量", row.get("volume", ""))
            lines.append(f"- {date}: 收盘 {close}, 涨跌幅 {change}%, 成交量 {volume}")
        return "\n".join(lines)

    @staticmethod
    def format_financial(df: Optional[pd.DataFrame], last_n: int = 4) -> str:
        if df is None or df.empty:
            return "[财务摘要: 数据不可用]"
        recent = df.head(last_n)
        lines = ["### 近期财务摘要"]
        for _, row in recent.iterrows():
            items = [f"{k}: {v}" for k, v in row.items() if pd.notna(v)]
            lines.append("- " + " | ".join(items[:8]))
        return "\n".join(lines)

    @staticmethod
    def format_key_metrics(metrics: Optional[dict]) -> str:
        if not metrics:
            return "[关键指标: 数据不可用]"
        lines = ["### 关键财务指标"]
        for k, v in metrics.items():
            lines.append(f"- {k}: {v}")
        return "\n".join(lines)

    @staticmethod
    def format_news(news: Optional[list[dict]], limit: int = 10) -> str:
        if not news:
            return "[新闻: 无相关新闻]"
        lines = [f"### 近期新闻 (共 {len(news)} 条)"]
        for item in news[:limit]:
            title = item.get("新闻标题", item.get("title", ""))
            time_ = item.get("发布时间", item.get("publish_time", ""))
            content = item.get("新闻内容", item.get("content", ""))[:100]
            lines.append(f"- [{time_}] {title}")
            if content:
                lines.append(f"  {content}...")
        return "\n".join(lines)

    @staticmethod
    def format_north_flow(df: Optional[pd.DataFrame], last_n: int = 5) -> str:
        if df is None or df.empty:
            return "[北向资金: 数据不可用]"
        recent = df.tail(last_n)
        lines = [f"### 近 {last_n} 日北向资金净流入"]
        for _, row in recent.iterrows():
            items = [f"{k}: {v}" for k, v in row.items() if pd.notna(v)]
            lines.append("- " + " | ".join(items[:4]))
        return "\n".join(lines)

    @staticmethod
    def format_margin(df: Optional[pd.DataFrame], last_n: int = 5) -> str:
        if df is None or df.empty:
            return "[融资融券: 数据不可用]"
        recent = df.head(last_n)
        lines = [f"### 近期融资融券数据"]
        for _, row in recent.iterrows():
            items = [f"{k}: {v}" for k, v in row.items() if pd.notna(v)]
            lines.append("- " + " | ".join(items[:6]))
        return "\n".join(lines)

    @staticmethod
    def format_macro_gdp(df: Optional[pd.DataFrame], last_n: int = 4) -> str:
        if df is None or df.empty:
            return "[宏观GDP: 数据不可用]"
        recent = df.tail(last_n)
        lines = ["### 近期宏观 GDP 数据"]
        for _, row in recent.iterrows():
            items = [f"{k}: {v}" for k, v in row.items() if pd.notna(v)]
            lines.append("- " + " | ".join(items[:6]))
        return "\n".join(lines)

    @staticmethod
    def format_industry_boards(df: Optional[pd.DataFrame], top_n: int = 10) -> str:
        if df is None or df.empty:
            return "[行业板块: 数据不可用]"
        top = df.head(top_n)
        lines = [f"### 行业板块排名 (Top {top_n})"]
        for _, row in top.iterrows():
            items = [f"{k}: {v}" for k, v in row.items() if pd.notna(v)]
            lines.append("- " + " | ".join(items[:5]))
        return "\n".join(lines)

    @classmethod
    def build_context(cls, sections: dict[str, Any]) -> str:
        """组装多个数据 section 为完整上下文。"""
        formatters = {
            "stock_info": cls.format_stock_info,
            "history": cls.format_history,
            "financial": cls.format_financial,
            "key_metrics": cls.format_key_metrics,
            "news": cls.format_news,
            "north_flow": cls.format_north_flow,
            "margin": cls.format_margin,
            "macro_gdp": cls.format_macro_gdp,
            "industry_boards": cls.format_industry_boards,
        }
        parts = []
        for name, data in sections.items():
            formatter = formatters.get(name)
            if formatter:
                parts.append(formatter(data))
            else:
                logger.warning(f"Unknown section: {name}")
        return "\n\n".join(parts)
