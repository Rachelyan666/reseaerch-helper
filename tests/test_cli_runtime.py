from typer.testing import CliRunner

from research_agent.cli import app


def test_task_commands_create_and_list_tasks(tmp_path, monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr("research_agent.cli._project_root", lambda: tmp_path)

    create_result = runner.invoke(app, ["task", "create", "Collect sources", "--prompt", "Research Acme"]) 
    list_result = runner.invoke(app, ["task", "list"])

    assert create_result.exit_code == 0
    assert "Collect sources" in create_result.stdout
    assert list_result.exit_code == 0
    assert "Collect sources" in list_result.stdout


def test_schedule_commands_create_and_list_jobs(tmp_path, monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr("research_agent.cli._project_root", lambda: tmp_path)

    create_result = runner.invoke(app, ["schedule", "create", "30 9 * * 1", "Run weekly market scan"])
    list_result = runner.invoke(app, ["schedule", "list"])

    assert create_result.exit_code == 0
    assert "Run weekly market scan" in create_result.stdout
    assert list_result.exit_code == 0
    assert "30 9 * * 1" in list_result.stdout
