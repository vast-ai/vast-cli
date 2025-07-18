from .base import CommandTestSuite, TestCase

class UnlistMachineTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="unlist machine",
            description="Unlist a machine by removing all ask type offer contracts"
        )
        self.generate_test_cases()
    
    def setup_test_machine(self):
        """Set up test machine with ask contracts"""
        # Implementation to create test machine
        pass
        
    def cleanup_test_machine(self):
        """Clean up test machine data"""
        # Implementation to clean up test machine
        pass
    
    def generate_test_cases(self):
        # Test case for successfully unlisting a machine
        self.add_test(TestCase(
            name="Unlist machine success",
            input_data={
                "machine_id": 123
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "machine_id": 123,
                    "user_id": 456
                }
            },
            setup=self.setup_test_machine,
            cleanup=self.cleanup_test_machine
        ))
        
        # Test case for machine not found
        self.add_test(TestCase(
            name="Machine not found",
            input_data={
                "machine_id": 99999
            },
            expected_output={
                "status_code": 404,
                "response": {
                    "success": False,
                    "error": "not_found",
                    "msg": "Machine not found"
                }
            }
        ))
        
        # Test case for unauthorized access
        self.add_test(TestCase(
            name="Unauthorized access",
            input_data={
                "machine_id": 123,
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
                "machine_id": 123
            },
            expected_output={
                "status_code": 429,
                "response": {
                    "detail": "API requests too frequent endpoint threshold=1.8"
                }
            }
        ))