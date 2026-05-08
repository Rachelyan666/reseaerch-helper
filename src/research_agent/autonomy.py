from __future__ import annotations

from dataclasses import dataclass

from research_agent.task_runtime import TaskManager, TaskRecord
from research_agent.team import MessageBus, TeammateManager


@dataclass(eq=True)
class IdleEvent:
    kind: str
    payload: str


class AutonomousCoordinator:
    def __init__(self, *, task_manager: TaskManager, teammate_manager: TeammateManager, bus: MessageBus) -> None:
        self.task_manager = task_manager
        self.teammate_manager = teammate_manager
        self.bus = bus

    def claim_next_ready_task(self, teammate_name: str) -> TaskRecord | None:
        self.teammate_manager.get_member(teammate_name)
        for task in self.task_manager.ready_tasks():
            if task.owner:
                continue
            return self.task_manager.claim(task.id, teammate_name)
        return None

    def idle_poll_once(self, teammate_name: str) -> IdleEvent | None:
        messages = self.bus.read_inbox(teammate_name)
        if messages:
            payload = "\n".join(message.content for message in messages)
            return IdleEvent(kind="message", payload=payload)
        claimed = self.claim_next_ready_task(teammate_name)
        if claimed is not None:
            return IdleEvent(kind="task", payload=f"Task #{claimed.id}: {claimed.subject}")
        return None
