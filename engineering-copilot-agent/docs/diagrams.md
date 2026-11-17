# Diagrams

All diagrams use Mermaid, which renders on GitHub and in VS Code's Markdown
preview (built-in Mermaid support or a Mermaid extension).

## 1. Architecture

```mermaid
flowchart LR
    Student([Student]) --> Agent[Copilot / Agent CLI]
    Agent --> Orchestrator[Orchestrator<br/>agent/orchestrator.py]
    Orchestrator -->|1. select| Skill[Skill<br/>skills/*/SKILL.md]
    Orchestrator -->|2. invoke| Registry[ToolRegistry]
    Registry --> Tool[Tool<br/>inspect_project]
    Tool -->|read-only| Repo[(Repository)]
    Repo --> Observation[Observation<br/>ToolResult JSON]
    Observation --> Orchestrator
    Skill -.->|procedure and response sections| Response
    Orchestrator --> Response[Educational response<br/>+ trace]
    Response --> Student
```

## 2. Request lifecycle

```mermaid
sequenceDiagram
    actor Student
    participant CLI as CLI (agent/cli.py)
    participant Orch as Orchestrator
    participant Skills as SkillLoader
    participant Reg as ToolRegistry
    participant Tool as inspect_project
    participant Repo as Repository

    Student->>CLI: engineering-agent review sample_project/calculator.py
    CLI->>Orch: run("review sample_project/calculator.py")
    Orch->>Orch: classify intent (code review)
    Orch->>Skills: load("code-review")
    Skills-->>Orch: Skill (procedure + response sections)
    Orch->>Reg: invoke(inspect_project, file_info)
    Reg->>Tool: validate arguments, run
    Tool->>Repo: resolve path inside root, stat
    Repo-->>Tool: metadata
    Tool-->>Reg: JSON data
    Reg-->>Orch: ToolResult (observation)
    Orch->>Reg: invoke(inspect_project, read_file) for code and tests
    Reg-->>Orch: ToolResult with content
    Orch->>Orch: parse with ast, apply review checklist
    Orch-->>CLI: AgentResponse (trace, reasoning_summary, response)
    CLI-->>Student: readable output or --json
```

## 3. Extending with skills and tools

```mermaid
flowchart TB
    subgraph Skills["Skills (procedures, Markdown)"]
        S1[explain-code/SKILL.md]
        S2[code-review/SKILL.md]
        S3[test-generator/SKILL.md<br/><i>your new skill</i>]
    end
    subgraph Tools["Tools (capabilities, Python)"]
        T1[inspect_project<br/>tree / read_file / file_info]
        T2[word_count<br/><i>your new tool</i>]
    end
    Loader[SkillLoader.discover] --> Skills
    Registry[ToolRegistry.register] --> Tools
    Rules[INTENT_RULES<br/>add a rule for the new intent] --> Orchestrator
    Orchestrator --> Loader
    Orchestrator --> Registry
```

Adding a **skill** = add a folder with `SKILL.md` (+ optionally an intent rule).
Adding a **tool** = write a `ToolSpec` factory and register it.

## 4. Decision flow inside the orchestrator

```mermaid
flowchart TD
    A[Request] --> B{Matches an intent rule?}
    B -- no --> H[Return help with examples]
    B -- yes --> C{Needs a skill?}
    C -- "no (inspect, info)" --> T[Call tool directly]
    C -- "yes (explain, review)" --> D[Load SKILL.md]
    D --> E[Call tool to observe files]
    T --> F{Tool ok?}
    E --> F
    F -- no --> G[Explain the controlled error]
    F -- yes --> R[Build response from observation<br/>using skill sections]
```
