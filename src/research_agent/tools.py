from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., Any]] = {}
        self._definitions: dict[str, dict[str, Any]] = {}

    def register(
        self,
        name: str,
        func: Callable[..., Any],
        *,
        description: str | None = None,
        input_schema: dict[str, Any] | None = None,
    ) -> None:
        self._tools[name] = func
        definition: dict[str, Any] = {"name": name}
        if description is not None:
            definition["description"] = description
        if input_schema is not None:
            definition["input_schema"] = input_schema
        self._definitions[name] = definition

    def definitions(self) -> list[dict[str, Any]]:
        return [self._definitions.get(name, {"name": name}) for name in sorted(self._tools)]

    def execute(self, name: str, arguments: dict[str, Any]) -> str:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        result = self._tools[name](**arguments)
        if isinstance(result, str):
            return result
        return json.dumps(result, indent=2, sort_keys=True)
