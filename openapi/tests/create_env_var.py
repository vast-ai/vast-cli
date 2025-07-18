from .base import CommandTestSuite, TestCase
 

class CreateEnvVarTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="create env-var",
            description="Create a new environment variable"
        )
        self.generate_test_cases()
    
    def setup_env_var(self):
        # Implementation to create necessary test data
        pass
        
    def cleanup_env_var(self):
        # Implementation to clean up test data
        pass
    
    def generate_test_cases(self):
        # Successful Environment Variable Creation
        self.add_test(TestCase(
            name="Successful Environment Variable Creation",
            input_data={
                "options": ["--key", "API_TOKEN", "--value","abc123xyz"]
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "msg": "Environment variable added successfully"
                }
            },
            setup=self.setup_env_var,
            cleanup=self.cleanup_env_var
        ))

        # Missing Input
        self.add_test(TestCase(
            name="Missing Input",
            input_data={
                "options": []
            },
            expected_output={
                "status_code": 400,
                "response": {
                    "success": False,
                    "error": "missing_input",
                    "msg": "Both 'key' and 'value' are required."
                }
            }
        ))

        # Unauthorized Access
        self.add_test(TestCase(
            name="Unauthorized Access",
            input_data={
                "options": ["API_TOKEN", "abc123xyz"],
                "headers": {"Authorization": "Bearer invalid_token"}
            },
            expected_output={
                "status_code": 401,
                "response": {
                    "success": False,
                    "error": "unauthorized",
                    "msg": "Invalid or missing API key"
                }
            }
        ))

        # Too Many Requests
        self.add_test(TestCase(
            name="Too Many Requests",
            input_data={
                "options": ["API_TOKEN", "abc123xyz"]
            },
            expected_output={
                "status_code": 429,
                "response": {
                    "detail": "API requests too frequent endpoint threshold=3.0"
                }
            }
        ))
 
def generate_test_cases(self):
    # Successful Environment Variable Creation
    self.add_test(TestCase(
        name="Successful Environment Variable Creation",
        input_data={
            "options": ["--key", "API_TOKEN", "--value", "abc123xyz", "--api_key", "secret_key", "--permissions", "read_write", "--name", "test-key", "--key_params", '{"ip_whitelist": ["1.2.3.4"]}']
        },
        expected_output={
            "status_code": 200,
            "response": {
                "success": True,
                "msg": "Environment variable added successfully"
            }
        },
        setup=self.setup_env_var,
        cleanup=self.cleanup_env_var
    ))