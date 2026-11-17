# Architecture

This document explains how the Engineering Copilot Agent is built and why.

## Core idea

| Layer | Responsibility | File |
|---|---|---|
| Model | Intelligence: understand language, generate text. | *Not included.* Replaced by deterministic rules. |
| Agent (orchestrator) | Decide, act, observe, respond. Keep a trace. | `agent/orchestrator.py` |
| Skills | Reusable procedures written in Markdown. | `skills/*/SKILL.md`, loaded by `agent/skill_loader.py` |
| Tools | Capabilities with a typed contract. | `tools/inspect_project.py`, registered in `agent/tool_registry.py` |
| Environment | What the agent observes. | The repository |

## Components

### `agent/models.py` - contracts

- `ToolSpec`: name, description, parameters (`ToolParameter`) and handler.
- `ToolResult`: `tool_name`, `ok`, `data` or `error`. Always JSON-serializable.
- `ToolError`: a controlled failure with a stable `code` and a `message`.
- `Skill`: name, description, path, Markdown content and response sections.
- `Finding`: one review finding (`kind`, `severity`, `category`, `file`, `line`,
  `observation`, `why_it_matters`, `suggestion`).
- `AgentResponse`: the full result of one run.

### `tools/inspect_project.py` - the tool

One tool, three read-only operations:

| Operation | Arguments | Returns |
|---|---|---|
| `tree` | `path` (default `.`), `max_depth` (1-10, default 3) | entries, counts, ASCII tree text |
| `read_file` | `path` | `path`, `content`, `line_count`, `size_bytes` |
| `file_info` | `path` | `type`, `extension`, `size_bytes`, `is_text`, `line_count` |

Every path goes through `resolve_inside_root`, then the sensitive-file denylist.
New operations are added to the `OPERATIONS` dictionary.

### `agent/tool_registry.py` - the registry

- `register(spec)`, `list_tools()`, `get(name)`, `invoke(name, arguments)`.
- `invoke` validates arguments against the `ToolSpec` (unknown or missing
  arguments fail), runs the handler, checks the result is JSON, and converts
  any `ToolError` into a `ToolResult` with `ok=False`.
- `build_default_registry(root)` registers the built-in tools.

### `agent/skill_loader.py` - the skill loader

- `discover()` lists folders in `skills/`.
- `load(name)` reads `SKILL.md`, parses the front matter (`name`,
  `description`) and the `## Response Sections` list.
- Invalid skills raise `InvalidSkillError` with a clear message; unknown skills
  raise `SkillNotFoundError`.

### `agent/orchestrator.py` - the agent loop

1. **Classify** the request with `INTENT_RULES` (first keyword match wins).
2. **Select a skill** if the intent needs a procedure (`explain-code`,
   `code-review`). Inspection and file info do not need one.
3. **Select and invoke** a tool operation through the registry.
4. **Observe** the structured `ToolResult`. Errors are explained, never guessed around.
5. **Apply the skill**: the skill's response sections decide the shape of the
   answer; `agent/responses.py` fills each section from facts.
6. **Respond** with an `AgentResponse` that includes a step-by-step `trace`
   and a short `reasoning_summary`.

`reasoning_summary` is a short, observable explanation of *what* was chosen and
*why*. It is not hidden reasoning.

### `agent/code_analysis.py` - safe reading of Python

Uses `ast.parse` to build a syntax tree. This never executes the code. It
collects facts (functions, parameters, calls, raised exceptions, concepts) and
runs small review checks. Each check is a short function that students can read
and extend.

### `agent/responses.py` - rendering

Turns observations into Markdown. If a skill defines a section the renderer
does not know, the response says so instead of inventing content.

### `agent/cli.py` - the interface

`argparse` subcommands: `inspect`, `info`, `explain`, `review`, `ask`,
`skills`, `tools`. `--json` prints the structured response.

## Design decisions

- **Deterministic rules instead of an LLM.** Students can predict and debug
  every decision; tests are stable; no API keys.
- **Skills are data, not code.** Changing the order of `## Response Sections`
  in a `SKILL.md` changes the order of the answer without touching Python.
- **Tools return data, not text.** JSON results can be tested, logged and
  composed.
- **Errors are observations.** A rejected path is reported clearly, which is
  how a well-behaved agent should react.
- **Standard library only** at runtime. `pytest` and `ruff` are development tools.

## How this maps to GitHub Copilot

| This project | GitHub Copilot in VS Code |
|---|---|
| `INTENT_RULES` | The language model decides |
| `skills/*/SKILL.md` | Agent skills, prompt files, instruction files |
| `ToolRegistry` | Built-in tools and MCP servers |
| `inspect_project` | Tools such as file search and file reading |
| `trace` | The tool-call log shown in the chat |
| `agent/instructions.md` | System and custom instructions (`.github/copilot-instructions.md`) |

## Limitations

- Intent classification is keyword-based; paraphrases may not match.
- Code analysis covers Python only; other files get basic facts.
- Review checks are heuristics; they can miss issues and need human judgment.
- Paths in free-text requests (`ask`) must contain a `/`, `\`, or a file extension.
