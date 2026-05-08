from pathlib import Path

import pytest

from research_agent.todos import TodoItem, TodoList


def test_todo_list_keeps_single_in_progress_item_and_preserves_order():
    todo_list = TodoList()
    todo_list.replace(
        [
            TodoItem(id="discover", content="Discover sources", status="completed"),
            TodoItem(id="fetch", content="Fetch source text", status="in_progress"),
            TodoItem(id="summarize", content="Summarize findings", status="pending"),
        ]
    )

    items = todo_list.items()

    assert [item.id for item in items] == ["discover", "fetch", "summarize"]
    assert [item.status for item in items] == ["completed", "in_progress", "pending"]


def test_todo_list_rejects_multiple_in_progress_items():
    todo_list = TodoList()

    with pytest.raises(ValueError, match="Only one todo item may be in_progress"):
        todo_list.replace(
            [
                TodoItem(id="one", content="first", status="in_progress"),
                TodoItem(id="two", content="second", status="in_progress"),
            ]
        )


def test_todo_list_supports_merge_updates_by_id():
    todo_list = TodoList(
        [
            TodoItem(id="discover", content="Discover sources", status="completed"),
            TodoItem(id="fetch", content="Fetch source text", status="pending"),
        ]
    )

    todo_list.merge(
        [
            TodoItem(id="fetch", content="Fetch source text", status="in_progress"),
            TodoItem(id="summarize", content="Summarize findings", status="pending"),
        ]
    )

    items = todo_list.items()
    assert [item.id for item in items] == ["discover", "fetch", "summarize"]
    assert [item.status for item in items] == ["completed", "in_progress", "pending"]
