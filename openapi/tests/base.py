# test_suite/base.py
from dataclasses import dataclass
from typing import Dict, Any, Optional, Callable, List

@dataclass
class TestCase:
    name: str
    input_data: Dict[str, Any]
    expected_output: Dict[str, Any]
    setup: Optional[Callable] = None      # Run before test
    cleanup: Optional[Callable] = None    # Run after test

class CommandTestSuite:
    def __init__(self, command: str, description: str):
        self.command = command
        self.description = description
        self.test_cases: List[TestCase] = []
        self.setup: Optional[Callable] = None      
        self.cleanup: Optional[Callable] = None    
        
    def add_test(self, test_case: TestCase):
        self.test_cases.append(test_case)