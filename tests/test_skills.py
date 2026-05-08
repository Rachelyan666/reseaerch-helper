from research_agent.skills import SkillLibrary


def test_skill_library_lists_metadata_without_loading_full_content(tmp_path):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "source-selection.md").write_text(
        "---\nname: source-selection\ndescription: Prefer official and reputable sources\n---\n# Source Selection\nUse primary sources first.\n",
        encoding="utf-8",
    )

    library = SkillLibrary(skills_dir)

    summaries = library.list_skills()

    assert summaries == [
        {
            "name": "source-selection",
            "description": "Prefer official and reputable sources",
        }
    ]


def test_skill_library_loads_full_content_only_when_requested(tmp_path):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    skill_path = skills_dir / "source-selection.md"
    skill_path.write_text(
        "---\nname: source-selection\ndescription: Prefer official and reputable sources\n---\n# Source Selection\nUse primary sources first.\n",
        encoding="utf-8",
    )

    library = SkillLibrary(skills_dir)

    loaded = library.load_skill("source-selection")

    assert loaded.name == "source-selection"
    assert "Use primary sources first." in loaded.content
