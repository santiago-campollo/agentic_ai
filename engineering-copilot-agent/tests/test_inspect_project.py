"""Tests for the read-only inspect_project tool."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from agent.models import ToolError
from tools.inspect_project import (
    MAX_FILE_SIZE_BYTES,
    create_inspect_project_tool,
    file_info,
    inspect_project,
    read_file,
    tree,
)


def test_tree_lists_files_and_hides_noise(workspace: Path) -> None:
    result = tree(workspace, {"path": "."})
    paths = {entry["path"] for entry in result["entries"]}

    assert {"src", "src/app.py", "src/pkg", "src/pkg/deep.py", "README.md"} <= paths
    assert not any(p.startswith((".git", "__pycache__")) for p in paths)
    assert ".env" not in paths
    assert result["file_count"] == 3
    assert result["directory_count"] == 2


def test_tree_respects_max_depth(workspace: Path) -> None:
    result = tree(workspace, {"path": ".", "max_depth": 1})
    paths = {entry["path"] for entry in result["entries"]}

    assert paths == {"src", "README.md"}
    assert all(entry["depth"] == 1 for entry in result["entries"])


def test_tree_order_is_deterministic_directories_first(workspace: Path) -> None:
    first = tree(workspace, {"path": "."})
    second = tree(workspace, {"path": "."})

    assert first == second
    assert first["entries"][0]["type"] == "directory"
    assert first["text"].splitlines()[0] == "./"


@pytest.mark.parametrize("depth", [0, 99, "3", True, None])
def test_tree_rejects_invalid_depth(workspace: Path, depth: object) -> None:
    with pytest.raises(ToolError) as error:
        tree(workspace, {"path": ".", "max_depth": depth})
    assert error.value.code == "INVALID_ARGUMENT"


def test_tree_rejects_a_file_path(workspace: Path) -> None:
    with pytest.raises(ToolError) as error:
        tree(workspace, {"path": "README.md"})
    assert error.value.code == "NOT_A_DIRECTORY"


def test_read_file_returns_content_and_metadata(workspace: Path) -> None:
    result = read_file(workspace, {"path": "src/app.py"})

    assert result["path"] == "src/app.py"
    assert "def greet" in result["content"]
    assert result["line_count"] == 6
    assert result["size_bytes"] == (workspace / "src" / "app.py").stat().st_size


def test_read_file_accepts_backslash_separators_on_any_os(workspace: Path) -> None:
    requested = "src\\app.py" if os.name == "nt" else "src/app.py"
    assert read_file(workspace, {"path": requested})["path"] == "src/app.py"


@pytest.mark.parametrize("requested", ["../outside.txt", "src/../../outside.txt"])
def test_read_file_rejects_path_traversal(workspace: Path, requested: str) -> None:
    with pytest.raises(ToolError) as error:
        read_file(workspace, {"path": requested})
    assert error.value.code == "PATH_OUTSIDE_ROOT"


def test_read_file_rejects_absolute_path_outside_root(workspace: Path) -> None:
    outside = workspace.parent / "outside.txt"
    with pytest.raises(ToolError) as error:
        read_file(workspace, {"path": str(outside)})
    assert error.value.code == "PATH_OUTSIDE_ROOT"


def test_read_file_rejects_symlink_escaping_root(workspace: Path) -> None:
    link = workspace / "link.txt"
    try:
        link.symlink_to(workspace.parent / "outside.txt")
    except (OSError, NotImplementedError):
        pytest.skip("Creating symlinks is not permitted on this system.")
    with pytest.raises(ToolError) as error:
        read_file(workspace, {"path": "link.txt"})
    assert error.value.code == "PATH_OUTSIDE_ROOT"


def test_read_file_rejects_large_files(workspace: Path) -> None:
    (workspace / "big.txt").write_text("a" * (MAX_FILE_SIZE_BYTES + 1), encoding="utf-8")
    with pytest.raises(ToolError) as error:
        read_file(workspace, {"path": "big.txt"})
    assert error.value.code == "FILE_TOO_LARGE"


def test_read_file_reports_missing_files(workspace: Path) -> None:
    with pytest.raises(ToolError) as error:
        read_file(workspace, {"path": "does_not_exist.py"})
    assert error.value.code == "NOT_FOUND"


def test_read_file_rejects_binary_files(workspace: Path) -> None:
    (workspace / "image.bin").write_bytes(b"\x89PNG\x00\x00binary")
    with pytest.raises(ToolError) as error:
        read_file(workspace, {"path": "image.bin"})
    assert error.value.code == "BINARY_FILE"


def test_read_file_rejects_directories(workspace: Path) -> None:
    with pytest.raises(ToolError) as error:
        read_file(workspace, {"path": "src"})
    assert error.value.code == "NOT_A_FILE"


@pytest.mark.parametrize(
    "name", [".env", ".env.local", "server.pem", "id_rsa", "credentials.json", ".git/config"]
)
def test_read_file_rejects_sensitive_files(workspace: Path, name: str) -> None:
    target = workspace / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("placeholder\n", encoding="utf-8")
    with pytest.raises(ToolError) as error:
        read_file(workspace, {"path": name})
    assert error.value.code == "SENSITIVE_FILE"


def test_read_file_requires_a_path(workspace: Path) -> None:
    with pytest.raises(ToolError) as error:
        read_file(workspace, {})
    assert error.value.code == "INVALID_ARGUMENT"


def test_file_info_reports_metadata(workspace: Path) -> None:
    info = file_info(workspace, {"path": "README.md"})

    assert info["type"] == "file"
    assert info["extension"] == ".md"
    assert info["is_text"] is True
    assert info["line_count"] == 3
    assert file_info(workspace, {"path": "src"})["type"] == "directory"


def test_file_info_detects_binary(workspace: Path) -> None:
    (workspace / "data.bin").write_bytes(b"\x00\x01\x02")
    info = file_info(workspace, {"path": "data.bin"})
    assert info["is_text"] is False
    assert info["line_count"] is None


def test_unknown_operation_is_rejected(workspace: Path) -> None:
    with pytest.raises(ToolError) as error:
        inspect_project(workspace, {"operation": "delete", "path": "README.md"})
    assert error.value.code == "UNKNOWN_OPERATION"


def test_results_are_json_serializable(workspace: Path) -> None:
    for arguments in (
        {"operation": "tree"},
        {"operation": "read_file", "path": "src/app.py"},
        {"operation": "file_info", "path": "src/app.py"},
    ):
        assert json.loads(json.dumps(inspect_project(workspace, arguments)))


def test_tool_spec_describes_contract(workspace: Path) -> None:
    spec = create_inspect_project_tool(workspace)
    description = spec.describe()

    assert description["name"] == "inspect_project"
    assert [p["name"] for p in description["parameters"]] == ["operation", "path", "max_depth"]
    assert spec.handler({"operation": "file_info", "path": "README.md"})["type"] == "file"


def test_tool_does_not_modify_files(workspace: Path) -> None:
    before = {p: p.read_bytes() for p in workspace.rglob("*") if p.is_file()}
    tree(workspace, {"path": "."})
    read_file(workspace, {"path": "src/app.py"})
    file_info(workspace, {"path": "README.md"})
    after = {p: p.read_bytes() for p in workspace.rglob("*") if p.is_file()}
    assert before == after
