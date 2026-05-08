import pytest

from research_agent.permissions import PermissionManager, PermissionRule
from research_agent.models import ToolCall


READ_ONLY_TOOLS = {"read_file", "search_web", "fetch_webpage", "skill_list", "skill_load"}


def test_permission_manager_denies_matching_dangerous_patterns_before_mode_checks():
    manager = PermissionManager(
        mode="auto",
        rules=[PermissionRule(tool="bash", pattern="sudo *", behavior="deny")],
        approval_callback=lambda tool_call: "allow",
        read_only_tools=READ_ONLY_TOOLS,
    )

    decision = manager.decide(ToolCall(id="1", name="bash", arguments={"command": "sudo rm -rf /tmp/build"}))

    assert decision.outcome == "deny"
    assert decision.reason == "deny_rule"


def test_permission_manager_auto_mode_allows_reads_and_asks_writes():
    prompts = []
    manager = PermissionManager(
        mode="auto",
        rules=[],
        approval_callback=lambda tool_call: prompts.append(tool_call.name) or "allow",
        read_only_tools=READ_ONLY_TOOLS,
    )

    read_decision = manager.decide(ToolCall(id="1", name="read_file", arguments={"path": "README.md"}))
    fetch_decision = manager.decide(ToolCall(id="2", name="fetch_webpage", arguments={"url": "https://example.com"}))
    write_decision = manager.decide(ToolCall(id="3", name="write_file", arguments={"path": "README.md", "content": "updated"}))

    assert read_decision.outcome == "allow"
    assert read_decision.reason == "mode_read_only"
    assert fetch_decision.outcome == "allow"
    assert fetch_decision.reason == "mode_read_only"
    assert write_decision.outcome == "allow"
    assert write_decision.reason == "user_approved"
    assert prompts == ["write_file"]


def test_permission_manager_always_response_adds_runtime_allow_rule():
    responses = iter(["always"])
    manager = PermissionManager(
        mode="default",
        rules=[],
        approval_callback=lambda tool_call: next(responses),
        read_only_tools=READ_ONLY_TOOLS,
    )

    first = manager.decide(ToolCall(id="1", name="write_file", arguments={"path": "notes.md", "content": "hello"}))
    second = manager.decide(ToolCall(id="2", name="write_file", arguments={"path": "notes.md", "content": "hello again"}))

    assert first.outcome == "allow"
    assert first.reason == "user_approved_always"
    assert second.outcome == "allow"
    assert second.reason == "allow_rule"


def test_permission_manager_plan_mode_blocks_writes_without_prompting():
    manager = PermissionManager(
        mode="plan",
        rules=[],
        approval_callback=lambda tool_call: pytest.fail("plan mode should not prompt for writes"),
        read_only_tools=READ_ONLY_TOOLS,
    )

    decision = manager.decide(ToolCall(id="1", name="write_file", arguments={"path": "README.md", "content": "updated"}))

    assert decision.outcome == "deny"
    assert decision.reason == "plan_mode_write_blocked"
