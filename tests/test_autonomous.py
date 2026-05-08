from research_agent.autonomy import AutonomousCoordinator
from research_agent.task_runtime import TaskManager
from research_agent.team import MessageBus, TeammateManager


def test_autonomous_coordinator_auto_claims_unowned_ready_task(tmp_path):
    tasks = TaskManager(tmp_path / ".tasks")
    teammate_manager = TeammateManager(tmp_path / ".team")
    teammate_manager.register(name="researcher", role="research")
    bus = MessageBus(tmp_path / ".team")
    task = tasks.create(subject="Research Acme competitors", prompt="Acme competitors")

    coordinator = AutonomousCoordinator(task_manager=tasks, teammate_manager=teammate_manager, bus=bus)
    claimed = coordinator.claim_next_ready_task("researcher")

    assert claimed is not None
    assert claimed.id == task.id
    assert tasks.get(task.id).owner == "researcher"
    assert tasks.get(task.id).status == "in_progress"


def test_idle_poll_prefers_inbox_messages_before_task_claims(tmp_path):
    tasks = TaskManager(tmp_path / ".tasks")
    teammate_manager = TeammateManager(tmp_path / ".team")
    teammate_manager.register(name="researcher", role="research")
    bus = MessageBus(tmp_path / ".team")
    tasks.create(subject="Research Acme competitors", prompt="Acme competitors")
    bus.send(sender="lead", recipient="researcher", content="Please review the findings")

    coordinator = AutonomousCoordinator(task_manager=tasks, teammate_manager=teammate_manager, bus=bus)
    event = coordinator.idle_poll_once("researcher")

    assert event.kind == "message"
    assert "Please review the findings" in event.payload
