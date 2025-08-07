from .base import CommandTestSuite, TestCase
 

class ResetAPIKeyTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="reset api-key",
            description="Reset the API key for a user"
        )
        self.generate_test_cases()

    def setup_user(self):
        # Implementation to create a test user
        pass

    def cleanup_user(self):
        # Implementation to remove the test user
        pass

    def generate_test_cases(self):
        # Basic reset API key test
        self.add_test(TestCase(
            name="Reset API key successfully",
            input_data={
                "client_id": "12345"  # Example user ID
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "msg": "API key reset successfully"
                }
            },
            setup=self.setup_user,
            cleanup=self.cleanup_user
        ))

        # Test with invalid user ID
        self.add_test(TestCase(
            name="Reset API key with invalid user ID",
            input_data={
                "user_id": -1  # Invalid user ID
            },
            expected_output={
                "status_code": 400,
                "response": {
                    "success": False,
                    "error": "invalid_user_id",
                    "msg": "Invalid user ID provided"
                }
            }
        ))

        # Test without authorization
        self.add_test(TestCase(
            name="Reset API key without authorization",
            input_data={
                "user_id": 12345  # Example user ID
            },
            expected_output={
                "status_code": 401,
                "response": {
                    "success": False,
                    "error": "unauthorized",
                    "msg": "Authorization required"
                }
            }
        ))