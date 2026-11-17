---
description: Explain a file using the explain-code skill at a chosen level.
argument-hint: path to a file and a level (beginner, intermediate or advanced)
---

Explain the file `${input:path:sample_project/calculator.py}` for a
`${input:level:beginner}` audience (beginner, intermediate or advanced).

Follow these steps:

1. Read [the explain-code skill](../../skills/explain-code/SKILL.md) and follow
   its procedure, rules and response sections exactly.
2. Read the file before explaining it. Optionally run:
   `engineering-agent explain ${input:path:sample_project/calculator.py} --level ${input:level:beginner}`
   and use its output as a starting point.
3. Use these sections, in this order: Purpose, Main Components, Execution Flow,
   Inputs and Outputs, Example, Important Concepts, Possible Improvements.
4. Adapt vocabulary and depth to the requested level.

Rules:

- Do not invent functions, parameters or behavior that are not in the file.
- Do not claim the output of code you did not run.
- Keep improvements short; this is not a code review.
- Do not modify any file.
