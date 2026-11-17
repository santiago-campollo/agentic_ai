# Instructor Notes (do not share before the demo)

`sample_project/` contains intentional, harmless defects. The tests pass, which
is part of the lesson: passing tests are not proof of correctness.

## Intentional defects

| # | Location | Defect | How the agent reports it |
|---|---|---|---|
| 1 | `calculator.py`, `divide`, `if b == 0: return 0` | Division by zero silently returns `0` instead of signalling an error. The result is mathematically wrong and hides bad input. | Verified, HIGH, Correctness |
| 2 | `calculator.py`, `calculate`, `raise ValueError("Invalid")` | Unknown operation produces an unhelpful message without the offending value or valid options. | Verified, MEDIUM, Error handling |
| 3 | `calculator.py`, `calculate` | Mixed responsibilities: computes **and** prints. Callers get console output they did not ask for; harder to test. | Potential concern, MEDIUM, Maintainability |
| 4 | `test_calculator.py` | Missing tests: `multiply` is never tested; no test for division by zero or unknown operations (`pytest.raises` is never used). | Verified, MEDIUM, Testing (two findings) |

There is also a LOW suggestion (if/elif chain -> dictionary dispatch). It is a
style choice, not a defect; use it to discuss the difference between
"suggestion" and "finding".

## Suggested discussion

- Ask students to find defect 1 by reading the code *before* running the review.
- Ask whether defect 3 is really a defect. It depends on intent, which is why
  the agent marks it as a *potential* concern.
- Ask what the correct behavior of `divide(5, 0)` should be. There is more than
  one valid answer (raise `ZeroDivisionError`, raise `ValueError`, return
  `math.inf`), but returning `0` is not one of them.

## Reference fix (for after the session)

```python
def divide(a: float, b: float) -> float:
    """Return a divided by b. Raises ZeroDivisionError when b is zero."""
    if b == 0:
        raise ZeroDivisionError("Cannot divide by zero.")
    return a / b


# Defined after add, subtract, multiply and divide.
OPERATIONS = {"add": add, "subtract": subtract, "multiply": multiply, "divide": divide}


def calculate(operation: str, a: float, b: float) -> float:
    """Run the requested operation on a and b."""
    try:
        function = OPERATIONS[operation]
    except KeyError:
        valid = ", ".join(sorted(OPERATIONS))
        raise ValueError(f"Unknown operation {operation!r}. Expected one of: {valid}.") from None
    return function(a, b)
```

Add tests for `multiply`, `pytest.raises(ZeroDivisionError)` and
`pytest.raises(ValueError, match="Unknown operation")`.

Keep the fix on a separate branch so the main branch stays ready for the next demo.

## Timing tips

- If time is short, skip the `--level advanced` run and the JSON output.
- If `engineering-agent` is not on PATH, use `python -m agent.cli`.
- The symlink test is skipped on Windows without Developer Mode; that is expected.
