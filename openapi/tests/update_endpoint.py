from .base import CommandTestSuite, TestCase

class UpdateEndpointTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="update endpoint",
            description="Update an existing endpoint group"
        )
        self.generate_test_cases()
    
    def setup_test_endpoint(self):
        """Set up test endpoint"""
        # Implementation to create test endpoint
        pass
        
    def cleanup_test_endpoint(self):
        """Clean up test endpoint"""
        # Implementation to clean up test endpoint
        pass
    
    def generate_test_cases(self):
        # Test case for successfully updating endpoint group
        self.add_test(TestCase(
            name="Update endpoint success",
            input_data={
                "id": 4242,
                "min_load": 100.0,
                "target_util": 0.9,
                "cold_mult": 2.0,
                "cold_workers": 5,
                "max_workers": 20,
                "endpoint_name": "LLama"
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "msg": "Operation completed successfully"
                }
            },
            setup=self.setup_test_endpoint,
            cleanup=self.cleanup_test_endpoint
        ))
        
        # Test case for endpoint not found
        self.add_test(TestCase(
            name="Endpoint not found",
            input_data={
                "id": 99999,
                "min_load": 100.0
            },
            expected_output={
                "status_code": 404,
                "response": {
                    "success": False,
                    "error": "not_found",
                    "msg": "Endpoint group not found"
                }
            }
        ))
        
        # Test case for invalid target utilization
        self.add_test(TestCase(
            name="Invalid target utilization",
            input_data={
                "id": 4242,
                "target_util": 1.5  # Invalid value > 1.0
            },
            expected_output={
                "status_code": 400,
                "response": {
                    "success": False,
                    "error": "invalid_parameter",
                    "msg": "Target utilization must be between 0 and 1"
                }
            }
        ))
        
        # Test case for invalid worker counts
        self.add_test(TestCase(
            name="Invalid worker counts",
            input_data={
                "id": 4242,
                "cold_workers": 10,
                "max_workers": 5  # max_workers less than cold_workers
            },
            expected_output={
                "status_code": 400,
                "response": {
                    "success": False,
                    "error": "invalid_parameter",
                    "msg": "Max workers must be greater than or equal to cold workers"
                }
            }
        ))
        
        # Test case for negative values
        self.add_test(TestCase(
            name="Negative values",
            input_data={
                "id": 4242,
                "min_load": -100.0,
                "cold_mult": -2.0
            },
            expected_output={
                "status_code": 400,
                "response": {
                    "success": False,
                    "error": "invalid_parameter",
                    "msg": "Parameters must be positive values"
                }
            }
        ))
        
        # Test case for rate limit exceeded
        self.add_test(TestCase(
            name="Rate limit exceeded",
            input_data={
                "id": 4242,
                "min_load": 100.0
            },
            expected_output={
                "status_code": 429,
                "response": {
                    "detail": "API requests too frequent endpoint threshold=2.0"
                }
            }
        ))
        
        # Test case for unauthorized access
        self.add_test(TestCase(
            name="Unauthorized access",
            input_data={
                "id": 4242,
                "min_load": 100.0,
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