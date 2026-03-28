"""P0 测试: 数据获取层 (mock akshare)。"""

import pytest
from unittest.mock import patch, MagicMock
import pandas as pd

from data.market import get_stock_info, get_stock_history
from data.financial import get_financial_summary, get_key_metrics
from data.news import get_stock_news, get_north_flow


class TestMarket:
    @patch("data.market.ak")
    def test_get_stock_info_happy_path(self, mock_ak):
        mock_ak.stock_individual_info_em.return_value = pd.DataFrame({
            "item": ["股票简称", "总市值", "市盈率(动态)"],
            "value": ["贵州茅台", "2.1万亿", "25.3"],
        })
        result = get_stock_info("600519")
        assert result["股票简称"] == "贵州茅台"
        assert result["总市值"] == "2.1万亿"

    @patch("data.market.ak")
    def test_get_stock_info_network_failure(self, mock_ak):
        mock_ak.stock_individual_info_em.side_effect = ConnectionError("timeout")
        result = get_stock_info("600519")
        assert result is None

    @patch("data.market.ak")
    def test_get_stock_history_happy_path(self, mock_ak):
        mock_ak.stock_zh_a_hist.return_value = pd.DataFrame({
            "日期": ["2024-01-02", "2024-01-03"],
            "收盘": [1800.0, 1810.0],
            "涨跌幅": [0.5, 0.56],
        })
        result = get_stock_history("600519")
        assert result is not None
        assert len(result) == 2


class TestFinancial:
    @patch("data.financial.ak")
    def test_get_financial_summary_happy_path(self, mock_ak):
        mock_ak.stock_financial_abstract_ths.return_value = pd.DataFrame({
            "报告期": ["2024-Q3"],
            "营业收入": ["1000亿"],
        })
        result = get_financial_summary("600519")
        assert result is not None
        assert len(result) == 1

    @patch("data.financial.ak")
    def test_get_financial_summary_empty(self, mock_ak):
        mock_ak.stock_financial_abstract_ths.return_value = pd.DataFrame()
        result = get_financial_summary("600519")
        assert result is not None
        assert len(result) == 0

    @patch("data.financial.ak")
    def test_get_key_metrics_happy_path(self, mock_ak):
        mock_ak.stock_individual_info_em.return_value = pd.DataFrame({
            "item": ["总市值", "市盈率(动态)", "流通市值", "其他"],
            "value": ["2.1万亿", "25.3", "2.0万亿", "xyz"],
        })
        result = get_key_metrics("600519")
        assert "总市值" in result
        assert "其他" not in result


class TestNews:
    @patch("data.news.ak")
    def test_get_stock_news_happy_path(self, mock_ak):
        mock_ak.stock_news_em.return_value = pd.DataFrame({
            "新闻标题": ["茅台涨价", "茅台发布Q3财报"],
            "发布时间": ["2024-10-01", "2024-10-15"],
        })
        result = get_stock_news("600519")
        assert len(result) == 2
        assert result[0]["新闻标题"] == "茅台涨价"

    @patch("data.news.ak")
    def test_get_stock_news_empty(self, mock_ak):
        mock_ak.stock_news_em.return_value = pd.DataFrame()
        result = get_stock_news("600519")
        assert result == []

    @patch("data.news.ak")
    def test_get_north_flow_network_failure(self, mock_ak):
        mock_ak.stock_hsgt_hist_em.side_effect = Exception("fail")
        result = get_north_flow()
        assert result is None
