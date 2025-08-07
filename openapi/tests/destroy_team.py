from .base import CommandTestSuite, TestCase
from .config import TestConfig

class DestroyTeamTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="destroy team",
            description="Destroy an existing team by ID"
        )
        self.generate_test_cases()

    def generate_test_cases(self):
        # Successful destruction case
        self.add_test(TestCase(
            name="Destroy team success",
            input_data={
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "msg": "Team destroyed successfully"
                }
            }
        ))
