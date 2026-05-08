from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from research_agent.models import ToolCall


@dataclass(eq=True)
class PreToolHookResult:
    should_block: bool = False
    message: str = ""


@dataclass(eq=True)
class PostToolHookResult:
    annotated_result: str


class HookManager:
    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path = Path(config_path) if config_path else None
        self._session_started = False
        self._config = self._load_config()

    def run_session_start(self) -> None:
        if self._session_started:
            return
        self._session_started = True
        for hook in self._hooks_for("SessionStart"):
            self._run_command(hook["command"], event="SessionStart")

    def run_pre_tool_use(self, tool_call: ToolCall) -> PreToolHookResult:
        messages: list[str] = []
        for hook in self._matching_hooks("PreToolUse", tool_call):
            completed = self._run_command(hook["command"], event="PreToolUse", tool_call=tool_call)
            message = self._message_from_process(completed)
            if completed.returncode == 1:
                return PreToolHookResult(should_block=True, message=message)
            if completed.returncode == 2 and message:
                messages.append(message)
        return PreToolHookResult(should_block=False, message="\n".join(messages).strip())

    def run_post_tool_use(self, tool_call: ToolCall, tool_result: str) -> PostToolHookResult:
        annotations: list[str] = []
        for hook in self._matching_hooks("PostToolUse", tool_call):
            completed = self._run_command(
                hook["command"],
                event="PostToolUse",
                tool_call=tool_call,
                tool_result=tool_result,
            )
            message = self._message_from_process(completed)
            if completed.returncode == 2 and message:
                annotations.append(message)
        annotated = tool_result
        if annotations:
            annotated = f"{tool_result}\n\nHook annotations:\n- " + "\n- ".join(annotations)
        return PostToolHookResult(annotated_result=annotated)

    def _matching_hooks(self, event: str, tool_call: ToolCall) -> list[dict[str, str]]:
        matched: list[dict[str, str]] = []
        for hook in self._hooks_for(event):
            matcher = hook.get("matcher")
            if matcher is None or matcher == tool_call.name:
                matched.append(hook)
        return matched

    def _hooks_for(self, event: str) -> list[dict[str, str]]:
        hooks = self._config.get(event, [])
        return [hook for hook in hooks if isinstance(hook, dict) and "command" in hook]

    def _load_config(self) -> dict[str, list[dict[str, str]]]:
        if self.config_path is None or not self.config_path.exists():
            return {}
        return json.loads(self.config_path.read_text(encoding="utf-8"))

    def _run_command(
        self,
        command: str,
        *,
        event: str,
        tool_call: ToolCall | None = None,
        tool_result: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["HOOK_EVENT"] = event
        if tool_call is not None:
            env["TOOL_CALL_ID"] = tool_call.id
            env["TOOL_NAME"] = tool_call.name
            env["TOOL_ARGS"] = json.dumps(tool_call.arguments, sort_keys=True)
        if tool_result is not None:
            env["TOOL_RESULT"] = tool_result
        shell_command = command
        if shell_command.startswith("python "):
            shell_command = f"{sys.executable} " + shell_command[len("python "):]
        return subprocess.run(
            shell_command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=str(self.config_path.parent) if self.config_path else None,
            env=env,
        )

    @staticmethod
    def _message_from_process(completed: subprocess.CompletedProcess[str]) -> str:
        return (completed.stderr or completed.stdout).strip()
