from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_agent.task_runtime import TaskManager


@dataclass(eq=True)
class WorktreeRecord:
    name: str
    path: str
    task_id: int | None = None
    state: str = "active"
    kind: str = "directory"
    branch: str = ""
    created_at: str = field(default_factory=lambda: _utc_now())
    updated_at: str = field(default_factory=lambda: _utc_now())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "WorktreeRecord":
        return cls(**payload)


class WorktreeManager:
    def __init__(self, worktrees_dir: Path, *, workspace_root: Path, task_manager: TaskManager) -> None:
        self.worktrees_dir = Path(worktrees_dir)
        self.workspace_root = Path(workspace_root)
        self.task_manager = task_manager
        self.worktrees_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.worktrees_dir / "index.json"
        self.events_path = self.worktrees_dir / "events.jsonl"
        self._index = self._load_index()

    def create(self, *, name: str, task_id: int | None = None) -> WorktreeRecord:
        path = self.worktrees_dir / name
        kind = "git" if self._is_git_repo() else "directory"
        branch = f"wt/{name}" if kind == "git" else ""
        if kind == "git":
            subprocess.run(["git", "worktree", "add", "-b", branch, str(path), "HEAD"], cwd=self.workspace_root, check=True, capture_output=True, text=True)
        else:
            path.mkdir(parents=True, exist_ok=True)
        record = WorktreeRecord(name=name, path=str(path), task_id=task_id, kind=kind, branch=branch)
        self._index[name] = record.to_dict()
        self._save_index()
        self._log_event("create", record)
        if task_id is not None:
            self.task_manager.update(task_id, status="in_progress", worktree=name)
        return record

    def get(self, name: str) -> WorktreeRecord:
        if name not in self._index:
            raise KeyError(f"Unknown worktree: {name}")
        return WorktreeRecord.from_dict(self._index[name])

    def list(self) -> list[WorktreeRecord]:
        return [WorktreeRecord.from_dict(self._index[name]) for name in sorted(self._index)]

    def mark_kept(self, name: str) -> WorktreeRecord:
        record = self.get(name)
        record.state = "kept"
        record.updated_at = _utc_now()
        self._index[name] = record.to_dict()
        self._save_index()
        self._log_event("keep", record)
        return record

    def remove(self, name: str) -> WorktreeRecord:
        record = self.get(name)
        path = Path(record.path)
        if record.kind == "git" and path.exists():
            subprocess.run(["git", "worktree", "remove", str(path), "--force"], cwd=self.workspace_root, check=True, capture_output=True, text=True)
        elif path.exists():
            shutil.rmtree(path)
        record.state = "removed"
        record.updated_at = _utc_now()
        self._index[name] = record.to_dict()
        self._save_index()
        self._log_event("remove", record)
        return record

    def _load_index(self) -> dict[str, Any]:
        if not self.index_path.exists():
            self.index_path.write_text("{}", encoding="utf-8")
            return {}
        return json.loads(self.index_path.read_text(encoding="utf-8"))

    def _save_index(self) -> None:
        self.index_path.write_text(json.dumps(self._index, indent=2, sort_keys=True), encoding="utf-8")

    def _log_event(self, event_type: str, record: WorktreeRecord) -> None:
        payload = {"event": event_type, "name": record.name, "task_id": record.task_id, "state": record.state, "created_at": _utc_now()}
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")

    def _is_git_repo(self) -> bool:
        probe = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=self.workspace_root, capture_output=True, text=True)
        return probe.returncode == 0 and probe.stdout.strip() == "true"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
