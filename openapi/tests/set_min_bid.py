from .base import CommandTestSuite, TestCase

class SetMinBidTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="set min-bid", 
            description="Test suite for the 'set min-bid' CLI command"
        )
        self.generate_test_cases()

    def setup_function(self):
        # Setup logic if needed
        pass

    def cleanup_function(self):
        # Cleanup logic if needed
        pass

    def generate_test_cases(self):
        # Successful set min-bid test case
        self.add_test(TestCase(
            name="Successful set min-bid",
            input_data={
                "machine_id": 123,
                "price": 0.2
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "msg": "Minimum bid price set successfully"
                }
            }
        ))
        
        # Example test case for a missing required parameter
        self.add_test(TestCase(
            name="Missing required parameter 'machine'",
            input_data={
                "options": [
                    "--price_min_bid", "0.2"
                ]
            },
            expected_output={
                "status_code": 400,
                "response": {
                    "error": "missing_input",
                    "msg": "Missing required parameters: machine"
                }
            }
        ))

        # Example test case for unauthorized access
        self.add_test(TestCase(
            name="Unauthorized access attempt",
            input_data={
                "options": [
                    "--machine", "123",
                    "--price_min_bid", "0.2"
                ]
            },
            expected_output={
                "status_code": 403,
                "response": {
                    "error": "not_authorized",
                    "msg": "Only machine owner can set minimum bid price"
                }
            }
        ))