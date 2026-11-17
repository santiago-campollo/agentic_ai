"""Tests for the ToolRegistry contract."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from agent.models import JsonDict, ToolError, ToolParameter, ToolSpec
from agent.tool_registry import ToolRegistry, build_default_registry


def _echo(arguments: Mapping[str, Any]) -> JsonDict:
    return {"echo": arguments["text"]}


def _failing(arguments: Mapping[str, Any]) -> JsonDict:
    raise ToolError("BOOM", "Controlled failure.")


def _not_json(arguments: Mapping[str, Any]) -> JsonDict:
    return {"value": object()}


def _spec(name: str, handler: Any = _echo) -> ToolSpec:
    return ToolSpec(
        name=name,
        description=f"{name} tool",
        parameters=(ToolParameter("text", "Text to echo.", required=True),),
        handler=handler,
    )


def test_register_list_and_get() -> None:
    registry = ToolRegistry()
    registry.register(_spec("zeta"))
    registry.register(_spec("alpha"))

    assert [tool.name for tool in registry.list_tools()] == ["alpha", "zeta"]
    assert registry.get("alpha").description == "alpha tool"


def test_duplicate_registration_fails() -> None:
    registry = ToolRegistry()
    registry.register(_spec("echo"))
    with pytest.raises(ValueError):
        registry.register(_spec("echo"))


def test_invoke_success_returns_structured_result() -> None:
    registry = ToolRegistry()
    registry.register(_spec("echo"))

    result = registry.invoke("echo", {"text": "hi"})

    assert result.ok is True
    assert result.data == {"echo": "hi"}
    assert json.loads(json.dumps(result.to_dict()))["tool_name"] == "echo"


def test_invoke_unknown_tool_returns_error_result() -> None:
    result = ToolRegistry().invoke("missing", {})
    assert result.ok is False
    assert result.error is not None and result.error["code"] == "UNKNOWN_TOOL"


@pytest.mark.parametrize(
    ("arguments", "fragment"),
    [({}, "Missing required"), ({"text": "x", "extra": 1}, "Unknown argument")],
)
def test_invoke_validates_arguments(arguments: dict[str, Any], fragment: str) -> None:
    registry = ToolRegistry()
    registry.register(_spec("echo"))

    result = registry.invoke("echo", arguments)

    assert result.ok is False
    assert result.error is not None
    assert result.error["code"] == "INVALID_ARGUMENT"
    assert fragment in result.error["message"]


def test_invoke_converts_tool_errors_into_results() -> None:
    registry = ToolRegistry()
    registry.register(_spec("fail", _failing))

    result = registry.invoke("fail", {"text": "x"})

    assert result.ok is False
    assert result.error == {"code": "BOOM", "message": "Controlled failure."}


def test_invoke_rejects_non_json_results() -> None:
    registry = ToolRegistry()
    registry.register(_spec("bad", _not_json))

    result = registry.invoke("bad", {"text": "x"})

    assert result.ok is False
    assert result.error is not None and result.error["code"] == "INVALID_RESULT"


def test_default_registry_invokes_inspect_project(workspace: Path) -> None:
    registry = build_default_registry(workspace)

    result = registry.invoke("inspect_project", {"operation": "read_file", "path": "README.md"})
    outside = registry.invoke(
        "inspect_project", {"operation": "read_file", "path": "../outside.txt"}
    )

    assert [tool.name for tool in registry.list_tools()] == ["inspect_project"]
    assert result.ok and result.data is not None and result.data["content"].startswith("# Demo")
    assert not outside.ok and outside.error is not None
    assert outside.error["code"] == "PATH_OUTSIDE_ROOT"
