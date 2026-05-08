import json

from research_agent.plugins import PluginManager


def test_plugin_manager_loads_manifest_and_normalizes_external_tool_names(tmp_path):
    plugin_script = tmp_path / "echo_plugin.py"
    plugin_script.write_text(
        "import json, sys\n"
        "payload = json.loads(sys.stdin.read())\n"
        "tool = payload['tool']\n"
        "args = payload.get('arguments', {})\n"
        "if payload.get('action') == 'manifest':\n"
        "    print(json.dumps({'server': 'echo', 'tools': [{'name': 'echo_note', 'description': 'Echo a note', 'input_schema': {'type': 'object', 'properties': {'text': {'type': 'string'}}, 'required': ['text']}}]}))\n"
        "else:\n"
        "    print(json.dumps({'content': f\"echo::{tool}::{args.get('text', '')}\"}))\n",
        encoding="utf-8",
    )
    manifest = tmp_path / "plugins" / "echo.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps({"name": "echo", "command": ["python3", str(plugin_script)]}), encoding="utf-8")

    manager = PluginManager(tmp_path / "plugins")
    definitions = manager.definitions()

    assert [tool["name"] for tool in definitions] == ["mcp__echo__echo_note"]
    assert manager.execute("mcp__echo__echo_note", {"text": "hello"}) == "echo::echo_note::hello"
