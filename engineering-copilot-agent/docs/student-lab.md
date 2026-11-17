# Student Lab (30-45 minutes)

Work through the exercises in order. Each one has acceptance criteria so you
know when you are done. Run every command from the repository root.

---

## Exercise 1 - Clone and run (5 min)

```bash
git clone <repository-url>
cd engineering-copilot-agent
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Linux/macOS:        source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Replace `<repository-url>` with the URL given by your instructor (or your fork).

**Acceptance criteria**

- [ ] `pytest` reports all tests passed (one symlink test may be skipped on Windows).
- [ ] `engineering-agent --version` prints a version.

## Exercise 2 - Inspect the sample project (3 min)

```bash
engineering-agent inspect sample_project
engineering-agent inspect . --depth 1
engineering-agent info sample_project/calculator.py
```

**Acceptance criteria**

- [ ] You can name the tool and the operation used by each command.
- [ ] You can explain why no skill was selected.
- [ ] You can explain why `.venv` does not appear in the tree.

## Exercise 3 - Use the explain-code skill (5 min)

```bash
engineering-agent explain sample_project/calculator.py --level beginner
engineering-agent explain sample_project/calculator.py --level advanced
```

Open `skills/explain-code/SKILL.md`.

**Acceptance criteria**

- [ ] You can list the seven response sections and show where they are defined.
- [ ] You can describe one difference between the beginner and advanced output.
- [ ] You can point to the trace step where the file was read.

## Exercise 4 - Use the code-review skill (5 min)

```bash
engineering-agent review sample_project/calculator.py
engineering-agent review sample_project --json
```

**Acceptance criteria**

- [ ] You can explain the difference between a verified finding, a potential
      concern and a suggestion, using one example of each from the output.
- [ ] You can say which two files the agent read and why.
- [ ] You decide (and justify) whether the HIGH finding is a real defect.

## Exercise 5 - Create a `test-generator` skill (8 min)

Create `skills/test-generator/SKILL.md`:

```markdown
---
name: test-generator
description: Propose pytest tests for a Python file, including edge and error cases.
---

# Skill: Test Generator

## Procedure

1. Read the file with inspect_project.read_file.
2. List every public function and its parameters.
3. For each function, propose one normal case, one edge case and one error case.
4. Use pytest and `pytest.raises` for error cases.
5. Do not write files unless the user asks.

## Response Sections

- Summary
- Proposed Tests
- Edge Cases
- How to Run
```

**Acceptance criteria**

- [ ] `engineering-agent skills` lists `test-generator` with its four sections.
- [ ] `pytest` still passes.
- [ ] Bonus: ask Copilot Chat to follow `skills/test-generator/SKILL.md` for
      `sample_project/calculator.py` and compare its proposal with the review findings.

## Exercise 6 - Register a simple tool (8 min)

Create the `word_count` tool from the README section "How to create a new tool"
and register it in `build_default_registry` (`agent/tool_registry.py`).

**Acceptance criteria**

- [ ] `engineering-agent tools` lists `word_count` with a required `path` parameter.
- [ ] Calling it on `../README.md` returns `PATH_OUTSIDE_ROOT` (it reuses the safety checks).

Quick check in Python:

```python
from pathlib import Path
from agent.tool_registry import build_default_registry

registry = build_default_registry(Path("."))
print(registry.invoke("word_count", {"path": "sample_project/README.md"}))
print(registry.invoke("word_count", {"path": "../README.md"}))
```

## Exercise 7 - Add a test (5 min)

Create `tests/test_word_count.py`:

```python
from pathlib import Path

from agent.tool_registry import build_default_registry


def test_word_count_counts_words(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("one two three", encoding="utf-8")
    result = build_default_registry(tmp_path).invoke("word_count", {"path": "notes.txt"})
    assert result.ok and result.data == {"path": "notes.txt", "words": 3}


def test_word_count_rejects_outside_paths(tmp_path: Path) -> None:
    result = build_default_registry(tmp_path).invoke("word_count", {"path": "../x.txt"})
    assert not result.ok and result.error["code"] == "PATH_OUTSIDE_ROOT"
```

**Acceptance criteria**

- [ ] `pytest tests/test_word_count.py` passes.
- [ ] `ruff check .` passes.

## Exercise 8 - Commit (2 min)

```bash
git checkout -b feat/test-generator-and-word-count
git add skills/test-generator tools/word_count.py agent/tool_registry.py tests/test_word_count.py
git status
git commit -m "feat: add test-generator skill and word_count tool"
```

**Acceptance criteria**

- [ ] `git status` shows no secrets, `.venv` or `__pycache__` files staged.
- [ ] The commit message follows the format in `CONTRIBUTING.md`.

## Exercise 9 (optional) - Open a pull request (5 min)

```bash
git push -u origin feat/test-generator-and-word-count
```

Open a pull request on GitHub and fill in the checklist from `CONTRIBUTING.md`.

**Acceptance criteria**

- [ ] The PR description explains what the skill and the tool do.
- [ ] Every checklist item is checked or explained.
- [ ] Bonus: ask Copilot to review the PR using `.github/prompts/review-project.prompt.md`.

---

## Reflection questions

1. Which part of this agent would a language model replace?
2. Why is the safety check in the tool and not only in the instructions?
3. What would go wrong if a skill could execute code by itself?
