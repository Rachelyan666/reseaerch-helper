from __future__ import annotations

import json
import os
from dataclasses import asdict
from typing import Any

import httpx

from research_agent.models import Message, ModelResponse, ToolCall


class OpenAIChatModel:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        http_client: Any | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required for live research mode")
        self.model = model or os.getenv("OPENAI_MODEL") or "gpt-4.1-mini"
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self.http_client = http_client or httpx.Client()
        self.timeout = timeout

    def generate(self, messages: list[Message], tools: list[dict[str, Any]], system_prompt: str) -> ModelResponse:
        payload = {
            "model": self.model,
            "messages": self._serialize_messages(messages, system_prompt),
            "tools": [self._serialize_tool(tool) for tool in tools],
            "tool_choice": "auto",
        }
        response = self.http_client.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        choice = data["choices"][0]
        message = choice.get("message", {})
        content = self._extract_content(message.get("content"))
        tool_calls = [
            ToolCall(
                id=tool_call["id"],
                name=tool_call["function"]["name"],
                arguments=json.loads(tool_call["function"].get("arguments") or "{}"),
            )
            for tool_call in message.get("tool_calls", [])
        ]
        finish_reason = choice.get("finish_reason")
        stop_reason = {
            "tool_calls": "tool_use",
            "length": "max_tokens",
        }.get(finish_reason, "end_turn")
        return ModelResponse(output_text=content, tool_calls=tool_calls, stop_reason=stop_reason)

    def _serialize_messages(self, messages: list[Message], system_prompt: str) -> list[dict[str, Any]]:
        serialized: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        for message in messages:
            if message.role == "assistant" and message.tool_calls:
                serialized.append(
                    {
                        "role": "assistant",
                        "content": message.content or None,
                        "tool_calls": [
                            {
                                "id": tool_call.id,
                                "type": "function",
                                "function": {
                                    "name": tool_call.name,
                                    "arguments": json.dumps(tool_call.arguments),
                                },
                            }
                            for tool_call in message.tool_calls
                        ],
                    }
                )
            elif message.role == "tool":
                serialized.append(
                    {
                        "role": "tool",
                        "tool_call_id": message.tool_call_id or "tool_call",
                        "content": message.content,
                    }
                )
            else:
                serialized.append({"role": message.role, "content": message.content})
        return serialized

    @staticmethod
    def _serialize_tool(tool: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("input_schema", {"type": "object", "properties": {}}),
            },
        }

    @staticmethod
    def _extract_content(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "\n".join(
                part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text"
            ).strip()
        return ""
