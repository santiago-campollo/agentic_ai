"""Tests for the command-line interface."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.cli import EXIT_FAILURE, EXIT_OK, EXIT_USAGE, main


def test_skills_command_lists_skills(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["skills"]) == EXIT_OK
    output = capsys.readouterr().out
    assert "explain-code" in output and "code-review" in output


def test_tools_command_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["tools", "--json"]) == EXIT_OK
    tools = json.loads(capsys.readouterr().out)
    assert tools[0]["name"] == "inspect_project"


def test_inspect_command(repo_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["inspect", "sample_project", "--root", str(repo_root)]) == EXIT_OK
    assert "calculator.py" in capsys.readouterr().out


def test_explain_command_json(repo_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [
            "explain",
            "sample_project/calculator.py",
            "--level",
            "beginner",
            "--root",
            str(repo_root),
            "--json",
        ]
    )
    data = json.loads(capsys.readouterr().out)
    assert code == EXIT_OK
    assert data["selected_skill"] == "explain-code"


def test_review_command(repo_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["review", "sample_project/calculator.py", "--root", str(repo_root)]) == EXIT_OK
    assert "Verified Findings" in capsys.readouterr().out


def test_missing_file_returns_failure(workspace: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["explain", "nope.py", "--root", str(workspace)]) == EXIT_FAILURE
    assert "NOT_FOUND" in capsys.readouterr().out


def test_path_traversal_returns_failure(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["review", "../outside.txt", "--root", str(workspace)]) == EXIT_FAILURE
    assert "PATH_OUTSIDE_ROOT" in capsys.readouterr().out


def test_unknown_intent_returns_failure(
    workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["ask", "make me a sandwich", "--root", str(workspace)]) == EXIT_FAILURE
    assert "How can I help?" in capsys.readouterr().out


def test_invalid_level_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["explain", "x.py", "--level", "expert"]) == EXIT_USAGE


def test_missing_root_is_a_usage_error(tmp_path: Path) -> None:
    assert main(["inspect", "--root", str(tmp_path / "missing")]) == EXIT_USAGE
