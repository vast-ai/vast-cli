from .base import CommandTestSuite, TestCase
from .config import TestConfig

class LogsTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="logs",
            description="Retrieve logs for a specific machine"
        )
        self.generate_test_cases()

    def generate_test_cases(self):
        # Positive test case for successful log retrieval
        self.add_test(TestCase(
            name="Retrieve logs successfully",
            input_data={
                "id": TestConfig.INSTANCE_ID
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "logs": [
                        # Example log entries
                        {"timestamp": "2023-10-01T12:00:00Z", "message": "Log entry 1"},
                        {"timestamp": "2023-10-01T12:05:00Z", "message": "Log entry 2"}
                    ]
                }
            }
        ))

        # # Test case for unauthorized access
        # self.add_test(TestCase(
        #     name="Unauthorized access",
        #     input_data={
        #         "machine_id": 12345  # Example machine ID
        #     },
        #     expected_output={
        #         "status_code": 403,
        #         "response": {
        #             "error": "not_authorized",
        #             "msg": "Only machine owner can access logs"
        #         }
        #     }
        # ))

        # # Test case for invalid machine ID
        # self.add_test(TestCase(
        #     name="Invalid machine ID",
        #     input_data={
        #         "machine_id": -1  # Invalid machine ID
        #     },
        #     expected_output={
        #         "status_code": 400,
        #         "response": {
        #             "error": "invalid_args",
        #             "msg": "Invalid machine id or parameters"
        #         }
        #     }
        # ))