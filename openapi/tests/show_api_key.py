from .base import CommandTestSuite, TestCase
from .config import TestConfig

class ShowAPIKeyTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="show api-key",
            description="Test showing API key details"
        )
        self.generate_test_cases()

    def generate_test_cases(self):
        # Only include successful case with 200 status code
        self.add_test(TestCase(
            name="Show API key successfully",
            input_data={
                "id": TestConfig.API_KEY_ID  # Assuming we add this to TestConfig
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "permissions": {},  # Allow any permissions structure
                    "name": None,      # Allow any name
                    "apikey_id": None,  # Allow any ID  
                    "created_at": None  # Allow any timestamp
                }
            }
        ))