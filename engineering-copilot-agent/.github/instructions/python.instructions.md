---
applyTo: "**/*.py"
description: Python conventions for the Engineering Copilot Agent.
---

# Python conventions

- Python 3.11+ only. Add `from __future__ import annotations` at the top of modules.
- Type-hint every function parameter and return value.
- Use `pathlib.Path` for paths, never string concatenation.
- Use `dataclasses` for plain data containers.
- Public modules, classes and functions need a short docstring.
- Raise `ToolError(code, message)` for expected tool failures; never return `None` to signal errors.
- Tool results must be JSON-serializable dictionaries.
- Sort anything that comes from the filesystem so results are deterministic on Windows, Linux and macOS.
- Use `as_posix()` when showing paths to users.
- Do not use `eval`, `exec`, `pickle`, `subprocess` with `shell=True`, or network calls.
- Tests use pytest and `tmp_path` for filesystem work. One behavior per test.
- Keep `ruff check .` and `ruff format --check .` clean.
