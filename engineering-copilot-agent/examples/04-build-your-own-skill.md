# Example 4 - Build your own skill

**Goal:** create a `summarize-docs` skill and teach the agent to use it for
requests like `summarize sample_project/README.md`.

## Step 1 - Write the procedure

Create `skills/summarize-docs/SKILL.md`:

```markdown
---
name: summarize-docs
description: Summarize a Markdown document into its main sections and key commands.
---

# Skill: Summarize Docs

## Procedure

1. Read the document with inspect_project.read_file.
2. List its headings in order.
3. Extract the commands shown in code blocks.
4. Do not invent sections that are not in the document.

## Response Sections

- Purpose
- Main Components
```

Check that it loads:

```bash
engineering-agent skills
```

You should see `summarize-docs` with sections `Purpose, Main Components`.

At this point the skill already **exists**: Copilot Chat can follow it if you
say "Follow skills/summarize-docs/SKILL.md to summarize sample_project/README.md".
The deterministic CLI still needs a rule to select it.

## Step 2 - Teach the orchestrator to select it

In `agent/orchestrator.py`, add a rule to `INTENT_RULES` **before** the
`code_explanation` rule:

```python
IntentRule(
    intent="code_explanation",
    label="documentation summary",
    keywords=("summarize", "summary"),
    skill_name="summarize-docs",
    example="summarize sample_project/README.md",
),
```

This reuses the explanation flow (`intent="code_explanation"`), which already
reads a file and renders the skill's sections. Sections named `Purpose` and
`Main Components` have generators, so for Markdown files you get the file
description and its headings.

## Step 3 - Try it

```bash
engineering-agent ask "summarize sample_project/README.md"
```

The trace now says `Selected summarize-docs skill.`

## Step 4 - Test it

Add to `tests/test_orchestrator.py`:

```python
def test_summarize_selects_summarize_docs(repo_root: Path, skills_dir: Path) -> None:
    response = _agent(repo_root, skills_dir).run("summarize sample_project/README.md")
    assert response.selected_skill == "summarize-docs"
    assert "## Main Components" in response.educational_response
```

```bash
pytest
```

## What you learned

- A skill is **data** (Markdown). Adding one needed zero Python for Copilot to use it.
- The orchestrator is the **decision maker**: it needs a rule to choose the skill.
- The tool did not change at all: the new skill reused an existing capability.
