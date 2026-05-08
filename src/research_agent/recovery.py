from __future__ import annotations

import time
from dataclasses import dataclass

from research_agent.models import Message


CONTINUE_MESSAGE = "Output limit hit. Continue directly from where you stopped. Do not restart or repeat."


class RetryableModelError(RuntimeError):
    pass


@dataclass(eq=True)
class RecoveryDecision:
    kind: str
    reason: str


@dataclass
class RecoveryState:
    continuation_attempts: int = 0
    compact_attempts: int = 0
    transport_attempts: int = 0


class RecoveryManager:
    def __init__(
        self,
        *,
        max_continuations: int = 2,
        max_compactions: int = 2,
        max_transport_retries: int = 3,
        backoff_seconds: float = 1.0,
    ) -> None:
        self.max_continuations = max_continuations
        self.max_compactions = max_compactions
        self.max_transport_retries = max_transport_retries
        self.backoff_seconds = backoff_seconds

    def choose_recovery(self, stop_reason: str | None, error_text: str | None) -> RecoveryDecision:
        error = (error_text or "").lower()
        if stop_reason == "max_tokens":
            return RecoveryDecision(kind="continue", reason="output truncated")
        if "prompt" in error and "long" in error:
            return RecoveryDecision(kind="compact", reason="context too large")
        if any(word in error for word in ("timeout", "rate", "unavailable", "connection")):
            return RecoveryDecision(kind="backoff", reason="transient transport failure")
        return RecoveryDecision(kind="fail", reason="unknown or non-recoverable error")

    def apply_continuation(self, history: list[Message], state: RecoveryState) -> list[Message]:
        if state.continuation_attempts >= self.max_continuations:
            raise RetryableModelError("Continuation retry budget exceeded")
        state.continuation_attempts += 1
        return [*history, Message(role="user", content=CONTINUE_MESSAGE)]

    def apply_compaction(self, history: list[Message], state: RecoveryState, compactor) -> list[Message]:
        if state.compact_attempts >= self.max_compactions:
            raise RetryableModelError("Compaction retry budget exceeded")
        state.compact_attempts += 1
        return compactor.compact(history)

    def apply_backoff(self, state: RecoveryState) -> None:
        if state.transport_attempts >= self.max_transport_retries:
            raise RetryableModelError("Transport retry budget exceeded")
        state.transport_attempts += 1
        if self.backoff_seconds > 0:
            time.sleep(self.backoff_seconds)
