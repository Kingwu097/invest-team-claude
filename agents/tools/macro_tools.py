"""宏观经济数据工具。修复数据时效性问题。"""

import logging
from datetime import datetime

from agents.tools import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class LPRTool(BaseTool):
    name = "china_lpr"
    description = "获取中国最新 LPR 利率数据（1年期/5年期贷款市场报价利率）"

    def execute(self, stock_code: str = "", **kwargs) -> ToolResult:
        import akshare as ak
        df = ak.macro_china_lpr()
        if df is None or df.empty:
            return ToolResult(
                tool_name=self.name, success=False,
                data_text="[LPR 数据不可用]", error="Empty",
            )
        recent = df.tail(6)
        text_lines = ["### 近 6 期 LPR 利率"]
        for _, row in recent.iterrows():
            text_lines.append(
                f"- {row['TRADE_DATE']}: 1年期 {row['LPR1Y']}% | 5年期 {row['LPR5Y']}%"
            )
        latest = df.iloc[-1]
        return ToolResult(
            tool_name=self.name, success=True,
            data_text="\n".join(text_lines),
            raw_data=df.tail(12),
            data_date=str(latest["TRADE_DATE"]),
            source="中国人民银行",
        )


class PMITool(BaseTool):
    name = "china_pmi"
    description = "获取中国财新制造业 PMI 数据（反映制造业景气度，50以上为扩张）"

    def execute(self, stock_code: str = "", **kwargs) -> ToolResult:
        import akshare as ak
        df = ak.macro_china_cx_pmi_yearly()
        if df is None or df.empty:
            return ToolResult(
                tool_name=self.name, success=False,
                data_text="[PMI 数据不可用]", error="Empty",
            )
        recent = df.tail(6)
        text_lines = ["### 近 6 期财新制造业 PMI"]
        for _, row in recent.iterrows():
            val = row["今值"]
            status = "扩张" if float(val) > 50 else "收缩"
            text_lines.append(
                f"- {row['日期']}: {val} ({status}) | 预测: {row['预测值']} | 前值: {row['前值']}"
            )
        latest = df.iloc[-1]
        return ToolResult(
            tool_name=self.name, success=True,
            data_text="\n".join(text_lines),
            raw_data=recent,
            data_date=str(latest["日期"]),
            source="财新/Markit",
        )


class IndustryBoardsTool(BaseTool):
    name = "industry_boards"
    description = "获取 A 股行业板块排名（涨跌幅排行，判断板块轮动和行业热度）"

    def execute(self, stock_code: str = "", **kwargs) -> ToolResult:
        import akshare as ak
        df = ak.stock_board_industry_name_em()
        if df is None or df.empty:
            return ToolResult(
                tool_name=self.name, success=False,
                data_text="[行业板块数据不可用]", error="Empty",
            )
        top10 = df.head(10)
        bottom5 = df.tail(5)

        text_lines = ["### 行业板块排名"]
        text_lines.append("\n**涨幅前 10:**")
        for _, row in top10.iterrows():
            items = [f"{k}: {v}" for k, v in row.items() if str(v).strip()]
            text_lines.append(f"- {' | '.join(items[:4])}")
        text_lines.append("\n**跌幅前 5:**")
        for _, row in bottom5.iterrows():
            items = [f"{k}: {v}" for k, v in row.items() if str(v).strip()]
            text_lines.append(f"- {' | '.join(items[:4])}")

        return ToolResult(
            tool_name=self.name, success=True,
            data_text="\n".join(text_lines),
            raw_data=df,
            data_date=datetime.now().strftime("%Y-%m-%d"),
            source="东方财富",
        )


class ChinaCPITool(BaseTool):
    name = "china_cpi"
    description = "获取中国 CPI 同比数据（居民消费价格指数，反映通胀水平）"

    def execute(self, stock_code: str = "", **kwargs) -> ToolResult:
        import akshare as ak
        try:
            df = ak.macro_china_cpi_yearly()
            if df is None or df.empty:
                raise ValueError("Empty")
            recent = df.tail(6)
            text_lines = ["### 近 6 期 CPI 数据"]
            for _, row in recent.iterrows():
                text_lines.append(f"- {row.iloc[0]}: 今值 {row.iloc[1]} | 前值 {row.iloc[-1]}")
            return ToolResult(
                tool_name=self.name, success=True,
                data_text="\n".join(text_lines),
                raw_data=recent,
                data_date=str(recent.iloc[-1].iloc[0]),
                source="国家统计局",
            )
        except Exception as e:
            return ToolResult(
                tool_name=self.name, success=False,
                data_text=f"[CPI 数据不可用: {e}]", error=str(e),
            )
