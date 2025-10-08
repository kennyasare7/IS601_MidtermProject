import datetime
from pathlib import Path
import pandas as pd
import pytest
from unittest.mock import Mock, patch, PropertyMock
from decimal import Decimal
from tempfile import TemporaryDirectory
from app.calculator import Calculator
from app.calculator_repl import calculator_repl
from app.calculator_config import CalculatorConfig
from app.exceptions import OperationError, ValidationError
from app.history import LoggingObserver, AutoSaveObserver
from app.operations import OperationFactory
from unittest.mock import MagicMock

# Fixture to initialize Calculator with a temporary directory for file paths
@pytest.fixture
def calculator():
    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        config = CalculatorConfig(base_dir=temp_path)

        # Patch properties to use the temporary directory paths
        with patch.object(CalculatorConfig, 'log_dir', new_callable=PropertyMock) as mock_log_dir, \
             patch.object(CalculatorConfig, 'log_file', new_callable=PropertyMock) as mock_log_file, \
             patch.object(CalculatorConfig, 'history_dir', new_callable=PropertyMock) as mock_history_dir, \
             patch.object(CalculatorConfig, 'history_file', new_callable=PropertyMock) as mock_history_file:
            
            # Set return values to use paths within the temporary directory
            mock_log_dir.return_value = temp_path / "logs"
            mock_log_file.return_value = temp_path / "logs/calculator.log"
            mock_history_dir.return_value = temp_path / "history"
            mock_history_file.return_value = temp_path / "history/calculator_history.csv"
            
            # Return an instance of Calculator with the mocked config
            yield Calculator(config=config)

# Test Calculator Initialization

def test_calculator_initialization(calculator):
    assert calculator.history == []
    assert calculator.undo_stack == []
    assert calculator.redo_stack == []
    assert calculator.operation_strategy is None

# Test Logging Setup

@patch('app.calculator.logging.info')
def test_logging_setup(logging_info_mock):
    with patch.object(CalculatorConfig, 'log_dir', new_callable=PropertyMock) as mock_log_dir, \
         patch.object(CalculatorConfig, 'log_file', new_callable=PropertyMock) as mock_log_file:
        mock_log_dir.return_value = Path('/tmp/logs')
        mock_log_file.return_value = Path('/tmp/logs/calculator.log')
        
        # Instantiate calculator to trigger logging
        calculator = Calculator(CalculatorConfig())
        logging_info_mock.assert_any_call("Calculator initialized with configuration")

# Test Adding and Removing Observers

def test_add_observer(calculator):
    observer = LoggingObserver()
    calculator.add_observer(observer)
    assert observer in calculator.observers

def test_remove_observer(calculator):
    observer = LoggingObserver()
    calculator.add_observer(observer)
    calculator.remove_observer(observer)
    assert observer not in calculator.observers

# Test Setting Operations

def test_set_operation(calculator):
    operation = OperationFactory.create_operation('add')
    calculator.set_operation(operation)
    assert calculator.operation_strategy == operation

# Test Performing Operations

def test_perform_operation_addition(calculator):
    operation = OperationFactory.create_operation('add')
    calculator.set_operation(operation)
    result = calculator.perform_operation(2, 3)
    assert result == Decimal('5')

def test_perform_operation_validation_error(calculator):
    calculator.set_operation(OperationFactory.create_operation('add'))
    with pytest.raises(ValidationError):
        calculator.perform_operation('invalid', 3)

def test_perform_operation_operation_error(calculator):
    with pytest.raises(OperationError, match="No operation set"):
        calculator.perform_operation(2, 3)

# Test Undo/Redo Functionality

def test_undo(calculator):
    operation = OperationFactory.create_operation('add')
    calculator.set_operation(operation)
    calculator.perform_operation(2, 3)
    calculator.undo()
    assert calculator.history == []

def test_redo(calculator):
    operation = OperationFactory.create_operation('add')
    calculator.set_operation(operation)
    calculator.perform_operation(2, 3)
    calculator.undo()
    calculator.redo()
    assert len(calculator.history) == 1

# Test History Management

@patch('app.calculator.pd.DataFrame.to_csv')
def test_save_history(mock_to_csv, calculator):
    operation = OperationFactory.create_operation('add')
    calculator.set_operation(operation)
    calculator.perform_operation(2, 3)
    calculator.save_history()
    mock_to_csv.assert_called_once()

@patch('app.calculator.pd.read_csv')
@patch('app.calculator.Path.exists', return_value=True)
def test_load_history(mock_exists, mock_read_csv, calculator):
    # Mock CSV data to match the expected format in from_dict
    mock_read_csv.return_value = pd.DataFrame({
        'operation': ['Addition'],
        'operand1': ['2'],
        'operand2': ['3'],
        'result': ['5'],
        'timestamp': [datetime.datetime.now().isoformat()]
    })
    
    # Test the load_history functionality
    try:
        calculator.load_history()
        # Verify history length after loading
        assert len(calculator.history) == 1
        # Verify the loaded values
        assert calculator.history[0].operation == "Addition"
        assert calculator.history[0].operand1 == Decimal("2")
        assert calculator.history[0].operand2 == Decimal("3")
        assert calculator.history[0].result == Decimal("5")
    except OperationError:
        pytest.fail("Loading history failed due to OperationError")
        
            
