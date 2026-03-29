# Invest Team Claude - 投资理财专家团队

基于 Multi-Agent 协作的投资理财专家团队系统。8 个专业 AI Agent 组成五层闭环架构（情报→决策→审查→执行→反馈），通过结构化辩论达成投资共识。

## 核心特色

- **五层闭环架构**：情报层（3 分析师并行）→ 决策层（理财顾问+量化研究员）→ 审查层（风控总监）→ 执行层（模拟交易）→ 反馈层（绩效跟踪）
- **Agent 辩论机制**：多个专业 Agent 从不同角度分析，互相质疑挑战，暴露风险盲点
- **可观测的协作过程**：每个 Agent 的推理链、信心度变化、辩论记录全程可追溯
- **实时 Dashboard**：Web 界面实时展示 Agent 分析和辩论过程（时间线 + 圆桌概览 + 信心度图 + 绩效仪表盘）
- **Agent 工具系统**：14 个可插拔数据工具（akshare + Web 搜索），每个工具标注数据截止日期
- **Agent 自进化**：基于绩效数据自动调整 Agent 在共识投票中的权重
- **自然语言交互**：对话模式，支持"分析茅台""新能源板块要不要加仓"等自然语言输入

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

# 4. 分析单只股票（五层完整流程）
python main.py --stock 600519

# 5. 多股票组合分析
python main.py --stock 600519 300750 000858

# 6. 自然语言交互模式
python main.py --chat
```

### 自然语言交互示例

```
💬 你: 帮我分析下贵州茅台
💬 你: 对比茅台和五粮液
💬 你: 新能源板块要不要加仓
💬 你: 我的持仓表现怎么样
```

### Dashboard 模式

```bash
# 启动 Dashboard 服务器
python -m uvicorn dashboard.server:app --host 0.0.0.0 --port 8000

# 打开浏览器访问 http://localhost:8000
```

Dashboard 提供：
- **分析视图**：圆桌概览 + 时间线（SSE 实时推送）+ 信心度变化图
- **绩效视图**：总分析次数/准确率/信心度/累计收益 + Agent 进化权重 + 交易记录
- **历史回放**：点击侧边栏的历史记录，回放完整分析过程

## 五层架构

```
┌─ 情报层 ─────────────────────────────┐
│  基本面分析师 / 宏观分析师 / 情绪分析师  │
│  14 个工具（akshare + Web 搜索）       │
│  → 三轮辩论 → 共识报告                 │
└──────────────┬────────────────────────┘
               ▼
┌─ 决策层 ─────────────────────────────┐
│  理财顾问（投资建议 + 仓位 + 止损止盈）  │
│  量化研究员（评分 + 波动率/回撤/夏普）   │
└──────────────┬────────────────────────┘
               ▼
┌─ 审查层 ─────────────────────────────┐
│  风控总监（硬性规则 + LLM 审核 + 裁决）  │
└──────────────┬────────────────────────┘
               ▼
┌─ 执行反馈层 ─────────────────────────┐
│  交易执行员 → 绩效归因分析师 → 闭环学习  │
└───────────────────────────────────────┘
```

## 项目结构

```
invest-team-claude/
├── main.py                  # CLI 入口（单股/组合/交互三种模式）
├── config/
│   ├── settings.py          # 配置管理（DeepSeek/Claude/GPT）
│   └── llm_client.py        # LLM 抽象层（JSON mode + Pydantic fallback）
├── agents/
│   ├── base.py              # Agent 基类（模板方法）
│   ├── fundamental.py       # 基本面分析师
│   ├── macro.py             # 宏观分析师
│   ├── sentiment.py         # 情绪分析师
│   ├── advisor.py           # 理财顾问
│   ├── quant.py             # 量化研究员
│   ├── risk_officer.py      # 风控总监
│   ├── trader.py            # 交易执行员
│   ├── performance.py       # 绩效归因分析师
│   ├── evolution.py         # Agent 自进化（权重校准）
│   ├── chat.py              # 自然语言交互（意图解析）
│   └── tools/               # Agent 工具系统
│       ├── __init__.py      # 工具基类 + 注册表
│       ├── market_tools.py  # 行情/财务工具（4 个）
│       ├── macro_tools.py   # 宏观数据工具（4 个）
│       ├── sentiment_tools.py # 新闻/搜索工具（5 个）
│       └── registry.py      # 工具集工厂
├── core/
│   ├── events.py            # 事件数据模型（30+ 事件类型）
│   ├── event_bus.py         # 事件总线（发布-订阅 + SSE 队列）
│   ├── event_store.py       # 事件持久化（SQLite）
│   └── pipeline.py          # 五层分析管道
├── dashboard/
│   ├── server.py            # FastAPI 后端（7 个 API 端点 + SSE）
│   └── frontend/
│       └── index.html       # React SPA（分析视图 + 绩效视图）
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
| GET | `/api/performance` | 绩效汇总 + 交易记录 |
| GET | `/api/evolution` | Agent 进化权重 |
| POST | `/api/evolution/calibrate` | 触发 Agent 权重校准 |

## 技术栈

- **LLM**: DeepSeek V3.2（通过 OpenAI SDK 兼容层）
- **数据源**: akshare（A 股行情/财务/新闻）+ DuckDuckGo 搜索
- **后端**: Python 3.12 + FastAPI + asyncio
- **前端**: React 18 + SVG 可视化
- **事件系统**: 自建 EventBus + SQLite 持久化
- **实时通信**: Server-Sent Events (SSE)

## 免责声明

本系统由 AI 生成分析报告，仅供参考，不构成投资建议。投资有风险，入市需谨慎。
