from .base import CommandTestSuite, TestCase
 
from .config import TestConfig

class ShowAPIKeysTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="show api-keys",
            description="Test showing API keys details"
        )
        self.generate_test_cases()

    def generate_test_cases(self):
        # Successful case with 200 status code
        self.add_test(TestCase(
            name="Show API keys successfully",
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

        # Unauthorized case with 401 status code
        self.add_test(TestCase(
            name="Unauthorized access",
            input_data={
                "id": TestConfig.INVALID_API_KEY_ID  # Assuming we add this to TestConfig
            },
            expected_output={
                "status_code": 401,
                "response": {
                    "success": False,
                    "error": "unauthorized",
                    "msg": "Invalid API key"
                }
            }
        ))

        # Bad Request case with 400 status code
        self.add_test(TestCase(
            name="Invalid API key format",
            input_data={
                "id": "invalid_format"  # Invalid format for API key
            },
            expected_output={
                "status_code": 400,
                "response": {
                    "success": False,
                    "error": "invalid_format",
                    "msg": "API key format is invalid"
                }
            }
        ))

        # Too Many Requests case with 429 status code
        self.add_test(TestCase(
            name="Rate limit exceeded",
            input_data={
                "id": TestConfig.API_KEY_ID  # Valid API key
            },
            expected_output={
                "status_code": 429,
                "response": {
                    "success": False,
                    "error": "rate_limit_exceeded",
                    "msg": "API requests too frequent"
                }
            }
        ))