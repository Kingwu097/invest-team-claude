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
from agents.advisor import AdvisorAgent
from agents.quant import QuantAgent
from agents.risk_officer import RiskOfficerAgent
from agents.trader import TraderAgent
from agents.performance import PerformanceTracker
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

    # Phase 3: 决策层
    print(f"\n💼 Phase 3: 决策层（理财顾问 + 量化研究员）...\n")
    advisor = AdvisorAgent(llm)
    quant_agent = QuantAgent(llm)

    proposal_task = advisor.generate_proposal(consensus, reports)
    quant_task = quant_agent.assess(stock_code, stock_name, reports)
    results_34 = await asyncio.gather(proposal_task, quant_task, return_exceptions=True)

    proposal = results_34[0] if not isinstance(results_34[0], Exception) else None
    quant_assessment = results_34[1] if not isinstance(results_34[1], Exception) else None

    if proposal:
        print(f"  ✅ 理财顾问: {proposal.action.value} | 仓位 {proposal.target_position_pct}% | 信心度 {proposal.confidence}%")
    else:
        print(f"  ❌ 理财顾问: 建议生成失败")
    if quant_assessment:
        print(f"  ✅ 量化研究员: 综合评分 {quant_assessment.composite_score}/100 | 仓位 {quant_assessment.position_sizing_pct}%")
    else:
        print(f"  ❌ 量化研究员: 评估失败")

    # Phase 4: 审查层
    risk_review = None
    if proposal:
        print(f"\n🛡️  Phase 4: 审查层（风控总监审核）...\n")
        risk_officer = RiskOfficerAgent(llm)
        risk_review = await risk_officer.review(proposal, quant_assessment, consensus)
        if risk_review:
            result_names = {"approved": "✅ 通过", "approved_with_conditions": "⚠️ 有条件通过", "rejected": "❌ 驳回", "needs_revision": "🔄 需修改"}
            print(f"  {result_names.get(risk_review.result.value, risk_review.result.value)} | 风险评分 {risk_review.risk_score}/100 | 批准仓位 {risk_review.approved_position_pct}%")
            for w in risk_review.warnings:
                print(f"  ⚠️ {w}")

    # Phase 5: 执行反馈层
    print(f"\n📋 Phase 5: 执行反馈层...\n")
    trade_record = None
    perf_summary = None
    if proposal:
        # 获取当前价格
        current_price = None
        try:
            from data.market import get_stock_history
            hist = get_stock_history(stock_code, days=5)
            if hist is not None and len(hist) > 0:
                current_price = float(hist.iloc[-1]["收盘"])
        except Exception:
            pass

        trader = TraderAgent()
        trade_record = await trader.execute_trade(proposal, risk_review, current_price)
        if trade_record:
            status = "✅ 已执行" if trade_record.executed else "⏸️ 未执行"
            print(f"  {status}: {trade_record.action.value} | 仓位 {trade_record.position_pct}%")
            if trade_record.entry_price:
                print(f"  执行价: {trade_record.entry_price}")
            if trade_record.stop_loss_price:
                print(f"  止损: {trade_record.stop_loss_price} | 止盈: {trade_record.take_profit_price}")

        # 绩效记录
        tracker = PerformanceTracker()
        tracker.record_trade(
            session_id="cli_" + datetime.now().strftime("%Y%m%d%H%M%S"),
            stock_code=stock_code, stock_name=stock_name,
            rating=consensus.final_rating.value,
            confidence=consensus.consensus_confidence,
            action=proposal.action.value,
            position_pct=trade_record.position_pct if trade_record else 0,
            entry_price=current_price,
        )
        perf_summary = tracker.get_summary()
        print(f"  📊 累计分析 {perf_summary.total_analyses} 次 | 平均信心度 {perf_summary.avg_confidence}%")

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
    if proposal:
        print("\n" + proposal.to_markdown())
    if quant_assessment:
        print("\n" + quant_assessment.to_markdown())
    if risk_review:
        print("\n" + risk_review.to_markdown())
    if trade_record:
        print("\n" + trade_record.to_markdown())
    if perf_summary:
        print("\n" + perf_summary.to_markdown())

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
        nargs="+",
        help="A 股股票代码（支持多只，如 600519 300750 000858）",
    )
    parser.add_argument(
        "--chat", "-c",
        action="store_true",
        help="进入自然语言交互模式",
    )
    args = parser.parse_args()

    if args.chat:
        asyncio.run(run_chat_mode())
    elif args.stock:
        if len(args.stock) == 1:
            asyncio.run(run_analysis(args.stock[0]))
        else:
            asyncio.run(run_portfolio_analysis(args.stock))
    else:
        parser.print_help()


