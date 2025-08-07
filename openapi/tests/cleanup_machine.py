from .base import CommandTestSuite, TestCase
from .config import TestConfig

class CleanupMachineTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="cleanup machine",
            description="Remove all expired storage instances from the machine"
        )
        self.generate_test_cases()

    def setup_test_machine(self):
        # Setup would create test machine state if needed
        pass

    def cleanup_test_machine(self):
        # Cleanup any test state after tests
        pass

    def generate_test_cases(self):
        # Basic cleanup test
        self.add_test(TestCase(
            name="Cleanup machine storage",
            input_data={
                "machine_id": TestConfig.VALID_MACHINE_ID
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "deleted_instances": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer"},
                                "machine_id": {"type": "integer"},
                                "storage_used": {"type": "number"}
                            }
                        }
                    }
                }
            },
            setup=self.setup_test_machine,
            cleanup=self.cleanup_test_machine
        ))

        # Test with specific machine ID
        self.add_test(TestCase(
            name="Cleanup specific machine",
            input_data={
                "options": [],
                "args": ["456"] # Specific machine ID
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "deleted_instances": []
                }
            }
        ))