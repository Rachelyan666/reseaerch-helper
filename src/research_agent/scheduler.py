from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(eq=True)
class ScheduleRecord:
    id: str
    cron_expr: str
    prompt: str
    recurring: bool = True
    enabled: bool = True
    created_at: str = ""
    last_fired_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ScheduleRecord":
        return cls(
            id=payload["id"],
            cron_expr=payload["cron_expr"],
            prompt=payload["prompt"],
            recurring=bool(payload.get("recurring", True)),
            enabled=bool(payload.get("enabled", True)),
            created_at=payload.get("created_at", _utc_now()),
            last_fired_at=payload.get("last_fired_at"),
        )


class ScheduleManager:
    def __init__(self, schedules_dir: Path) -> None:
        self.schedules_dir = Path(schedules_dir)
        self.schedules_dir.mkdir(parents=True, exist_ok=True)
        self._next_index = self._max_index() + 1

    def create(self, *, cron_expr: str, prompt: str, recurring: bool = True) -> ScheduleRecord:
        record = ScheduleRecord(
            id=f"job_{self._next_index:03d}",
            cron_expr=cron_expr,
            prompt=prompt,
            recurring=recurring,
            created_at=_utc_now(),
        )
        self._next_index += 1
        self._save(record)
        return record

    def get(self, job_id: str) -> ScheduleRecord:
        path = self._job_path(job_id)
        if not path.exists():
            raise KeyError(f"Unknown schedule: {job_id}")
        return ScheduleRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def list_jobs(self) -> list[ScheduleRecord]:
        return [ScheduleRecord.from_dict(json.loads(path.read_text(encoding="utf-8"))) for path in sorted(self.schedules_dir.glob("job_*.json"))]

    def collect_due_prompts(self, now: datetime) -> list[ScheduleRecord]:
        due: list[ScheduleRecord] = []
        for record in self.list_jobs():
            if not record.enabled:
                continue
            if not _matches_cron(record.cron_expr, now):
                continue
            minute_key = _minute_key(now)
            if record.last_fired_at == minute_key:
                continue
            record.last_fired_at = minute_key
            if not record.recurring:
                record.enabled = False
            self._save(record)
            due.append(record)
        return due

    def render(self) -> str:
        jobs = self.list_jobs()
        if not jobs:
            return "No schedules."
        return "\n".join(
            f"[{job.id}] enabled={job.enabled} recurring={job.recurring} cron={job.cron_expr} prompt={job.prompt}"
            for job in jobs
        )

    def _job_path(self, job_id: str) -> Path:
        return self.schedules_dir / f"{job_id}.json"

    def _save(self, record: ScheduleRecord) -> None:
        self._job_path(record.id).write_text(json.dumps(record.to_dict(), indent=2, sort_keys=True), encoding="utf-8")

    def _max_index(self) -> int:
        indices = []
        for path in self.schedules_dir.glob("job_*.json"):
            try:
                indices.append(int(path.stem.split("_")[-1]))
            except ValueError:
                continue
        return max(indices, default=0)


def _matches_cron(cron_expr: str, now: datetime) -> bool:
    fields = cron_expr.split()
    if len(fields) != 5:
        raise ValueError("Cron expression must have five fields: minute hour day month weekday")
    minute, hour, day, month, weekday = fields
    cron_weekday = (now.weekday() + 1) % 7
    return all(
        [
            _matches_field(minute, now.minute),
            _matches_field(hour, now.hour),
            _matches_field(day, now.day),
            _matches_field(month, now.month),
            _matches_field(weekday, cron_weekday),
        ]
    )


def _matches_field(field: str, value: int) -> bool:
    if field == "*":
        return True
    for part in field.split(","):
        if part == "*":
            return True
        if part.startswith("*/"):
            step = int(part[2:])
            return step > 0 and value % step == 0
        if int(part) == value:
            return True
    return False


def _minute_key(now: datetime) -> str:
    return now.replace(second=0, microsecond=0).isoformat()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
