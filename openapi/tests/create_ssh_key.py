from .base import CommandTestSuite, TestCase

class CreateSSHKeyTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="create ssh-key",
            description="Create a new SSH key and associate it with your account"
        )
        self.generate_test_cases()
    
    def setup_ssh_key(self):
        # Implementation to create necessary test data
        pass
        
    def cleanup_ssh_key(self):
        # Implementation to clean up test data
        pass
    
    def generate_test_cases(self):
        # Successful SSH Key Creation
        self.add_test(TestCase(
            name="Successful SSH Key Creation",
            input_data={
                "ssh_key": "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC..."
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "key": {
                        "id": 123,
                        "user_id": 456,
                        "public_key": "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC...",
                        "created_at": "2023-01-01T12:00:00Z",
                        "deleted_at": None
                    }
                }
            },
            setup=self.setup_ssh_key,
            cleanup=self.cleanup_ssh_key
        ))
