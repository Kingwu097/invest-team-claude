"""行情和基本面相关工具。"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from agents.tools import BaseTool, ToolResult
from data._retry import retry_fetch

logger = logging.getLogger(__name__)


class StockInfoTool(BaseTool):
    name = "stock_info"
    description = "获取个股基本信息（总市值、流通市值、PE/PB、涨跌幅等实时数据）"

    def execute(self, stock_code: str, **kwargs) -> ToolResult:
        import akshare as ak
        df = ak.stock_individual_info_em(symbol=stock_code)
        info = {row["item"]: row["value"] for _, row in df.iterrows()}
        text_lines = [f"### {info.get('股票简称', stock_code)} ({stock_code}) 基本信息"]
        for k, v in info.items():
            text_lines.append(f"- {k}: {v}")
        return ToolResult(
            tool_name=self.name, success=True,
            data_text="\n".join(text_lines),
            raw_data=info,
            data_date=datetime.now().strftime("%Y-%m-%d"),
            source="东方财富",
        )


class StockHistoryTool(BaseTool):
    name = "stock_history"
    description = "获取个股近期行情走势（日K线：开盘/收盘/最高/最低/成交量/换手率）"
    parameters_description = "days: 获取最近多少天，默认 60"

    def execute(self, stock_code: str, **kwargs) -> ToolResult:
        import akshare as ak
        days = kwargs.get("days", 60)
        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
        df = ak.stock_zh_a_hist(
            symbol=stock_code, period="daily",
            start_date=start, end_date=end, adjust="qfq",
        )
        if df is None or df.empty:
            return ToolResult(
                tool_name=self.name, success=False,
                data_text="[行情数据不可用]", error="Empty data",
            )
        latest = df.iloc[-1]
        first = df.iloc[0]
        change_pct = ((latest["收盘"] - first["收盘"]) / first["收盘"] * 100)

        text_lines = [
            f"### 近 {len(df)} 个交易日行情",
            f"- 最新收盘: {latest['收盘']} ({latest['日期']})",
            f"- 区间涨跌幅: {change_pct:.2f}%",
            f"- 区间最高: {df['最高'].max()} / 最低: {df['最低'].min()}",
            f"- 近5日平均成交量: {df.tail(5)['成交量'].mean():,.0f}",
            f"- 近5日平均换手率: {df.tail(5)['换手率'].mean():.2f}%",
            "",
            "近10个交易日:",
        ]
        for _, row in df.tail(10).iterrows():
            text_lines.append(
                f"  {row['日期']} | 收盘: {row['收盘']} | "
                f"涨跌幅: {row['涨跌幅']}% | 成交量: {row['成交量']:,.0f}"
            )
        return ToolResult(
            tool_name=self.name, success=True,
            data_text="\n".join(text_lines),
            raw_data=df,
            data_date=str(latest["日期"]),
            source="东方财富",
        )


class FinancialSummaryTool(BaseTool):
    name = "financial_summary"
    description = "获取公司最新季度财务数据（净利润、营收、ROE、毛利率、资产负债率等）"

    def execute(self, stock_code: str, **kwargs) -> ToolResult:
        import akshare as ak
        df = ak.stock_financial_abstract_ths(symbol=stock_code)
        if df is None or df.empty:
            return ToolResult(
                tool_name=self.name, success=False,
                data_text="[财务数据不可用]", error="Empty data",
            )
        recent = df.tail(4)
        text_lines = ["### 最近 4 个季度财务摘要"]
        for _, row in recent.iterrows():
            text_lines.append(f"\n**{row['报告期']}**")
            for col in df.columns[1:]:
                val = row[col]
                if pd.notna(val) and str(val).strip():
                    text_lines.append(f"- {col}: {val}")

        latest = df.iloc[-1]
        return ToolResult(
            tool_name=self.name, success=True,
            data_text="\n".join(text_lines),
            raw_data=df,
            data_date=str(latest["报告期"]),
            source="同花顺",
        )


class KeyMetricsTool(BaseTool):
    name = "key_metrics"
    description = "获取个股实时估值指标（动态PE、PB、总市值、流通市值、涨跌幅）"

    def execute(self, stock_code: str, **kwargs) -> ToolResult:
        import akshare as ak
        df = ak.stock_individual_info_em(symbol=stock_code)
        metrics = {}
        for _, row in df.iterrows():
            metrics[row["item"]] = row["value"]

        key_fields = [
            "总市值", "流通市值", "市盈率(动态)", "市净率",
            "60日涨跌幅", "年初至今涨跌幅", "行业", "上市时间",
        ]
        text_lines = ["### 关键估值指标"]
        for f in key_fields:
            if f in metrics:
                text_lines.append(f"- {f}: {metrics[f]}")

        return ToolResult(
            tool_name=self.name, success=True,
            data_text="\n".join(text_lines),
            raw_data=metrics,
            data_date=datetime.now().strftime("%Y-%m-%d"),
            source="东方财富",
        )
