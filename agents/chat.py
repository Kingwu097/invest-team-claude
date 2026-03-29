"""自然语言交互模式。

用户可以用自然语言提问，系统自动解析意图并路由到对应分析：
- "帮我分析下贵州茅台" → 单股分析
- "新能源板块要不要加仓？" → 板块代表股分析
- "对比一下茅台和五粮液" → 多股组合分析
- "我的持仓表现怎么样" → 绩效报告
"""

import logging
import re
from typing import Optional

from config.llm_client import LLMClient

logger = logging.getLogger(__name__)

# 常见股票名称→代码映射（高频）
STOCK_ALIASES = {
    "茅台": "600519", "贵州茅台": "600519",
    "五粮液": "000858", "泸州老窖": "000568",
    "宁德时代": "300750", "比亚迪": "002594",
    "中国平安": "601318", "招商银行": "600036",
    "腾讯": None,  # 港股，暂不支持
    "阿里": None,  # 美股，暂不支持
    "中信证券": "600030", "工商银行": "601398",
    "万科": "000002", "格力电器": "000651",
    "美的集团": "000333", "海尔智家": "600690",
    "恒瑞医药": "600276", "片仔癀": "600436",
    "隆基绿能": "601012", "阳光电源": "300274",
    "中芯国际": "688981", "海光信息": "688041",
}

# 行业板块→代表股映射
SECTOR_STOCKS = {
    "白酒": ["600519", "000858", "000568"],
    "新能源": ["300750", "002594", "601012"],
    "银行": ["600036", "601398", "601318"],
    "医药": ["600276", "600436", "300760"],
    "半导体": ["688981", "688041", "002371"],
    "消费": ["000651", "000333", "600690"],
    "券商": ["600030", "601688", "000166"],
    "地产": ["000002", "001979", "600048"],
    "光伏": ["601012", "300274", "688599"],
    "人工智能": ["688041", "002230", "300496"],
}


class IntentType:
    SINGLE_STOCK = "single_stock"
    MULTI_STOCK = "multi_stock"
    SECTOR = "sector"
    PERFORMANCE = "performance"
    HELP = "help"
    UNKNOWN = "unknown"


class ParsedIntent:
    def __init__(self, intent_type: str, stock_codes: list[str] = None,
                 sector: str = "", raw_query: str = ""):
        self.intent_type = intent_type
        self.stock_codes = stock_codes or []
        self.sector = sector
        self.raw_query = raw_query


def parse_intent(query: str) -> ParsedIntent:
    """解析用户自然语言意图（规则优先，不需要 LLM 调用）。"""
    query = query.strip()

    # 绩效查询
    if any(kw in query for kw in ["持仓", "绩效", "表现", "收益", "盈亏", "历史"]):
        return ParsedIntent(IntentType.PERFORMANCE, raw_query=query)

    # 帮助
    if any(kw in query for kw in ["帮助", "help", "怎么用", "使用说明"]):
        return ParsedIntent(IntentType.HELP, raw_query=query)

    # 提取股票代码（6位数字）
    codes = re.findall(r'\b([036]\d{5})\b', query)

    # 提取股票名称
    for name, code in STOCK_ALIASES.items():
        if name in query and code:
            if code not in codes:
                codes.append(code)

    # 板块分析
    for sector, sector_codes in SECTOR_STOCKS.items():
        if sector in query:
            return ParsedIntent(
                IntentType.SECTOR,
                stock_codes=sector_codes,
                sector=sector,
                raw_query=query,
            )

    if len(codes) == 1:
        return ParsedIntent(IntentType.SINGLE_STOCK, stock_codes=codes, raw_query=query)
    elif len(codes) > 1:
        return ParsedIntent(IntentType.MULTI_STOCK, stock_codes=codes, raw_query=query)

    # 无法解析
    return ParsedIntent(IntentType.UNKNOWN, raw_query=query)


async def parse_intent_with_llm(query: str, llm: LLMClient) -> ParsedIntent:
    """当规则解析失败时，用 LLM 辅助解析意图。"""
    intent = parse_intent(query)
    if intent.intent_type != IntentType.UNKNOWN:
        return intent

    # LLM fallback
    system = (
        "你是一个意图解析助手。用户会用自然语言描述投资需求。"
        "请从中提取：1. 股票代码或名称 2. 分析类型（单股/对比/板块/绩效）"
        "只输出 JSON: {\"codes\": [\"600519\"], \"type\": \"single\"}"
    )
    try:
        text = await llm.call_text(system_prompt=system, user_message=query, max_tokens=100)
        import json
        data = json.loads(text.strip().strip("`").strip())
        codes = data.get("codes", [])
        if codes:
            t = IntentType.SINGLE_STOCK if len(codes) == 1 else IntentType.MULTI_STOCK
            return ParsedIntent(t, stock_codes=codes, raw_query=query)
    except Exception:
        pass

    return intent


def get_help_text() -> str:
    """返回帮助文本。"""
    return """
投资理财专家团队 — 自然语言交互模式

用法示例：
  "帮我分析下贵州茅台"          → 分析 600519
  "300750 怎么样"              → 分析宁德时代
  "对比茅台和五粮液"            → 对比 600519 vs 000858
  "新能源板块要不要加仓"         → 分析新能源代表股
  "白酒行业前景如何"            → 分析白酒代表股
  "我的持仓表现怎么样"          → 查看绩效报告
  "退出" / "exit"              → 退出

支持的板块: """ + "、".join(SECTOR_STOCKS.keys())
