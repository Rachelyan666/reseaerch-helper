from pathlib import Path

from typer.testing import CliRunner

from research_agent.cli import app


runner = CliRunner()


class FakeAgent:
    def __init__(self, response: str):
        self.response = response

    def run(self, prompt: str) -> str:
        return self.response


class FakeLiveAgent(FakeAgent):
    def close(self) -> None:
        return None


def test_demo_writes_markdown_note_file_in_workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "research_agent.cli._build_demo_agent",
        lambda paths=None: FakeAgent("# Research note\n\n## Query\n- Acme\n"),
    )

    result = runner.invoke(app, ["--workspace", str(tmp_path), "demo", "Acme competitors"])

    assert result.exit_code == 0
    notes_dir = tmp_path / "notes"
    note_files = sorted(notes_dir.glob("*.md"))
    assert len(note_files) == 1
    assert note_files[0].read_text(encoding="utf-8") == "# Research note\n\n## Query\n- Acme\n"
    assert str(note_files[0]) in result.stdout


def test_research_writes_markdown_note_file_to_explicit_output_path(tmp_path, monkeypatch):
    output_path = tmp_path / "custom-note.md"
    monkeypatch.setattr(
        "research_agent.cli._build_live_agent",
        lambda api_key=None, progress_callback=None: FakeLiveAgent("# Research note\n\n## Sources\n- https://example.com\n"),
    )
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    result = runner.invoke(
        app,
        [
            "--workspace",
            str(tmp_path),
            "research",
            "Acme competitors",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert output_path.exists()
    assert output_path.read_text(encoding="utf-8") == "# Research note\n\n## Sources\n- https://example.com\n"
    assert str(output_path) in result.stdout
