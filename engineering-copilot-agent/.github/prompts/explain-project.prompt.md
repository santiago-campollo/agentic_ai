---
description: Explain the architecture of the Engineering Copilot Agent for students.
---

Explain the architecture of this repository to an engineering student.

Follow these steps:

1. Read [the README](../../README.md), [the architecture doc](../../docs/architecture.md)
   and [the agent instructions](../../agent/instructions.md).
2. Inspect the code before describing it:
   [orchestrator](../../agent/orchestrator.py),
   [tool registry](../../agent/tool_registry.py),
   [skill loader](../../agent/skill_loader.py),
   [inspect_project tool](../../tools/inspect_project.py).
3. Explain the difference between **model**, **agent**, **tool** and **skill**
   using concrete files from this repository as examples.
4. Walk through the request lifecycle for
   `engineering-agent review sample_project/calculator.py`, step by step,
   matching each step to the trace the CLI prints.
5. Include one Mermaid diagram of the flow:
   Student -> Agent -> Orchestrator -> Skill -> Tool -> Repository -> Observation -> Response.
6. End with two ideas a student could implement to extend the agent.

Rules:

- Only describe functions and files that exist. Read them first.
- Keep the explanation beginner-friendly and under 600 words.
- Do not modify any file.
