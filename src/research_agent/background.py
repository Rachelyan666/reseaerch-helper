from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from typing import Callable

from research_agent.task_runtime import TaskManager


@dataclass(eq=True)
class BackgroundNotification:
    run_id: str
    subject: str
    status: str
    result: str
    task_id: int | None = None


class BackgroundManager:
    def __init__(self, task_manager: TaskManager | None = None) -> None:
        self.task_manager = task_manager
        self.tasks: dict[str, dict[str, str | int | None]] = {}
        self._notification_queue: list[BackgroundNotification] = []
        self._lock = threading.Lock()

    def run(self, *, subject: str, worker: Callable[[], str], task_id: int | None = None) -> str:
        run_id = uuid.uuid4().hex[:8]
        self.tasks[run_id] = {"subject": subject, "status": "running", "task_id": task_id}
        if task_id is not None and self.task_manager is not None:
            self.task_manager.update(task_id, status="in_progress")
        thread = threading.Thread(target=self._execute, args=(run_id, subject, worker, task_id), daemon=True)
        thread.start()
        thread.join(0.001)
        return run_id

    def drain_notifications(self) -> list[BackgroundNotification]:
        with self._lock:
            notifications = list(self._notification_queue)
            self._notification_queue.clear()
        return notifications

    def _execute(self, run_id: str, subject: str, worker: Callable[[], str], task_id: int | None) -> None:
        try:
            result = worker()
            status = "completed"
        except Exception as exc:
            result = f"Background task failed: {exc}"
            status = "failed"
        self.tasks[run_id]["status"] = status
        if task_id is not None and self.task_manager is not None:
            self.task_manager.update(task_id, status=status, result=result)
        notification = BackgroundNotification(
            run_id=run_id,
            subject=subject,
            status=status,
            result=result,
            task_id=task_id,
        )
        with self._lock:
            self._notification_queue.append(notification)
