"""Shared fixtures for the test suite."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def repo_root() -> Path:
    """The repository root (contains skills/ and sample_project/)."""
    return REPO_ROOT


@pytest.fixture
def skills_dir() -> Path:
    """The real skills directory shipped with the repository."""
    return REPO_ROOT / "skills"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """A small fake workspace with code, noise and sensitive files.

    The workspace lives in ``tmp_path / "ws"`` so tests can also create files
    *outside* it (in ``tmp_path``) to check path traversal protection.
    """
    root = tmp_path / "ws"
    (root / "src" / "pkg").mkdir(parents=True)
    (root / "src" / "app.py").write_text(
        '"""Demo app."""\n\n\ndef greet(name: str) -> str:\n    """Say hi."""\n'
        '    return f"Hello {name}"\n',
        encoding="utf-8",
    )
    (root / "src" / "pkg" / "deep.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "README.md").write_text("# Demo\n\nHello.\n", encoding="utf-8")
    (root / ".env").write_text("NOT_A_REAL_SECRET=placeholder\n", encoding="utf-8")
    (root / "__pycache__").mkdir()
    (root / "__pycache__" / "app.cpython.pyc").write_bytes(b"\x00\x01")
    (root / ".git").mkdir()
    (root / ".git" / "config").write_text("[core]\n", encoding="utf-8")
    (tmp_path / "outside.txt").write_text("outside the workspace\n", encoding="utf-8")
    return root
