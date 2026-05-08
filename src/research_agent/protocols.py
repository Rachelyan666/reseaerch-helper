from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(eq=True)
class ProtocolRequest:
    request_id: str
    kind: str
    status: str = "pending"
    target: str = ""
    sender: str = ""
    recipient: str = ""
    plan: str = ""
    reason: str = ""
    created_at: str = field(default_factory=lambda: _utc_now())
    updated_at: str = field(default_factory=lambda: _utc_now())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProtocolRequest":
        return cls(**payload)


class ProtocolManager:
    def __init__(self, team_dir: Path) -> None:
        self.team_dir = Path(team_dir)
        self.team_dir.mkdir(parents=True, exist_ok=True)
        self.shutdown_path = self.team_dir / "shutdown_requests.json"
        self.plan_path = self.team_dir / "plan_requests.json"
        self._shutdown = self._load(self.shutdown_path)
        self._plans = self._load(self.plan_path)

    def create_shutdown_request(self, *, target: str) -> ProtocolRequest:
        request = ProtocolRequest(request_id=_request_id(), kind="shutdown", target=target)
        self._shutdown[request.request_id] = request.to_dict()
        self._save(self.shutdown_path, self._shutdown)
        return request

    def record_shutdown_response(self, request_id: str, *, approve: bool, reason: str = "") -> ProtocolRequest:
        request = self.get_shutdown_request(request_id)
        request.status = "approved" if approve else "rejected"
        request.reason = reason
        request.updated_at = _utc_now()
        self._shutdown[request_id] = request.to_dict()
        self._save(self.shutdown_path, self._shutdown)
        return request

    def get_shutdown_request(self, request_id: str) -> ProtocolRequest:
        if request_id not in self._shutdown:
            raise KeyError(f"Unknown shutdown request: {request_id}")
        return ProtocolRequest.from_dict(self._shutdown[request_id])

    def create_plan_request(self, *, sender: str, recipient: str, plan: str) -> ProtocolRequest:
        request = ProtocolRequest(request_id=_request_id(), kind="plan", sender=sender, recipient=recipient, plan=plan)
        self._plans[request.request_id] = request.to_dict()
        self._save(self.plan_path, self._plans)
        return request

    def record_plan_response(self, request_id: str, *, approve: bool, reason: str = "") -> ProtocolRequest:
        request = self.get_plan_request(request_id)
        request.status = "approved" if approve else "rejected"
        request.reason = reason
        request.updated_at = _utc_now()
        self._plans[request_id] = request.to_dict()
        self._save(self.plan_path, self._plans)
        return request

    def get_plan_request(self, request_id: str) -> ProtocolRequest:
        if request_id not in self._plans:
            raise KeyError(f"Unknown plan request: {request_id}")
        return ProtocolRequest.from_dict(self._plans[request_id])

    def _load(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            path.write_text("{}", encoding="utf-8")
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _save(path: Path, payload: dict[str, Any]) -> None:
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _request_id() -> str:
    return uuid.uuid4().hex[:8]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
