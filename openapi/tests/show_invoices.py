from .base import CommandTestSuite, TestCase
 

class ShowInvoicesTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="show invoices",
            description="Test invoice retrieval functionality"
        )
        self.generate_test_cases()

    def generate_test_cases(self):
        # Successful retrieval test case
        self.add_test(TestCase(
            name="Successful invoice retrieval",
            input_data={
                "user_id": "me",  # Example invoice ID
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "invoice": {
                        "id": 1,
                        "date": "2023-09-01",
                        "amount": 150.0,
                        "status": "paid"
                    }
                }
            }
        ))

        # Invoice not found test case
        self.add_test(TestCase(
            name="Invoice not found",
            input_data={
                "invoice_id": 9999,  # Non-existent invoice ID
            },
            expected_output={
                "status_code": 404,
                "response": {
                    "success": False,
                    "msg": "Invoice not found"
                }
            }
        ))

        # Unauthorized access test case
        self.add_test(TestCase(
            name="Unauthorized access",
            input_data={
                "invoice_id": 1,
            },
            expected_output={
                "status_code": 401,
                "response": {
                    "success": False,
                    "msg": "Unauthorized access"
                }
            }
        ))

        # Invalid ID format test case
        self.add_test(TestCase(
            name="Invalid ID format",
            input_data={
                "invoice_id": "invalid-id",  # Invalid ID format
            },
            expected_output={
                "status_code": 400,
                "response": {
                    "success": False,
                    "msg": "Invalid ID format"
                }
            }
        ))

        # Rate limit exceeded test case
        self.add_test(TestCase(
            name="Rate limit exceeded",
            input_data={
                "invoice_id": 1,
            },
            expected_output={
                "status_code": 429,
                "response": {
                    "success": False,
                    "msg": "Rate limit exceeded"
                }
            }
        ))