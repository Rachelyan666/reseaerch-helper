from research_agent.task_runtime import TaskManager
from research_agent.worktrees import WorktreeManager


def test_worktree_manager_creates_isolated_directory_and_binds_task(tmp_path):
    tasks = TaskManager(tmp_path / ".tasks")
    task = tasks.create(subject="Research Acme competitors")
    manager = WorktreeManager(tmp_path / ".worktrees", workspace_root=tmp_path, task_manager=tasks)

    record = manager.create(name="acme-research", task_id=task.id)

    assert (tmp_path / ".worktrees" / "acme-research").is_dir()
    assert record.task_id == task.id
    assert tasks.get(task.id).worktree == "acme-research"
    assert tasks.get(task.id).status == "in_progress"


def test_worktree_manager_can_keep_or_remove_lane(tmp_path):
    tasks = TaskManager(tmp_path / ".tasks")
    manager = WorktreeManager(tmp_path / ".worktrees", workspace_root=tmp_path, task_manager=tasks)
    record = manager.create(name="lane-a")

    kept = manager.mark_kept(record.name)
    assert kept.state == "kept"

    removed = manager.remove(record.name)
    assert removed.state == "removed"
    assert not (tmp_path / ".worktrees" / "lane-a").exists()
