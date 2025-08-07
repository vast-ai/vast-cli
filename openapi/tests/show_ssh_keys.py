from .base import CommandTestSuite, TestCase

class ShowSSHKeysTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="show ssh-keys",
            description="List and display SSH keys associated with user account"
        )
        self.generate_test_cases()
    
    def setup_ssh_keys(self):
        """Create test SSH keys for testing"""
        # Implementation to create test keys
        pass
        
    def cleanup_ssh_keys(self):
        """Remove test SSH keys after testing"""
        # Implementation to remove test keys
        pass
    
    def generate_test_cases(self):
        # Test case for listing all SSH keys
        self.add_test(TestCase(
            name="List all SSH keys",
            input_data={
                "options": []
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "ssh_keys": [
                        {
                            "id": 1,
                            "user_id": 123,
                            "key": "ssh-rsa AAAA...",
                            "created_at": "2024-01-01T00:00:00Z",
                            "deleted_at": None
                        }
                    ]
                }
            },
            setup=self.setup_ssh_keys,
            cleanup=self.cleanup_ssh_keys
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
                    "error": "unauthorized",
                    "msg": "Invalid or missing authentication token"
                }
            }
        ))
        
        # Test case for no SSH keys found
        self.add_test(TestCase(
            name="No SSH keys found",
            input_data={
                "options": []
            },
            expected_output={
                "status_code": 404,
                "response": {
                    "error": "not_found",
                    "msg": "No SSH keys found for user"
                }
            },
            setup=lambda: None,  # Empty setup to ensure no keys exist
            cleanup=self.cleanup_ssh_keys
        ))
        
        # Test case with specified format
        self.add_test(TestCase(
            name="List SSH keys with specific format",
            input_data={
                "options": ["--format", "id,key"]
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "ssh_keys": [
                        {
                            "id": 1,
                            "key": "ssh-rsa AAAA..."
                        }
                    ]
                }
            },
            setup=self.setup_ssh_keys,
            cleanup=self.cleanup_ssh_keys
        ))