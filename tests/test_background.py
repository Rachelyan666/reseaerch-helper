import time

from research_agent.background import BackgroundManager
from research_agent.task_runtime import TaskManager


def test_background_manager_completes_task_and_emits_notification(tmp_path):
    task_manager = TaskManager(tmp_path / ".tasks")
    task = task_manager.create(subject="Research Acme", prompt="Research Acme")
    background = BackgroundManager(task_manager=task_manager)

    run_id = background.run(subject="Research Acme", worker=lambda: "# Research note", task_id=task.id)

    deadline = time.time() + 2
    notifications = []
    while time.time() < deadline:
        notifications = background.drain_notifications()
        if notifications:
            break
        time.sleep(0.01)

    assert notifications
    assert notifications[0].run_id == run_id
    assert notifications[0].status == "completed"
    assert task_manager.get(task.id).status == "completed"
    assert task_manager.get(task.id).result == "# Research note"
