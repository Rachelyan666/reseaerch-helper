import json

from typer.testing import CliRunner

from research_agent.cli import app


def test_team_commands_register_send_and_read_inbox(tmp_path, monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr("research_agent.cli._project_root", lambda: tmp_path)

    register_result = runner.invoke(app, ["team", "register", "researcher", "research"])
    send_result = runner.invoke(app, ["team", "send", "lead", "researcher", "Draft a plan"])
    inbox_result = runner.invoke(app, ["team", "inbox", "researcher"])

    assert register_result.exit_code == 0
    assert send_result.exit_code == 0
    assert inbox_result.exit_code == 0
    assert "Draft a plan" in inbox_result.stdout


def test_plugin_list_shows_normalized_external_tools(tmp_path, monkeypatch):
    plugin_script = tmp_path / "echo_plugin.py"
    plugin_script.write_text(
        "import json, sys\n"
        "payload = json.loads(sys.stdin.read())\n"
        "if payload.get('action') == 'manifest':\n"
        "    print(json.dumps({'server': 'echo', 'tools': [{'name': 'echo_note', 'description': 'Echo a note', 'input_schema': {'type': 'object', 'properties': {'text': {'type': 'string'}}, 'required': ['text']}}]}))\n"
        "else:\n"
        "    print(json.dumps({'content': 'ok'}))\n",
        encoding="utf-8",
    )
    manifest_dir = tmp_path / "plugins"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / "echo.json").write_text(json.dumps({"name": "echo", "command": ["python3", str(plugin_script)]}), encoding="utf-8")
    runner = CliRunner()
    monkeypatch.setattr("research_agent.cli._project_root", lambda: tmp_path)

    result = runner.invoke(app, ["plugin", "list"])

    assert result.exit_code == 0
    assert "mcp__echo__echo_note" in result.stdout
