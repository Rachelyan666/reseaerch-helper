from research_agent.models import Message, ModelResponse
from research_agent.recovery import RecoveryManager, RecoveryState, RetryableModelError


def test_recovery_manager_classifies_truncation_context_overflow_and_transport_errors():
    manager = RecoveryManager()

    assert manager.choose_recovery(stop_reason="max_tokens", error_text=None).kind == "continue"
    assert manager.choose_recovery(stop_reason=None, error_text="prompt too long for model window").kind == "compact"
    assert manager.choose_recovery(stop_reason=None, error_text="connection timeout from provider").kind == "backoff"
    assert manager.choose_recovery(stop_reason=None, error_text="permission denied").kind == "fail"


def test_recovery_manager_applies_continuation_message_and_retry_budget():
    manager = RecoveryManager(max_continuations=1)
    history = [Message(role="assistant", content="partial output")]
    state = RecoveryState()

    updated = manager.apply_continuation(history, state)

    assert updated[-1].role == "user"
    assert "Continue directly" in updated[-1].content
    assert state.continuation_attempts == 1

    try:
        manager.apply_continuation(updated, state)
    except RetryableModelError as exc:
        assert "Continuation retry budget exceeded" in str(exc)
    else:
        raise AssertionError("Expected RetryableModelError after retry budget exceeded")


def test_recovery_manager_backoff_budget_counts_attempts_without_sleeping():
    manager = RecoveryManager(max_transport_retries=2, backoff_seconds=0)
    state = RecoveryState()

    manager.apply_backoff(state)
    manager.apply_backoff(state)

    assert state.transport_attempts == 2

    try:
        manager.apply_backoff(state)
    except RetryableModelError as exc:
        assert "Transport retry budget exceeded" in str(exc)
    else:
        raise AssertionError("Expected RetryableModelError after transport retry budget exceeded")
