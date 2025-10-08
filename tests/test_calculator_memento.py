import pytest
from decimal import Decimal
from app.calculation import Calculation
from app.calculator_memento import CalculatorMemento


def test_calculator_memento_stores_history():
    # Create fake calculations
    calc1 = Calculation("Addition", Decimal("2"), Decimal("3"))
    calc2 = Calculation("Subtraction", Decimal("5"), Decimal("2"))

    # Store them in a memento
    memento = CalculatorMemento(history=[calc1, calc2])

    # Verify the memento keeps the exact list
    assert memento.history == [calc1, calc2]
    assert len(memento.history) == 2


def test_calculator_memento_empty_list():
    # Test that memento can handle an empty history
    memento = CalculatorMemento(history=[])
    assert isinstance(memento.history, list)
    assert memento.history == []