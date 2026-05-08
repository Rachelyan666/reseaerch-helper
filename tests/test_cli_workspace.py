from typer.testing import CliRunner

from research_agent.cli import app


runner = CliRunner()


def test_task_commands_use_explicit_workspace_option(tmp_path):
    create_result = runner.invoke(app, ["--workspace", str(tmp_path), "task", "create", "Collect sources", "--prompt", "Research Acme"])
    list_result = runner.invoke(app, ["--workspace", str(tmp_path), "task", "list"])

    assert create_result.exit_code == 0
    assert "Collect sources" in create_result.stdout
    assert list_result.exit_code == 0
    assert "Collect sources" in list_result.stdout


def test_team_commands_use_workspace_option(tmp_path):
    register_result = runner.invoke(app, ["--workspace", str(tmp_path), "team", "register", "researcher", "research"])
    send_result = runner.invoke(app, ["--workspace", str(tmp_path), "team", "send", "lead", "researcher", "Draft a plan"])
    inbox_result = runner.invoke(app, ["--workspace", str(tmp_path), "team", "inbox", "researcher"])

    assert register_result.exit_code == 0
    assert send_result.exit_code == 0
    assert inbox_result.exit_code == 0
    assert "Draft a plan" in inbox_result.stdout
