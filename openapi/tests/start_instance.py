from .base import CommandTestSuite, TestCase

class StartInstanceTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="start instance",
            description="Start a specific instance"
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
        # Test case for successfully starting an instance
        self.add_test(TestCase(
            name="Start instance success",
            input_data={
                "id": 123,
                "api_key": "test_api_key",
                "state": "running"
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "msg": "Instance successfully started"
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
                "api_key": "test_api_key",
                "state": "running"
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
        
        # Test case for invalid instance ID
        self.add_test(TestCase(
            name="Invalid instance ID",
            input_data={
                "id": -1,
                "api_key": "test_api_key",
                "state": "running"
            },
            expected_output={
                "status_code": 400,
                "response": {
                    "success": False,
                    "error": "invalid_id",
                    "msg": "Invalid instance ID"
                }
            }
        ))
        
        # Test case for invalid state value
        self.add_test(TestCase(
            name="Invalid state value",
            input_data={
                "id": 123,
                "api_key": "test_api_key",
                "state": "invalid_state"
            },
            expected_output={
                "status_code": 400,
                "response": {
                    "success": False,
                    "error": "invalid_state",
                    "msg": "Invalid state value. Must be 'running'."
                }
            }
        ))