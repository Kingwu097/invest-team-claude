"""P1 测试: LLM 客户端。"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from config.llm_client import LLMClient, LLMError


class TestLLMClientInit:
    @patch("config.llm_client.settings")
    def test_missing_api_key_raises(self, mock_settings):
        mock_settings.validate.return_value = ["DEEPSEEK_API_KEY 未配置。"]
        with pytest.raises(LLMError, match="配置错误"):
            LLMClient()


class TestExtractJson:
    def test_extract_from_code_block(self):
        text = '```json\n{"rating": "buy", "confidence": 85}\n```'
        result = LLMClient._extract_json(text)
        assert '"rating": "buy"' in result

    def test_extract_from_bare_json(self):
        text = 'Here is the result: {"rating": "buy"}'
        result = LLMClient._extract_json(text)
        assert '"rating": "buy"' in result

    def test_extract_from_plain_text(self):
        text = "no json here"
        result = LLMClient._extract_json(text)
        assert result == "no json here"
