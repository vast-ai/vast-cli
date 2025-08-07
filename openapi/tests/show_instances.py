from .base import CommandTestSuite, TestCase
from .config import TestConfig

class ShowInstancesTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="show instances",
            description="Test suite for the 'show instances' command"
        )
        self.add_tests()

    def add_tests(self):
        # Test case for successfully showing instances
        self.add_test(TestCase(
            name="Show instances successfully",
            input_data={},
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "instances": []  # Allow any list of instances
                }
            }
        ))

        # Test case for user not found
        self.add_test(TestCase(
            name="User not found",
            input_data={
                "options": ["--user-id", "999999"]  # Assuming this user ID does not exist
            },
            expected_output={
                "status_code": 404,
                "response": {
                    "error": "not_found",
                    "msg": "User not found"
                }
            }
        ))



