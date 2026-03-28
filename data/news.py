"""新闻和情绪数据获取。封装 akshare 新闻/资金流向相关接口。"""

import logging
from typing import Optional

import akshare as ak
import pandas as pd

from data._retry import retry_fetch

logger = logging.getLogger(__name__)


@retry_fetch
def get_stock_news(symbol: str, limit: int = 20) -> list[dict]:
    """获取个股新闻。"""
    df = ak.stock_news_em(symbol=symbol)
    if df is None or df.empty:
        return []
    df = df.head(limit)
    return df.to_dict("records")


@retry_fetch
def get_north_flow() -> Optional[pd.DataFrame]:
    """获取北向资金（沪股通）历史数据。"""
    return ak.stock_hsgt_hist_em(symbol="沪股通")


@retry_fetch
def get_margin_data(symbol: str = "") -> Optional[pd.DataFrame]:
    """获取融资融券账户汇总数据。"""
    return ak.stock_margin_account_info()
