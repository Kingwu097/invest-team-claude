"""财务数据获取。封装 akshare 财务相关接口。"""

import logging
from typing import Optional

import akshare as ak
import pandas as pd

from data._retry import retry_fetch

logger = logging.getLogger(__name__)


@retry_fetch
def get_financial_summary(symbol: str) -> Optional[pd.DataFrame]:
    """获取财务摘要数据。"""
    return ak.stock_financial_abstract_ths(symbol=symbol)


@retry_fetch
def get_key_metrics(symbol: str) -> dict:
    """从个股信息中提取关键财务指标。"""
    df = ak.stock_individual_info_em(symbol=symbol)
    metrics = {}
    key_fields = [
        "总市值", "流通市值", "市盈率(动态)", "市净率",
        "60日涨跌幅", "年初至今涨跌幅",
    ]
    for _, row in df.iterrows():
        if row["item"] in key_fields:
            metrics[row["item"]] = row["value"]
    return metrics
