"""Data models and contracts shared by the agent, its tools and its skills.

Everything here is plain data. Keeping the contracts small and explicit makes it
easy to see what flows between the orchestrator, the tools and the skills.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

JsonDict = dict[str, Any]
"""A dictionary that can be serialized with :func:`json.dumps`."""

ToolHandler = Callable[[Mapping[str, Any]], JsonDict]
"""Signature every tool handler must follow: structured input -> JSON-serializable output."""


class ToolError(Exception):
    """A controlled, expected failure raised by a tool.

    Tools raise ``ToolError`` instead of crashing so the agent can explain the
    problem to the user. ``code`` is a stable identifier (for example
    ``PATH_OUTSIDE_ROOT``) and ``message`` is a human-readable explanation.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def to_dict(self) -> JsonDict:
        """Return the error as a JSON-serializable dictionary."""
        return {"code": self.code, "message": self.message}


@dataclass(frozen=True)
class ToolParameter:
    """Describes one argument that a tool accepts."""

    name: str
    description: str
    required: bool = False


@dataclass(frozen=True)
class ToolSpec:
    """The contract of a tool: name, description, accepted arguments and handler.

    The handler receives a mapping of arguments and returns a JSON-serializable
    dictionary. It raises :class:`ToolError` for expected failures.
    """

    name: str
    description: str
    parameters: tuple[ToolParameter, ...]
    handler: ToolHandler

    def describe(self) -> JsonDict:
        """Return a JSON-serializable description of the tool (without the handler)."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": [asdict(parameter) for parameter in self.parameters],
        }


@dataclass
class ToolResult:
    """The structured observation returned after invoking a tool."""

    tool_name: str
    ok: bool
    data: JsonDict | None = None
    error: JsonDict | None = None

    def to_dict(self) -> JsonDict:
        """Return the result as a JSON-serializable dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class Skill:
    """A reusable procedure written in Markdown (``SKILL.md``).

    A skill does not execute anything. It tells the agent *how* to approach a
    task and *how* to structure the answer.
    """

    name: str
    description: str
    path: Path
    content: str
    response_sections: tuple[str, ...] = ()

    def summary(self) -> JsonDict:
        """Return the skill metadata as a JSON-serializable dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "path": self.path.as_posix(),
            "response_sections": list(self.response_sections),
        }


@dataclass(frozen=True)
class Finding:
    """One code-review finding.

    ``kind`` separates facts from opinions:

    * ``verified``: directly observed in the inspected files.
    * ``potential``: a plausible risk that depends on context.
    * ``suggestion``: an optional improvement.
    """

    kind: str
    severity: str
    category: str
    file: str
    line: int | None
    observation: str
    why_it_matters: str
    suggestion: str

    def to_dict(self) -> JsonDict:
        """Return the finding as a JSON-serializable dictionary."""
        return asdict(self)


@dataclass
class AgentResponse:
    """The complete, structured result of one agent run."""

    request: str
    selected_skill: str | None
    selected_tool: str | None
    tool_arguments: JsonDict
    observation: JsonDict
    reasoning_summary: str
    educational_response: str
    trace: list[str]
    success: bool = True
    supporting_observations: list[JsonDict] = field(default_factory=list)

    def to_dict(self) -> JsonDict:
        """Return the response as a JSON-serializable dictionary."""
        return asdict(self)

    def to_json(self) -> str:
        """Return the response serialized as indented JSON."""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)
