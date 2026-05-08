from __future__ import annotations

from research_agent.models import Message


class ContextCompactor:
    def __init__(self, max_messages: int = 12, keep_last: int = 4) -> None:
        self.max_messages = max_messages
        self.keep_last = keep_last

    def compact(self, history: list[Message]) -> list[Message]:
        if len(history) <= self.max_messages:
            return history
        if history and history[0].role == "system" and history[0].content.startswith("Earlier conversation summary:"):
            return history
        older_messages = history[: -self.keep_last]
        recent_messages = history[-self.keep_last :]
        while recent_messages and recent_messages[0].role == "tool" and older_messages:
            recent_messages = [older_messages[-1], *recent_messages]
            older_messages = older_messages[:-1]
        summary_lines = ["Earlier conversation summary:"]
        for message in older_messages:
            summary_lines.append(f"- {message.role}: {message.content}")
        summary = Message(role="system", content="\n".join(summary_lines))
        return [summary, *recent_messages]
