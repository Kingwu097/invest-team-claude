"""Agent 工具系统。让 Agent 像 OpenAI function calling 一样动态调用工具。

每个 Tool 是一个独立的数据获取/分析能力单元：
- 有名称、描述（让 LLM 知道何时该用）
- 有 execute() 方法
- 返回结构化结果（文本 + 元数据）

Agent 的 system prompt 中会包含可用工具列表，
LLM 可以选择调用哪些工具获取实时数据。
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """工具执行结果。"""
    tool_name: str
    success: bool
    data_text: str  # LLM 可读的文本
    raw_data: Any = None  # 原始数据（DataFrame/dict）
    data_date: Optional[str] = None  # 数据截止日期
    source: str = ""  # 数据来源
    error: Optional[str] = None


class BaseTool(ABC):
    """工具基类。"""

    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称（英文，用于 function calling）。"""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述（中文，让 LLM 理解何时使用）。"""
        ...

    @property
    def parameters_description(self) -> str:
        """参数描述（可选）。"""
        return ""

    @abstractmethod
    def execute(self, stock_code: str, **kwargs) -> ToolResult:
        """执行工具，返回结果。"""
        ...

    def to_prompt_description(self) -> str:
        """生成 LLM prompt 中的工具描述。"""
        desc = f"- **{self.name}**: {self.description}"
        if self.parameters_description:
            desc += f" (参数: {self.parameters_description})"
        return desc


class ToolRegistry:
    """工具注册表。管理所有可用工具。"""

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def list_tools(self) -> list[BaseTool]:
        return list(self._tools.values())

    def get_tools_prompt(self) -> str:
        """生成可用工具的 prompt 描述。"""
        lines = ["你可以使用以下数据工具获取最新信息：", ""]
        for tool in self._tools.values():
            lines.append(tool.to_prompt_description())
        return "\n".join(lines)

    def execute_tools(
        self, tool_names: list[str], stock_code: str, **kwargs
    ) -> list[ToolResult]:
        """批量执行工具。"""
        results = []
        for name in tool_names:
            tool = self._tools.get(name)
            if not tool:
                results.append(ToolResult(
                    tool_name=name, success=False,
                    data_text=f"[工具 {name} 不存在]",
                    error=f"Unknown tool: {name}",
                ))
                continue
            try:
                result = tool.execute(stock_code, **kwargs)
                results.append(result)
            except Exception as e:
                logger.warning(f"工具 {name} 执行失败: {e}")
                results.append(ToolResult(
                    tool_name=name, success=False,
                    data_text=f"[{name}: 数据获取失败 — {e}]",
                    error=str(e),
                ))
        return results

    def build_context(self, results: list[ToolResult]) -> str:
        """将工具执行结果组装为 LLM 上下文。"""
        parts = []
        for r in results:
            if r.success:
                header = f"## {r.tool_name}"
                if r.data_date:
                    header += f" (数据截止: {r.data_date})"
                if r.source:
                    header += f" [来源: {r.source}]"
                parts.append(f"{header}\n{r.data_text}")
            else:
                parts.append(f"## {r.tool_name}\n[不可用: {r.error or '获取失败'}]")
        return "\n\n".join(parts)
