"""Tests for SkillLoader."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.skill_loader import InvalidSkillError, SkillError, SkillLoader, SkillNotFoundError


def _write_skill(skills_dir: Path, name: str, content: str) -> None:
    (skills_dir / name).mkdir(parents=True)
    (skills_dir / name / "SKILL.md").write_text(content, encoding="utf-8")


VALID_SKILL = """---
name: demo-skill
description: A demo skill.
---

# Demo

## Procedure

1. Do the thing.

## Response Sections

- First
- Second

## Notes

- Not a section.
"""


def test_discovers_repository_skills(skills_dir: Path) -> None:
    names = SkillLoader(skills_dir).discover()
    assert {"explain-code", "code-review"} <= set(names)
    assert names == sorted(names)


def test_loads_explain_code_skill(skills_dir: Path) -> None:
    skill = SkillLoader(skills_dir).load("explain-code")

    assert skill.name == "explain-code"
    assert skill.description
    assert "## Procedure" in skill.content
    assert skill.response_sections == (
        "Purpose",
        "Main Components",
        "Execution Flow",
        "Inputs and Outputs",
        "Example",
        "Important Concepts",
        "Possible Improvements",
    )


def test_loads_code_review_skill(skills_dir: Path) -> None:
    skill = SkillLoader(skills_dir).load("code-review")
    assert skill.response_sections[:4] == (
        "Summary",
        "Verified Findings",
        "Potential Concerns",
        "Suggestions",
    )


def test_load_all_returns_json_serializable_summaries(skills_dir: Path) -> None:
    skills = SkillLoader(skills_dir).load_all()
    assert json.loads(json.dumps([skill.summary() for skill in skills]))


def test_parses_front_matter_and_sections(tmp_path: Path) -> None:
    _write_skill(tmp_path, "demo-skill", VALID_SKILL)
    skill = SkillLoader(tmp_path).load("demo-skill")

    assert skill.description == "A demo skill."
    assert skill.response_sections == ("First", "Second")


def test_unknown_skill_raises_not_found(skills_dir: Path) -> None:
    with pytest.raises(SkillNotFoundError, match="Available skills"):
        SkillLoader(skills_dir).load("does-not-exist")


@pytest.mark.parametrize("name", ["../secrets", "Explain", "a/b", ""])
def test_invalid_skill_names_are_rejected(skills_dir: Path, name: str) -> None:
    with pytest.raises(SkillNotFoundError):
        SkillLoader(skills_dir).load(name)


def test_missing_skill_file_is_invalid(tmp_path: Path) -> None:
    (tmp_path / "empty-skill").mkdir()
    with pytest.raises(InvalidSkillError, match="no SKILL.md"):
        SkillLoader(tmp_path).load("empty-skill")


@pytest.mark.parametrize(
    ("content", "fragment"),
    [
        ("# No front matter\n", "missing front matter"),
        ("---\nname: bad\n", "not closed"),
        ("---\nname: other\ndescription: x\n---\nBody\n", "directory is 'bad'"),
        ("---\nname: bad\n---\nBody\n", "description"),
        ("---\nname: bad\ndescription: x\n---\n\n", "no instructions"),
    ],
)
def test_malformed_skills_raise_clear_errors(tmp_path: Path, content: str, fragment: str) -> None:
    _write_skill(tmp_path, "bad", content)
    with pytest.raises(InvalidSkillError, match=fragment):
        SkillLoader(tmp_path).load("bad")


def test_missing_skills_directory(tmp_path: Path) -> None:
    with pytest.raises(SkillError, match="not found"):
        SkillLoader(tmp_path / "nope").discover()
