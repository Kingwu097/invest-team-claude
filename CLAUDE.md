# CLAUDE.md — Project Guidelines

## Project Overview
投资理财专家团队系统 (Invest Team Claude)：基于 Multi-Agent 协作的投资分析系统。三个专业 AI 分析师（基本面/宏观/情绪）并行分析，通过结构化辩论达成共识。

## Tech Stack
- **Backend:** Python 3.12+ / asyncio / Pydantic v2
- **LLM:** DeepSeek V3.2 via OpenAI SDK compatible API (`deepseek-chat`)
- **Data:** akshare (A 股行情/财务/新闻)
- **Frontend (Phase 2):** React + TailwindCSS + SSE

## Running
```bash
cp .env.example .env  # Fill in DEEPSEEK_API_KEY
pip install -r requirements.txt
python main.py --stock 600519
```

## Testing
```bash
python -m pytest tests/ -v
```

## Design System
Always read DESIGN.md before making any visual or UI decisions.
All font choices, colors, spacing, and aesthetic direction are defined there.
Do not deviate without explicit user approval.
In QA mode, flag any code that doesn't match DESIGN.md.

## Architecture
- `agents/base.py` — Template method pattern, subclasses override 3 hooks
- `config/llm_client.py` — LLM abstraction (DeepSeek JSON mode → Pydantic fallback)
- `debate/orchestrator.py` — 3-round debate (cross review → challenge → vote)
- `data/formatter.py` — DataFormatter centralizes data→LLM context formatting
- Debate passes structured summaries (not full reports) to control token budget

## Conventions
- Stock codes: 6-digit A-share format (starts with 0/3/6)
- All reports include disclaimer: "本报告由 AI 生成，仅供参考，不构成投资建议。"
- API keys via .env, never hardcoded
