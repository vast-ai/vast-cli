from .base import CommandTestSuite, TestCase

class UpdateSSHKeyTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="update ssh-key",
            description="Update an existing SSH key"
        )
        self.generate_test_cases()
    
    def setup_test_ssh_key(self):
        """Set up test SSH key"""
        # Implementation to create test SSH key
        pass
        
    def cleanup_test_ssh_key(self):
        """Clean up test SSH key"""
        # Implementation to clean up test SSH key
        pass
    
    def generate_test_cases(self):
        # Test case for successfully updating SSH key
        self.add_test(TestCase(
            name="Update SSH key success",
            input_data={
                "id": 123,
                "ssh_key": "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC3..."
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "key": {
                        "id": 123,
                        "public_key": "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC3..."
                    }
                }
            },
            setup=self.setup_test_ssh_key,
            cleanup=self.cleanup_test_ssh_key
        ))
        
        # Test case for missing SSH key
        self.add_test(TestCase(
            name="Missing SSH key",
            input_data={
                "id": 123
            },
            expected_output={
                "status_code": 400,
                "response": {
                    "success": False,
                    "error": "missing_parameter",
                    "msg": "SSH key parameter is required"
                }
            }
        ))
        
        # Test case for invalid SSH key format
        self.add_test(TestCase(
            name="Invalid SSH key format",
            input_data={
                "id": 123,
                "ssh_key": "invalid_key_format"
            },
            expected_output={
                "status_code": 400,
                "response": {
                    "success": False,
                    "error": "invalid_format",
                    "msg": "Invalid SSH key format"
                }
            }
        ))
        
        # Test case for nonexistent SSH key ID
        self.add_test(TestCase(
            name="Nonexistent SSH key ID",
            input_data={
                "id": 99999,
                "ssh_key": "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC3..."
            },
            expected_output={
                "status_code": 400,
                "response": {
                    "success": False,
                    "error": "not_found",
                    "msg": "SSH key not found"
                }
            }
        ))
        
        # Test case for rate limit exceeded
        self.add_test(TestCase(
            name="Rate limit exceeded",
            input_data={
                "id": 123,
                "ssh_key": "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC3..."
            },
            expected_output={
                "status_code": 429,
                "response": {
                    "detail": "API requests too frequent endpoint threshold=1.0"
                }
            }
        ))