from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


VALID_MEMORY_KINDS = ("user", "feedback", "project", "reference")


@dataclass(eq=True)
class MemoryEntry:
    slug: str
    kind: str
    title: str
    description: str
    content: str
    created_at: str | None = None


class MemoryStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, entry: MemoryEntry) -> Path:
        self._validate_kind(entry.kind)
        if entry.created_at is None:
            entry.created_at = datetime.now(timezone.utc).isoformat()
        path = self.root / f"{entry.slug}.md"
        path.write_text(self._render(entry), encoding="utf-8")
        return path

    def load_relevant(self, limit: int = 10) -> list[MemoryEntry]:
        entries = [self._parse(path) for path in self.root.glob("*.md")]
        entries.sort(key=lambda entry: entry.created_at or "")
        return entries[:limit]

    def _parse(self, path: Path) -> MemoryEntry:
        raw = path.read_text(encoding="utf-8")
        lines = raw.splitlines()
        metadata: dict[str, str] = {}
        content = raw.strip()
        if len(lines) >= 3 and lines[0].strip() == "---":
            end_index = 1
            while end_index < len(lines) and lines[end_index].strip() != "---":
                line = lines[end_index]
                if ":" in line:
                    key, value = line.split(":", 1)
                    metadata[key.strip()] = value.strip()
                end_index += 1
            content = "\n".join(lines[end_index + 1 :]).strip()
        kind = metadata.get("kind", "project")
        self._validate_kind(kind)
        return MemoryEntry(
            slug=path.stem,
            kind=kind,
            title=metadata.get("title", path.stem.replace("-", " ").title()),
            description=metadata.get("description", ""),
            content=content,
            created_at=metadata.get("created_at"),
        )

    @staticmethod
    def _render(entry: MemoryEntry) -> str:
        return (
            "---\n"
            f"kind: {entry.kind}\n"
            f"title: {entry.title}\n"
            f"description: {entry.description}\n"
            f"created_at: {entry.created_at}\n"
            "---\n"
            f"{entry.content}\n"
        )

    @staticmethod
    def _validate_kind(kind: str) -> None:
        if kind not in VALID_MEMORY_KINDS:
            raise ValueError(f"Invalid memory kind: {kind}")
