"""Tests for the ast-based analysis and review heuristics."""

from __future__ import annotations

from agent.code_analysis import analyze_python_source, is_test_file_name, review_python_source

SOURCE = '''"""Demo."""


def divide(a: float, b: float) -> float:
    """Divide."""
    if b == 0:
        return 0
    return a / b


def ratio(a, b):
    return a / b


def run(code: str) -> None:
    """Run code."""
    eval(code)
'''


def test_analyze_collects_functions_and_concepts() -> None:
    facts = analyze_python_source(SOURCE)

    assert [f.name for f in facts.functions] == ["divide", "ratio", "run"]
    assert facts.functions[0].signature() == "divide(a: float, b: float) -> float"
    assert "conditionals" in facts.concepts and "type_hints" in facts.concepts


def test_review_distinguishes_verified_potential_and_suggestions() -> None:
    findings = review_python_source("demo.py", SOURCE)
    by_observation = {f.observation: f for f in findings}

    silent_zero = next(f for f in findings if "returns the constant `0`" in f.observation)
    unchecked = next(f for f in findings if "without checking" in f.observation)
    assert silent_zero.kind == "verified" and silent_zero.severity == "HIGH"
    assert unchecked.kind == "potential"
    assert any(f.category == "Security" for f in findings)
    assert any(f.kind == "suggestion" and "`ratio`" in f.observation for f in findings)
    assert findings[0].kind == "verified"
    assert len(by_observation) == len(findings)


def test_review_reports_syntax_errors() -> None:
    findings = review_python_source("broken.py", "def broken(:\n")
    assert findings[0].severity == "HIGH" and findings[0].line == 1


def test_is_test_file_name() -> None:
    assert is_test_file_name("a/test_calc.py")
    assert is_test_file_name("calc_test.py")
    assert not is_test_file_name("calc.py")
