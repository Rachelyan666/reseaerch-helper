from pathlib import Path

from research_agent.config import AgentPaths


def test_agent_paths_defaults_to_workspace_relative_runtime_dirs(tmp_path):
    paths = AgentPaths.from_workspace(tmp_path)

    assert paths.workspace_root == tmp_path.resolve()
    assert paths.tasks_dir == tmp_path / ".tasks"
    assert paths.schedules_dir == tmp_path / ".schedules"
    assert paths.team_dir == tmp_path / ".team"
    assert paths.plugins_dir == tmp_path / "plugins"


def test_agent_paths_uses_environment_workspace_when_argument_is_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("RESEARCH_AGENT_WORKSPACE", str(tmp_path))

    paths = AgentPaths.from_workspace()

    assert paths.workspace_root == tmp_path.resolve()