async def run_chat_mode():
    """自然语言交互模式。"""
    from agents.chat import (
        parse_intent, parse_intent_with_llm, get_help_text,
        IntentType,
    )
    from agents.performance import PerformanceTracker

    print(f"\n{'='*60}")
    print("  投资理财专家团队 — 自然语言交互模式")
    print(f"{'='*60}")
    print(get_help_text())

    llm = None
    try:
        llm = LLMClient()
    except Exception:
        pass

    while True:
        try:
            query = input("\n💬 你: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n再见！")
            break

        if not query:
            continue
        if query.lower() in ("退出", "exit", "quit", "q"):
            print("再见！")
            break

        # 解析意图
        if llm:
            intent = await parse_intent_with_llm(query, llm)
        else:
            intent = parse_intent(query)

        if intent.intent_type == IntentType.HELP:
            print(get_help_text())

        elif intent.intent_type == IntentType.PERFORMANCE:
            tracker = PerformanceTracker()
            summary = tracker.get_summary()
            print(f"\n{summary.to_markdown()}")
            trades = tracker.list_trades(limit=10)
            if trades:
                print("\n### 最近交易记录")
                for t in trades:
                    print(f"  {t.get('analysis_date','')} | {t.get('stock_name', t['stock_code'])} | "
                          f"{t.get('action','-')} | {t.get('rating','-')} ({t.get('confidence',0)}%)")

        elif intent.intent_type == IntentType.SINGLE_STOCK:
            print(f"\n📊 分析 {intent.stock_codes[0]}...")
            try:
                await run_analysis(intent.stock_codes[0])
            except Exception as e:
                print(f"❌ 分析失败: {e}")

        elif intent.intent_type in (IntentType.MULTI_STOCK, IntentType.SECTOR):
            label = f"板块 [{intent.sector}]" if intent.sector else "组合"
            print(f"\n📊 {label}分析: {', '.join(intent.stock_codes)}...")
            try:
                await run_portfolio_analysis(intent.stock_codes)
            except Exception as e:
                print(f"❌ 分析失败: {e}")

        elif intent.intent_type == IntentType.UNKNOWN:
            print("🤔 没有识别到股票代码或意图。试试：")
            print("  · 输入股票代码：600519")
            print("  · 输入股票名称：分析茅台")
            print("  · 输入板块名称：新能源板块")
            print("  · 输入 '帮助' 查看更多用法")


async def run_portfolio_analysis(stock_codes: list[str]):
    """多股票组合分析。"""
    from agents.performance import PerformanceTracker

    start_time = time.time()
    print(f"\n{'='*60}")
    print(f"  投资组合分析: {', '.join(stock_codes)}")
    print(f"{'='*60}\n")

    results = []
    for i, code in enumerate(stock_codes, 1):
        print(f"\n{'─'*40}")
        print(f"  [{i}/{len(stock_codes)}] 分析 {code}")
        print(f"{'─'*40}")
        try:
            await run_analysis(code)
        except Exception as e:
            print(f"  ❌ {code} 分析失败: {e}")

    elapsed = time.time() - start_time

    # 组合绩效
    tracker = PerformanceTracker()
    perf = tracker.get_summary()
    trades = tracker.list_trades(limit=len(stock_codes))

    print(f"\n{'='*60}")
    print(f"  组合分析完成 | {len(stock_codes)} 只股票 | 总耗时 {elapsed:.0f}s")
    print(f"{'='*60}\n")

    print("## 投资组合汇总\n")
    print("| 股票 | 操作 | 仓位 | 评级 | 信心度 |")
    print("|------|------|------|------|--------|")
    for t in trades:
        print(f"| {t.get('stock_name', t['stock_code'])} | {t.get('action', '-')} | {t.get('position_pct', 0)}% | {t.get('rating', '-')} | {t.get('confidence', 0)}% |")

    # 检查总仓位
    total_pct = sum(t.get("position_pct", 0) for t in trades)
    cash_pct = max(0, 100 - total_pct)
    print(f"\n**总仓位**: {total_pct:.1f}% | **现金**: {cash_pct:.1f}%")

    print(f"\n{perf.to_markdown()}")


if __name__ == "__main__":
    main()
