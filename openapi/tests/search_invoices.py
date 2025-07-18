from .base import CommandTestSuite, TestCase
from .config import TestConfig

class SearchInvoicesTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="search invoices", 
            description="Test invoice search functionality"
        )
        self.generate_test_cases()

    def generate_test_cases(self):
        # Successful search test case
        self.add_test(TestCase(
            name="Successful invoice search",
            input_data={
                "query": "2023-09",  # Example search query for September 2023
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "invoices": [
                        {
                            "id": 1,
                            "date": "2023-09-01",
                            "amount": 150.0,
                            "status": "paid"
                        },
                        {
                            "id": 2,
                            "date": "2023-09-15",
                            "amount": 200.0,
                            "status": "unpaid"
                        }
                    ]
                }
            }
        ))

        # Invalid query test case
        self.add_test(TestCase(
            name="Invalid query format",
            input_data={
                "query": "invalid-date-format",  # Invalid date format
            },
            expected_output={
                "status_code": 400,
                "response": {
                    "success": False,
                    "msg": "Invalid query format"
                }
            }
        ))

        # No results found test case
        self.add_test(TestCase(
            name="No invoices found",
            input_data={
                "query": "2025-01",  # Future date with no invoices
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "invoices": []  # Empty list indicating no results
                }
            }
        ))

        # Unauthorized access test case
        self.add_test(TestCase(
            name="Unauthorized access",
            input_data={
                "query": "2023-09",
            },
            expected_output={
                "status_code": 401,
                "response": {
                    "success": False,
                    "msg": "Unauthorized access"
                }
            }
        ))

        # Rate limit exceeded test case
        self.add_test(TestCase(
            name="Rate limit exceeded",
            input_data={
                "query": "2023-09",
            },
            expected_output={
                "status_code": 429,
                "response": {
                    "success": False,
                    "msg": "Rate limit exceeded"
                }
            }
        ))