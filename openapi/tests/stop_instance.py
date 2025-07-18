from .base import CommandTestSuite, TestCase

class StopInstanceTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="stop instance",
            description="Stop a running instance"
        )
        self.generate_test_cases()
    
    def setup_test_instance(self):
        """Set up test instance data"""
        # Implementation to create test instance
        pass
        
    def cleanup_test_instance(self):
        """Clean up test instance data"""
        # Implementation to clean up test instance
        pass
    
    def generate_test_cases(self):
        # Test case for successfully stopping an instance
        self.add_test(TestCase(
            name="Stop instance success",
            input_data={
                "id": 1234,
                "state": "stopped"
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "msg": "Operation completed successfully"
                }
            },
            setup=self.setup_test_instance,
            cleanup=self.cleanup_test_instance
        ))
        
        # Test case for instance not found
        self.add_test(TestCase(
            name="Instance not found",
            input_data={
                "id": 99999,
                "state": "stopped"
            },
            expected_output={
                "status_code": 404,
                "response": {
                    "success": False,
                    "error": "not_found",
                    "msg": "Instance not found"
                }
            }
        ))
        
        # Test case for missing billing information
        self.add_test(TestCase(
            name="Missing billing info",
            input_data={
                "id": 1234,
                "state": "stopped"
            },
            expected_output={
                "status_code": 400,
                "response": {
                    "success": False,
                    "error": "missing_billing",
                    "msg": "Missing billing information"
                }
            }
        ))
        
        # Test case for unauthorized access
        self.add_test(TestCase(
            name="Unauthorized access",
            input_data={
                "id": 1234,
                "state": "stopped",
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
                "id": 1234,
                "state": "stopped"
            },
            expected_output={
                "status_code": 429,
                "response": {
                    "detail": "API requests too frequent endpoint threshold=1.0"
                }
            }
        ))
        
        # Test case for invalid state value
        self.add_test(TestCase(
            name="Invalid state value",
            input_data={
                "id": 1234,
                "state": "invalid_state"
            },
            expected_output={
                "status_code": 400,
                "response": {
                    "success": False,
                    "error": "invalid_input",
                    "msg": "State must be 'stopped'"
                }
            }
        ))