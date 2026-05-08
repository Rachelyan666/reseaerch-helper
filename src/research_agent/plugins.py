from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(eq=True)
class PluginTool:
    server: str
    tool_name: str
    description: str
    input_schema: dict[str, Any]
    command: list[str]

    @property
    def normalized_name(self) -> str:
        return f"mcp__{self.server}__{self.tool_name}"


class PluginManager:
    def __init__(self, manifest_dir: Path) -> None:
        self.manifest_dir = Path(manifest_dir)
        self.manifest_dir.mkdir(parents=True, exist_ok=True)
        self._tools = self._discover_tools()

    def definitions(self) -> list[dict[str, Any]]:
        return [
            {"name": tool.normalized_name, "description": tool.description, "input_schema": tool.input_schema}
            for tool in sorted(self._tools.values(), key=lambda item: item.normalized_name)
        ]

    def has_tool(self, name: str) -> bool:
        return name in self._tools

    def execute(self, name: str, arguments: dict[str, Any]) -> str:
        if name not in self._tools:
            raise KeyError(f"Unknown plugin tool: {name}")
        tool = self._tools[name]
        payload = {"action": "invoke", "tool": tool.tool_name, "arguments": arguments}
        result = _run_json_command(tool.command, payload)
        content = result.get("content", result)
        if isinstance(content, str):
            return content
        return json.dumps(content, indent=2, sort_keys=True)

    def _discover_tools(self) -> dict[str, PluginTool]:
        tools: dict[str, PluginTool] = {}
        for manifest_path in sorted(self.manifest_dir.glob("*.json")):
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            command = list(manifest["command"])
            manifest_payload = _run_json_command(command, {"action": "manifest", "tool": ""})
            server = manifest_payload.get("server", manifest.get("name", manifest_path.stem))
            for tool_payload in manifest_payload.get("tools", []):
                tool = PluginTool(
                    server=server,
                    tool_name=tool_payload["name"],
                    description=tool_payload.get("description", "External MCP/plugin tool"),
                    input_schema=tool_payload.get("input_schema", {"type": "object", "properties": {}}),
                    command=command,
                )
                tools[tool.normalized_name] = tool
        return tools


def _run_json_command(command: list[str], payload: dict[str, Any]) -> dict[str, Any]:
    completed = subprocess.run(command, input=json.dumps(payload), capture_output=True, text=True, check=True)
    stdout = completed.stdout.strip() or "{}"
    return json.loads(stdout)
