from datetime import datetime

from research_agent.scheduler import ScheduleManager


def test_schedule_manager_persists_jobs_and_triggers_matching_minute(tmp_path):
    manager = ScheduleManager(tmp_path / ".schedules")

    job = manager.create(cron_expr="30 9 * * 1", prompt="Run weekly market scan", recurring=True)
    reloaded = ScheduleManager(tmp_path / ".schedules")

    assert [item.id for item in reloaded.list_jobs()] == [job.id]

    due = reloaded.collect_due_prompts(datetime(2026, 5, 4, 9, 30))
    assert [item.prompt for item in due] == ["Run weekly market scan"]

    assert reloaded.collect_due_prompts(datetime(2026, 5, 4, 9, 30)) == []
    assert reloaded.collect_due_prompts(datetime(2026, 5, 11, 9, 30))[0].id == job.id


def test_one_shot_schedule_is_disabled_after_firing(tmp_path):
    manager = ScheduleManager(tmp_path / ".schedules")
    job = manager.create(cron_expr="15 14 * * *", prompt="Check pricing page", recurring=False)

    due = manager.collect_due_prompts(datetime(2026, 5, 4, 14, 15))

    assert [item.id for item in due] == [job.id]
    assert manager.get(job.id).enabled is False
