from .base import CommandTestSuite, TestCase
from .config import TestConfig

class ShowMachinesTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="show machines",
            description="Retrieve list of machines associated with user"
        )
        self.generate_test_cases()

    def setup_test_machines(self):
        """Setup test machines if needed"""
        pass

    def cleanup_test_machines(self):
        """Cleanup test machines if needed"""
        pass

    def generate_test_cases(self):
        # Basic successful fetch test
        self.add_test(TestCase(
            name="Fetch all machines successfully",
            input_data={
                "user_id": TestConfig.USER_ID
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "machines": [
                        {
                            "id": str,  # Will match any string
                            "name": str,  # Will match any string
                            # Add other expected machine properties
                        }
                    ]
                }
            },
            setup=self.setup_test_machines,
            cleanup=self.cleanup_test_machines
        ))

        # Test unauthorized access
        self.add_test(TestCase(
            name="Unauthorized access",
            input_data={
                "user_id": "invalid_user_id",
                "api_key": "invalid_api_key"
            },
            expected_output={
                "status_code": 401,
                "response": {
                    "error": "unauthorized",
                    "msg": "Invalid API key or user authentication"
                }
            }
        ))

