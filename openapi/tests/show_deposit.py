from .base import CommandTestSuite, TestCase

class ShowDepositTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="show deposit",
            description="Show deposit details for an instance"
        )
        self.generate_test_cases()
    
    def setup_test_instance(self):
        """Create test instance with deposit"""
        # Implementation to create test instance
        pass
        
    def cleanup_test_instance(self):
        """Remove test instance"""
        # Implementation to remove test instance
        pass
    
    def generate_test_cases(self):
        # Test successful deposit retrieval
        self.add_test(TestCase(
            name="Show deposit successfully",
            input_data={
                "id": 123,  # Instance ID
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "refundable_deposit": 100.0,
                    "total_discount": 10.0,
                    "discount_months": 3
                }
            },
            setup=self.setup_test_instance,
            cleanup=self.cleanup_test_instance
        ))
        
        # Test instance not found
        self.add_test(TestCase(
            name="Instance not found",
            input_data={
                "options": ["999999"]  # Non-existent instance ID
            },
            expected_output={
                "status_code": 404,
                "response": {
                    "success": False,
                    "error": "no_such_instance",
                    "msg": "Instance 999999 not found."
                }
            }
        ))

        # Test rate limit exceeded
        self.add_test(TestCase(
            name="Rate limit exceeded",
            input_data={
                "options": ["123"]
            },
            expected_output={
                "status_code": 429,
                "response": {
                    "detail": "API requests too frequent endpoint threshold=3.0"
                }
            }
        ))

        # Test missing instance ID
        self.add_test(TestCase(
            name="Missing instance ID",
            input_data={
                "options": []
            },
            expected_output={
                "status_code": 400,
                "response": {
                    "success": False,
                    "error": "missing_input",
                    "msg": "Instance ID is required"
                }
            }
        ))

        # Test unauthorized access
        self.add_test(TestCase(
            name="Unauthorized access",
            input_data={
                "options": ["123"],
                "headers": {
                    "Authorization": "Bearer invalid_token"
                }
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