from .base import CommandTestSuite, TestCase

class StartInstancesTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="start instances",
            description="Start multiple instances by their IDs"
        )
        self.generate_test_cases()
    
    def setup_test_instances(self):
        """Set up test instances data"""
        # Implementation to create test instances
        pass
        
    def cleanup_test_instances(self):
        """Clean up test instances data"""
        # Implementation to clean up test instances
        pass
    
    def generate_test_cases(self):
        # Test case for successfully starting multiple instances
        self.add_test(TestCase(
            name="Start multiple instances success",
            input_data={
                "IDs": [123, 456, 789]
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "msg": "Instances started successfully"
                }
            },
            setup=self.setup_test_instances,
            cleanup=self.cleanup_test_instances
        ))
        
        # Test case for missing input
        self.add_test(TestCase(
            name="Missing input",
            input_data={},
            expected_output={
                "status_code": 400,
                "response": {
                    "error": "missing_input"
                }
            }
        ))
        
        # Test case for empty input
        self.add_test(TestCase(
            name="Empty input",
            input_data={
                "IDs": []
            },
            expected_output={
                "status_code": 400,
                "response": {
                    "error": "empty_input"
                }
            }
        ))
        
        # Test case for unauthorized access
        self.add_test(TestCase(
            name="Unauthorized access",
            input_data={
                "IDs": [123, 456],
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
        
        # Test case for forbidden access
        self.add_test(TestCase(
            name="Forbidden access",
            input_data={
                "IDs": [123, 456]
            },
            expected_output={
                "status_code": 403,
                "response": {
                    "success": False,
                    "error": "forbidden",
                    "msg": "User does not have permission to start these instances"
                }
            }
        ))
        
        # Test case for rate limit exceeded
        self.add_test(TestCase(
            name="Rate limit exceeded",
            input_data={
                "IDs": [123, 456]
            },
            expected_output={
                "status_code": 429,
                "response": {
                    "detail": "API requests too frequent endpoint threshold=2.0"
                }
            }
        ))
        
        # Test case for invalid instance ID
        self.add_test(TestCase(
            name="Invalid instance ID",
            input_data={
                "IDs": [123, -456, 789]
            },
            expected_output={
                "status_code": 400,
                "response": {
                    "error": "invalid_instance_id"
                }
            }
        ))
        
        # Test case for exceeding maximum IDs limit
        self.add_test(TestCase(
            name="Exceed maximum IDs limit",
            input_data={
                "IDs": list(range(101))  # Create list of 101 IDs
            },
            expected_output={
                "status_code": 400,
                "response": {
                    "error": "invalid_input",
                    "msg": "Maximum of 100 instances allowed"
                }
            }
        ))