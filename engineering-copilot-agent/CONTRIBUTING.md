# Contributing

Thanks for helping make this project better. It is a teaching repository, so
**clarity beats cleverness**.

## Environment setup

```bash
git clone <repository-url>
cd engineering-copilot-agent
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Linux/macOS:        source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Replace `<repository-url>` with the real URL of the repository (or of your fork).

## Code conventions

- Python 3.11+, standard library first. Do not add a dependency for convenience.
- Type hints on every function. Docstrings on public modules, classes and functions.
- `pathlib.Path` for paths; `as_posix()` when showing paths to users.
- Tools return JSON-serializable dictionaries and raise `ToolError` for expected failures.
- Keep results deterministic: sort filesystem results, no randomness, no network.
- Never use `eval`, `exec`, `pickle`, `shell=True` or dynamic imports.
- Format and lint with Ruff:

  ```bash
  ruff format .
  ruff check .
  ```

## How to add a skill

1. Create `skills/<name>/SKILL.md`. The folder name must use lowercase letters,
   digits and hyphens.
2. Add front matter with `name` (same as the folder) and `description`.
3. Write a numbered **Procedure**, the **Rules**, and a `## Response Sections` list.
4. Check it loads: `engineering-agent skills`.
5. If the CLI should use it, add an `IntentRule` to `INTENT_RULES` in
   `agent/orchestrator.py` and a handler for the new intent.
6. Add a test in `tests/test_skill_loader.py` or `tests/test_orchestrator.py`.

## How to add a tool

1. Create `tools/<name>.py` with a `create_<name>_tool(root: Path) -> ToolSpec` factory.
2. Define parameters with `ToolParameter` and mark required ones.
3. Validate every path with `resolve_inside_root` (or reuse `read_file`).
4. Raise `ToolError(code, message)` for expected failures.
5. Register it in `build_default_registry` in `agent/tool_registry.py`.
6. Check it appears in `engineering-agent tools`.
7. Add tests using `tmp_path`, including at least one rejection case.

Tools must not write files, execute code or call the network unless the change
is explicitly discussed and reviewed as a security-sensitive change.

## Running tests

```bash
pytest                         # all tests, including sample_project
pytest tests/test_orchestrator.py -k review
pytest -x -vv                  # stop at first failure, verbose
```

## Commit format

Use short, imperative messages with a type prefix
([Conventional Commits](https://www.conventionalcommits.org/) style):

```text
feat: add word_count tool
fix: reject absolute paths outside the root
docs: explain skills vs tools in README
test: cover binary file rejection
refactor: simplify intent rules
```

## Pull request checklist

- [ ] `pytest` passes.
- [ ] `ruff check .` and `ruff format --check .` pass.
- [ ] New code has type hints and docstrings.
- [ ] New behavior has tests (including a failure case).
- [ ] No secrets, tokens or `.env` files are committed.
- [ ] Safety boundaries are unchanged (read-only, inside root, denylist).
- [ ] `sample_project/` defects were not fixed accidentally.
- [ ] Docs (`README.md`, `docs/`) are updated if commands or behavior changed.

## Contribution challenges

### Challenge 1: Build your first skill

Create `skills/test-generator/SKILL.md` that teaches the agent to propose pytest
tests for a file.

Acceptance criteria:

- `engineering-agent skills` lists `test-generator` with its description.
- The skill has a numbered procedure (read the file, list public functions,
  propose normal cases, edge cases and error cases).
- It has a `## Response Sections` list (for example: Summary, Proposed Tests,
  Edge Cases, How to Run).
- It says that tests are *proposed*, not written to disk, unless the user asks.
- `pytest` still passes.

### Challenge 2: Build your first tool

Create a `word_count` tool (see the example in the README).

Acceptance criteria:

- `engineering-agent tools` lists `word_count` with a `path` parameter.
- It reuses `read_file` or `resolve_inside_root`, so `../` paths are rejected.
- `tests/test_word_count.py` covers a normal file, a missing file and a path
  outside the root, using `tmp_path`.
- `pytest` and `ruff check .` pass.
