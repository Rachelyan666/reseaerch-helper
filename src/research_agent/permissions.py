from __future__ import annotations

import json
from dataclasses import dataclass, field
from fnmatch import fnmatch
from typing import Callable, Iterable

from research_agent.models import ToolCall


DEFAULT_READ_ONLY_TOOLS = {"read_file", "search_web", "fetch_webpage", "skill_list", "skill_load"}


@dataclass(eq=True)
class PermissionRule:
    tool: str
    pattern: str = "*"
    behavior: str = "allow"


@dataclass(eq=True)
class PermissionDecision:
    outcome: str
    reason: str


@dataclass
class PermissionManager:
    mode: str = "default"
    rules: list[PermissionRule] = field(default_factory=list)
    approval_callback: Callable[[ToolCall], str] | None = None
    read_only_tools: set[str] = field(default_factory=lambda: set(DEFAULT_READ_ONLY_TOOLS))

    def __init__(
        self,
        mode: str = "default",
        rules: Iterable[PermissionRule] | None = None,
        approval_callback: Callable[[ToolCall], str] | None = None,
        read_only_tools: Iterable[str] | None = None,
    ) -> None:
        self.mode = mode
        self.rules = list(rules or [])
        self.approval_callback = approval_callback
        self.read_only_tools = set(read_only_tools or DEFAULT_READ_ONLY_TOOLS)

    def decide(self, tool_call: ToolCall) -> PermissionDecision:
        deny_rule = self._find_matching_rule(tool_call, behavior="deny")
        if deny_rule is not None:
            return PermissionDecision(outcome="deny", reason="deny_rule")

        if self.mode == "plan" and not self._is_read_only(tool_call):
            return PermissionDecision(outcome="deny", reason="plan_mode_write_blocked")
        if self.mode == "auto" and self._is_read_only(tool_call):
            return PermissionDecision(outcome="allow", reason="mode_read_only")

        allow_rule = self._find_matching_rule(tool_call, behavior="allow")
        if allow_rule is not None:
            return PermissionDecision(outcome="allow", reason="allow_rule")

        if self.approval_callback is None:
            return PermissionDecision(outcome="deny", reason="no_approval_callback")

        response = self.approval_callback(tool_call).strip().lower()
        if response == "always":
            self.rules.append(PermissionRule(tool=tool_call.name, pattern=self._rule_pattern_from_call(tool_call), behavior="allow"))
            return PermissionDecision(outcome="allow", reason="user_approved_always")
        if response in {"allow", "yes", "y"}:
            return PermissionDecision(outcome="allow", reason="user_approved")
        return PermissionDecision(outcome="deny", reason="user_denied")

    def _find_matching_rule(self, tool_call: ToolCall, behavior: str) -> PermissionRule | None:
        target = self._rule_pattern_from_call(tool_call)
        for rule in self.rules:
            if rule.behavior != behavior:
                continue
            if rule.tool != tool_call.name:
                continue
            if fnmatch(target, rule.pattern):
                return rule
        return None

    def _is_read_only(self, tool_call: ToolCall) -> bool:
        return tool_call.name in self.read_only_tools

    @staticmethod
    def _rule_pattern_from_call(tool_call: ToolCall) -> str:
        for key in ("path", "command", "query", "name"):
            value = tool_call.arguments.get(key)
            if isinstance(value, str) and value:
                return value
        return json.dumps(tool_call.arguments, sort_keys=True)
