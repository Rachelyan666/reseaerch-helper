from research_agent.task_runtime import TaskManager


def test_task_manager_persists_dependencies_and_ready_queue(tmp_path):
    manager = TaskManager(tmp_path / ".tasks")

    task1 = manager.create(subject="Collect sources", prompt="Collect sources for Acme")
    task2 = manager.create(subject="Fetch official page", blocked_by=[task1.id])
    task3 = manager.create(subject="Summarize findings", blocked_by=[task1.id, task2.id])

    assert [task.id for task in manager.ready_tasks()] == [task1.id]
    assert manager.get(task1.id).blocks == [task2.id, task3.id]
    assert manager.get(task2.id).blocked_by == [task1.id]

    reloaded = TaskManager(tmp_path / ".tasks")
    assert reloaded.get(task3.id).blocked_by == [task1.id, task2.id]
    assert [task.id for task in reloaded.ready_tasks()] == [task1.id]


def test_completing_task_unblocks_dependents_and_persists_result(tmp_path):
    manager = TaskManager(tmp_path / ".tasks")

    task1 = manager.create(subject="Collect sources")
    task2 = manager.create(subject="Fetch official page", blocked_by=[task1.id])

    updated = manager.update(task1.id, status="completed", result="done")

    assert updated.status == "completed"
    assert updated.result == "done"
    assert manager.get(task2.id).blocked_by == []
    assert [task.id for task in manager.ready_tasks()] == [task2.id]
