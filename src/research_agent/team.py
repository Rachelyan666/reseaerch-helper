from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(eq=True)
class TeamMember:
    name: str
    role: str
    status: str = "working"
    created_at: str = field(default_factory=lambda: _utc_now())
    updated_at: str = field(default_factory=lambda: _utc_now())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TeamMember":
        return cls(
            name=payload["name"],
            role=payload["role"],
            status=payload.get("status", "working"),
            created_at=payload.get("created_at", _utc_now()),
            updated_at=payload.get("updated_at", _utc_now()),
        )


@dataclass(eq=True)
class TeamMessage:
    sender: str
    recipient: str
    content: str
    message_type: str = "message"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: _utc_now())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TeamMessage":
        return cls(
            sender=payload["sender"],
            recipient=payload["recipient"],
            content=payload["content"],
            message_type=payload.get("message_type", "message"),
            metadata=dict(payload.get("metadata", {})),
            created_at=payload.get("created_at", _utc_now()),
        )


class MessageBus:
    def __init__(self, team_dir: Path) -> None:
        self.team_dir = Path(team_dir)
        self.inbox_dir = self.team_dir / "inbox"
        self.inbox_dir.mkdir(parents=True, exist_ok=True)

    def send(
        self,
        *,
        sender: str,
        recipient: str,
        content: str,
        message_type: str = "message",
        metadata: dict[str, Any] | None = None,
    ) -> TeamMessage:
        message = TeamMessage(
            sender=sender,
            recipient=recipient,
            content=content,
            message_type=message_type,
            metadata=dict(metadata or {}),
        )
        inbox_path = self._inbox_path(recipient)
        with inbox_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(message.to_dict(), sort_keys=True) + "\n")
        return message

    def read_inbox(self, recipient: str) -> list[TeamMessage]:
        inbox_path = self._inbox_path(recipient)
        if not inbox_path.exists():
            return []
        lines = [line for line in inbox_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        inbox_path.write_text("", encoding="utf-8")
        return [TeamMessage.from_dict(json.loads(line)) for line in lines]

    def _inbox_path(self, recipient: str) -> Path:
        return self.inbox_dir / f"{recipient}.jsonl"


class TeammateManager:
    def __init__(self, team_dir: Path) -> None:
        self.team_dir = Path(team_dir)
        self.team_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = self.team_dir / "config.json"
        self._config = self._load_config()

    def register(self, *, name: str, role: str, status: str = "working") -> TeamMember:
        members = self._config.setdefault("members", [])
        existing = next((item for item in members if item["name"] == name), None)
        if existing is None:
            member = TeamMember(name=name, role=role, status=status)
            members.append(member.to_dict())
        else:
            existing["role"] = role
            existing["status"] = status
            existing["updated_at"] = _utc_now()
            member = TeamMember.from_dict(existing)
        self._save_config()
        return member

    def list_members(self) -> list[TeamMember]:
        return [TeamMember.from_dict(payload) for payload in self._config.get("members", [])]

    def get_member(self, name: str) -> TeamMember:
        for member in self.list_members():
            if member.name == name:
                return member
        raise KeyError(f"Unknown teammate: {name}")

    def set_status(self, name: str, status: str) -> TeamMember:
        for payload in self._config.get("members", []):
            if payload["name"] == name:
                payload["status"] = status
                payload["updated_at"] = _utc_now()
                self._save_config()
                return TeamMember.from_dict(payload)
        raise KeyError(f"Unknown teammate: {name}")

    def _load_config(self) -> dict[str, Any]:
        if self.config_path.exists():
            return json.loads(self.config_path.read_text(encoding="utf-8"))
        payload = {"members": []}
        self.config_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return payload

    def _save_config(self) -> None:
        self.config_path.write_text(json.dumps(self._config, indent=2, sort_keys=True), encoding="utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
