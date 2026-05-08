from pathlib import Path

from research_agent import cli


def test_load_project_env_reads_dotenv_file_into_process_environment(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "OPENAI_API_KEY=dotenv-test-key\nOPENAI_MODEL=gpt-test-model\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    loaded = cli.load_project_env(tmp_path)

    assert loaded == env_file
    assert cli.os.getenv("OPENAI_API_KEY") == "dotenv-test-key"
    assert cli.os.getenv("OPENAI_MODEL") == "gpt-test-model"



def test_load_project_env_does_not_override_existing_environment_variables(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=dotenv-test-key\n", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "already-set")

    cli.load_project_env(tmp_path)

    assert cli.os.getenv("OPENAI_API_KEY") == "already-set"



def test_load_project_env_ignores_placeholder_values(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=your_openai_api_key_here\n", encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    loaded = cli.load_project_env(tmp_path)

    assert loaded == env_file
    assert cli.os.getenv("OPENAI_API_KEY") is None



def test_load_project_env_returns_none_when_no_dotenv_file_exists(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    loaded = cli.load_project_env(tmp_path)

    assert loaded is None
    assert cli.os.getenv("OPENAI_API_KEY") is None


def test_cli_uses_environment_workspace_when_flag_is_not_provided(tmp_path, monkeypatch):
    from typer.testing import CliRunner

    runner = CliRunner()
    monkeypatch.setenv("RESEARCH_AGENT_WORKSPACE", str(tmp_path))

    create_result = runner.invoke(cli.app, ["task", "create", "Collect sources"])
    list_result = runner.invoke(cli.app, ["task", "list"])

    assert create_result.exit_code == 0
    assert list_result.exit_code == 0
    assert "Collect sources" in list_result.stdout
