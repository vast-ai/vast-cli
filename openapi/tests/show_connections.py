from .base import CommandTestSuite, TestCase
from .config import TestConfig

class ShowConnectionsTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="show connections",
            description="Test suite for retrieving user's cloud connections"
        )
        self.generate_test_cases()

    def generate_test_cases(self):
        # Test case for successful connections retrieval
        self.add_test(TestCase(
            name="List cloud connections successfully",
            input_data={},  # No input parameters needed
            expected_output={
                "status_code": 200,
                "response": [
                    {
                        "id": 1,
                        "cloud_type": "s3",
                        "name": "Test S3 Connection"
                    },
                    {
                        "id": 2, 
                        "cloud_type": "drive",
                        "name": "Test Drive Connection"
                    }
                ]
            },
        ))
