from .base import CommandTestSuite, TestCase

class ShowIPAddrsTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="show ipaddrs",
            description="Test suite for the 'show ipaddrs' command"
        )
        self.setup = self.setup_environment
        self.cleanup = self.cleanup_environment
        self.add_tests()

    def setup_environment(self):
        """Setup code to prepare the environment for tests"""
        print("Setting up environment for 'show ipaddrs' tests")

    def cleanup_environment(self):
        """Cleanup code to reset the environment after tests"""
        print("Cleaning up environment after 'show ipaddrs' tests")

    def add_tests(self):
        """Add test cases to the suite"""
        # Test case for successful retrieval
        self.add_test(TestCase(
            name="valid_request",
            input_data={
                "user_id": "me"
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "results": [
                        {
                            "id": 123,
                            "user_id": 456,
                            "ip_address": "192.168.1.1",
                            "timestamp": "2023-10-01T12:00:00Z"
                        }
                    ]
                }
            }
        ))

        # Test case for unauthorized access
        self.add_test(TestCase(
            name="unauthorized_access",
            input_data={
                "options": [],
                "headers": {
                    "Authorization": "Bearer invalid_token"
                }
            },
            expected_output={
                "status_code": 401,
                "response": {
                    "success": False,
                    "error": "unauthorized",
                    "msg": "Invalid API key or unauthorized access"
                }
            }
        ))

        # Test case for forbidden access
        self.add_test(TestCase(
            name="forbidden_access",
            input_data={
                "options": [],
                "parameters": {
                    "user_id": "other_user"
                }
            },
            expected_output={
                "status_code": 403,
                "response": {
                    "success": False,
                    "error": "forbidden",
                    "msg": "Insufficient permissions to access this resource"
                }
            }
        ))

        # Test case for rate limit exceeded
        self.add_test(TestCase(
            name="rate_limit_exceeded",
            input_data={
                "options": [],
                "simulate_rate_limit": True
            },
            expected_output={
                "status_code": 429,
                "response": {
                    "detail": "API requests too frequent endpoint threshold=2.9"
                }
            }
        ))

        # Test case for invalid parameters
        self.add_test(TestCase(
            name="invalid_parameters",
            input_data={
                "options": ["--invalid", "param"]
            },
            expected_output={
                "status_code": 400,
                "response": {
                    "success": False,
                    "error": "invalid_parameters",
                    "msg": "Invalid parameters provided"
                }
            }
        ))