from .base import CommandTestSuite, TestCase
from .config import TestConfig

class RemoveDefJobTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="remove defjob",
            description="Remove a default job configuration"
        )
        self.generate_test_cases()

    def setup_defjob(self):
        # Implementation to create a test default job
        pass

    def cleanup_defjob(self):
        # Implementation to remove the test default job
        pass

    def generate_test_cases(self):
        # Positive test case for successful removal
        self.add_test(TestCase(
            name="Remove existing default job",
            input_data={
                "machine_id": TestConfig.VALID_MACHINE_ID,  # Example job ID and machine ID
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "msg": "Default job removed successfully"
                }
            },
            setup=self.setup_defjob,
            cleanup=self.cleanup_defjob
        ))

        # Test case for attempting to remove a non-existent job
        self.add_test(TestCase(
            name="Remove non-existent default job",
            input_data={
                "options": ["--job-id", "99999"]  # Non-existent job ID
            },
            expected_output={
                "status_code": 404,
                "response": {
                    "success": False,
                    "error": "not_found",
                    "msg": "Default job not found"
                }
            }
        ))