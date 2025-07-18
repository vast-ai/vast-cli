from .base import CommandTestSuite, TestCase
 

class CreateEndpointTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="create endpoint",
            description="Create a new endpoint for job processing"
        )
        self.generate_test_cases()
    
    def setup_endpoint(self):
        # Implementation to create necessary test data
        pass
        
    def cleanup_endpoint(self):
        # Implementation to clean up test data
        pass
    
    def generate_test_cases(self):
        # Successful Endpoint Creation
        self.add_test(TestCase(
            name="Successful Endpoint Creation",
            input_data={
                "options": [
                    "--client_id", "me",
                    "--min_load", "0.5",
                    "--target_util", "0.75",
                    "--cold_mult", "1.0",
                    "--cold_workers", "2",
                    "--max_workers", "10",
                    "--endpoint_name", "my_endpoint"
                ]
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "msg": "Operation completed successfully"
                }
            },
            setup=self.setup_endpoint,
            cleanup=self.cleanup_endpoint
        ))

        # Missing Required Fields
        self.add_test(TestCase(
            name="Missing Required Fields",
            input_data={
                "options": [
                    "--client_id", "me",
                    "--min_load", "0.5"
                    # Missing other required fields
                ]
            },
            expected_output={
                "status_code": 400,
                "response": {
                    "success": False,
                    "error": "missing_input"
                }
            }
        ))

        # Unauthorized Access
        self.add_test(TestCase(
            name="Unauthorized Access",
            input_data={
                "options": [
                    "--client_id", "me",
                    "--min_load", "0.5",
                    "--target_util", "0.75",
                    "--cold_mult", "1.0",
                    "--cold_workers", "2",
                    "--max_workers", "10",
                    "--endpoint_name", "my_endpoint"
                ],
                "headers": {
                    "Authorization": "Bearer invalid_token"
                }
            },
            expected_output={
                "status_code": 401,
                "response": {
                    "success": False,
                    "error": "unauthorized"
                }
            }
        ))

        # Rate Limiting
        self.add_test(TestCase(
            name="Rate Limiting",
            input_data={
                "options": [
                    "--client_id", "me",
                    "--min_load", "0.5",
                    "--target_util", "0.75",
                    "--cold_mult", "1.0",
                    "--cold_workers", "2",
                    "--max_workers", "10",
                    "--endpoint_name", "my_endpoint"
                ]
            },
            expected_output={
                "status_code": 429,
                "response": {
                    "detail": "API requests too frequent endpoint threshold=3.0"
                }
            }
        ))