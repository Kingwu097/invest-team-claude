"""行情数据获取。封装 akshare 行情相关接口，带重试和降级。"""

import logging
from typing import Optional

import akshare as ak
import pandas as pd

from data._retry import retry_fetch

logger = logging.getLogger(__name__)


@retry_fetch
def get_stock_info(symbol: str) -> dict:
    """获取个股基本信息。"""
    df = ak.stock_individual_info_em(symbol=symbol)
    info = {}
    for _, row in df.iterrows():
        info[row["item"]] = row["value"]
    return info


@retry_fetch
def get_stock_history(
    symbol: str, period: str = "daily", days: int = 120
) -> Optional[pd.DataFrame]:
    """获取历史行情数据。"""
    from datetime import datetime, timedelta

    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
    df = ak.stock_zh_a_hist(
        symbol=symbol, period=period,
        start_date=start, end_date=end, adjust="qfq"
    )
    return df
