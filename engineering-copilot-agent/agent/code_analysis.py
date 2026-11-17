"""Static code analysis built on Python's ``ast`` module.

``ast.parse`` only builds a syntax tree from text. It never imports, compiles
into a running program, or executes the inspected code. This is how the agent
"reads" Python safely.

The review checks are small, deterministic heuristics. They are deliberately
simple so students can read them and add their own.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import PurePosixPath

from agent.models import Finding

CONCEPT_ORDER = (
    "imports",
    "functions",
    "type_hints",
    "docstrings",
    "conditionals",
    "loops",
    "comprehensions",
    "exceptions",
    "exception_handling",
    "f_strings",
    "side_effects",
    "classes",
    "decorators",
    "context_managers",
    "assertions",
)

KIND_ORDER = {"verified": 0, "potential": 1, "suggestion": 2}
SEVERITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
DISPATCH_CHAIN_THRESHOLD = 4
SHORT_MESSAGE_WORDS = 2
DANGEROUS_CALLS = frozenset({"eval", "exec"})

FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


@dataclass(frozen=True)
class ParameterFact:
    """A function parameter and its type annotation, if any."""

    name: str
    annotation: str | None


@dataclass(frozen=True)
class FunctionFact:
    """Facts about one function, collected from the syntax tree."""

    name: str
    line: int
    end_line: int
    parameters: tuple[ParameterFact, ...]
    returns: str | None
    docstring: str | None
    calls: tuple[str, ...]
    raises: tuple[str, ...]
    compared_strings: tuple[str, ...]
    branch_count: int
    returns_value: bool

    @property
    def is_public(self) -> bool:
        """``True`` when the name does not start with an underscore."""
        return not self.name.startswith("_")

    @property
    def is_test(self) -> bool:
        """``True`` for pytest-style test functions."""
        return self.name.startswith("test_")

    @property
    def prints(self) -> bool:
        """``True`` when the function calls ``print``."""
        return "print" in self.calls

    def signature(self) -> str:
        """Return a readable signature such as ``add(a: float, b: float) -> float``."""
        params = ", ".join(
            f"{p.name}: {p.annotation}" if p.annotation else p.name for p in self.parameters
        )
        returns = f" -> {self.returns}" if self.returns else ""
        return f"{self.name}({params}){returns}"


@dataclass(frozen=True)
class ClassFact:
    """Facts about one class."""

    name: str
    line: int
    docstring: str | None
    methods: tuple[str, ...]


@dataclass(frozen=True)
class ModuleFacts:
    """Facts about a whole Python module."""

    docstring: str | None
    line_count: int
    imports: tuple[str, ...]
    functions: tuple[FunctionFact, ...]
    classes: tuple[ClassFact, ...]
    has_main_guard: bool
    concepts: tuple[str, ...]


def _unique(values: Iterable[str | None]) -> tuple[str, ...]:
    """Remove duplicates and ``None`` while keeping the original order."""
    return tuple(dict.fromkeys(value for value in values if value))


def _exception_name(node: ast.expr | None) -> str | None:
    if isinstance(node, ast.Call):
        node = node.func
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _call_name(node: ast.Call) -> str | None:
    return node.func.id if isinstance(node.func, ast.Name) else None


def _is_none(node: ast.expr | None) -> bool:
    return node is None or (isinstance(node, ast.Constant) and node.value is None)


def _function_fact(node: FunctionNode) -> FunctionFact:
    arguments = node.args
    all_args = [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs]
    if arguments.vararg:
        all_args.append(arguments.vararg)
    if arguments.kwarg:
        all_args.append(arguments.kwarg)

    nodes = list(ast.walk(node))
    return FunctionFact(
        name=node.name,
        line=node.lineno,
        end_line=node.end_lineno or node.lineno,
        parameters=tuple(
            ParameterFact(arg.arg, ast.unparse(arg.annotation) if arg.annotation else None)
            for arg in all_args
        ),
        returns=ast.unparse(node.returns) if node.returns else None,
        docstring=ast.get_docstring(node),
        calls=_unique(_call_name(n) for n in nodes if isinstance(n, ast.Call)),
        raises=_unique(_exception_name(n.exc) for n in nodes if isinstance(n, ast.Raise)),
        compared_strings=_unique(
            operand.value
            for n in nodes
            if isinstance(n, ast.Compare)
            for operand in (n.left, *n.comparators)
            if isinstance(operand, ast.Constant) and isinstance(operand.value, str)
        ),
        branch_count=sum(isinstance(n, ast.If | ast.IfExp | ast.match_case) for n in nodes),
        returns_value=any(isinstance(n, ast.Return) and not _is_none(n.value) for n in nodes),
    )


def _detect_concepts(tree: ast.Module) -> tuple[str, ...]:
    found: set[str] = set()
    simple_markers: dict[type, str] = {
        ast.If: "conditionals",
        ast.IfExp: "conditionals",
        ast.For: "loops",
        ast.While: "loops",
        ast.ListComp: "comprehensions",
        ast.SetComp: "comprehensions",
        ast.DictComp: "comprehensions",
        ast.GeneratorExp: "comprehensions",
        ast.Raise: "exceptions",
        ast.Try: "exception_handling",
        ast.JoinedStr: "f_strings",
        ast.ClassDef: "classes",
        ast.With: "context_managers",
        ast.Assert: "assertions",
        ast.Import: "imports",
        ast.ImportFrom: "imports",
    }
    for node in ast.walk(tree):
        if type(node) in simple_markers:
            found.add(simple_markers[type(node)])
        if isinstance(node, FunctionNode):
            found.add("functions")
            if node.decorator_list:
                found.add("decorators")
            if node.returns or any(arg.annotation for arg in node.args.args):
                found.add("type_hints")
            if ast.get_docstring(node):
                found.add("docstrings")
        elif isinstance(node, ast.Call) and _call_name(node) == "print":
            found.add("side_effects")
    return tuple(concept for concept in CONCEPT_ORDER if concept in found)


def _has_main_guard(tree: ast.Module) -> bool:
    return any(
        isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and isinstance(node.test.left, ast.Name)
        and node.test.left.id == "__name__"
        for node in tree.body
    )


def _imports(tree: ast.Module) -> tuple[str, ...]:
    names: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or ".")
    return _unique(names)


def analyze_python_source(source: str) -> ModuleFacts:
    """Collect structural facts about Python ``source``.

    Raises:
        SyntaxError: if the source is not valid Python.
    """
    tree = ast.parse(source)
    return ModuleFacts(
        docstring=ast.get_docstring(tree),
        line_count=len(source.splitlines()),
        imports=_imports(tree),
        functions=tuple(_function_fact(n) for n in tree.body if isinstance(n, FunctionNode)),
        classes=tuple(
            ClassFact(
                name=n.name,
                line=n.lineno,
                docstring=ast.get_docstring(n),
                methods=tuple(m.name for m in n.body if isinstance(m, FunctionNode)),
            )
            for n in tree.body
            if isinstance(n, ast.ClassDef)
        ),
        has_main_guard=_has_main_guard(tree),
        concepts=_detect_concepts(tree),
    )


# --------------------------------------------------------------------------- review checks


def _zero_guard(function: FunctionNode, name: str) -> ast.If | None:
    """Find ``if <name> == 0:`` inside ``function``."""
    for node in ast.walk(function):
        if not (isinstance(node, ast.If) and isinstance(node.test, ast.Compare)):
            continue
        test = node.test
        if len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq):
            continue
        operands = (test.left, test.comparators[0])
        has_name = any(isinstance(o, ast.Name) and o.id == name for o in operands)
        has_zero = any(
            isinstance(o, ast.Constant) and not isinstance(o.value, bool) and o.value == 0
            for o in operands
        )
        if has_name and has_zero:
            return node
    return None


def _check_division(path: str, function: FunctionNode) -> list[Finding]:
    divisors: dict[str, int] = {}
    for node in ast.walk(function):
        if (
            isinstance(node, ast.BinOp)
            and isinstance(node.op, ast.Div | ast.FloorDiv | ast.Mod)
            and isinstance(node.right, ast.Name)
        ):
            divisors.setdefault(node.right.id, node.lineno)

    findings: list[Finding] = []
    for name, line in divisors.items():
        guard = _zero_guard(function, name)
        if guard is None:
            findings.append(
                Finding(
                    kind="potential",
                    severity="MEDIUM",
                    category="Edge cases",
                    file=path,
                    line=line,
                    observation=(
                        f"`{function.name}` divides by `{name}` without checking whether it is zero."
                    ),
                    why_it_matters=(
                        "Dividing by zero raises ZeroDivisionError. That can be acceptable, "
                        "but only if it is the intended, documented and tested behavior."
                    ),
                    suggestion=(
                        "Decide the contract: validate the input and raise a clear error, or "
                        "document that ZeroDivisionError propagates. Add a test either way."
                    ),
                )
            )
            continue
        first = guard.body[0]
        if isinstance(first, ast.Return) and isinstance(first.value, ast.Constant):
            findings.append(
                Finding(
                    kind="verified",
                    severity="HIGH",
                    category="Correctness",
                    file=path,
                    line=guard.lineno,
                    observation=(
                        f"When `{name} == 0`, `{function.name}` returns the constant "
                        f"`{ast.unparse(first.value)}` instead of signalling an error."
                    ),
                    why_it_matters=(
                        "Division by zero is undefined. Returning a plausible number hides the "
                        "problem: callers cannot tell a real result from invalid input, and the "
                        "wrong value can silently spread through the program."
                    ),
                    suggestion=(
                        "Raise an exception (for example `ZeroDivisionError` or "
                        '`ValueError("Cannot divide by zero")`) and add a test that uses '
                        "`pytest.raises`."
                    ),
                )
            )
    return findings


def _check_print_and_return(path: str, function: FunctionNode) -> list[Finding]:
    fact = _function_fact(function)
    if not (fact.prints and fact.returns_value) or fact.is_test:
        return []
    return [
        Finding(
            kind="potential",
            severity="MEDIUM",
            category="Maintainability",
            file=path,
            line=function.lineno,
            observation=f"`{function.name}` both prints output and returns a value.",
            why_it_matters=(
                "The function mixes two responsibilities: computing a result and presenting it. "
                "Callers that only want the result also get console output, which makes the "
                "function harder to reuse and to test."
            ),
            suggestion=(
                f"Keep `{function.name}` focused on computing and returning. Print in the caller, "
                "or use the `logging` module if diagnostic output is needed."
            ),
        )
    ]


def _dispatch_chain(node: ast.If) -> tuple[str | None, int]:
    """Measure an ``if/elif`` chain that compares one variable with constants."""
    variable: str | None = None
    length = 0
    current: ast.stmt | None = node
    while isinstance(current, ast.If):
        test = current.test
        if not (
            isinstance(test, ast.Compare)
            and isinstance(test.left, ast.Name)
            and len(test.comparators) == 1
            and isinstance(test.comparators[0], ast.Constant)
            and (variable is None or test.left.id == variable)
        ):
            break
        variable = test.left.id
        length += 1
        current = current.orelse[0] if len(current.orelse) == 1 else None
    return variable, length


def _check_dispatch_chain(path: str, function: FunctionNode) -> list[Finding]:
    for statement in function.body:
        if not isinstance(statement, ast.If):
            continue
        variable, length = _dispatch_chain(statement)
        if variable and length >= DISPATCH_CHAIN_THRESHOLD:
            return [
                Finding(
                    kind="suggestion",
                    severity="LOW",
                    category="Readability",
                    file=path,
                    line=statement.lineno,
                    observation=(
                        f"`{function.name}` uses an if/elif chain with {length} branches that "
                        f"compare `{variable}` with fixed values."
                    ),
                    why_it_matters=(
                        "Every new option requires editing the chain, and long chains are easy "
                        "to get subtly wrong."
                    ),
                    suggestion=(
                        "Consider a dictionary that maps each value to a function, then look the "
                        "function up once."
                    ),
                )
            ]
    return []


def _check_documentation(path: str, function: FunctionNode) -> list[Finding]:
    fact = _function_fact(function)
    if not fact.is_public or fact.is_test:
        return []
    findings: list[Finding] = []
    if not fact.docstring:
        findings.append(
            Finding(
                kind="suggestion",
                severity="LOW",
                category="Readability",
                file=path,
                line=function.lineno,
                observation=f"Public function `{function.name}` has no docstring.",
                why_it_matters="Docstrings explain intent and appear in IDE tooltips and help().",
                suggestion="Add a one-line docstring describing what the function returns.",
            )
        )
    untyped = [
        p.name for p in fact.parameters if p.annotation is None and p.name not in {"self", "cls"}
    ]
    if untyped or (fact.returns is None and function.name != "__init__"):
        findings.append(
            Finding(
                kind="suggestion",
                severity="LOW",
                category="Readability",
                file=path,
                line=function.lineno,
                observation=f"`{function.name}` is missing some type hints.",
                why_it_matters="Type hints document expectations and let editors catch mistakes early.",
                suggestion="Annotate every parameter and the return type.",
            )
        )
    return findings


def _check_raises(path: str, tree: ast.Module) -> list[Finding]:
    findings: list[Finding] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call)):
            continue
        name = _exception_name(node.exc) or "Exception"
        args = node.exc.args
        if name in {"Exception", "BaseException"}:
            findings.append(
                Finding(
                    kind="verified",
                    severity="LOW",
                    category="Error handling",
                    file=path,
                    line=node.lineno,
                    observation=f"Raises the generic `{name}` type.",
                    why_it_matters="Callers cannot catch this specific problem without catching everything.",
                    suggestion="Raise a specific type such as `ValueError` or `TypeError`.",
                )
            )
        if (
            len(args) == 1
            and isinstance(args[0], ast.Constant)
            and isinstance(args[0].value, str)
            and len(args[0].value.split()) <= SHORT_MESSAGE_WORDS
        ):
            findings.append(
                Finding(
                    kind="verified",
                    severity="MEDIUM",
                    category="Error handling",
                    file=path,
                    line=node.lineno,
                    observation=(
                        f"`raise {name}({args[0].value!r})` uses a short, fixed message with no context."
                    ),
                    why_it_matters=(
                        "When the error appears, the user cannot tell which value was wrong or "
                        "which values are accepted, so debugging takes longer."
                    ),
                    suggestion=(
                        "Include the offending value and the accepted options, for example "
                        f'`raise {name}(f"Unknown value {{value!r}}. Expected one of: ...")`.'
                    ),
                )
            )
    return findings


def _check_exception_handlers(path: str, tree: ast.Module) -> list[Finding]:
    findings: list[Finding] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        if node.type is None:
            findings.append(
                Finding(
                    kind="verified",
                    severity="MEDIUM",
                    category="Error handling",
                    file=path,
                    line=node.lineno,
                    observation="Uses a bare `except:` clause.",
                    why_it_matters="It also catches KeyboardInterrupt and SystemExit and hides real bugs.",
                    suggestion="Catch the specific exception types you expect.",
                )
            )
        if all(isinstance(statement, ast.Pass) for statement in node.body):
            findings.append(
                Finding(
                    kind="verified",
                    severity="MEDIUM",
                    category="Error handling",
                    file=path,
                    line=node.lineno,
                    observation="An exception handler silently ignores the error (`pass`).",
                    why_it_matters="Failures disappear without a trace, which makes debugging very hard.",
                    suggestion="Handle the error, log it, or let it propagate.",
                )
            )
    return findings


def _check_dangerous_calls(path: str, tree: ast.Module) -> list[Finding]:
    findings: list[Finding] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node)
        if name in DANGEROUS_CALLS:
            findings.append(
                Finding(
                    kind="verified",
                    severity="HIGH",
                    category="Security",
                    file=path,
                    line=node.lineno,
                    observation=f"Calls `{name}()`, which executes dynamic code.",
                    why_it_matters="If any part of the input is user-controlled, it can run arbitrary code.",
                    suggestion="Replace dynamic execution with explicit logic or a safe parser.",
                )
            )
        for keyword in node.keywords:
            if (
                keyword.arg == "shell"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value is True
            ):
                findings.append(
                    Finding(
                        kind="verified",
                        severity="HIGH",
                        category="Security",
                        file=path,
                        line=node.lineno,
                        observation="Starts a process with `shell=True`.",
                        why_it_matters="Shell parsing enables command injection when arguments contain user input.",
                        suggestion="Pass a list of arguments and keep `shell=False`.",
                    )
                )
    return findings


def _module_has_error_paths(tree: ast.Module) -> bool:
    return any(
        isinstance(node, ast.Raise)
        or (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div | ast.FloorDiv | ast.Mod))
        for node in ast.walk(tree)
    )


def _check_tests(
    path: str, tree: ast.Module, test_path: str | None, test_source: str | None
) -> list[Finding]:
    public = [
        node.name
        for node in tree.body
        if isinstance(node, FunctionNode) and not node.name.startswith("_")
    ]
    if not public:
        return []
    if test_source is None or test_path is None:
        return [
            Finding(
                kind="potential",
                severity="MEDIUM",
                category="Testing",
                file=path,
                line=None,
                observation=f"No matching test file was found for `{path}`.",
                why_it_matters="Without tests, changes can break behavior without anyone noticing.",
                suggestion=f"Create `test_{PurePosixPath(path).stem}.py` with pytest tests.",
            )
        ]
    try:
        test_tree = ast.parse(test_source)
    except SyntaxError as error:
        return [
            Finding(
                kind="verified",
                severity="MEDIUM",
                category="Testing",
                file=test_path,
                line=error.lineno,
                observation="The test file could not be parsed.",
                why_it_matters="Tests that do not parse do not run.",
                suggestion="Fix the syntax error so pytest can collect the tests.",
            )
        ]

    referenced: set[str] = set()
    for node in ast.walk(test_tree):
        if isinstance(node, ast.Name):
            referenced.add(node.id)
        elif isinstance(node, ast.Attribute):
            referenced.add(node.attr)
        elif isinstance(node, ast.ImportFrom):
            referenced.update(alias.asname or alias.name for alias in node.names)

    findings: list[Finding] = []
    untested = [name for name in public if name not in referenced]
    if untested:
        findings.append(
            Finding(
                kind="verified",
                severity="MEDIUM",
                category="Testing",
                file=test_path,
                line=None,
                observation=(
                    f"`{test_path}` never references: {', '.join(f'`{n}`' for n in untested)}."
                ),
                why_it_matters="Code that no test exercises can break without anyone noticing.",
                suggestion=(
                    "Add at least one test per public function, plus edge cases such as zero, "
                    "negative numbers and floats."
                ),
            )
        )
    if _module_has_error_paths(tree) and "raises" not in referenced:
        findings.append(
            Finding(
                kind="verified",
                severity="MEDIUM",
                category="Testing",
                file=test_path,
                line=None,
                observation=(
                    f"`{test_path}` has no `pytest.raises` checks, but `{path}` contains error "
                    "paths (raise statements or division)."
                ),
                why_it_matters="Error paths are where bugs hide; untested ones often behave unexpectedly.",
                suggestion="Add tests for invalid input using `with pytest.raises(...)`.",
            )
        )
    return findings


def sort_findings(findings: Iterable[Finding]) -> list[Finding]:
    """Order findings: verified first, then by severity, file and line."""
    return sorted(
        findings,
        key=lambda f: (
            KIND_ORDER.get(f.kind, 9),
            SEVERITY_ORDER.get(f.severity, 9),
            f.file,
            f.line or 0,
        ),
    )


def review_python_source(
    path: str,
    source: str,
    *,
    test_path: str | None = None,
    test_source: str | None = None,
    is_test_file: bool = False,
) -> list[Finding]:
    """Run every review check on one Python file and return sorted findings."""
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        return [
            Finding(
                kind="verified",
                severity="HIGH",
                category="Correctness",
                file=path,
                line=error.lineno,
                observation=f"The file is not valid Python: {error.msg}.",
                why_it_matters="Python cannot import or run a file with syntax errors.",
                suggestion="Fix the syntax error first; other checks were skipped.",
            )
        ]

    findings: list[Finding] = []
    for node in ast.walk(tree):
        if isinstance(node, FunctionNode):
            findings += _check_division(path, node)
            findings += _check_print_and_return(path, node)
            findings += _check_dispatch_chain(path, node)
            if not is_test_file:
                findings += _check_documentation(path, node)
    findings += _check_raises(path, tree)
    findings += _check_exception_handlers(path, tree)
    findings += _check_dangerous_calls(path, tree)
    if not is_test_file:
        findings += _check_tests(path, tree, test_path, test_source)
    return sort_findings(findings)


def is_test_file_name(path: str) -> bool:
    """Return ``True`` for pytest-style file names (``test_*.py`` or ``*_test.py``)."""
    name = PurePosixPath(path).name
    return name.endswith(".py") and (name.startswith("test_") or name.endswith("_test.py"))
