"""Discover and load skills from ``skills/<name>/SKILL.md``.

A skill is *instructions*, not code. The loader only reads Markdown and extracts
a little metadata so the agent can choose and apply the right procedure.

Expected file format::

    ---
    name: explain-code
    description: One sentence describing when to use the skill.
    ---

    # Title
    ...
    ## Response Sections
    - Purpose
    - Main Components
"""

from __future__ import annotations

import re
from pathlib import Path

from agent.models import Skill

SKILL_FILE_NAME = "SKILL.md"
RESPONSE_SECTIONS_HEADING = "response sections"
_VALID_SKILL_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_LIST_ITEM = re.compile(r"^\s*(?:[-*]|\d+\.)\s+(.+?)\s*$")


class SkillError(Exception):
    """Base class for skill loading problems."""


class SkillNotFoundError(SkillError):
    """Raised when a requested skill does not exist."""


class InvalidSkillError(SkillError):
    """Raised when a skill exists but its ``SKILL.md`` is missing or malformed."""


class SkillLoader:
    """Finds skills inside a directory and parses their ``SKILL.md`` files."""

    def __init__(self, skills_dir: Path) -> None:
        self.skills_dir = Path(skills_dir)

    def discover(self) -> list[str]:
        """Return the sorted names of all skill directories."""
        if not self.skills_dir.is_dir():
            raise SkillError(f"Skills directory not found: {self.skills_dir}")
        return sorted(
            child.name
            for child in self.skills_dir.iterdir()
            if child.is_dir() and not child.name.startswith((".", "_"))
        )

    def load(self, name: str) -> Skill:
        """Load one skill by name.

        Raises:
            SkillNotFoundError: if the name is invalid or the directory is missing.
            InvalidSkillError: if ``SKILL.md`` is missing or malformed.
        """
        if not _VALID_SKILL_NAME.match(name):
            raise SkillNotFoundError(
                f"Invalid skill name '{name}'. Use lowercase letters, digits and hyphens."
            )
        skill_dir = self.skills_dir / name
        if not skill_dir.is_dir():
            available = ", ".join(self.discover()) or "none"
            raise SkillNotFoundError(f"Skill '{name}' not found. Available skills: {available}.")

        skill_file = skill_dir / SKILL_FILE_NAME
        if not skill_file.is_file():
            raise InvalidSkillError(f"Skill '{name}' has no {SKILL_FILE_NAME} file.")

        content = skill_file.read_text(encoding="utf-8")
        metadata, body = parse_front_matter(content, skill_file)
        declared_name = metadata.get("name", "")
        description = metadata.get("description", "")
        if declared_name != name:
            raise InvalidSkillError(
                f"{skill_file}: front matter 'name' is '{declared_name}' "
                f"but the directory is '{name}'."
            )
        if not description:
            raise InvalidSkillError(f"{skill_file}: front matter needs a 'description'.")
        if not body.strip():
            raise InvalidSkillError(f"{skill_file}: the skill has no instructions.")

        return Skill(
            name=name,
            description=description,
            path=skill_file,
            content=content,
            response_sections=parse_response_sections(body),
        )

    def load_all(self) -> list[Skill]:
        """Load every discovered skill. Raises on the first invalid skill."""
        return [self.load(name) for name in self.discover()]


def parse_front_matter(content: str, source: Path) -> tuple[dict[str, str], str]:
    """Split simple ``key: value`` front matter from the Markdown body."""
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        raise InvalidSkillError(f"{source}: missing front matter (file must start with '---').")
    try:
        end = next(i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration:
        raise InvalidSkillError(f"{source}: front matter is not closed with '---'.") from None

    metadata: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, separator, value = line.partition(":")
        if not separator:
            raise InvalidSkillError(f"{source}: invalid front matter line: '{line}'.")
        metadata[key.strip()] = value.strip().strip("'\"")
    return metadata, "\n".join(lines[end + 1 :])


def parse_response_sections(body: str) -> tuple[str, ...]:
    """Return the list items under the ``## Response Sections`` heading."""
    sections: list[str] = []
    inside = False
    for line in body.splitlines():
        if line.startswith("#"):
            inside = line.lstrip("#").strip().lower() == RESPONSE_SECTIONS_HEADING
            continue
        match = _LIST_ITEM.match(line) if inside else None
        if match:
            sections.append(match.group(1).strip("`*_ "))
    return tuple(sections)
