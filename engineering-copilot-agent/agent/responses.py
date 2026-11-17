"""Render observations into educational Markdown responses.

The *skill* decides which sections a response has (``## Response Sections`` in
``SKILL.md``). This module only knows how to fill sections it recognizes from
deterministic facts. Unknown sections are reported honestly instead of being
invented, which mirrors the "do not invent" rule in the skills.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath

from agent.code_analysis import FunctionFact, ModuleFacts
from agent.models import Finding, JsonDict

CONCEPTS: dict[str, tuple[str, str, str]] = {
    "imports": (
        "Imports",
        "`import` lets a file use code written in another file or library.",
        "Imports run the target module once and bind names in the current namespace.",
    ),
    "functions": (
        "Functions",
        "A function is a named, reusable recipe: it takes inputs (parameters) and can give "
        "back a result with `return`.",
        "`def` creates a function object when the module loads; the body runs only when called.",
    ),
    "type_hints": (
        "Type hints",
        "Notes like `a: float` and `-> float` say which kind of value is expected and returned.",
        "Annotations are not enforced at runtime; tools such as Pylance or mypy check them.",
    ),
    "docstrings": (
        "Docstrings",
        "The text in triple quotes right after `def` explains what the function does.",
        "Docstrings are stored in `__doc__` and power `help()` and editor tooltips.",
    ),
    "conditionals": (
        "Conditionals",
        "`if` / `elif` / `else` let the program choose between different paths.",
        "Long `if/elif` chains on one value can often become a dictionary lookup.",
    ),
    "loops": (
        "Loops",
        "`for` and `while` repeat a block of code.",
        "Prefer iterating directly over collections instead of using indexes.",
    ),
    "comprehensions": (
        "Comprehensions",
        "A compact way to build a list, set or dictionary from another collection.",
        "Comprehensions are expressions; keep them short so they stay readable.",
    ),
    "exceptions": (
        "Exceptions",
        "`raise` stops normal execution and reports an error that the caller can handle.",
        "Use specific exception types with messages that include the offending value.",
    ),
    "exception_handling": (
        "Exception handling",
        "`try` / `except` catches errors so the program can react instead of crashing.",
        "Catch the narrowest exception possible; broad handlers hide bugs.",
    ),
    "f_strings": (
        "f-strings",
        'Strings that start with `f` can embed values, like `f"Total: {total}"`.',
        "f-strings are evaluated at runtime and are the idiomatic way to format text.",
    ),
    "side_effects": (
        "Side effects",
        "`print()` writes to the screen. That is an effect beyond returning a value.",
        "Functions without side effects are easier to test, reuse and reason about.",
    ),
    "classes": (
        "Classes",
        "A class groups data and the functions (methods) that work on that data.",
        "Prefer dataclasses for simple data containers.",
    ),
    "decorators": (
        "Decorators",
        "`@something` above a function wraps it to add behavior.",
        "A decorator is a callable that receives a function and returns a replacement.",
    ),
    "context_managers": (
        "Context managers",
        "`with` sets something up and guarantees it is cleaned up afterwards.",
        "`with` calls `__enter__` and `__exit__`, even when an exception is raised.",
    ),
    "assertions": (
        "Assertions",
        "`assert` checks that something is true. pytest uses it to verify results.",
        "pytest rewrites `assert` statements to show detailed failure messages.",
    ),
}

LEVEL_NOTES = {
    "beginner": "Level: beginner. Technical terms are explained in plain language.",
    "intermediate": "Level: intermediate. Focus on structure and design choices.",
    "advanced": "Level: advanced. Concise, with line ranges and design notes.",
}

_NUMBER_SAMPLES = ("6", "3", "2", "1")
_UNKNOWN_SECTION = (
    "_This section is defined in SKILL.md, but this deterministic agent has no generator "
    "for it. A language-model-based agent would write it by following the skill's "
    "instructions._"
)


@dataclass(frozen=True)
class ExplainContext:
    """Everything needed to render an explanation."""

    path: str
    content: str
    level: str
    facts: ModuleFacts | None
    parse_error: str | None


@dataclass(frozen=True)
class ReviewedFile:
    """A file that was read during a review."""

    path: str
    test_path: str | None
    analyzed: bool


# --------------------------------------------------------------------------- helpers


def _bullets(items: Sequence[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _render_sections(sections: Sequence[str], generators: dict[str, Callable[[], str]]) -> str:
    """Render each skill-defined section with its generator (case-insensitive)."""
    lookup = {name.lower(): generator for name, generator in generators.items()}
    parts = []
    for section in sections:
        generator = lookup.get(section.lower())
        parts.append(f"## {section}\n\n{generator() if generator else _UNKNOWN_SECTION}")
    return "\n\n".join(parts)


def _not_python(context: ExplainContext) -> str:
    if context.parse_error:
        return f"Structural analysis was skipped: {context.parse_error}"
    return "Structural analysis is implemented only for Python (`.py`) files."


# --------------------------------------------------------------------------- explain-code


def _sample_arguments(function: FunctionFact) -> str:
    values: list[str] = []
    numbers = iter(_NUMBER_SAMPLES)
    strings = iter(function.compared_strings)
    for parameter in function.parameters:
        annotation = (parameter.annotation or "").lower()
        if annotation == "str":
            values.append(repr(next(strings, "text")))
        elif annotation == "bool":
            values.append("True")
        else:
            values.append(next(numbers, "1"))
    return ", ".join(values)


def _entry_points(facts: ModuleFacts) -> list[FunctionFact]:
    names = {function.name for function in facts.functions}
    return [
        function
        for function in facts.functions
        if any(call in names and call != function.name for call in function.calls)
    ]


def _internal_calls(function: FunctionFact, facts: ModuleFacts) -> list[str]:
    names = {f.name for f in facts.functions}
    return [call for call in function.calls if call in names and call != function.name]


def _explain_purpose(context: ExplainContext) -> str:
    name = PurePosixPath(context.path).name
    facts = context.facts
    if facts is None:
        suffix = PurePosixPath(context.path).suffix or "(no extension)"
        return f"`{name}` is a `{suffix}` text file with {len(context.content.splitlines())} lines."
    lines = []
    if facts.docstring:
        lines.append(f"The module docstring says: _{facts.docstring.strip().splitlines()[0]}_")
    else:
        lines.append("The module has no docstring, so its purpose is inferred from its contents.")
    tests = [f for f in facts.functions if f.is_test]
    if tests:
        lines.append(f"`{name}` contains {len(tests)} pytest test function(s).")
    else:
        lines.append(
            f"`{name}` defines {len(facts.functions)} function(s) and "
            f"{len(facts.classes)} class(es) that other code can use."
        )
    if context.level == "beginner":
        lines.append("In plain words: this file is a toolbox. Each function is one tool.")
    return "\n\n".join(lines)


def _explain_components(context: ExplainContext) -> str:
    facts = context.facts
    if facts is None:
        headings = [line.strip() for line in context.content.splitlines() if line.startswith("#")]
        return _bullets(headings) if headings else _not_python(context)
    items = []
    for function in facts.functions:
        summary = (function.docstring or "No docstring.").splitlines()[0]
        if context.level == "advanced":
            calls = _internal_calls(function, facts)
            extra = f"; calls {', '.join(calls)}" if calls else ""
            items.append(
                f"`{function.signature()}` (lines {function.line}-{function.end_line}, "
                f"{function.branch_count} branch(es){extra}): {summary}"
            )
        else:
            items.append(f"`{function.name}` (line {function.line}): {summary}")
    for cls in facts.classes:
        methods = ", ".join(cls.methods) or "no methods"
        items.append(f"class `{cls.name}` (line {cls.line}): methods {methods}")
    return _bullets(items) if items else "No top-level functions or classes were found."


def _explain_flow(context: ExplainContext) -> str:
    facts = context.facts
    if facts is None:
        return _not_python(context)
    name = PurePosixPath(context.path).name
    steps = [
        f"When Python imports `{name}`, it runs the top level of the file: it processes "
        f"{len(facts.imports)} import(s) and defines {len(facts.functions)} function(s). "
        "No function body runs yet."
    ]
    if facts.has_main_guard:
        steps.append(
            'The `if __name__ == "__main__":` block runs only when the file is executed directly.'
        )
    if any(f.is_test for f in facts.functions):
        steps.append(
            "pytest discovers every function whose name starts with `test_` and runs it; "
            "a test fails when an `assert` is false."
        )
    entry_points = _entry_points(facts)
    for function in entry_points:
        calls = ", ".join(f"`{c}`" for c in _internal_calls(function, facts))
        step = f"`{function.name}` coordinates the work and calls {calls}"
        if function.branch_count:
            step += f", choosing with {function.branch_count} conditional branch(es)"
        steps.append(step + ".")
    leaves = [f"`{f.name}`" for f in facts.functions if f not in entry_points and not f.is_test]
    if leaves:
        steps.append(f"{', '.join(leaves)} compute a value directly and return it.")
    for function in facts.functions:
        if function.raises:
            steps.append(f"`{function.name}` can raise {', '.join(function.raises)}.")
        if function.prints:
            steps.append(f"`{function.name}` also prints messages while it runs.")
    if context.level == "advanced":
        return "\n".join(f"{i}. {step}" for i, step in enumerate(steps, start=1))
    return _bullets(steps)


def _explain_io(context: ExplainContext) -> str:
    facts = context.facts
    if facts is None:
        return _not_python(context)
    items = []
    for function in facts.functions:
        inputs = (
            ", ".join(
                f"`{p.name}` ({p.annotation or 'not annotated'})" for p in function.parameters
            )
            or "none"
        )
        output = function.returns or "not annotated (read the `return` statements)"
        items.append(f"`{function.name}`: inputs {inputs}; output {output}.")
    return _bullets(items) if items else "This file does not define functions with inputs."


def _explain_example(context: ExplainContext) -> str:
    facts = context.facts
    if facts is None:
        return _not_python(context)
    if any(f.is_test for f in facts.functions):
        return f"Run these tests from the repository root:\n\n```bash\npytest {context.path}\n```"
    public = [f for f in facts.functions if f.is_public]
    if not public:
        return "There is no public function to call in this file."
    entry_points = [f for f in _entry_points(facts) if f.is_public]
    function = entry_points[0] if entry_points else public[0]
    module = PurePosixPath(context.path).stem
    lines = []
    if context.level == "beginner":
        lines.append(
            f"# Make the function available (run Python from the folder with {module}.py)."
        )
    lines.append(f"from {module} import {function.name}")
    lines.append("")
    if context.level == "beginner":
        lines.append("# Call the function with sample inputs and keep the result.")
    lines.append(f"result = {function.name}({_sample_arguments(function)})")
    lines.append("print(result)")
    return (
        "```python\n"
        + "\n".join(lines)
        + "\n```\n\nThe agent never runs code, so the output is not shown. "
        "Try it yourself and compare with what you expect."
    )


def _explain_concepts(context: ExplainContext) -> str:
    facts = context.facts
    if facts is None:
        return _not_python(context)
    items = []
    for key in facts.concepts:
        title, simple, technical = CONCEPTS[key]
        if context.level == "beginner":
            items.append(f"**{title}**: {simple}")
        elif context.level == "intermediate":
            items.append(f"**{title}**: {simple} {technical}")
        else:
            items.append(f"**{title}**: {technical}")
    return _bullets(items) if items else "No notable language features were detected."


def _explain_improvements(context: ExplainContext) -> str:
    facts = context.facts
    if facts is None:
        return _not_python(context)
    items = []
    if not facts.docstring:
        items.append("Add a module docstring that states the purpose of the file.")
    undocumented = [
        f"`{f.name}`" for f in facts.functions if f.is_public and not f.is_test and not f.docstring
    ]
    if undocumented:
        items.append(f"Add docstrings to {', '.join(undocumented)}.")
    untyped = [
        f"`{f.name}`"
        for f in facts.functions
        if not f.is_test and (f.returns is None or any(p.annotation is None for p in f.parameters))
    ]
    if untyped:
        items.append(f"Add type hints to {', '.join(untyped)}.")
    if not items:
        items.append("No obvious documentation or typing gaps were detected.")
    items.append(
        f"This is an explanation, not a review. For a structured review run "
        f"`engineering-agent review {context.path}`."
    )
    return _bullets(items)


def render_explanation(context: ExplainContext, sections: Sequence[str]) -> str:
    """Render an explanation using the sections defined by the explain-code skill."""
    generators: dict[str, Callable[[], str]] = {
        "Purpose": lambda: _explain_purpose(context),
        "Main Components": lambda: _explain_components(context),
        "Execution Flow": lambda: _explain_flow(context),
        "Inputs and Outputs": lambda: _explain_io(context),
        "Example": lambda: _explain_example(context),
        "Important Concepts": lambda: _explain_concepts(context),
        "Possible Improvements": lambda: _explain_improvements(context),
    }
    header = f"# Explanation of `{context.path}`\n\n_{LEVEL_NOTES[context.level]}_"
    return f"{header}\n\n{_render_sections(sections, generators)}"


# --------------------------------------------------------------------------- code-review


def _location(finding: Finding) -> str:
    return (
        f"{finding.file}, line {finding.line}" if finding.line else f"{finding.file} (whole file)"
    )


def _render_findings(findings: Sequence[Finding], empty_message: str) -> str:
    if not findings:
        return empty_message
    blocks = []
    for index, finding in enumerate(findings, start=1):
        blocks.append(
            f"### {index}. [{finding.severity}] {finding.category} - {_location(finding)}\n\n"
            f"- **Observation:** {finding.observation}\n"
            f"- **Why it matters:** {finding.why_it_matters}\n"
            f"- **Suggested improvement:** {finding.suggestion}"
        )
    return "\n\n".join(blocks)


def _review_summary(files: Sequence[ReviewedFile], findings: Sequence[Finding]) -> str:
    counts = Counter(f.kind for f in findings)
    file_lines = []
    for reviewed in files:
        tests = f" (tests: `{reviewed.test_path}`)" if reviewed.test_path else ""
        status = "" if reviewed.analyzed else " - not analyzed (only Python files are checked)"
        file_lines.append(f"`{reviewed.path}`{tests}{status}")
    highest = min(
        (f.severity for f in findings),
        key=lambda s: {"HIGH": 0, "MEDIUM": 1, "LOW": 2}[s],
        default=None,
    )
    return (
        f"Reviewed {len(files)} file(s):\n\n{_bullets(file_lines)}\n\n"
        f"Found **{counts['verified']} verified finding(s)**, "
        f"**{counts['potential']} potential concern(s)** and "
        f"**{counts['suggestion']} suggestion(s)**. "
        f"Highest severity: **{highest or 'none'}**.\n\n"
        "No files were modified."
    )


def render_review(
    files: Sequence[ReviewedFile], findings: Sequence[Finding], sections: Sequence[str]
) -> str:
    """Render a review using the sections defined by the code-review skill."""
    by_kind = {
        kind: [f for f in findings if f.kind == kind]
        for kind in ("verified", "potential", "suggestion")
    }
    generators: dict[str, Callable[[], str]] = {
        "Summary": lambda: _review_summary(files, findings),
        "Verified Findings": lambda: _render_findings(by_kind["verified"], "No verified findings."),
        "Potential Concerns": lambda: _render_findings(
            by_kind["potential"], "No potential concerns."
        ),
        "Suggestions": lambda: _render_findings(by_kind["suggestion"], "No suggestions."),
        "Limitations": lambda: (
            "These checks are small deterministic heuristics based on the syntax tree. "
            "They do not run the code, and they can miss problems or need human judgment. "
            "Treat potential concerns as questions to investigate, not confirmed defects."
        ),
    }
    return f"# Code review\n\n{_render_sections(sections, generators)}"


# --------------------------------------------------------------------------- direct tool answers


def render_tree(data: JsonDict) -> str:
    """Render the result of ``inspect_project.tree``."""
    extensions = Counter(
        PurePosixPath(entry["path"]).suffix or "(none)"
        for entry in data["entries"]
        if entry["type"] == "file"
    )
    types = ", ".join(f"`{ext}` ({count})" for ext, count in sorted(extensions.items())) or "none"
    truncated = "\n- The listing was truncated." if data["truncated"] else ""
    return (
        "# Project structure\n\n"
        f"```text\n{data['text']}\n```\n\n"
        f"- Directories: {data['directory_count']}, files: {data['file_count']} "
        f"(max depth: {data['max_depth']}).\n"
        f"- File types: {types}.{truncated}\n\n"
        "## What happened\n\n"
        "- Listing files is a **capability**, not a **procedure**, so the agent called the "
        "tool directly and did not need a skill.\n"
        "- The tool hides noise such as `.git`, `.venv` and `__pycache__`, and sensitive files "
        "such as `.env`."
    )


def render_file_info(data: JsonDict) -> str:
    """Render the result of ``inspect_project.file_info``."""
    rows = [f"Path: `{data['path']}`", f"Type: {data['type']}"]
    if data["type"] == "file":
        rows += [
            f"Extension: `{data['extension'] or '(none)'}`",
            f"Size: {data['size_bytes']} bytes",
            f"Text file: {data['is_text'] if data['is_text'] is not None else 'unknown (too large)'}",
            f"Lines: {data['line_count'] if data['line_count'] is not None else 'n/a'}",
        ]
    return f"# File information\n\n{_bullets(rows)}"


_ERROR_HINTS = {
    "PATH_OUTSIDE_ROOT": "The tool only works inside the workspace root. This is a safety "
    "boundary working as intended, not a bug.",
    "SENSITIVE_FILE": "Files that often contain secrets (`.env`, private keys, credentials) "
    "are on a denylist and are never read.",
    "NOT_FOUND": "Check the spelling, or run `engineering-agent inspect .` to see what exists.",
    "NOT_A_FILE": "This operation needs a file. Use `engineering-agent inspect <folder>` for folders.",
    "NOT_A_DIRECTORY": "This operation needs a folder. Use `explain` or `info` for files.",
    "FILE_TOO_LARGE": "Large files are rejected to keep responses small and fast.",
    "BINARY_FILE": "Only UTF-8 text files can be read.",
    "INVALID_ARGUMENT": "Check the arguments and try again.",
}


def render_tool_error(error: JsonDict) -> str:
    """Explain a controlled tool error to the student."""
    hint = _ERROR_HINTS.get(error.get("code", ""), "")
    return (
        "# Request could not be completed\n\n"
        "The `inspect_project` tool returned a controlled error:\n\n"
        f"- Code: `{error.get('code')}`\n"
        f"- Message: {error.get('message')}\n\n"
        f"{hint}"
    ).rstrip()


def render_help(rules: Sequence[tuple[str, Sequence[str], str]], reason: str) -> str:
    """Render help text listing supported intents, keywords and example requests."""
    rows = "\n".join(
        f"| {label} | {', '.join(keywords)} | `{example}` |" for label, keywords, example in rules
    )
    return (
        f"# How can I help?\n\n{reason}\n\n"
        "The agent recognizes requests with simple keyword rules:\n\n"
        "| Intent | Keywords | Example |\n|---|---|---|\n"
        f"{rows}\n\n"
        "CLI shortcuts:\n\n"
        "```bash\n"
        "engineering-agent inspect sample_project\n"
        "engineering-agent explain sample_project/calculator.py --level beginner\n"
        "engineering-agent review sample_project/calculator.py\n"
        "engineering-agent skills\n"
        "engineering-agent tools\n"
        "```"
    )
