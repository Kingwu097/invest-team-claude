# CLAUDE.md — Project Guidelines

## Project Overview
投资理财专家团队系统 (Invest Team Claude)：基于 Multi-Agent 协作的投资分析系统。8 个专业 AI Agent 组成五层闭环架构，通过结构化辩论达成投资共识。

## Tech Stack
- **Backend:** Python 3.12+ / asyncio / Pydantic v2 / FastAPI
- **LLM:** DeepSeek V3.2 via OpenAI SDK compatible API (`deepseek-chat`)
- **Data:** akshare (A 股行情/财务/新闻) + DuckDuckGo (Web 搜索)
- **Frontend:** React 18 (CDN) + SVG 可视化 + SSE 实时推送

## Running
```bash
# CLI 模式
cp .env.example .env  # Fill in DEEPSEEK_API_KEY
pip install -r requirements.txt
python main.py --stock 600519              # 单股分析
python main.py --stock 600519 300750       # 组合分析
python main.py --chat                      # 自然语言交互

# Dashboard 模式
python -m uvicorn dashboard.server:app --port 8000
```

## Testing
```bash
python -m pytest tests/ -v
```

## Design System
Always read DESIGN.md before making any visual or UI decisions.
All font choices, colors, spacing, and aesthetic direction are defined there.
Do not deviate without explicit user approval.

## Architecture (Five Layers)
1. **情报层**: `agents/fundamental.py`, `agents/macro.py`, `agents/sentiment.py` — 3 个分析师并行分析 + 辩论
2. **决策层**: `agents/advisor.py` (理财顾问), `agents/quant.py` (量化研究员)
3. **审查层**: `agents/risk_officer.py` (风控总监，硬性规则+LLM 审核)
4. **执行层**: `agents/trader.py` (模拟交易)
5. **反馈层**: `agents/performance.py` (绩效跟踪), `agents/evolution.py` (权重自进化)

Key modules:
- `agents/base.py` — Template method pattern, subclasses override 3 hooks
- `agents/tools/` — 14 个可插拔数据工具（每个 Agent 有自己的 ToolRegistry）
- `config/llm_client.py` — LLM abstraction (DeepSeek JSON mode → Pydantic fallback)
- `debate/orchestrator.py` — 3-round debate (cross review → challenge → vote)
- `core/pipeline.py` — 五层分析管道（事件驱动，支持 SSE 推送）
- `core/event_bus.py` + `core/event_store.py` — 事件系统（发布-订阅 + SQLite 持久化）
- `dashboard/server.py` — FastAPI 后端（7 个 API 端点）

## Conventions
- Stock codes: 6-digit A-share format (starts with 0/3/6)
- All reports include disclaimer: "本报告由 AI 生成，仅供参考，不构成投资建议。"
- API keys via .env, never hardcoded
- Agent tools must return ToolResult with data_date and source
- Risk officer applies hard rules: max 20% single stock, high volatility → 10%, deadlock → 5%
