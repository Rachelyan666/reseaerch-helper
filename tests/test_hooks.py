import json

from research_agent.hooks import HookManager
from research_agent.models import ToolCall


def test_hook_manager_blocks_pre_tool_use_on_exit_code_one(tmp_path):
    config_path = tmp_path / ".hooks.json"
    config_path.write_text(
        json.dumps(
            {
                "PreToolUse": [
                    {
                        "matcher": "search_web",
                        "command": "python -c \"import sys; sys.stderr.write('blocked by policy'); raise SystemExit(1)\"",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    manager = HookManager(config_path)
    result = manager.run_pre_tool_use(ToolCall(id="1", name="search_web", arguments={"query": "acme"}))

    assert result.should_block is True
    assert "blocked by policy" in result.message


def test_hook_manager_injects_message_on_exit_code_two_and_appends_post_tool_annotation(tmp_path):
    config_path = tmp_path / ".hooks.json"
    config_path.write_text(
        json.dumps(
            {
                "PreToolUse": [
                    {
                        "matcher": "search_web",
                        "command": "python -c \"import sys; sys.stderr.write('remember source quality'); raise SystemExit(2)\"",
                    }
                ],
                "PostToolUse": [
                    {
                        "matcher": "search_web",
                        "command": "python -c \"import sys; sys.stderr.write('audit logged'); raise SystemExit(2)\"",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    manager = HookManager(config_path)
    pre_result = manager.run_pre_tool_use(ToolCall(id="1", name="search_web", arguments={"query": "acme"}))
    post_result = manager.run_post_tool_use(
        ToolCall(id="1", name="search_web", arguments={"query": "acme"}),
        tool_result='{"items": []}',
    )

    assert pre_result.should_block is False
    assert pre_result.message == "remember source quality"
    assert "audit logged" in post_result.annotated_result


def test_hook_manager_runs_session_start_hooks_once(tmp_path):
    marker = tmp_path / "session-start.txt"
    config_path = tmp_path / ".hooks.json"
    config_path.write_text(
        json.dumps(
            {
                "SessionStart": [
                    {
                        "command": f"python -c \"from pathlib import Path; p = Path(r'{marker}'); p.write_text(str(int(p.read_text() or '0') + 1) if p.exists() else '1')\""
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    manager = HookManager(config_path)
    manager.run_session_start()
    manager.run_session_start()

    assert marker.read_text(encoding="utf-8") == "1"
