"""P1 测试: DataFormatter。"""

import pytest
import pandas as pd

from data.formatter import DataFormatter


class TestDataFormatter:
    def test_format_stock_info(self):
        info = {"股票简称": "贵州茅台", "总市值": "2.1万亿"}
        result = DataFormatter.format_stock_info(info)
        assert "贵州茅台" in result
        assert "2.1万亿" in result

    def test_format_stock_info_none(self):
        result = DataFormatter.format_stock_info(None)
        assert "数据不可用" in result

    def test_format_history(self):
        df = pd.DataFrame({
            "日期": ["2024-01-02", "2024-01-03"],
            "收盘": [1800.0, 1810.0],
            "涨跌幅": [0.5, 0.56],
            "成交量": [10000, 12000],
        })
        result = DataFormatter.format_history(df)
        assert "1800" in result
        assert "1810" in result

    def test_format_history_empty(self):
        result = DataFormatter.format_history(pd.DataFrame())
        assert "数据不可用" in result

    def test_format_news(self):
        news = [
            {"新闻标题": "茅台涨价", "发布时间": "2024-10-01", "新闻内容": "内容..."},
            {"新闻标题": "Q3 财报", "发布时间": "2024-10-15", "新闻内容": "内容2..."},
        ]
        result = DataFormatter.format_news(news)
        assert "茅台涨价" in result
        assert "Q3 财报" in result

    def test_format_news_empty(self):
        result = DataFormatter.format_news([])
        assert "无相关新闻" in result

    def test_build_context_mixed(self):
        result = DataFormatter.build_context({
            "stock_info": {"股票简称": "茅台"},
            "key_metrics": {"PE": 25},
            "news": None,
        })
        assert "茅台" in result
        assert "PE" in result

    def test_build_context_unknown_section(self):
        result = DataFormatter.build_context({"unknown_section": "data"})
        assert result == ""  # unknown section ignored
