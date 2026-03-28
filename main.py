#!/usr/bin/env python3
"""投资理财专家团队 CLI 入口。

用法: python main.py --stock 600519
"""

import argparse
import asyncio
import logging
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from config.llm_client import LLMClient, LLMError
from config.settings import settings
from agents.fundamental import FundamentalAgent
from agents.macro import MacroAgent
from agents.sentiment import SentimentAgent
from debate.orchestrator import DebateOrchestrator
from models.report import AnalysisReport


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def validate_stock_code(code: str) -> str:
    """校验 A 股代码格式。"""
    code = code.strip()
    if not re.match(r"^[036]\d{5}$", code):
        raise argparse.ArgumentTypeError(
            f"无效的 A 股代码: {code}（应为 6 位数字，以 0/3/6 开头）"
        )
    return code


async def run_analysis(stock_code: str):
    """执行完整分析流程。"""
    start_time = time.time()

    # 初始化 LLM 客户端
    try:
        llm = LLMClient()
    except LLMError as e:
        logger.error(f"❌ {e}")
        logger.error("请检查 .env 文件中的 API Key 配置。参考 .env.example")
        sys.exit(1)

    # 获取股票名称
    from data.market import get_stock_info
    stock_info = get_stock_info(stock_code)
    stock_name = stock_info.get("股票简称", stock_code) if stock_info else stock_code

    print(f"\n{'='*60}")
    print(f"  投资理财专家团队分析: {stock_name} ({stock_code})")
    print(f"{'='*60}\n")

    # 初始化三个 Agent
    agents = [
        FundamentalAgent(llm),
        MacroAgent(llm),
        SentimentAgent(llm),
    ]

    # Phase 1: 三个 Agent 并行分析
    print("📊 Phase 1: 情报收集（三个分析师并行分析）...\n")
    tasks = [agent.analyze(stock_code, stock_name) for agent in agents]
    reports_raw = await asyncio.gather(*tasks, return_exceptions=True)

    reports: list[AnalysisReport] = []
    for i, result in enumerate(reports_raw):
        if isinstance(result, AnalysisReport):
            reports.append(result)
            print(f"  ✅ {agents[i]._role_name()}: {result.rating.value} ({result.confidence}%)")
        elif isinstance(result, Exception):
            print(f"  ❌ {agents[i]._role_name()}: 离线 — {result}")
        else:
            print(f"  ❌ {agents[i]._role_name()}: 无结果")

    if not reports:
        logger.error("所有 Agent 均失败，无法进行分析。")
        sys.exit(1)

    # Phase 2: 辩论
    print(f"\n🗣️  Phase 2: 团队辩论（{len(reports)} 个分析师参与）...\n")
    online_agents = [a for a in agents if a.is_online]
    orchestrator = DebateOrchestrator(online_agents)
    consensus = await orchestrator.run_debate(reports)

    elapsed = time.time() - start_time

    # 输出报告
    print(f"\n{'='*60}")
    print(f"  分析完成 | 耗时 {elapsed:.1f}s | Token: {llm.total_tokens:,}")
    print(f"{'='*60}\n")

    # 构建完整 Markdown 报告
    full_report = _build_full_report(
        stock_name, stock_code, reports, orchestrator, consensus, elapsed, llm.total_tokens
    )

    # 输出到终端
    print(consensus.to_markdown())

    # 保存到文件
    output_dir = settings.OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_path = output_dir / f"{stock_code}_{timestamp}.md"
    json_path = output_dir / f"{stock_code}_{timestamp}.json"

    md_path.write_text(full_report, encoding="utf-8")
    json_path.write_text(consensus.model_dump_json(indent=2), encoding="utf-8")

    print(f"\n📄 报告已保存:")
    print(f"  Markdown: {md_path}")
    print(f"  JSON:     {json_path}")


def _build_full_report(
    stock_name, stock_code, reports, orchestrator, consensus, elapsed, total_tokens
) -> str:
    """构建完整 Markdown 报告。"""
    lines = [
        f"# {stock_name} ({stock_code}) 投资分析报告",
        f"\n*生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
        f"*耗时: {elapsed:.1f}s | Token: {total_tokens:,}*\n",
        "---\n",
        consensus.to_markdown(),
        "\n---\n",
        "## 详细分析报告\n",
    ]
    for report in reports:
        lines.append(report.to_markdown())
        lines.append("\n---\n")

    # 辩论过程
    lines.append("## 辩论过程记录\n")
    for round_ in orchestrator.rounds:
        if round_.round_number == 1:
            lines.append("### Round 1: 交叉审查\n")
            for c in round_.challenges:
                lines.append(
                    f"- **{c.challenger.value}** → {c.target.value}: {c.challenge}"
                )
        elif round_.round_number == 2:
            lines.append("\n### Round 2: 质疑与反驳\n")
            for r in round_.responses:
                change = ""
                if r.position_changed:
                    change = f" (**信心度变化: {r.confidence_before}% → {r.confidence_after}%**)"
                lines.append(
                    f"- **{r.responder.value}** 回应: {r.response[:200]}{change}"
                )
        elif round_.round_number == 3:
            lines.append("\n### Round 3: 投票\n")
            for v in round_.votes:
                lines.append(
                    f"- **{v.agent.value}**: {v.rating.value} ({v.confidence}%) — {v.reasoning}"
                )

    lines.append(
        "\n---\n*本报告由 AI 生成，仅供参考，不构成投资建议。投资有风险，入市需谨慎。*"
    )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="投资理财专家团队 — Multi-Agent 投资分析系统"
    )
    parser.add_argument(
        "--stock", "-s",
        type=validate_stock_code,
        required=True,
        help="A 股股票代码（如 600519）",
    )
    args = parser.parse_args()

    asyncio.run(run_analysis(args.stock))


if __name__ == "__main__":
    main()