# Test Clearing History

def test_clear_history(calculator):
    operation = OperationFactory.create_operation('add')
    calculator.set_operation(operation)
    calculator.perform_operation(2, 3)
    calculator.clear_history()
    assert calculator.history == []
    assert calculator.undo_stack == []
    assert calculator.redo_stack == []

# Test REPL Commands (using patches for input/output handling)

@patch('builtins.input', side_effect=['exit'])
@patch('builtins.print')
def test_calculator_repl_exit(mock_print, mock_input):
    with patch('app.calculator.Calculator.save_history') as mock_save_history:
        calculator_repl()
        mock_save_history.assert_called_once()
        mock_print.assert_any_call("History saved successfully.")
        mock_print.assert_any_call("Goodbye!")

@patch('builtins.input', side_effect=['help', 'exit'])
@patch('builtins.print')
def test_calculator_repl_help(mock_print, mock_input):
    calculator_repl()
    mock_print.assert_any_call("\nAvailable commands:")

@patch('builtins.input', side_effect=['add', '2', '3', 'exit'])
@patch('builtins.print')
def test_calculator_repl_addition(mock_print, mock_input):
    calculator_repl()
    mock_print.assert_any_call("\nResult: 5")

# --- 1. Test logging setup failure ---
def test_setup_logging_failure(tmp_path):
    config = CalculatorConfig(base_dir=tmp_path)
    calc = Calculator(config=config)
    with patch("app.calculator.os.makedirs", side_effect=PermissionError("no access")):
        with pytest.raises(PermissionError):
            calc._setup_logging()

# --- 2. Test setup_directories failure ---
def test_setup_directories_failure(tmp_path):
    config = CalculatorConfig(base_dir=tmp_path)
    calc = Calculator(config=config)
    with patch("app.calculator.Path.mkdir", side_effect=PermissionError("no permission")):
        with pytest.raises(PermissionError):
            calc._setup_directories()

# --- 3. Test perform_operation generic Exception ---
def test_perform_operation_generic_exception(calculator):
    calc = calculator
    mock_operation = MagicMock()
    mock_operation.execute.side_effect = RuntimeError("boom")
    calc.set_operation(mock_operation)
    with pytest.raises(OperationError, match="Operation failed"):
        calc.perform_operation(2, 3)

# --- 4. Test save_history failure ---
def test_save_history_failure(calculator):
    with patch("app.calculator.pd.DataFrame.to_csv", side_effect=Exception("save fail")):
        with pytest.raises(OperationError, match="Failed to save history"):
            calculator.save_history()

# --- 5. Test load_history failure ---
def test_load_history_failure(calculator):
    with patch("app.calculator.Path.exists", return_value=True), \
         patch("app.calculator.pd.read_csv", side_effect=Exception("bad read")):
        with pytest.raises(OperationError, match="Failed to load history"):
            calculator.load_history()

# --- 6. Test undo/redo return False ---
def test_undo_redo_false(calculator):
    calc = calculator
    assert calc.undo() is False
    assert calc.redo() is False

# --- 9. Test REPL: 'clear', 'history', 'undo', 'redo' ---
@patch('builtins.input', side_effect=['clear', 'history', 'undo', 'redo', 'exit'])
@patch('builtins.print')
def test_calculator_repl_history_clear_undo_redo(mock_print, mock_input):
    with patch('app.calculator.Calculator.save_history'):
        calculator_repl()
        mock_print.assert_any_call("History cleared")
        mock_print.assert_any_call("No calculations in history")
        mock_print.assert_any_call("Nothing to undo")
        mock_print.assert_any_call("Nothing to redo")
        mock_print.assert_any_call("Goodbye!")

# --- 10. Test REPL: 'save' and 'load' commands ---
@patch('builtins.input', side_effect=['save', 'load', 'exit'])
@patch('builtins.print')
def test_calculator_repl_save_load(mock_print, mock_input):
    with patch('app.calculator.Calculator.save_history') as mock_save, \
         patch('app.calculator.Calculator.load_history') as mock_load:
        calculator_repl()
        mock_save.assert_called()
        mock_load.assert_called()
        mock_print.assert_any_call("History loaded successfully")
        mock_print.assert_any_call("Goodbye!")

# --- 11. Test REPL: operation canceled ---
@patch('builtins.input', side_effect=['add', 'cancel', 'exit'])
@patch('builtins.print')
def test_calculator_repl_cancel_operation(mock_print, mock_input):
    calculator_repl()
    mock_print.assert_any_call("Operation cancelled")

# --- 12. Test REPL: unknown command ---
@patch('builtins.input', side_effect=['nonsense', 'exit'])
@patch('builtins.print')
def test_calculator_repl_unknown_command(mock_print, mock_input):
    calculator_repl()
    mock_print.assert_any_call("Unknown command: 'nonsense'. Type 'help' for available commands.")

# --- 13. Test REPL: top-level fatal error handling ---
@patch('builtins.print')
@patch('app.calculator.Calculator.__init__', side_effect=Exception("mocked failure"))
def test_calculator_repl_fatal_error(mock_init, mock_print):
    with pytest.raises(Exception):
        calculator_repl()
    mock_print.assert_any_call("Fatal error: mocked failure")