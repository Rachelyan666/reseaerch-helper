from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

VALID_STATUSES = {"pending", "in_progress", "completed", "cancelled"}


@dataclass(eq=True)
class TodoItem:
    id: str
    content: str
    status: str

    def __post_init__(self) -> None:
        if self.status not in VALID_STATUSES:
            raise ValueError(f"Invalid todo status: {self.status}")


class TodoList:
    def __init__(self, items: Iterable[TodoItem] | None = None) -> None:
        self._items: list[TodoItem] = []
        if items:
            self.replace(list(items))

    def replace(self, items: list[TodoItem]) -> None:
        self._validate(items)
        self._items = list(items)

    def merge(self, items: list[TodoItem]) -> None:
        merged = {item.id: item for item in self._items}
        order = [item.id for item in self._items]
        for item in items:
            if item.id not in merged:
                order.append(item.id)
            merged[item.id] = item
        result = [merged[item_id] for item_id in order]
        self._validate(result)
        self._items = result

    def items(self) -> list[TodoItem]:
        return list(self._items)

    def render(self) -> str:
        if not self._items:
            return "No todos."
        lines = [f"- [{item.status}] {item.id}: {item.content}" for item in self._items]
        return "\n".join(lines)

    @staticmethod
    def _validate(items: list[TodoItem]) -> None:
        in_progress_count = sum(1 for item in items if item.status == "in_progress")
        if in_progress_count > 1:
            raise ValueError("Only one todo item may be in_progress")
