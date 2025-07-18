from .base import CommandTestSuite, TestCase

class DeleteEnvVarTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="delete env-var",
            description="Delete an environment variable"
        )
        self.generate_test_cases()

    def generate_test_cases(self):
        # Successful deletion of an environment variable
        self.add_test(TestCase(
            name="Delete env-var success",
            input_data={
                "key": "example_key"  # Adding the required 'key' parameter
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "msg": "Environment variable deleted successfully"
                }
            }
        ))
