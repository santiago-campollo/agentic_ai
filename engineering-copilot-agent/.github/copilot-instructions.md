# GitHub Copilot instructions for this repository

## Purpose

This is an **educational** repository for engineering students. It shows the
fundamentals of an AI agent with a small, deterministic Python project:

- Models provide intelligence.
- Agents coordinate decisions and actions (`agent/orchestrator.py`).
- Skills provide reusable procedures (`skills/<name>/SKILL.md`).
- Tools provide capabilities (`tools/inspect_project.py`).
- The repository is the environment being observed.

Optimize every answer for learning: clear, small and easy to follow.

## Coding guidelines

- Target Python 3.11+. Use the standard library whenever possible.
- Use type hints, `pathlib.Path` and `dataclasses` where they keep the code clear.
- Prefer small, readable functions over clever abstractions.
- Write docstrings for public modules, classes and functions.
- Tools return JSON-serializable dictionaries and raise `ToolError` for expected failures.
- Keep results deterministic (sorted output, no randomness, no network calls).
- Do not add external services, API keys, databases, Docker or new dependencies
  unless the user explicitly asks for them.
- Run `pytest` and `ruff check .` after changes.

## Safety constraints (do not weaken)

- `inspect_project` is **read-only**. Do not add write, delete or execute operations to it.
- Every path must be resolved and validated with `resolve_inside_root` before use.
- Keep the sensitive-file denylist (`.env`, private keys, credentials).
- Never use `eval`, `exec`, `pickle`, `shell=True` or dynamic imports.
- Never commit secrets or realistic-looking example tokens.

## How to explain or review code

- Before explaining code, read `skills/explain-code/SKILL.md` and follow its
  procedure and response sections.
- Before reviewing code, read `skills/code-review/SKILL.md` and follow its
  procedure and finding format.
- Inspect files before making claims about them. You can run
  `engineering-agent inspect <path>` or read the file directly.
- Clearly separate **verified findings** (observed in the code) from
  **potential concerns** and **suggestions**. Never present an assumption as a
  confirmed defect.
- Do not modify files in `sample_project/` during an explanation or review
  unless the user explicitly asks for a fix. Its defects are intentional teaching material.

## Repository map

- `agent/` - orchestrator, models, skill loader, tool registry, CLI.
- `tools/` - tool implementations.
- `skills/` - Markdown procedures.
- `sample_project/` - the calculator used in the demo.
- `tests/` - pytest suite.
- `docs/` - architecture, diagrams, demo script and student lab.
