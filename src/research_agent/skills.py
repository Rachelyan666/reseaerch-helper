from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(eq=True)
class LoadedSkill:
    name: str
    description: str
    content: str
    path: Path


class SkillLibrary:
    def __init__(self, skills_dir: Path) -> None:
        self.skills_dir = Path(skills_dir)

    def list_skills(self) -> list[dict[str, str]]:
        skills: list[dict[str, str]] = []
        if not self.skills_dir.exists():
            return skills
        for path in sorted(self.skills_dir.glob("*.md")):
            name, description, _ = self._parse_skill(path)
            skills.append({"name": name, "description": description})
        return skills

    def load_skill(self, name: str) -> LoadedSkill:
        path = self.skills_dir / f"{name}.md"
        if not path.exists():
            raise FileNotFoundError(f"Skill not found: {name}")
        parsed_name, description, content = self._parse_skill(path)
        return LoadedSkill(name=parsed_name, description=description, content=content, path=path)

    @staticmethod
    def _parse_skill(path: Path) -> tuple[str, str, str]:
        raw = path.read_text(encoding="utf-8")
        lines = raw.splitlines()
        if len(lines) >= 3 and lines[0].strip() == "---":
            metadata: dict[str, str] = {}
            end_index = 1
            while end_index < len(lines) and lines[end_index].strip() != "---":
                line = lines[end_index]
                if ":" in line:
                    key, value = line.split(":", 1)
                    metadata[key.strip()] = value.strip()
                end_index += 1
            content = "\n".join(lines[end_index + 1 :]).strip()
            return metadata.get("name", path.stem), metadata.get("description", ""), content
        return path.stem, "", raw.strip()
