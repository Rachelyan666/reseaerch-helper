from research_agent.memory_store import MemoryEntry
from research_agent.prompting import SystemPromptBuilder


def test_system_prompt_builder_assembles_sections_in_fixed_order(tmp_path):
    memory_entries = [
        MemoryEntry(
            slug="official-sources",
            kind="project",
            title="Official sources",
            description="Prefer official sources",
            content="Prefer official company sources before commentary.",
        )
    ]
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("# Local instructions\nDo not publish speculative claims.", encoding="utf-8")

    builder = SystemPromptBuilder(
        core_prompt="CORE",
        tool_definitions=[{"name": "search_web"}, {"name": "write_note"}],
        loaded_skills=["source-selection: Prefer official sources first"],
        memory_entries=memory_entries,
        instruction_paths=[claude_md],
        runtime_context={"cwd": str(tmp_path), "mode": "auto"},
    )

    prompt = builder.build()

    assert prompt.index("CORE") < prompt.index("## Tool Catalog")
    assert prompt.index("## Tool Catalog") < prompt.index("## Skills")
    assert prompt.index("## Skills") < prompt.index("## Memory")
    assert prompt.index("## Memory") < prompt.index("## CLAUDE.md Chain")
    assert prompt.index("## CLAUDE.md Chain") < prompt.index("## Runtime Context")
    assert "Prefer official company sources" in prompt
    assert "mode: auto" in prompt
