from .base import CommandTestSuite, TestCase
from .config import TestConfig

class ExecuteCommandTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="execute",
            description="Execute a command or script"
        )
        self.generate_test_cases()

    def generate_test_cases(self):
        # Successful execution
        self.add_test(TestCase(
            name="Execute command success",
            input_data={
                "id": TestConfig.INSTANCE_ID,
                "command": "echo 'Hello, World!'"
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "output": "Hello, World!"
                }
            }
        ))
