from .base import CommandTestSuite, TestCase
from .config import TestConfig

class DestroyInstanceTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="destroy instance",
            description="Destroy an existing instance by ID"
        )
        self.generate_test_cases()
    
    def generate_test_cases(self):
        # Successful destruction case
        self.add_test(TestCase(
            name="Destroy instance success",
            input_data={
                "id": TestConfig.INSTANCE_ID
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "msg": "Instance destroyed successfully"
                }
            }
        ))
