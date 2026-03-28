"""LLM 客户端抽象层。

封装 DeepSeek/Claude/GPT API 调用，支持：
- JSON mode 优先的结构化输出（DeepSeek response_format）
- Function Calling（DeepSeek/OpenAI tool_choice）
- Pydantic fallback 解析
- 重试 + 指数退避
"""

import asyncio
import json
import logging
import re
from typing import Optional, Type, TypeVar

from pydantic import BaseModel

from config.settings import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

MAX_RETRIES = 3
RETRY_DELAYS = [2, 4, 8]


class LLMError(Exception):
    """LLM 调用失败。"""
    pass


class LLMClient:
    """统一的 LLM 客户端。默认使用 DeepSeek V3.2。"""

    def __init__(self):
        errors = settings.validate()
        if errors:
            raise LLMError(f"配置错误: {'; '.join(errors)}")

        self._provider = settings.DEFAULT_PROVIDER
        self._total_tokens = 0

        if self._provider == "deepseek":
            import openai
            self._client = openai.AsyncOpenAI(
                api_key=settings.DEEPSEEK_API_KEY,
                base_url=settings.DEEPSEEK_BASE_URL,
            )
        elif self._provider == "anthropic":
            import anthropic
            self._anthropic = anthropic.AsyncAnthropic(
                api_key=settings.ANTHROPIC_API_KEY
            )
        elif self._provider == "openai":
            import openai
            self._client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        else:
            raise LLMError(f"Unknown provider: {self._provider}")

    @property
    def total_tokens(self) -> int:
        return self._total_tokens

    def reset_token_count(self):
        self._total_tokens = 0

    async def call_text(
        self,
        system_prompt: str,
        user_message: str,
        model: Optional[str] = None,
        max_tokens: int = 4096,
    ) -> str:
        """调用 LLM 获取纯文本响应。"""
        model = model or settings.DEFAULT_MODEL
        return await self._call_with_retry(
            system_prompt, user_message, model, max_tokens
        )

    async def call_structured(
        self,
        system_prompt: str,
        user_message: str,
        response_model: Type[T],
        model: Optional[str] = None,
        max_tokens: int = 4096,
    ) -> T:
        """调用 LLM 获取结构化响应。

        策略:
        - DeepSeek: JSON mode (response_format) 优先 → Pydantic fallback
        - Anthropic: tool_use 优先 → Pydantic fallback
        - OpenAI: JSON mode 优先 → Pydantic fallback
        """
        model = model or settings.DEFAULT_MODEL

        # 尝试 1: JSON mode / tool_use
        try:
            if self._provider == "anthropic":
                return await self._call_tool_use_anthropic(
                    system_prompt, user_message, response_model, model, max_tokens
                )
            else:
                return await self._call_json_mode(
                    system_prompt, user_message, response_model, model, max_tokens
                )
        except Exception as e:
            logger.warning(f"结构化输出首次尝试失败: {e}")

        # 尝试 2: Pydantic fallback
        try:
            return await self._call_pydantic_fallback(
                system_prompt, user_message, response_model, model, max_tokens
            )
        except Exception as e:
            logger.warning(f"Pydantic fallback 也失败: {e}")

        # 尝试 3: 再试一次 JSON mode
        try:
            if self._provider == "anthropic":
                return await self._call_tool_use_anthropic(
                    system_prompt, user_message, response_model, model, max_tokens
                )
            else:
                return await self._call_json_mode(
                    system_prompt, user_message, response_model, model, max_tokens
                )
        except Exception as e:
            raise LLMError(f"结构化输出解析失败（3 次尝试后）: {e}")

    # === 底层调用 ===

    async def _call_with_retry(
        self,
        system_prompt: str,
        user_message: str,
        model: str,
        max_tokens: int,
    ) -> str:
        """带重试的 LLM 调用。"""
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                return await self._raw_call(
                    system_prompt, user_message, model, max_tokens
                )
            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAYS[attempt]
                    logger.warning(
                        f"LLM 调用失败 (attempt {attempt + 1}), "
                        f"{delay}s 后重试: {e}"
                    )
                    await asyncio.sleep(delay)
        raise LLMError(f"LLM 调用失败（{MAX_RETRIES} 次重试后）: {last_error}")

    async def _raw_call(
        self,
        system_prompt: str,
        user_message: str,
        model: str,
        max_tokens: int,
    ) -> str:
        """底层 LLM API 调用。"""
        if self._provider == "anthropic":
            response = await self._anthropic.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            self._total_tokens += (
                response.usage.input_tokens + response.usage.output_tokens
            )
            return response.content[0].text

        # DeepSeek 和 OpenAI 共用 OpenAI SDK
        response = await self._client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
        if response.usage:
            self._total_tokens += response.usage.total_tokens
        return response.choices[0].message.content or ""

    # === 结构化输出策略 ===

    async def _call_json_mode(
        self,
        system_prompt: str,
        user_message: str,
        response_model: Type[T],
        model: str,
        max_tokens: int,
    ) -> T:
        """通过 JSON mode 获取结构化输出（DeepSeek / OpenAI）。

        DeepSeek 要求 system/user 消息中包含 "json" 字样。
        """
        schema_str = json.dumps(
            response_model.model_json_schema(), ensure_ascii=False, indent=2
        )
        enhanced_system = (
            f"{system_prompt}\n\n"
            f"请严格以 json 格式输出，符合以下 schema:\n{schema_str}"
        )

        response = await self._client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": enhanced_system},
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
        )
        if response.usage:
            self._total_tokens += response.usage.total_tokens

        content = response.choices[0].message.content or ""
        if not content.strip():
            raise LLMError("DeepSeek 返回空 content（已知问题，需调整 prompt）")

        json_str = self._extract_json(content)
        return response_model.model_validate_json(json_str)

    async def _call_tool_use_anthropic(
        self,
        system_prompt: str,
        user_message: str,
        response_model: Type[T],
        model: str,
        max_tokens: int,
    ) -> T:
        """通过 tool_use 获取结构化输出（仅 Anthropic）。"""
        schema = response_model.model_json_schema()
        tool_name = response_model.__name__.lower()

        response = await self._anthropic.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
            tools=[
                {
                    "name": tool_name,
                    "description": f"Output structured {response_model.__name__}",
                    "input_schema": schema,
                }
            ],
            tool_choice={"type": "tool", "name": tool_name},
        )
        self._total_tokens += (
            response.usage.input_tokens + response.usage.output_tokens
        )

        for block in response.content:
            if block.type == "tool_use":
                return response_model.model_validate(block.input)

        raise LLMError("No tool_use block in response")

    async def _call_pydantic_fallback(
        self,
        system_prompt: str,
        user_message: str,
        response_model: Type[T],
        model: str,
        max_tokens: int,
    ) -> T:
        """文本输出 + Pydantic 解析 fallback。"""
        schema_str = json.dumps(
            response_model.model_json_schema(), ensure_ascii=False, indent=2
        )
        enhanced_prompt = (
            f"{system_prompt}\n\n"
            f"请以 JSON 格式输出，符合以下 schema:\n{schema_str}"
        )
        text = await self._call_with_retry(
            enhanced_prompt, user_message, model, max_tokens
        )
        json_str = self._extract_json(text)
        return response_model.model_validate_json(json_str)

    @staticmethod
    def _extract_json(text: str) -> str:
        """从 LLM 文本输出中提取 JSON 字符串。"""
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return match.group(0)
        return text.strip()
