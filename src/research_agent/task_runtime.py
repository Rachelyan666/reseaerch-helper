from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VALID_TASK_STATUSES = {"pending", "in_progress", "completed", "failed", "cancelled"}


@dataclass(eq=True)
class TaskRecord:
    id: int
    subject: str
    description: str = ""
    status: str = "pending"
    blocked_by: list[int] = field(default_factory=list)
    blocks: list[int] = field(default_factory=list)
    owner: str = ""
    prompt: str = ""
    result: str = ""
    worktree: str = ""
    created_at: str = field(default_factory=lambda: _utc_now())
    updated_at: str = field(default_factory=lambda: _utc_now())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TaskRecord":
        return cls(
            id=int(payload["id"]),
            subject=payload["subject"],
            description=payload.get("description", ""),
            status=payload.get("status", "pending"),
            blocked_by=[int(item) for item in payload.get("blocked_by", [])],
            blocks=[int(item) for item in payload.get("blocks", [])],
            owner=payload.get("owner", ""),
            prompt=payload.get("prompt", ""),
            result=payload.get("result", ""),
            worktree=payload.get("worktree", ""),
            created_at=payload.get("created_at", _utc_now()),
            updated_at=payload.get("updated_at", _utc_now()),
        )


class TaskManager:
    def __init__(self, tasks_dir: Path) -> None:
        self.tasks_dir = Path(tasks_dir)
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        self._next_id = self._max_id() + 1

    def create(
        self,
        *,
        subject: str,
        description: str = "",
        blocked_by: list[int] | None = None,
        owner: str = "",
        prompt: str = "",
        worktree: str = "",
    ) -> TaskRecord:
        dependencies = list(blocked_by or [])
        task = TaskRecord(
            id=self._next_id,
            subject=subject,
            description=description,
            blocked_by=dependencies,
            owner=owner,
            prompt=prompt,
            worktree=worktree,
        )
        self._next_id += 1
        self._save(task)
        for dependency_id in dependencies:
            dependency = self.get(dependency_id)
            if task.id not in dependency.blocks:
                dependency.blocks.append(task.id)
                dependency.updated_at = _utc_now()
                self._save(dependency)
        return task

    def get(self, task_id: int) -> TaskRecord:
        path = self._task_path(task_id)
        if not path.exists():
            raise KeyError(f"Unknown task: {task_id}")
        return TaskRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def list_tasks(self, status: str | None = None) -> list[TaskRecord]:
        tasks = [TaskRecord.from_dict(json.loads(path.read_text(encoding="utf-8"))) for path in sorted(self.tasks_dir.glob("task_*.json"))]
        if status is not None:
            tasks = [task for task in tasks if task.status == status]
        return tasks

    def ready_tasks(self) -> list[TaskRecord]:
        return [task for task in self.list_tasks() if task.status == "pending" and not task.blocked_by]

    def claim(self, task_id: int, owner: str) -> TaskRecord:
        return self.update(task_id, status="in_progress", owner=owner)

    def update(
        self,
        task_id: int,
        *,
        status: str | None = None,
        description: str | None = None,
        owner: str | None = None,
        prompt: str | None = None,
        result: str | None = None,
        worktree: str | None = None,
    ) -> TaskRecord:
        task = self.get(task_id)
        if status is not None:
            if status not in VALID_TASK_STATUSES:
                raise ValueError(f"Invalid task status: {status}")
            task.status = status
        if description is not None:
            task.description = description
        if owner is not None:
            task.owner = owner
        if prompt is not None:
            task.prompt = prompt
        if result is not None:
            task.result = result
        if worktree is not None:
            task.worktree = worktree
        task.updated_at = _utc_now()
        self._save(task)
        if task.status == "completed":
            self._clear_dependency(task.id)
        return self.get(task.id)

    def render(self, tasks: list[TaskRecord] | None = None) -> str:
        records = tasks if tasks is not None else self.list_tasks()
        if not records:
            return "No tasks."
        lines = []
        for task in records:
            blocked = f" blocked_by={task.blocked_by}" if task.blocked_by else ""
            prompt = f" prompt={task.prompt!r}" if task.prompt else ""
            owner = f" owner={task.owner}" if task.owner else ""
            worktree = f" worktree={task.worktree}" if task.worktree else ""
            lines.append(f"[{task.id}] {task.status} {task.subject}{blocked}{owner}{worktree}{prompt}")
        return "\n".join(lines)

    def _clear_dependency(self, completed_id: int) -> None:
        for task in self.list_tasks():
            if completed_id in task.blocked_by:
                task.blocked_by = [dependency_id for dependency_id in task.blocked_by if dependency_id != completed_id]
                task.updated_at = _utc_now()
                self._save(task)

    def _task_path(self, task_id: int) -> Path:
        return self.tasks_dir / f"task_{task_id}.json"

    def _save(self, task: TaskRecord) -> None:
        self._task_path(task.id).write_text(json.dumps(task.to_dict(), indent=2, sort_keys=True), encoding="utf-8")

    def _max_id(self) -> int:
        task_ids = []
        for path in self.tasks_dir.glob("task_*.json"):
            try:
                task_ids.append(int(path.stem.split("_")[-1]))
            except ValueError:
                continue
        return max(task_ids, default=0)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
