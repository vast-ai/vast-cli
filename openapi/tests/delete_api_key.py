from .base import CommandTestSuite, TestCase

class DeleteApiKeyTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="delete api-key",
            description="Delete an existing API key"
        )
        self.generate_test_cases()

    def generate_test_cases(self):
        # Successful API key deletion
        self.add_test(TestCase(
            name="Delete API key success",
            input_data={
                "id": 12345  # Example API key ID
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "msg": "API key deleted successfully"
                }
            }
        ))
