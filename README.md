# Invest Team Claude - 投资理财专家团队

基于 Multi-Agent 协作的投资理财专家团队系统。三个专业 AI 分析师（基本面/宏观/情绪）并行分析，通过结构化辩论达成共识，生成投资洞察报告。

## 核心特色

- **Agent 辩论机制**：多个专业 Agent 从不同角度分析，互相质疑挑战，暴露风险盲点
- **可观测的协作过程**：每个 Agent 的推理链、信心度变化、辩论记录全程可追溯
- **实时 Dashboard**：Web 界面实时展示 Agent 分析和辩论过程（时间线 + 圆桌概览 + 信心度图）
- **结构化共识**：信心度加权投票，高分歧标记，未达成共识时保留各方论据

## 快速开始

### CLI 模式

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 API Key
cp .env.example .env
# 编辑 .env 填入你的 DeepSeek API Key

# 3. 验证数据源
python scripts/verify_akshare.py

# 4. 运行分析
python main.py --stock 600519
```

### Dashboard 模式

```bash
# 启动 Dashboard 服务器
python -m uvicorn dashboard.server:app --host 0.0.0.0 --port 8000

# 打开浏览器访问 http://localhost:8000
```

Dashboard 提供：
- 侧边栏输入股票代码，一键发起分析
- **圆桌概览**：三个 Agent 的评级和信心度一目了然
- **时间线**：实时展示数据获取→Agent 分析→辩论→共识的全过程（SSE 流式推送）
- **信心度变化图**：三个 Agent 信心度随辩论轮次的变化折线图
- **历史回放**：点击侧边栏的历史记录，回放完整分析过程

## 项目结构

```
invest-team-claude/
├── main.py                  # CLI 入口
├── config/
│   ├── settings.py          # 配置管理（DeepSeek/Claude/GPT）
│   └── llm_client.py        # LLM 抽象层（JSON mode + Pydantic fallback）
├── agents/
│   ├── base.py              # Agent 基类（模板方法）
│   ├── fundamental.py       # 基本面分析师
│   ├── macro.py             # 宏观分析师
│   └── sentiment.py         # 情绪分析师
├── core/                    # Phase 2: 事件驱动核心
│   ├── events.py            # 事件数据模型（25+ 事件类型）
│   ├── event_bus.py         # 事件总线（发布-订阅 + SSE 队列）
│   ├── event_store.py       # 事件持久化（SQLite）
│   └── pipeline.py          # 分析管道（封装完整流程 + 事件发布）
├── dashboard/               # Phase 2: Web Dashboard
│   ├── server.py            # FastAPI 后端 + SSE 推送
│   └── frontend/
│       └── index.html       # React SPA（CDN 模式）
├── data/
│   ├── market.py            # 行情数据（akshare）
│   ├── financial.py         # 财务数据
│   ├── news.py              # 新闻/情绪数据
│   └── formatter.py         # DataFormatter
├── debate/
│   └── orchestrator.py      # 辩论协调器（三轮制）
├── models/
│   └── report.py            # 数据模型（Pydantic v2）
├── tests/                   # 39 个测试
├── DESIGN.md                # 设计系统
└── CLAUDE.md                # 项目指南
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/analyze` | 发起新分析（异步，返回 session_id） |
| GET | `/api/events/{session_id}` | SSE 实时事件流 |
| GET | `/api/sessions` | 历史分析列表 |
| GET | `/api/sessions/{session_id}` | 单个分析详情 + 完整事件 |

## 技术栈

- **LLM**: DeepSeek V3.2（通过 OpenAI SDK 兼容层）
- **数据源**: akshare（A 股行情/财务/新闻）
- **后端**: Python 3.12 + FastAPI + asyncio
- **前端**: React 18 + SVG 可视化
- **事件系统**: 自建 EventBus + SQLite 持久化
- **实时通信**: Server-Sent Events (SSE)

## 免责声明

本系统由 AI 生成分析报告，仅供参考，不构成投资建议。投资有风险，入市需谨慎。
