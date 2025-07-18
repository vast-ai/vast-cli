from .base import CommandTestSuite, TestCase

class UpdateAutogroupTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="update autogroup",
            description="Update an existing autoscale group"
        )
        self.generate_test_cases()
    
    def setup_test_autogroup(self):
        """Set up test autogroup"""
        # Implementation to create test autogroup
        pass
        
    def cleanup_test_autogroup(self):
        """Clean up test autogroup"""
        # Implementation to clean up test autogroup
        pass
    
    def generate_test_cases(self):
        # Test case for successfully updating autogroup
        self.add_test(TestCase(
            name="Update autogroup success",
            input_data={
                "id": 123,
                "min_load": 100.0,
                "target_util": 0.9,
                "cold_mult": 2.0,
                "test_workers": 2,
                "template_hash": "abc123",
                "search_params": "gpu_ram>=23 num_gpus=2",
                "launch_args": "--image test/image:latest",
                "gpu_ram": 32.0,
                "endpoint_name": "test-endpoint"
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True
                }
            },
            setup=self.setup_test_autogroup,
            cleanup=self.cleanup_test_autogroup
        ))
        
        # Test case for autogroup not found
        self.add_test(TestCase(
            name="Autogroup not found",
            input_data={
                "id": 99999,
                "min_load": 100.0,
                "target_util": 0.9
            },
            expected_output={
                "status_code": 404,
                "response": {
                    "success": False,
                    "error": "not_found",
                    "msg": "Autogroup not found"
                }
            }
        ))
        
        # Test case for unauthorized access
        self.add_test(TestCase(
            name="Unauthorized access",
            input_data={
                "id": 123,
                "min_load": 100.0,
                "target_util": 0.9,
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
        
        # Test case for invalid parameters
        self.add_test(TestCase(
            name="Invalid parameters",
            input_data={
                "id": 123,
                "min_load": -100.0,  # Invalid negative value
                "target_util": 2.0,   # Invalid value > 1.0
                "cold_mult": 0.0      # Invalid zero value
            },
            expected_output={
                "status_code": 400,
                "response": {
                    "success": False,
                    "error": "invalid_parameters",
                    "msg": "Invalid parameter values provided"
                }
            }
        ))
        
        # Test case for incomplete parameters
        self.add_test(TestCase(
            name="Incomplete parameters",
            input_data={
                "id": 123  # Missing required parameters
            },
            expected_output={
                "status_code": 400,
                "response": {
                    "success": False,
                    "error": "missing_parameters",
                    "msg": "Required parameters missing"
                }
            }
        ))
        
        # Test case with conflicting template specifications
        self.add_test(TestCase(
            name="Conflicting template specs",
            input_data={
                "id": 123,
                "min_load": 100.0,
                "target_util": 0.9,
                "template_hash": "abc123",
                "template_id": 456  # Conflicting with template_hash
            },
            expected_output={
                "status_code": 400,
                "response": {
                    "success": False,
                    "error": "invalid_request",
                    "msg": "Cannot specify both template_hash and template_id"
                }
            }
        ))