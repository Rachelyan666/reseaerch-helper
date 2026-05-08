from typer.testing import CliRunner

from research_agent.cli import _build_live_agent, app
from research_agent.config import AgentPaths


def test_build_live_agent_registers_real_research_tools_when_api_key_is_provided():
    agent = _build_live_agent(api_key="test-key")

    definitions = agent.tool_registry.definitions()
    names = [tool["name"] for tool in definitions]

    assert "search_web" in names
    assert "fetch_webpage" in names
    if hasattr(agent, "close"):
        agent.close()


def test_build_live_agent_reads_api_key_from_workspace_dotenv(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("OPENAI_API_KEY=dotenv-test-key\n", encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    agent = _build_live_agent(paths=AgentPaths.from_workspace(tmp_path))

    assert agent.model.api_key == "dotenv-test-key"
    if hasattr(agent, "close"):
        agent.close()


def test_live_chat_prints_progress_logs(monkeypatch):
    runner = CliRunner()

    class FakeAgent:
        def __init__(self, progress_callback):
            self.progress_callback = progress_callback

        def run(self, prompt):
            self.progress_callback("Thinking…")
            self.progress_callback("Searching the web for: Figma competitors")
            return "# Research note"

    def fake_build_live_agent(api_key=None, progress_callback=None):
        return FakeAgent(progress_callback)

    monkeypatch.setattr("research_agent.cli._build_live_agent", fake_build_live_agent)
    monkeypatch.setattr("research_agent.cli.load_project_env", lambda: None)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    result = runner.invoke(app, ["chat", "--live"], input="Figma competitors\nquit\n")

    assert result.exit_code == 0
    assert "Thinking…" in result.stdout
    assert "Searching the web for: Figma competitors" in result.stdout
    assert "# Research note" in result.stdout
