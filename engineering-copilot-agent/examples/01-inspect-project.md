# Example 1 - Inspect a project

**Concept:** a *tool* gives the agent a capability. Listing files does not need
a procedure, so no skill is selected.

## Run it

```bash
engineering-agent inspect sample_project
```

## Output

```text
Engineering Copilot Agent
=========================
Request        : inspect sample_project
Selected skill : - (none needed)
Selected tool  : inspect_project.tree
Tool arguments : {"operation": "tree", "path": "sample_project"}
Why            : The request asks to see the project structure. Listing files is a direct capability of inspect_project.tree, so no skill (procedure) was needed.

Trace
-----
 1. Received request.
 2. Classified intent as project inspection.
 3. No skill needed: this request maps directly to a tool operation.
 4. Selected inspect_project.tree.
 5. Validated requested path and listed the directory tree.
 6. Produced educational response.

Response
--------
# Project structure

sample_project/
|-- calculator.py
|-- README.md
`-- test_calculator.py

- Directories: 0, files: 3 (max depth: 3).
- File types: `.md` (1), `.py` (2).
...
```

## What to notice

1. **Selected skill** is empty. Not every task needs a procedure.
2. **Tool arguments** are structured data, not free text.
3. The trace shows the path was **validated** before anything was listed.

## Try next

```bash
engineering-agent inspect . --depth 1          # shallower tree of the whole repo
engineering-agent info sample_project/calculator.py
engineering-agent inspect sample_project --json  # see the raw observation
engineering-agent inspect ..                     # PATH_OUTSIDE_ROOT, exit code 1
```

In the JSON output, look at `observation.data.entries`: this is exactly what
the agent "sees".
