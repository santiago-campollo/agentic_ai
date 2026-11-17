---
applyTo: "**/*.md"
description: Documentation style for the Engineering Copilot Agent.
---

# Documentation conventions

- Write in simple, friendly English for engineering students.
- Prefer short sentences, numbered steps and concrete commands.
- Every command must be copy-pasteable and must work from the repository root.
- Show both Windows PowerShell and Linux/macOS variants when commands differ.
- Use Mermaid for diagrams. Do not link external images.
- Only document files, commands and options that exist. Verify before writing.
- Do not reveal the intentional defects of `sample_project/` outside
  `docs/instructor-notes.md`.
- Skills (`skills/*/SKILL.md`) must start with front matter containing `name`
  (equal to the folder name) and `description`, and should include a
  `## Response Sections` list.
