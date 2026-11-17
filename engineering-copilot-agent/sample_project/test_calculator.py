"""Tests for the sample calculator."""

from calculator import add, calculate, divide, subtract


def test_add() -> None:
    assert add(2, 3) == 5


def test_subtract() -> None:
    assert subtract(5, 3) == 2


def test_divide() -> None:
    assert divide(10, 2) == 5


def test_calculate_add() -> None:
    assert calculate("add", 1, 2) == 3
