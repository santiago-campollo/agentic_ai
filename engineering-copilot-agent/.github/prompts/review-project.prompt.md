---
description: Review the project or a single file using the code-review skill.
argument-hint: path to a file or folder (default sample_project)
---

Review `${input:path:sample_project}` using the code-review skill.

Follow these steps:

1. Read [the code-review skill](../../skills/code-review/SKILL.md) and follow its
   procedure, finding format and response sections.
2. Inspect before judging. Read every file you comment on and its matching
   test file. Optionally run `engineering-agent review ${input:path:sample_project}`
   to get a deterministic baseline, then add your own analysis.
3. Start with a short summary, then list:
   - **Verified findings** (directly observed in the code),
   - **Potential concerns** (plausible risks that depend on context),
   - **Suggestions** (optional improvements).
4. For every finding include: Severity (LOW, MEDIUM, HIGH), Category, File,
   Line or section, Observation, Why it matters, Suggested improvement.

Rules:

- Never present an assumption as a confirmed defect.
- Do not modify any file, especially in `sample_project/`, unless I explicitly
  ask for a fix in a follow-up message.
