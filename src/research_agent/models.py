from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(eq=True)
class Message:
    role: str
    content: str
    tool_call_id: str | None = None
    tool_calls: list["ToolCall"] = field(default_factory=list)


@dataclass(eq=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(eq=True)
class ToolResult:
    tool_call_id: str
    content: str


@dataclass(eq=True)
class ModelResponse:
    output_text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str | None = None

    def __post_init__(self) -> None:
        if self.stop_reason is None:
            self.stop_reason = "tool_use" if self.tool_calls else "end_turn"
