# Sample Project: Calculator

A deliberately small calculator used as the **environment** that the agent
observes during the demo.

## Files

- `calculator.py` - four arithmetic functions and a `calculate` dispatcher.
- `test_calculator.py` - pytest tests.

## Usage

```python
from calculator import calculate

calculate("add", 2, 3)
```

Run the tests from the repository root:

```bash
pytest sample_project
```

## Your mission

The tests pass, but that does not mean the code is perfect. Use the agent to
explain and review this project, then decide which findings are real problems:

```bash
engineering-agent explain sample_project/calculator.py --level beginner
engineering-agent review sample_project/calculator.py
```

Do not fix anything during the review. Discuss the findings first.
