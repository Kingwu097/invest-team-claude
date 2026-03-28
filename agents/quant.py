"""量化研究员 Agent。基于历史数据做定量分析和风险度量。

接收：stock_code + AnalysisReport[]
输出：QuantAssessment（估值/动量/质量评分 + 风险指标 + 仓位建议）
"""

import logging
import math
from datetime import datetime, timedelta
from typing import Optional

from config.llm_client import LLMClient
from models.report import AgentRole, AnalysisReport, QuantAssessment

logger = logging.getLogger(__name__)


class QuantAgent:
    """量化研究员。用数学模型做定量评估。"""

    def __init__(self, llm: LLMClient):
        self.llm = llm
        self.is_online = True

    @property
    def role(self) -> AgentRole:
        return AgentRole.QUANT

    def _role_name(self) -> str:
        return "量化研究员"

    async def assess(
        self,
        stock_code: str,
        stock_name: str,
        reports: list[AnalysisReport],
    ) -> Optional[QuantAssessment]:
        """执行定量评估。先用数据计算量化指标，再用 LLM 做综合评估。"""
        try:
            # 1. 计算量化指标
            quant_data = self._compute_quant_metrics(stock_code)

            # 2. LLM 综合评估
            system_prompt = (
                "你是一位量化研究员，专注于用数学模型评估投资标的。\n\n"
                "你的分析框架：\n"
                "1. 估值评分（0-100）：PE/PB 分位数、相对行业的折溢价\n"
                "2. 动量评分（0-100）：价格趋势强度、量价配合度\n"
                "3. 质量评分（0-100）：ROE 稳定性、盈利质量、现金流\n"
                "4. 综合评分 = 估值×0.4 + 动量×0.3 + 质量×0.3\n"
                "5. 建议仓位 = 综合评分/100 × 15%（上限 15%）\n\n"
                "用数据说话，给出具体数值。"
            )

            report_summaries = "\n".join(r.to_summary_text() for r in reports)
            user_msg = (
                f"请对 {stock_name}({stock_code}) 进行量化评估。\n\n"
                f"## 量化计算结果\n{quant_data}\n\n"
                f"## 分析师报告摘要\n{report_summaries}"
            )

            assessment = await self.llm.call_structured(
                system_prompt=system_prompt,
                user_message=user_msg,
                response_model=QuantAssessment,
            )
            assessment.stock_code = stock_code
            assessment.stock_name = stock_name

            # 覆盖计算值（如果成功计算了的话）
            if quant_data != "[数据不足]":
                self._apply_computed_metrics(assessment, stock_code)

            logger.info(
                f"[quant] 综合评分: {assessment.composite_score}/100 | "
                f"建议仓位: {assessment.position_sizing_pct}%"
            )
            return assessment
        except Exception as e:
            logger.error(f"[quant] 评估失败: {e}")
            self.is_online = False
            return None

    def _compute_quant_metrics(self, stock_code: str) -> str:
        """基于历史数据计算量化指标。"""
        try:
            import akshare as ak
            import numpy as np

            end = datetime.now().strftime("%Y%m%d")
            start = (datetime.now() - timedelta(days=120)).strftime("%Y%m%d")
            df = ak.stock_zh_a_hist(
                symbol=stock_code, period="daily",
                start_date=start, end_date=end, adjust="qfq",
            )
            if df is None or len(df) < 20:
                return "[数据不足]"

            closes = df["收盘"].values.astype(float)
            volumes = df["成交量"].values.astype(float)

            # 波动率（年化）
            returns = np.diff(np.log(closes))
            vol_30d = np.std(returns[-30:]) * np.sqrt(252) * 100 if len(returns) >= 30 else None

            # 最大回撤
            peak = np.maximum.accumulate(closes[-60:])
            drawdown = (closes[-60:] - peak) / peak * 100
            max_dd = float(np.min(drawdown))

            # 动量（20日 / 60日收益率）
            mom_20 = (closes[-1] / closes[-20] - 1) * 100 if len(closes) >= 20 else 0
            mom_60 = (closes[-1] / closes[-60] - 1) * 100 if len(closes) >= 60 else 0

            # 量价配合（近20日成交量趋势 vs 价格趋势）
            vol_trend = np.mean(volumes[-5:]) / np.mean(volumes[-20:]) if np.mean(volumes[-20:]) > 0 else 1

            lines = [
                f"- 30日年化波动率: {vol_30d:.1f}%" if vol_30d else "- 波动率: 数据不足",
                f"- 60日最大回撤: {max_dd:.1f}%",
                f"- 20日动量: {mom_20:+.1f}%",
                f"- 60日动量: {mom_60:+.1f}%",
                f"- 量价配合度: {vol_trend:.2f} (>1 放量, <1 缩量)",
                f"- 近期均价: {np.mean(closes[-5:]):.2f}",
                f"- 数据区间: {df.iloc[0]['日期']} ~ {df.iloc[-1]['日期']}",
            ]
            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"[quant] 量化计算失败: {e}")
            return "[数据不足]"

    def _apply_computed_metrics(self, assessment: QuantAssessment, stock_code: str):
        """将实际计算的风险指标写入评估结果。"""
        try:
            import akshare as ak
            import numpy as np

            end = datetime.now().strftime("%Y%m%d")
            start = (datetime.now() - timedelta(days=120)).strftime("%Y%m%d")
            df = ak.stock_zh_a_hist(
                symbol=stock_code, period="daily",
                start_date=start, end_date=end, adjust="qfq",
            )
            if df is None or len(df) < 30:
                return

            closes = df["收盘"].values.astype(float)
            returns = np.diff(np.log(closes))

            # 30日波动率
            assessment.volatility_30d = round(float(np.std(returns[-30:]) * np.sqrt(252) * 100), 1)

            # 60日最大回撤
            peak = np.maximum.accumulate(closes[-60:])
            drawdown = (closes[-60:] - peak) / peak * 100
            assessment.max_drawdown_60d = round(float(np.min(drawdown)), 1)

            # 夏普比率估算（假设无风险利率 2%）
            ann_return = float(np.mean(returns[-60:]) * 252 * 100)
            ann_vol = float(np.std(returns[-60:]) * np.sqrt(252) * 100)
            if ann_vol > 0:
                assessment.sharpe_estimate = round((ann_return - 2) / ann_vol, 2)
        except Exception:
            pass
