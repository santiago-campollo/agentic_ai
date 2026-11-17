"""``inspect_project``: a read-only tool that lets the agent observe a repository.

Operations
----------
* ``tree``      - list directories and files up to a maximum depth.
* ``read_file`` - read one UTF-8 text file (size limited).
* ``file_info`` - return basic metadata about a file or directory.

Safety boundaries
-----------------
* Every path is resolved and must stay inside the configured root directory.
* Files that commonly contain secrets (``.env``, private keys, credentials) are denied.
* Binary files and files larger than ``MAX_FILE_SIZE_BYTES`` are rejected.
* The tool never writes files, never executes code and never runs commands.

To add a new operation, write a function with the signature
``(root: Path, arguments: Mapping[str, Any]) -> JsonDict`` and add it to
``OPERATIONS``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from functools import partial
from pathlib import Path
from typing import Any

from agent.models import JsonDict, ToolError, ToolParameter, ToolSpec

TOOL_NAME = "inspect_project"
MAX_FILE_SIZE_BYTES = 100 * 1024
DEFAULT_MAX_DEPTH = 3
MAX_ALLOWED_DEPTH = 10
MAX_TREE_ENTRIES = 500

IGNORED_DIR_NAMES = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "env",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".tox",
        ".idea",
        ".vscode",
        "node_modules",
        "build",
        "dist",
    }
)
IGNORED_DIR_SUFFIXES = (".egg-info",)
IGNORED_FILE_SUFFIXES = frozenset({".pyc", ".pyo", ".pyd", ".so", ".dll", ".exe", ".class", ".o"})

SENSITIVE_DIR_NAMES = frozenset({".git", ".ssh", ".aws", ".azure", ".gnupg", ".kube", ".docker"})
SENSITIVE_FILE_NAMES = frozenset(
    {
        "id_rsa",
        "id_dsa",
        "id_ecdsa",
        "id_ed25519",
        ".netrc",
        ".pypirc",
        ".npmrc",
        ".git-credentials",
        "credentials",
        "credentials.json",
        "secrets.json",
        "secrets.yaml",
        "secrets.yml",
        "secrets.toml",
    }
)
SENSITIVE_FILE_PREFIXES = (".env",)
SENSITIVE_FILE_SUFFIXES = frozenset(
    {".pem", ".key", ".p12", ".pfx", ".jks", ".keystore", ".kdbx", ".ppk", ".gpg", ".asc"}
)


def resolve_inside_root(root: Path, requested: object) -> Path:
    """Resolve ``requested`` against ``root`` and ensure it stays inside ``root``.

    ``Path.resolve`` collapses ``..`` segments and follows symbolic links, so the
    containment check runs on the *real* location of the target.

    Raises:
        ToolError: ``INVALID_ARGUMENT`` for malformed input or
            ``PATH_OUTSIDE_ROOT`` when the path escapes the workspace.
    """
    if not isinstance(requested, str) or not requested.strip():
        raise ToolError("INVALID_ARGUMENT", "'path' must be a non-empty string.")
    if "\x00" in requested:
        raise ToolError("INVALID_ARGUMENT", "'path' must not contain null bytes.")

    root_resolved = root.resolve()
    try:
        candidate = (root_resolved / requested.strip()).resolve()
    except (OSError, RuntimeError) as error:
        raise ToolError(
            "INVALID_ARGUMENT", f"Could not resolve path '{requested}': {error}"
        ) from error

    if not candidate.is_relative_to(root_resolved):
        raise ToolError(
            "PATH_OUTSIDE_ROOT",
            f"Access denied: '{requested}' resolves outside the workspace root.",
        )
    return candidate


def is_sensitive_path(relative_path: Path) -> bool:
    """Return ``True`` when a path looks like it may contain secrets."""
    parts = [part.lower() for part in relative_path.parts]
    if not parts:
        return False
    if any(part in SENSITIVE_DIR_NAMES for part in parts):
        return True
    name = parts[-1]
    return (
        name in SENSITIVE_FILE_NAMES
        or name.startswith(SENSITIVE_FILE_PREFIXES)
        or Path(name).suffix in SENSITIVE_FILE_SUFFIXES
    )


def count_lines(text: str) -> int:
    """Return the number of lines in ``text``."""
    return len(text.splitlines())


def _display_path(root: Path, path: Path) -> str:
    """Return ``path`` relative to ``root`` using forward slashes on every OS."""
    relative = path.relative_to(root)
    return relative.as_posix() if relative.parts else "."


def _require_path(arguments: Mapping[str, Any]) -> object:
    if "path" not in arguments:
        raise ToolError("INVALID_ARGUMENT", "This operation requires a 'path' argument.")
    return arguments["path"]


def _resolve_allowed(root: Path, requested: object) -> Path:
    """Resolve a path and reject sensitive locations."""
    target = resolve_inside_root(root, requested)
    if is_sensitive_path(target.relative_to(root.resolve())):
        raise ToolError(
            "SENSITIVE_FILE",
            f"Access denied: '{requested}' matches the sensitive-file denylist.",
        )
    return target


def _read_text(path: Path) -> tuple[str, int]:
    """Read a UTF-8 text file and return ``(text, size_in_bytes)``."""
    try:
        size = path.stat().st_size
        if size > MAX_FILE_SIZE_BYTES:
            raise ToolError(
                "FILE_TOO_LARGE",
                f"File is {size} bytes; the limit is {MAX_FILE_SIZE_BYTES} bytes.",
            )
        raw = path.read_bytes()
    except OSError as error:
        raise ToolError("READ_ERROR", f"Could not read file: {error.strerror or error}") from error

    if b"\x00" in raw:
        raise ToolError("BINARY_FILE", "File appears to be binary; only text files are supported.")
    try:
        return raw.decode("utf-8-sig"), size
    except UnicodeDecodeError:
        raise ToolError("BINARY_FILE", "File is not valid UTF-8 text.") from None


def _parse_depth(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ToolError("INVALID_ARGUMENT", "'max_depth' must be an integer.")
    if not 1 <= value <= MAX_ALLOWED_DEPTH:
        raise ToolError(
            "INVALID_ARGUMENT", f"'max_depth' must be between 1 and {MAX_ALLOWED_DEPTH}."
        )
    return value


def _is_visible(child: Path, root: Path) -> bool:
    """Decide whether ``tree`` should show ``child``."""
    if child.is_symlink():
        return False
    if child.is_dir():
        if child.name in IGNORED_DIR_NAMES or child.name.endswith(IGNORED_DIR_SUFFIXES):
            return False
    elif child.suffix.lower() in IGNORED_FILE_SUFFIXES:
        return False
    return not is_sensitive_path(child.relative_to(root))


def _visible_children(directory: Path, root: Path) -> list[Path]:
    """Return visible children sorted deterministically: directories first, then by name."""
    try:
        children = [child for child in directory.iterdir() if _is_visible(child, root)]
    except OSError:
        return []
    return sorted(children, key=lambda child: (not child.is_dir(), child.name.lower(), child.name))


def _walk(
    directory: Path,
    root: Path,
    depth: int,
    max_depth: int,
    prefix: str,
    entries: list[JsonDict],
    lines: list[str],
) -> bool:
    """Recursively collect entries. Returns ``True`` if the listing was truncated."""
    children = _visible_children(directory, root)
    for index, child in enumerate(children):
        if len(entries) >= MAX_TREE_ENTRIES:
            lines.append(f"{prefix}`-- ... (truncated)")
            return True
        is_last = index == len(children) - 1
        is_dir = child.is_dir()
        lines.append(f"{prefix}{'`-- ' if is_last else '|-- '}{child.name}{'/' if is_dir else ''}")
        entries.append(
            {
                "path": _display_path(root, child),
                "type": "directory" if is_dir else "file",
                "depth": depth,
            }
        )
        if is_dir and depth < max_depth:
            child_prefix = prefix + ("    " if is_last else "|   ")
            if _walk(child, root, depth + 1, max_depth, child_prefix, entries, lines):
                return True
    return False


def tree(root: Path, arguments: Mapping[str, Any]) -> JsonDict:
    """List directories and files below ``path`` (default ``.``) up to ``max_depth``."""
    root = root.resolve()
    target = resolve_inside_root(root, arguments.get("path", "."))
    max_depth = _parse_depth(arguments.get("max_depth", DEFAULT_MAX_DEPTH))
    if not target.exists():
        raise ToolError("NOT_FOUND", f"Directory not found: '{arguments.get('path', '.')}'.")
    if not target.is_dir():
        raise ToolError("NOT_A_DIRECTORY", f"'{_display_path(root, target)}' is not a directory.")

    display = _display_path(root, target)
    entries: list[JsonDict] = []
    lines = [f"{display}/"]
    truncated = _walk(target, root, 1, max_depth, "", entries, lines)
    return {
        "operation": "tree",
        "path": display,
        "max_depth": max_depth,
        "directory_count": sum(1 for entry in entries if entry["type"] == "directory"),
        "file_count": sum(1 for entry in entries if entry["type"] == "file"),
        "truncated": truncated,
        "entries": entries,
        "text": "\n".join(lines),
    }


def read_file(root: Path, arguments: Mapping[str, Any]) -> JsonDict:
    """Read a UTF-8 text file inside the workspace and return its content and metadata."""
    root = root.resolve()
    requested = _require_path(arguments)
    target = _resolve_allowed(root, requested)
    if not target.exists():
        raise ToolError("NOT_FOUND", f"File not found: '{requested}'.")
    if not target.is_file():
        raise ToolError("NOT_A_FILE", f"'{_display_path(root, target)}' is not a regular file.")

    text, size = _read_text(target)
    return {
        "operation": "read_file",
        "path": _display_path(root, target),
        "size_bytes": size,
        "line_count": count_lines(text),
        "content": text,
    }


def file_info(root: Path, arguments: Mapping[str, Any]) -> JsonDict:
    """Return basic metadata (type, extension, size, line count) for a path."""
    root = root.resolve()
    requested = _require_path(arguments)
    target = _resolve_allowed(root, requested)
    if not target.exists():
        raise ToolError("NOT_FOUND", f"Path not found: '{requested}'.")

    display = _display_path(root, target)
    if target.is_dir():
        return {"operation": "file_info", "path": display, "name": target.name, "type": "directory"}

    info: JsonDict = {
        "operation": "file_info",
        "path": display,
        "name": target.name,
        "type": "file",
        "extension": target.suffix,
        "size_bytes": target.stat().st_size,
        "is_text": None,
        "line_count": None,
    }
    try:
        text, _ = _read_text(target)
    except ToolError as error:
        if error.code == "BINARY_FILE":
            info["is_text"] = False
        elif error.code != "FILE_TOO_LARGE":
            raise
    else:
        info["is_text"] = True
        info["line_count"] = count_lines(text)
    return info


Operation = Callable[[Path, Mapping[str, Any]], JsonDict]

OPERATIONS: dict[str, Operation] = {
    "tree": tree,
    "read_file": read_file,
    "file_info": file_info,
}


def inspect_project(root: Path, arguments: Mapping[str, Any]) -> JsonDict:
    """Dispatch ``arguments['operation']`` to the matching read-only operation."""
    operation = arguments.get("operation")
    handler = OPERATIONS.get(operation) if isinstance(operation, str) else None
    if handler is None:
        available = ", ".join(sorted(OPERATIONS))
        raise ToolError(
            "UNKNOWN_OPERATION", f"Unknown operation {operation!r}. Available: {available}."
        )
    return handler(root, arguments)


def create_inspect_project_tool(root: Path) -> ToolSpec:
    """Build the ``inspect_project`` tool bound to a workspace ``root`` directory."""
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError(f"Workspace root is not a directory: {root}")
    return ToolSpec(
        name=TOOL_NAME,
        description=(
            "Read-only inspection of the workspace: list the directory tree, read a text "
            "file, or get file metadata. Never writes files or executes code."
        ),
        parameters=(
            ToolParameter("operation", f"One of: {', '.join(sorted(OPERATIONS))}.", required=True),
            ToolParameter("path", "Path relative to the workspace root. Defaults to '.' for tree."),
            ToolParameter(
                "max_depth",
                f"tree only: depth from 1 to {MAX_ALLOWED_DEPTH} (default {DEFAULT_MAX_DEPTH}).",
            ),
        ),
        handler=partial(inspect_project, root),
    )
