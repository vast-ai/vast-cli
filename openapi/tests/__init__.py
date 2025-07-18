# test_suite/__init__.py
import os
import importlib
import inspect
from pathlib import Path
from typing import Dict, Type
from .base import CommandTestSuite, TestCase

def load_test_suites() -> Dict[str, CommandTestSuite]:
    """
    Dynamically load and register all test suite classes from Python files in this directory.
    """
    test_suites = {}
    current_dir = Path(__file__).parent
    
    # Iterate through all .py files in the directory
    for file_path in current_dir.glob('*.py'):
        # Skip __init__.py and base.py
        if file_path.name in ['__init__.py', 'base.py']:
            continue
            
        try:
            # Convert file path to module name (remove .py and replace / with .)
            module_name = f"test_suite.{file_path.stem}"
            
            # Import the module
            module = importlib.import_module(module_name)
            
            # Find all classes in the module that inherit from CommandTestSuite
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and 
                    issubclass(obj, CommandTestSuite) and 
                    obj != CommandTestSuite):
                    # Initialize the test suite
                    suite = obj()
                    # Use the command name from the suite as the key
                    test_suites[suite.command] = suite
        
        except Exception as e:
            print(f"Error loading test suite from {file_path}: {str(e)}")
    
    return test_suites

# Load all test suites
TEST_SUITES = load_test_suites()

# Export the registry and base classes
__all__ = ['TEST_SUITES', 'CommandTestSuite', 'TestCase']