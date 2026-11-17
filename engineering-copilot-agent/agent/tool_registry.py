"""A small registry that lets the agent discover and invoke tools by name."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from agent.models import ToolError, ToolResult, ToolSpec
from tools.inspect_project import create_inspect_project_tool


class ToolRegistry:
    """Stores tools and invokes them with validated, structured arguments.

    ``invoke`` never raises for expected problems. It always returns a
    :class:`ToolResult`, so the agent can treat failures as observations.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        """Add a tool. Raises ``ValueError`` if the name is already registered."""
        if spec.name in self._tools:
            raise ValueError(f"A tool named '{spec.name}' is already registered.")
        self._tools[spec.name] = spec

    def list_tools(self) -> list[ToolSpec]:
        """Return all registered tools sorted by name."""
        return [self._tools[name] for name in sorted(self._tools)]

    def get(self, name: str) -> ToolSpec:
        """Return a tool by name or raise ``ToolError`` with code ``UNKNOWN_TOOL``."""
        try:
            return self._tools[name]
        except KeyError:
            available = ", ".join(sorted(self._tools)) or "none"
            raise ToolError(
                "UNKNOWN_TOOL", f"Unknown tool '{name}'. Available tools: {available}."
            ) from None

    def invoke(self, name: str, arguments: Mapping[str, Any]) -> ToolResult:
        """Validate ``arguments`` against the tool contract and run the tool."""
        try:
            spec = self.get(name)
            _validate_arguments(spec, arguments)
            data = spec.handler(arguments)
            _ensure_json_serializable(spec.name, data)
        except ToolError as error:
            return ToolResult(tool_name=name, ok=False, error=error.to_dict())
        return ToolResult(tool_name=name, ok=True, data=data)


def _validate_arguments(spec: ToolSpec, arguments: Mapping[str, Any]) -> None:
    if not isinstance(arguments, Mapping):
        raise ToolError("INVALID_ARGUMENT", "Tool arguments must be a mapping (dictionary).")
    known = {parameter.name for parameter in spec.parameters}
    unknown = sorted(set(arguments) - known)
    if unknown:
        raise ToolError(
            "INVALID_ARGUMENT",
            f"Unknown argument(s) for '{spec.name}': {', '.join(unknown)}.",
        )
    missing = [p.name for p in spec.parameters if p.required and p.name not in arguments]
    if missing:
        raise ToolError(
            "INVALID_ARGUMENT",
            f"Missing required argument(s) for '{spec.name}': {', '.join(missing)}.",
        )


def _ensure_json_serializable(tool_name: str, data: object) -> None:
    if not isinstance(data, dict):
        raise ToolError("INVALID_RESULT", f"Tool '{tool_name}' must return a dictionary.")
    try:
        json.dumps(data)
    except (TypeError, ValueError) as error:
        raise ToolError(
            "INVALID_RESULT", f"Tool '{tool_name}' returned non-JSON data: {error}"
        ) from error


def build_default_registry(root: Path) -> ToolRegistry:
    """Create a registry with the built-in tools bound to ``root``."""
    registry = ToolRegistry()
    registry.register(create_inspect_project_tool(root))
    return registry
