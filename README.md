# Invest Team Claude - 投资理财专家团队

基于 Multi-Agent 协作的投资理财专家团队系统。三个专业 AI 分析师（基本面/宏观/情绪）并行分析，通过结构化辩论达成共识，生成投资洞察报告。

## 核心特色

- **Agent 辩论机制**：多个专业 Agent 从不同角度分析，互相质疑挑战，暴露风险盲点
- **可观测的协作过程**：每个 Agent 的推理链、信心度变化、辩论记录全程可追溯
- **结构化共识**：信心度加权投票，高分歧标记，未达成共识时保留各方论据

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 API Key
cp .env.example .env
# 编辑 .env 填入你的 Claude/OpenAI API Key

# 3. 验证数据源
python scripts/verify_akshare.py

# 4. 运行分析
python main.py --stock 600519
```

## 项目结构

```
invest-team-claude/
├── main.py                  # CLI 入口
├── config/
│   ├── settings.py          # 配置管理
│   └── llm_client.py        # LLM 抽象层
├── agents/
│   ├── base.py              # Agent 基类（模板方法）
│   ├── fundamental.py       # 基本面分析师
│   ├── macro.py             # 宏观分析师
│   └── sentiment.py         # 情绪分析师
├── data/
│   ├── market.py            # 行情数据
│   ├── financial.py         # 财务数据
│   ├── news.py              # 新闻/情绪数据
│   └── formatter.py         # DataFormatter
├── debate/
│   └── orchestrator.py      # 辩论协调器
├── models/
│   └── report.py            # 数据模型
└── tests/                   # 测试
```

## 免责声明

本系统由 AI 生成分析报告，仅供参考，不构成投资建议。投资有风险，入市需谨慎。
