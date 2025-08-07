from .base import CommandTestSuite, TestCase

class SSHURLTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="ssh-url",
            description="Retrieve SSH connection details for an instance"
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
        # Test case for successfully retrieving SSH details
        self.add_test(TestCase(
            name="Get SSH details",
            input_data={
                "id": 123
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "ipaddr": "192.168.1.1",
                    "port": 22
                }
            },
            setup=self.setup_test_instance,
            cleanup=self.cleanup_test_instance
        ))
        
        # Test case for unauthorized access
        self.add_test(TestCase(
            name="Unauthorized access",
            input_data={
                "id": 123,
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
        
        # Test case for non-existent instance
        self.add_test(TestCase(
            name="Instance not found",
            input_data={
                "id": 99999
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
                "id": -1
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