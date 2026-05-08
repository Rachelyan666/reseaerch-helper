from research_agent.protocols import ProtocolManager


def test_shutdown_protocol_tracks_request_and_response(tmp_path):
    manager = ProtocolManager(tmp_path / ".team")

    request = manager.create_shutdown_request(target="researcher")
    updated = manager.record_shutdown_response(request.request_id, approve=True, reason="done")

    assert request.status == "pending"
    assert updated.status == "approved"
    assert manager.get_shutdown_request(request.request_id).reason == "done"


def test_plan_approval_protocol_tracks_request_and_rejection(tmp_path):
    manager = ProtocolManager(tmp_path / ".team")

    request = manager.create_plan_request(sender="researcher", recipient="lead", plan="Collect sources then summarize")
    updated = manager.record_plan_response(request.request_id, approve=False, reason="need source list first")

    assert request.plan == "Collect sources then summarize"
    assert updated.status == "rejected"
    assert manager.get_plan_request(request.request_id).reason == "need source list first"
