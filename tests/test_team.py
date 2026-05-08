import json

from research_agent.team import MessageBus, TeammateManager


def test_teammate_manager_persists_roster_and_statuses(tmp_path):
    manager = TeammateManager(tmp_path / ".team")
    manager.register(name="lead", role="lead")
    member = manager.register(name="researcher", role="research")
    manager.set_status("researcher", "idle")

    reloaded = TeammateManager(tmp_path / ".team")

    assert [item.name for item in reloaded.list_members()] == ["lead", "researcher"]
    assert member.role == "research"
    assert reloaded.get_member("researcher").status == "idle"


def test_message_bus_uses_append_only_jsonl_and_drains_inbox(tmp_path):
    bus = MessageBus(tmp_path / ".team")
    bus.send(sender="lead", recipient="researcher", content="Check pricing page", message_type="assignment", metadata={"task_id": 7})
    bus.send(sender="lead", recipient="researcher", content="Second note")

    inbox_path = tmp_path / ".team" / "inbox" / "researcher.jsonl"
    lines = inbox_path.read_text(encoding="utf-8").splitlines()

    assert len(lines) == 2
    assert json.loads(lines[0])["metadata"]["task_id"] == 7

    drained = bus.read_inbox("researcher")
    assert [message.content for message in drained] == ["Check pricing page", "Second note"]
    assert bus.read_inbox("researcher") == []
