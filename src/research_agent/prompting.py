from __future__ import annotations

from pathlib import Path
from typing import Iterable

from research_agent.memory_store import MemoryEntry


class SystemPromptBuilder:
    def __init__(
        self,
        *,
        core_prompt: str,
        tool_definitions: list[dict[str, str]],
        loaded_skills: Iterable[str],
        memory_entries: Iterable[MemoryEntry],
        instruction_paths: Iterable[Path],
        runtime_context: dict[str, str],
    ) -> None:
        self.core_prompt = core_prompt
        self.tool_definitions = tool_definitions
        self.loaded_skills = list(loaded_skills)
        self.memory_entries = list(memory_entries)
        self.instruction_paths = [Path(path) for path in instruction_paths]
        self.runtime_context = runtime_context

    def build(self) -> str:
        parts = [
            self._build_core(),
            self._build_tools(),
            self._build_skills(),
            self._build_memory(),
            self._build_claude_md(),
            self._build_runtime(),
        ]
        return "\n\n".join(part for part in parts if part)

    def _build_core(self) -> str:
        return self.core_prompt

    def _build_tools(self) -> str:
        if not self.tool_definitions:
            return ""
        lines = ["## Tool Catalog"]
        lines.extend(f"- {tool['name']}" for tool in self.tool_definitions)
        return "\n".join(lines)

    def _build_skills(self) -> str:
        if not self.loaded_skills:
            return ""
        return "## Skills\n" + "\n".join(f"- {skill}" for skill in self.loaded_skills)

    def _build_memory(self) -> str:
        if not self.memory_entries:
            return ""
        lines = ["## Memory"]
        for entry in self.memory_entries:
            lines.append(f"- [{entry.kind}] {entry.title}: {entry.description}")
            lines.append(f"  {entry.content}")
        return "\n".join(lines)

    def _build_claude_md(self) -> str:
        contents: list[str] = []
        for path in self.instruction_paths:
            if path.exists():
                contents.append(f"### {path}\n{path.read_text(encoding='utf-8').strip()}")
        if not contents:
            return ""
        return "## CLAUDE.md Chain\n" + "\n\n".join(contents)

    def _build_runtime(self) -> str:
        if not self.runtime_context:
            return ""
        lines = ["## Runtime Context"]
        lines.extend(f"- {key}: {value}" for key, value in self.runtime_context.items())
        return "\n".join(lines)


def discover_instruction_chain(workspace_root: Path | None) -> list[Path]:
    if workspace_root is None:
        return []
    current = Path(workspace_root).resolve()
    candidates: list[Path] = []
    for path in [current, *current.parents]:
        candidate = path / "CLAUDE.md"
        if candidate.exists():
            candidates.append(candidate)
    return list(reversed(candidates))
