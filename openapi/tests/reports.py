from .base import CommandTestSuite, TestCase
from .config import TestConfig
class ReportsTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="reports",
            description="Get the user reports for a given machine"
        )
        self.generate_test_cases()

    def setup_reports(self):
        # Implementation to create test reports
        pass

    def cleanup_reports(self):
        # Implementation to remove test reports
        pass

    def generate_test_cases(self):
        # Basic report retrieval test
        self.add_test(TestCase(
            name="Retrieve user reports",
            input_data={
                "machine_id": TestConfig.VALID_MACHINE_ID  # Added machine_id parameter
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "reports": {
                        # Will be checked for structure only
                        # since actual values are dynamic
                    }
                }
            },
            setup=self.setup_reports,
            cleanup=self.cleanup_reports
        ))

        # Add more test cases as needed to cover different scenarios