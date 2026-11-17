"""Tests for the deterministic orchestrator."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.orchestrator import AgentOrchestrator, classify_intent, extract_path
from agent.skill_loader import SkillLoader
from agent.tool_registry import build_default_registry


def _agent(root: Path, skills_dir: Path) -> AgentOrchestrator:
    return AgentOrchestrator(build_default_registry(root), SkillLoader(skills_dir))


@pytest.mark.parametrize(
    ("request_text", "intent"),
    [
        ("inspect project", "project_inspection"),
        ("show project structure", "project_inspection"),
        ("explain file sample_project/calculator.py", "code_explanation"),
        ("explain code", "code_explanation"),
        ("review project", "code_review"),
        ("review file calculator.py", "code_review"),
        ("find potential issues", "code_review"),
        ("file info README.md", "file_info"),
    ],
)
def test_classify_intent(request_text: str, intent: str) -> None:
    rule = classify_intent(request_text)
    assert rule is not None and rule.intent == intent


def test_classify_intent_returns_none_for_unknown_requests() -> None:
    assert classify_intent("make me a sandwich") is None


@pytest.mark.parametrize(
    ("request_text", "expected"),
    [
        ("explain sample_project/calculator.py please", "sample_project/calculator.py"),
        ('review "src\\app.py"?', "src\\app.py"),
        ("explain calculator.py", "calculator.py"),
        ("inspect .", "."),
        ("show project structure", None),
    ],
)
def test_extract_path(request_text: str, expected: str | None) -> None:
    assert extract_path(request_text) == expected


def test_explain_selects_explain_code_skill(workspace: Path, skills_dir: Path) -> None:
    response = _agent(workspace, skills_dir).run("explain src/app.py", level="beginner")

    assert response.success
    assert response.selected_skill == "explain-code"
    assert response.selected_tool == "inspect_project.read_file"
    assert response.tool_arguments == {"operation": "read_file", "path": "src/app.py"}
    assert response.observation["ok"] is True
    assert "Selected explain-code skill." in response.trace
    assert response.trace[0] == "Received request."
    assert response.trace[-1] == "Produced educational response."
    for section in ("## Purpose", "## Main Components", "## Example", "## Possible Improvements"):
        assert section in response.educational_response
    assert "`greet`" in response.educational_response


def test_explain_levels_change_the_response(workspace: Path, skills_dir: Path) -> None:
    agent = _agent(workspace, skills_dir)
    beginner = agent.run("explain src/app.py", level="beginner").educational_response
    advanced = agent.run("explain src/app.py", level="advanced").educational_response

    assert beginner != advanced
    assert "Level: beginner" in beginner
    assert "lines 4-6" in advanced


def test_explain_without_path_returns_help(workspace: Path, skills_dir: Path) -> None:
    response = _agent(workspace, skills_dir).run("explain the code")
    assert not response.success
    assert "file path" in response.educational_response


def test_explain_rejects_unknown_level(workspace: Path, skills_dir: Path) -> None:
    response = _agent(workspace, skills_dir).run("explain src/app.py", level="expert")
    assert not response.success


def test_review_selects_code_review_skill_on_sample_project(
    repo_root: Path, skills_dir: Path
) -> None:
    calculator = repo_root / "sample_project" / "calculator.py"
    before = calculator.read_bytes()

    response = _agent(repo_root, skills_dir).run("review sample_project/calculator.py")

    assert response.success
    assert response.selected_skill == "code-review"
    assert response.selected_tool == "inspect_project.read_file"
    text = response.educational_response
    assert text.index("## Summary") < text.index("## Verified Findings")
    assert "## Potential Concerns" in text and "## Suggestions" in text
    assert "[HIGH] Correctness" in text
    assert "`multiply`" in text
    tools_used = [call["tool"] for call in response.supporting_observations]
    assert "inspect_project.file_info" in tools_used
    assert calculator.read_bytes() == before


def test_review_directory_reads_every_python_file(workspace: Path, skills_dir: Path) -> None:
    response = _agent(workspace, skills_dir).run("find potential issues in src/")

    assert response.success
    assert response.selected_skill == "code-review"
    assert "`src/app.py`" in response.educational_response
    assert "`src/pkg/deep.py`" in response.educational_response


def test_inspect_uses_tool_without_skill(workspace: Path, skills_dir: Path) -> None:
    response = _agent(workspace, skills_dir).run("show project structure")

    assert response.success
    assert response.selected_skill is None
    assert response.selected_tool == "inspect_project.tree"
    assert "No skill needed" in " ".join(response.trace)
    assert "src/" in response.educational_response


def test_unknown_intent_returns_help(workspace: Path, skills_dir: Path) -> None:
    response = _agent(workspace, skills_dir).run("make me a sandwich")

    assert not response.success
    assert response.selected_skill is None and response.selected_tool is None
    assert "explain sample_project/calculator.py" in response.educational_response


def test_path_traversal_is_reported_not_guessed(workspace: Path, skills_dir: Path) -> None:
    response = _agent(workspace, skills_dir).run("explain ../outside.txt")

    assert not response.success
    assert response.observation["error"]["code"] == "PATH_OUTSIDE_ROOT"
    assert response.observation["data"] is None
    assert "safety boundary" in response.educational_response


def test_sensitive_file_is_not_read(workspace: Path, skills_dir: Path) -> None:
    response = _agent(workspace, skills_dir).run("explain .env")

    assert not response.success
    assert response.observation["error"]["code"] == "SENSITIVE_FILE"
    assert "placeholder" not in response.to_json()


def test_response_is_json_serializable(workspace: Path, skills_dir: Path) -> None:
    response = _agent(workspace, skills_dir).run("review src/app.py")
    data = json.loads(response.to_json())

    expected_keys = {
        "request",
        "selected_skill",
        "selected_tool",
        "tool_arguments",
        "observation",
        "reasoning_summary",
        "educational_response",
        "trace",
    }
    assert expected_keys <= data.keys()
