"""A tiny calculator used as the review target in the Engineering Copilot Agent demo."""


def add(a: float, b: float) -> float:
    """Return the sum of a and b."""
    return a + b


def subtract(a: float, b: float) -> float:
    """Return a minus b."""
    return a - b


def multiply(a: float, b: float) -> float:
    """Return the product of a and b."""
    return a * b


def divide(a: float, b: float) -> float:
    """Return a divided by b."""
    if b == 0:
        return 0
    return a / b


def calculate(operation: str, a: float, b: float) -> float:
    """Run the requested operation on a and b and report the result."""
    print(f"Calculating {operation} with {a} and {b}")
    if operation == "add":
        result = add(a, b)
    elif operation == "subtract":
        result = subtract(a, b)
    elif operation == "multiply":
        result = multiply(a, b)
    elif operation == "divide":
        result = divide(a, b)
    else:
        raise ValueError("Invalid")
    print(f"Result: {result}")
    return result
