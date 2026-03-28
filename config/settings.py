"""配置管理。从 .env 加载 API keys 和模型配置。"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")


class Settings:
    """全局配置。"""

    # LLM — 支持 deepseek / anthropic / openai
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    DEFAULT_PROVIDER: str = os.getenv("DEFAULT_PROVIDER", "deepseek")
    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "deepseek-chat")
    DEBATE_MODEL: str = os.getenv("DEBATE_MODEL", "deepseek-chat")
    FAST_MODEL: str = os.getenv("FAST_MODEL", "deepseek-chat")

    # Token 预算
    MAX_TOKENS_PER_ANALYSIS: int = int(os.getenv("MAX_TOKENS_PER_ANALYSIS", "80000"))

    # 输出
    OUTPUT_DIR: Path = Path(__file__).parent.parent / "output" / "reports"

    @classmethod
    def validate(cls) -> list[str]:
        """校验配置，返回错误列表。"""
        errors = []
        if cls.DEFAULT_PROVIDER == "deepseek" and not cls.DEEPSEEK_API_KEY:
            errors.append(
                "DEEPSEEK_API_KEY 未配置。请在 .env 中设置。"
                "获取地址: https://platform.deepseek.com/api_keys"
            )
        if cls.DEFAULT_PROVIDER == "anthropic" and not cls.ANTHROPIC_API_KEY:
            errors.append("ANTHROPIC_API_KEY 未配置。请在 .env 中设置。")
        if cls.DEFAULT_PROVIDER == "openai" and not cls.OPENAI_API_KEY:
            errors.append("OPENAI_API_KEY 未配置。请在 .env 中设置。")
        return errors


settings = Settings()
