"""A deterministic, educational agent orchestrator.

There is no language model here. Decisions are made with small, transparent
rules so students can see every step of the agent loop:

    request -> classify intent -> select skill -> select & invoke tool
            -> observe structured result -> apply skill procedure -> respond

Each step is recorded in ``trace``. ``reasoning_summary`` is a short, observable
explanation of the choices made; it is not a hidden chain of thought.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from agent.code_analysis import analyze_python_source, is_test_file_name, review_python_source
from agent.models import AgentResponse, Finding, JsonDict, Skill, ToolResult
from agent.responses import (
    ExplainContext,
    ReviewedFile,
    render_explanation,
    render_file_info,
    render_help,
    render_review,
    render_tool_error,
    render_tree,
)
from agent.skill_loader import SkillError, SkillLoader
from agent.tool_registry import ToolRegistry

INSPECT_TOOL = "inspect_project"
EXPLAIN_LEVELS = ("beginner", "intermediate", "advanced")
DEFAULT_LEVEL = "intermediate"
REVIEW_TREE_DEPTH = 5
MAX_REVIEW_FILES = 20


@dataclass(frozen=True)
class IntentRule:
    """Maps keywords in a request to an intent and (optionally) a skill."""

    intent: str
    label: str
    keywords: tuple[str, ...]
    skill_name: str | None
    example: str

    def matches(self, request: str) -> bool:
        """Return ``True`` if any keyword appears as whole words in ``request``."""
        text = request.lower()
        return any(re.search(rf"\b{re.escape(keyword)}\b", text) for keyword in self.keywords)


# Order matters: the first matching rule wins.
INTENT_RULES: tuple[IntentRule, ...] = (
    IntentRule(
        intent="code_review",
        label="code review",
        keywords=("review", "potential issues", "issues", "bugs", "audit"),
        skill_name="code-review",
        example="review sample_project/calculator.py",
    ),
    IntentRule(
        intent="code_explanation",
        label="code explanation",
        keywords=("explain", "what does", "how does", "describe"),
        skill_name="explain-code",
        example="explain sample_project/calculator.py",
    ),
    IntentRule(
        intent="file_info",
        label="file metadata lookup",
        keywords=("info", "metadata"),
        skill_name=None,
        example="info sample_project/calculator.py",
    ),
    IntentRule(
        intent="project_inspection",
        label="project inspection",
        keywords=("inspect", "structure", "tree", "show project", "list files"),
        skill_name=None,
        example="inspect sample_project/",
    ),
)

_EXTENSION = re.compile(r"\.[A-Za-z0-9]+$")


def classify_intent(request: str) -> IntentRule | None:
    """Return the first rule that matches ``request``, or ``None``."""
    return next((rule for rule in INTENT_RULES if rule.matches(request)), None)


def extract_path(request: str) -> str | None:
    """Find the first path-like token in a free-text request.

    A token is path-like if it is ``.``, contains a slash, or ends with a file
    extension. Example: ``"explain sample_project/calculator.py please"``.
    """
    try:
        tokens = shlex.split(request, posix=False)
    except ValueError:
        tokens = request.split()
    for token in tokens:
        candidate = token.rstrip(",;:?!").strip("\"'")
        if not candidate or candidate.startswith("-"):
            continue
        if (
            candidate == "."
            or "/" in candidate
            or "\\" in candidate
            or _EXTENSION.search(candidate)
        ):
            return candidate
    return None


@dataclass
class _Run:
    """Mutable state for one agent run: trace steps and tool calls."""

    request: str
    trace: list[str] = field(default_factory=list)
    calls: list[JsonDict] = field(default_factory=list)
    primary_index: int | None = None

    def step(self, message: str) -> None:
        self.trace.append(message)


class AgentOrchestrator:
    """Coordinates skills and tools to answer one request at a time."""

    def __init__(self, registry: ToolRegistry, skill_loader: SkillLoader) -> None:
        self.registry = registry
        self.skill_loader = skill_loader

    # ------------------------------------------------------------------ public API

    def run(
        self,
        request: str,
        *,
        path: str | None = None,
        level: str = DEFAULT_LEVEL,
        max_depth: int | None = None,
    ) -> AgentResponse:
        """Handle a request and return a structured :class:`AgentResponse`.

        Args:
            request: Free-text request, for example ``"review sample_project"``.
            path: Optional explicit path; overrides any path found in ``request``.
            level: Explanation depth: ``beginner``, ``intermediate`` or ``advanced``.
            max_depth: Optional depth for project inspection.
        """
        run = _Run(request)
        run.step("Received request.")
        rule = classify_intent(request)
        if rule is None:
            run.step("Could not classify the intent with the available keyword rules.")
            run.step("Returned help with example requests.")
            return self._finish(
                run,
                skill=None,
                reasoning="No intent rule matched the request, so the agent returned help.",
                response=self.help_text("I could not match your request to a known intent."),
                success=False,
            )

        run.step(f"Classified intent as {rule.label}.")
        target = path if path is not None else extract_path(request)

        if rule.skill_name is None:
            run.step("No skill needed: this request maps directly to a tool operation.")
            if rule.intent == "file_info":
                return self._file_info(run, target)
            return self._inspect(run, target or ".", max_depth)

        try:
            skill = self.skill_loader.load(rule.skill_name)
        except SkillError as error:
            run.step(f"Could not load the {rule.skill_name} skill.")
            return self._finish(
                run,
                skill=None,
                reasoning=f"The {rule.skill_name} skill is required but could not be loaded.",
                response=f"# Skill error\n\n{error}",
                success=False,
            )
        run.step(f"Selected {skill.name} skill.")
        run.step(f"Loaded instructions from skills/{skill.name}/SKILL.md.")

        if rule.intent == "code_explanation":
            return self._explain(run, skill, target, level)
        return self._review(run, skill, target or ".")

    @staticmethod
    def help_text(reason: str) -> str:
        """Return help listing the supported intents and examples."""
        return render_help([(r.label, r.keywords, r.example) for r in INTENT_RULES], reason)

    # ------------------------------------------------------------------ tool calls

    def _invoke(self, run: _Run, arguments: JsonDict, *, primary: bool = False) -> ToolResult:
        operation = arguments["operation"]
        run.step(f"Selected {INSPECT_TOOL}.{operation}.")
        result = self.registry.invoke(INSPECT_TOOL, arguments)
        run.calls.append(
            {
                "tool": f"{INSPECT_TOOL}.{operation}",
                "arguments": dict(arguments),
                "result": result.to_dict(),
            }
        )
        if primary:
            run.primary_index = len(run.calls) - 1

        if not result.ok:
            error = result.error or {}
            run.step(f"Tool returned a controlled error ({error.get('code')}).")
        elif operation == "read_file":
            run.step("Validated requested path.")
            run.step("Read file successfully.")
        elif operation == "tree":
            run.step("Validated requested path and listed the directory tree.")
        else:
            run.step("Validated requested path and collected file metadata.")
        return result

    def _finish(
        self,
        run: _Run,
        *,
        skill: Skill | None,
        reasoning: str,
        response: str,
        success: bool = True,
    ) -> AgentResponse:
        index = run.primary_index
        if index is None and run.calls:
            index = 0
        primary: JsonDict = run.calls[index] if index is not None else {}
        return AgentResponse(
            request=run.request,
            selected_skill=skill.name if skill else None,
            selected_tool=primary.get("tool"),
            tool_arguments=primary.get("arguments", {}),
            observation=primary.get("result", {}),
            reasoning_summary=reasoning,
            educational_response=response,
            trace=run.trace,
            success=success,
            supporting_observations=[c for i, c in enumerate(run.calls) if i != index],
        )

    def _tool_failure(self, run: _Run, skill: Skill | None, result: ToolResult) -> AgentResponse:
        run.step("Explained the controlled error instead of guessing.")
        return self._finish(
            run,
            skill=skill,
            reasoning=(
                "The tool rejected the request, so the agent reports the error and does not "
                "invent an answer."
            ),
            response=render_tool_error(result.error or {}),
            success=False,
        )

    # ------------------------------------------------------------------ intents

    def _inspect(self, run: _Run, target: str, max_depth: int | None) -> AgentResponse:
        arguments: JsonDict = {"operation": "tree", "path": target}
        if max_depth is not None:
            arguments["max_depth"] = max_depth
        result = self._invoke(run, arguments, primary=True)
        if not result.ok or result.data is None:
            return self._tool_failure(run, None, result)
        run.step("Produced educational response.")
        return self._finish(
            run,
            skill=None,
            reasoning=(
                "The request asks to see the project structure. Listing files is a direct "
                "capability of inspect_project.tree, so no skill (procedure) was needed."
            ),
            response=render_tree(result.data),
        )

    def _file_info(self, run: _Run, target: str | None) -> AgentResponse:
        if not target:
            run.step("No file path was found in the request.")
            return self._finish(
                run,
                skill=None,
                reasoning="File metadata needs a path, and none was provided.",
                response=self.help_text(
                    "Please include a path, e.g. `info sample_project/calculator.py`."
                ),
                success=False,
            )
        result = self._invoke(run, {"operation": "file_info", "path": target}, primary=True)
        if not result.ok or result.data is None:
            return self._tool_failure(run, None, result)
        run.step("Produced educational response.")
        return self._finish(
            run,
            skill=None,
            reasoning="The request asks for file metadata, a direct capability of inspect_project.file_info.",
            response=render_file_info(result.data),
        )

    def _explain(self, run: _Run, skill: Skill, target: str | None, level: str) -> AgentResponse:
        if level not in EXPLAIN_LEVELS:
            run.step(f"Rejected unsupported level '{level}'.")
            return self._finish(
                run,
                skill=skill,
                reasoning="The requested explanation level is not supported.",
                response=f"# Invalid level\n\nUse one of: {', '.join(EXPLAIN_LEVELS)}.",
                success=False,
            )
        if not target:
            run.step("No file path was found in the request.")
            return self._finish(
                run,
                skill=skill,
                reasoning="Explaining code requires a file, and none was provided.",
                response=self.help_text(
                    "Please include a file path, e.g. `explain sample_project/calculator.py`."
                ),
                success=False,
            )

        result = self._invoke(run, {"operation": "read_file", "path": target}, primary=True)
        if not result.ok or result.data is None:
            return self._tool_failure(run, skill, result)

        path, content = result.data["path"], result.data["content"]
        facts, parse_error = None, None
        if path.endswith(".py"):
            try:
                facts = analyze_python_source(content)
                run.step("Parsed the source with ast (the code was not executed).")
            except SyntaxError as error:
                parse_error = f"the file is not valid Python (line {error.lineno}: {error.msg})."
                run.step("Could not parse the source; continued with basic facts.")

        sections = skill.response_sections or ("Purpose",)
        run.step(
            f"Applied the {skill.name} response structure ({len(sections)} sections, {level} level)."
        )
        response = render_explanation(
            ExplainContext(path, content, level, facts, parse_error), sections
        )
        run.step("Produced educational response.")
        return self._finish(
            run,
            skill=skill,
            reasoning=(
                f"The request asks for an explanation, so the {skill.name} skill was selected. "
                f"Explaining code requires its real contents, so the agent called "
                f"{INSPECT_TOOL}.read_file on '{path}'."
            ),
            response=response,
        )

    def _review(self, run: _Run, skill: Skill, target: str) -> AgentResponse:
        info = self._invoke(run, {"operation": "file_info", "path": target})
        if not info.ok or info.data is None:
            return self._tool_failure(run, skill, info)

        if info.data["type"] == "directory":
            plan = self._plan_directory_review(run, info.data["path"])
            if isinstance(plan, AgentResponse):
                return plan
        else:
            plan = [(info.data["path"], None)]

        reviewed: list[ReviewedFile] = []
        findings: list[Finding] = []
        for index, (source_path, test_path) in enumerate(plan):
            outcome = self._review_file(run, source_path, test_path, primary=index == 0)
            if isinstance(outcome, ToolResult):
                return self._tool_failure(run, skill, outcome)
            reviewed.append(outcome[0])
            findings.extend(outcome[1])

        run.step(
            "Applied the code-review checklist: correctness, error handling, readability, "
            "tests, security and edge cases."
        )
        run.step("Prioritized findings: verified first, then by severity.")
        sections = skill.response_sections or ("Summary",)
        response = render_review(reviewed, findings, sections)
        run.step("Produced educational response (no files were modified).")
        return self._finish(
            run,
            skill=skill,
            reasoning=(
                f"The request asks for a review, so the {skill.name} skill was selected. "
                "Findings must be grounded in real files, so the agent read the code and its "
                f"matching tests with {INSPECT_TOOL}.read_file before reporting anything."
            ),
            response=response,
        )

    def _plan_directory_review(
        self, run: _Run, directory: str
    ) -> list[tuple[str, str | None]] | AgentResponse:
        """List Python files in ``directory`` and pair each source file with its test."""
        tree = self._invoke(
            run, {"operation": "tree", "path": directory, "max_depth": REVIEW_TREE_DEPTH}
        )
        if not tree.ok or tree.data is None:
            return self._tool_failure(run, None, tree)
        python_files = [
            entry["path"]
            for entry in tree.data["entries"]
            if entry["type"] == "file" and entry["path"].endswith(".py")
        ]
        tests = {PurePosixPath(p).name: p for p in python_files if is_test_file_name(p)}
        sources = [p for p in python_files if not is_test_file_name(p)]
        if not sources:
            run.step("No Python source files were found.")
            return self._finish(
                run,
                skill=None,
                reasoning="There were no Python source files to review in this directory.",
                response=f"# Code review\n\nNo Python source files were found in `{directory}`.",
                success=False,
            )
        if len(sources) > MAX_REVIEW_FILES:
            run.step(f"Limited the review to the first {MAX_REVIEW_FILES} source files.")
            sources = sources[:MAX_REVIEW_FILES]
        return [(p, tests.get(f"test_{PurePosixPath(p).name}")) for p in sources]

    def _review_file(
        self, run: _Run, source_path: str, test_path: str | None, *, primary: bool
    ) -> tuple[ReviewedFile, list[Finding]] | ToolResult:
        """Read one file (and its tests) and run the review checks."""
        source = self._invoke(run, {"operation": "read_file", "path": source_path}, primary=primary)
        if not source.ok or source.data is None:
            return source
        path = source.data["path"]
        if not path.endswith(".py"):
            run.step(f"Skipped detailed checks for {path}: only Python files are analyzed.")
            return ReviewedFile(path, None, analyzed=False), []

        is_test = is_test_file_name(path)
        test_source: str | None = None
        if not is_test:
            test_path, test_source = self._find_test(run, path, test_path)

        findings = review_python_source(
            path,
            source.data["content"],
            test_path=test_path,
            test_source=test_source,
            is_test_file=is_test,
        )
        return ReviewedFile(path, test_path if test_source else None, analyzed=True), findings

    def _find_test(
        self, run: _Run, path: str, known_test: str | None
    ) -> tuple[str | None, str | None]:
        """Read the matching test file: ``test_<name>.py`` next to the file or in ``tests/``."""
        name = f"test_{PurePosixPath(path).name}"
        candidates = (
            [known_test]
            if known_test
            else [
                (PurePosixPath(path).parent / name).as_posix(),
                f"tests/{name}",
            ]
        )
        for candidate in candidates:
            result = self._invoke(run, {"operation": "read_file", "path": candidate})
            if result.ok and result.data is not None:
                return result.data["path"], result.data["content"]
        run.step(f"No matching test file was found for {path}.")
        return None, None
