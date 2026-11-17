# Demo Script (10-15 minutes)

A presenter guide for showing the Engineering Copilot Agent to engineering
students. Run every command from the repository root with the virtual
environment active.

**Before the session**

```bash
pip install -e ".[dev]"
pytest -q
```

Open VS Code with the integrated terminal and `sample_project/calculator.py` in
a tab. Increase the terminal font size.

---

## 1. Hook: what is an agent? (1-2 min)

**Say:** "A chatbot answers. An agent *decides, acts, observes and then
answers*. Today you will see each of those steps printed on screen."

**Ask:** "When Copilot edits a file for you, who actually opens the file?"
(Expected: a tool, not the model.)

Show the four ideas on a slide or in the README:

- Models provide intelligence.
- Agents coordinate decisions and actions.
- Skills provide reusable procedures.
- Tools provide capabilities.

## 2. The environment: inspect the project (2 min)

```bash
engineering-agent inspect sample_project
```

**Expect:** an ASCII tree with `calculator.py`, `README.md`, `test_calculator.py`,
`Selected skill : - (none needed)`, and `Selected tool : inspect_project.tree`.

**Explain:** listing files is a *capability*. No procedure is needed, so the
agent calls the tool directly. Point out the trace lines.

**Ask:** "Why do you think `.git` and `.env` are not in the tree?"

## 3. Skill vs. tool (2-3 min)

```bash
engineering-agent skills
engineering-agent tools
```

**Expect:** two skills with their response sections, one tool with three
operations.

**Explain (key moment):** open `skills/explain-code/SKILL.md` next to
`tools/inspect_project.py`.

- The **skill** is Markdown. It cannot read a file. It says *how* to explain.
- The **tool** is Python. It cannot explain anything. It *reads* files safely.
- The **agent** combines them.

**Ask:** "If I wanted the agent to write documentation, would I add a skill, a
tool, or both?" (Answer: a skill for the procedure; a tool only if it needs a
new capability, such as writing files.)

**Optional live trick:** swap two lines under `## Response Sections` in
`skills/explain-code/SKILL.md`, run the next command, and show that the order of
the answer changed without touching Python. Undo the change afterwards.

## 4. Explain code (2-3 min)

```bash
engineering-agent explain sample_project/calculator.py --level beginner
```

**Expect:** trace steps 1-10 and sections Purpose, Main Components, Execution
Flow, Inputs and Outputs, Example, Important Concepts, Possible Improvements.

**Explain:** the agent read the file with a tool, parsed it with `ast` (no
code was executed) and filled the sections that the skill defines.

Then show the difference in depth:

```bash
engineering-agent explain sample_project/calculator.py --level advanced
```

**Ask:** "The example does not show the result. Why?" (The agent never runs
code. It does not claim things it did not observe.)

## 5. Review and discover a defect (3 min)

**Ask first:** "The tests pass. Is this calculator correct?" Let students look at
`calculator.py` for 30 seconds.

```bash
engineering-agent review sample_project/calculator.py
```

**Expect:** a summary, then Verified Findings with a `[HIGH] Correctness` item
for `divide`, plus testing and error-message findings, one potential concern
and one suggestion.

**Explain:**

- Verified findings are facts observed in code.
- Potential concerns depend on intent. They are questions, not accusations.
- The agent read the test file too (look at the trace).
- No file was modified.

**Ask:** "What should `divide(5, 0)` do? Who decides?"

## 6. Safety boundaries (1 min)

```bash
engineering-agent explain ../README.md
```

**Expect:** `PATH_OUTSIDE_ROOT` and exit code 1. The agent explains the error
and does not guess.

**Say:** "Good agents have boundaries enforced in code, not just in prompts."

## 7. Structured output and Copilot (1-2 min)

```bash
engineering-agent review sample_project/calculator.py --json
```

**Explain:** `selected_skill`, `selected_tool`, `tool_arguments`,
`observation`, `reasoning_summary`, `trace`. This is what a real agent passes
around internally.

In VS Code, open Copilot Chat and run the prompt file
`/review-project` (from `.github/prompts/`). Compare its answer with the CLI.

## 8. Close (1 min)

**Say:**

> Models provide intelligence.
> Agents coordinate decisions and actions.
> Skills provide reusable procedures.
> Tools provide capabilities.

**Call to action:** "Clone the repo and do the lab in `docs/student-lab.md`.
Your first challenge is to write a new skill."
