from .base import CommandTestSuite, TestCase
from datetime import datetime, timezone

class ShowSubaccountsTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="show subaccounts",
            description="Display list of subaccounts associated with user account"
        )
        self.generate_test_cases()
    
    def setup_test_subaccounts(self):
        """Create test subaccounts for testing"""
        # Implementation to create test subaccounts
        pass
        
    def cleanup_test_subaccounts(self):
        """Remove test subaccounts after testing"""
        # Implementation to remove test subaccounts
        pass
    
    def generate_test_cases(self):
        # Test case for successfully listing subaccounts
        self.add_test(TestCase(
            name="List all subaccounts",
            input_data={
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "users": [
                        {
                            "id": 1001,
                            "parent_id": 1000,
                            "api_key": "test_api_key_1",
                            "created_at": "2024-01-01T00:00:00Z",
                            "deleted_at": None
                        },
                        {
                            "id": 1002,
                            "parent_id": 1000,
                            "api_key": "test_api_key_2",
                            "created_at": "2024-01-02T00:00:00Z",
                            "deleted_at": None
                        }
                    ]
                }
            },
            setup=self.setup_test_subaccounts,
            cleanup=self.cleanup_test_subaccounts
        ))
        
        # Test case for unauthorized access
        self.add_test(TestCase(
            name="Unauthorized access",
            input_data={
                "options": [],
                "headers": {
                    "Authorization": "Bearer invalid_token"
                }
            },
            expected_output={
                "status_code": 401,
                "response": {
                    "success": False,
                    "error": "unauthorized",
                    "msg": "Invalid or missing authentication token"
                }
            }
        ))
        
        # Test case for rate limit exceeded
        self.add_test(TestCase(
            name="Rate limit exceeded",
            input_data={
                "options": []
            },
            expected_output={
                "status_code": 429,
                "response": {
                    "detail": "API requests too frequent endpoint threshold=2.1"
                }
            },
            setup=lambda: None,
            cleanup=lambda: None
        ))
        
        # Test case for no subaccounts
        self.add_test(TestCase(
            name="No subaccounts found",
            input_data={
                "options": []
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "users": []
                }
            },
            setup=lambda: None,  # Empty setup to ensure no subaccounts exist
            cleanup=self.cleanup_test_subaccounts
        ))
        
        # Test case with deleted subaccounts
        self.add_test(TestCase(
            name="List including deleted subaccounts",
            input_data={
                "options": ["--include-deleted"]
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "users": [
                        {
                            "id": 1003,
                            "parent_id": 1000,
                            "api_key": "test_api_key_3",
                            "created_at": "2024-01-03T00:00:00Z",
                            "deleted_at": "2024-01-04T00:00:00Z"
                        }
                    ]
                }
            },
            setup=self.setup_test_subaccounts,
            cleanup=self.cleanup_test_subaccounts
        ))