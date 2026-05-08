from research_agent.compaction import ContextCompactor
from research_agent.models import Message


def test_context_compactor_replaces_older_history_with_summary_when_threshold_exceeded():
    compactor = ContextCompactor(max_messages=4, keep_last=2)
    history = [
        Message(role="user", content="question 1"),
        Message(role="assistant", content="analysis 1"),
        Message(role="user", content="question 2"),
        Message(role="assistant", content="analysis 2"),
        Message(role="user", content="question 3"),
    ]

    compacted = compactor.compact(history)

    assert len(compacted) == 3
    assert compacted[0].role == "system"
    assert "question 1" in compacted[0].content
    assert compacted[1:] == history[-2:]


def test_context_compactor_leaves_short_histories_unchanged():
    compactor = ContextCompactor(max_messages=5, keep_last=2)
    history = [
        Message(role="user", content="question 1"),
        Message(role="assistant", content="analysis 1"),
    ]

    assert compactor.compact(history) == history


def test_context_compactor_does_not_leave_orphan_tool_results_in_recent_history():
    compactor = ContextCompactor(max_messages=4, keep_last=2)
    history = [
        Message(role="user", content="Research Acme"),
        Message(role="assistant", content="Planning"),
        Message(role="assistant", content="Searching", tool_calls=[]),
        Message(role="tool", content='{"results": ["https://example.com"]}', tool_call_id="search-1"),
        Message(role="assistant", content="Final answer"),
    ]

    compacted = compactor.compact(history)

    assert compacted[0].role == "system"
    assert compacted[1].role == "assistant"
    assert compacted[1].content == "Searching"
    assert compacted[2].role == "tool"
    assert compacted[2].tool_call_id == "search-1"
    assert compacted[3].role == "assistant"
