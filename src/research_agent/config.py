from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_ENV_WORKSPACE = "RESEARCH_AGENT_WORKSPACE"


@dataclass(frozen=True)
class AgentPaths:
    workspace_root: Path
    tasks_dir: Path
    schedules_dir: Path
    team_dir: Path
    worktrees_dir: Path
    memory_dir: Path
    notes_dir: Path
    plugins_dir: Path
    skills_dir: Path
    hooks_path: Path

    @classmethod
    def from_workspace(
        cls,
        workspace_root: str | Path | None = None,
        *,
        skills_dir: str | Path | None = None,
        hooks_path: str | Path | None = None,
    ) -> "AgentPaths":
        root = _resolve_workspace_root(workspace_root)
        return cls(
            workspace_root=root,
            tasks_dir=root / ".tasks",
            schedules_dir=root / ".schedules",
            team_dir=root / ".team",
            worktrees_dir=root / ".worktrees",
            memory_dir=root / ".memory",
            notes_dir=root / "notes",
            plugins_dir=root / "plugins",
            skills_dir=Path(skills_dir).expanduser().resolve() if skills_dir else root / "skills",
            hooks_path=Path(hooks_path).expanduser().resolve() if hooks_path else root / ".hooks.json",
        )

    def package_skills_dir(self) -> Path:
        return Path(__file__).resolve().parent / "resources" / "skills"

    def resolved_skills_dir(self) -> Path:
        if self.skills_dir.exists():
            return self.skills_dir
        return self.package_skills_dir()


def _resolve_workspace_root(workspace_root: str | Path | None = None) -> Path:
    if workspace_root is None:
        workspace_root = os.getenv(DEFAULT_ENV_WORKSPACE)
    if workspace_root is None:
        return Path.cwd().resolve()
    return Path(workspace_root).expanduser().resolve()
