---
name: explain-code
description: Explain what a source file does, adapted to a beginner, intermediate or advanced audience.
---

# Skill: Explain Code

Use this skill when someone asks what a file does, how it works, or wants to
learn from it. A skill is a **procedure**: it tells the agent how to think about
the task and how to shape the answer. It does not read files by itself; the
agent uses a tool (`inspect_project.read_file`) for that.

## When to use

- "Explain `sample_project/calculator.py`."
- "What does this file do?"
- "Describe how this module works for a beginner."

Do not use this skill for a full code review. Use `code-review` instead.

## Inputs

- A file path inside the workspace.
- A level: `beginner`, `intermediate` (default) or `advanced`.

## Procedure

1. **Observe first.** Read the file with `inspect_project.read_file`. Never
   explain a file you have not read.
2. **Identify the purpose.** Use the module docstring, file name and the main
   functions or classes.
3. **Explain inputs and outputs.** For each public function, list its
   parameters and what it returns.
4. **Identify the main components.** Functions, classes and important constants.
5. **Describe the execution flow.** What happens on import, which function
   calls which, where decisions and errors happen.
6. **Create a simple example.** Show how to call the main function. Do not
   claim an output you did not observe; the agent does not run code.
7. **Explain important concepts** found in the file (functions, type hints,
   exceptions, f-strings, ...).
8. **Point out a few possible improvements** without turning the explanation
   into a full review.
9. **Adapt the depth to the level:**
   - `beginner`: plain language, short sentences, analogies, comments in the example.
   - `intermediate`: structure plus design choices and trade-offs.
   - `advanced`: concise, include line ranges, call relationships and design notes.

## Rules

- Do not invent functions, classes, parameters or behavior that are not in the
  inspected file.
- If something is unclear from the code, say so instead of guessing.
- Do not modify any file.
- Keep improvements short; recommend `code-review` for a deeper analysis.

## Response Sections

- Purpose
- Main Components
- Execution Flow
- Inputs and Outputs
- Example
- Important Concepts
- Possible Improvements

## Quality checklist

Before answering, confirm that:

- Every function you mention exists in the file.
- The example uses real function names and parameters.
- The vocabulary matches the requested level.
