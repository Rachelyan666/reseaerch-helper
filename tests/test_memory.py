from research_agent.memory_store import MemoryEntry, MemoryStore


def test_memory_store_persists_markdown_files_with_frontmatter_and_loads_relevant_entries(tmp_path):
    store = MemoryStore(tmp_path / ".memory")
    store.save(
        MemoryEntry(
            slug="prefer-official-sources",
            kind="project",
            title="Prefer official sources",
            description="Use primary sources before commentary",
            content="Official sites and filings should be prioritized for company research.",
        )
    )
    store.save(
        MemoryEntry(
            slug="concise-style",
            kind="user",
            title="Concise style",
            description="User prefers concise answers",
            content="Keep summaries short unless the user asks for more detail.",
        )
    )

    entries = store.load_relevant(limit=10)

    assert [entry.kind for entry in entries] == ["project", "user"]
    assert "Official sites" in entries[0].content
    assert (tmp_path / ".memory" / "prefer-official-sources.md").exists()


def test_memory_store_rejects_unknown_memory_kinds(tmp_path):
    store = MemoryStore(tmp_path / ".memory")

    try:
        store.save(
            MemoryEntry(
                slug="bad-kind",
                kind="temporary",
                title="Bad",
                description="Should fail",
                content="nope",
            )
        )
    except ValueError as exc:
        assert "Invalid memory kind" in str(exc)
    else:
        raise AssertionError("Expected ValueError for invalid memory kind")
