from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from research_agent.models import Message


@dataclass
class FunctionSubagentRunner:
    worker: Callable[[str, list[Message]], str]

    def run(self, task: str, parent_messages: list[Message]) -> str:
        return self.worker(task, list(parent_messages))
