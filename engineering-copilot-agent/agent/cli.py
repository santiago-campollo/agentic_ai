"""Command-line interface for the Engineering Copilot Agent.

Examples::

    engineering-agent inspect sample_project
    engineering-agent explain sample_project/calculator.py --level beginner
    engineering-agent review sample_project/calculator.py
    engineering-agent ask "find potential issues in sample_project/calculator.py"
    engineering-agent skills
    engineering-agent tools

Exit codes: 0 success, 1 controlled failure (invalid path, unknown intent,
invalid skill, ...), 2 usage error (bad arguments or missing workspace root).
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from agent import __version__
from agent.models import AgentResponse
from agent.orchestrator import DEFAULT_LEVEL, EXPLAIN_LEVELS, AgentOrchestrator
from agent.skill_loader import SkillError, SkillLoader
from agent.tool_registry import ToolRegistry, build_default_registry

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_USAGE = 2
DEFAULT_SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser with all subcommands."""
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Workspace root the agent may read (default: current directory).",
    )
    common.add_argument(
        "--skills-dir",
        type=Path,
        default=DEFAULT_SKILLS_DIR,
        help="Directory that contains skills (default: the repository's skills/ folder).",
    )
    common.add_argument("--json", action="store_true", help="Print structured JSON output.")

    parser = argparse.ArgumentParser(
        prog="engineering-agent",
        description="An educational agent that inspects, explains and reviews code.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    inspect = commands.add_parser("inspect", parents=[common], help="Show the project structure.")
    inspect.add_argument("path", nargs="?", default=".", help="Folder to inspect (default: .).")
    inspect.add_argument("--depth", type=int, default=None, help="Maximum depth (1-10).")

    info = commands.add_parser("info", parents=[common], help="Show file metadata.")
    info.add_argument("path", help="File or folder.")

    explain = commands.add_parser("explain", parents=[common], help="Explain a file.")
    explain.add_argument("path", help="File to explain.")
    explain.add_argument("--level", choices=EXPLAIN_LEVELS, default=DEFAULT_LEVEL)

    review = commands.add_parser("review", parents=[common], help="Review a file or folder.")
    review.add_argument("path", nargs="?", default=".", help="File or folder (default: .).")

    ask = commands.add_parser("ask", parents=[common], help="Send a free-text request.")
    ask.add_argument("request", help='For example: "explain sample_project/calculator.py".')
    ask.add_argument("--level", choices=EXPLAIN_LEVELS, default=DEFAULT_LEVEL)

    commands.add_parser("skills", parents=[common], help="List available skills.")
    commands.add_parser("tools", parents=[common], help="List available tools.")
    return parser


def format_response(response: AgentResponse) -> str:
    """Format an :class:`AgentResponse` for humans."""
    arguments = json.dumps(response.tool_arguments) if response.tool_arguments else "-"
    trace = "\n".join(f"{i:>2}. {step}" for i, step in enumerate(response.trace, start=1))
    return (
        "Engineering Copilot Agent\n"
        "=========================\n"
        f"Request        : {response.request}\n"
        f"Selected skill : {response.selected_skill or '- (none needed)'}\n"
        f"Selected tool  : {response.selected_tool or '-'}\n"
        f"Tool arguments : {arguments}\n"
        f"Why            : {response.reasoning_summary}\n\n"
        f"Trace\n-----\n{trace}\n\n"
        f"Response\n--------\n{response.educational_response}\n"
    )


def _list_skills(loader: SkillLoader, as_json: bool) -> int:
    try:
        skills = loader.load_all()
    except SkillError as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_FAILURE
    if as_json:
        print(json.dumps([skill.summary() for skill in skills], indent=2))
        return EXIT_OK
    print("Available skills (procedures written in Markdown):\n")
    for skill in skills:
        print(f"- {skill.name}: {skill.description}")
        print(f"  file: skills/{skill.name}/SKILL.md")
        print(f"  response sections: {', '.join(skill.response_sections) or '-'}")
    return EXIT_OK


def _list_tools(registry: ToolRegistry, as_json: bool) -> int:
    tools = registry.list_tools()
    if as_json:
        print(json.dumps([tool.describe() for tool in tools], indent=2))
        return EXIT_OK
    print("Available tools (capabilities implemented in Python):\n")
    for tool in tools:
        print(f"- {tool.name}: {tool.description}")
        for parameter in tool.parameters:
            required = "required" if parameter.required else "optional"
            print(f"    {parameter.name} ({required}): {parameter.description}")
    return EXIT_OK


def _configure_stdout() -> None:
    # Avoid UnicodeEncodeError on legacy Windows code pages when output is redirected.
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(errors="replace")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return an exit code."""
    _configure_stdout()
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exit_request:
        return int(exit_request.code or 0)

    root: Path = args.root
    if not root.is_dir():
        print(f"error: workspace root is not a directory: {root}", file=sys.stderr)
        return EXIT_USAGE

    registry = build_default_registry(root)
    loader = SkillLoader(args.skills_dir)

    if args.command == "skills":
        return _list_skills(loader, args.json)
    if args.command == "tools":
        return _list_tools(registry, args.json)

    orchestrator = AgentOrchestrator(registry, loader)
    if args.command == "ask":
        response = orchestrator.run(args.request, level=args.level)
    elif args.command == "explain":
        response = orchestrator.run(f"explain {args.path}", path=args.path, level=args.level)
    elif args.command == "inspect":
        response = orchestrator.run(f"inspect {args.path}", path=args.path, max_depth=args.depth)
    else:
        response = orchestrator.run(f"{args.command} {args.path}", path=args.path)

    print(response.to_json() if args.json else format_response(response))
    return EXIT_OK if response.success else EXIT_FAILURE


if __name__ == "__main__":
    raise SystemExit(main())
