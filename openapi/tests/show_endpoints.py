from .base import CommandTestSuite, TestCase

class ShowEndpointsTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="show endpoints",
            description="Test suite for displaying user's current endpoint groups"
        )
        self.generate_test_cases()

    def setup_test_endpoints(self):
        """Create test endpoints for validation"""
        pass

    def cleanup_test_endpoints(self):
        """Remove test endpoints after validation"""
        pass

    def generate_test_cases(self):
        # Test successful endpoint retrieval
        self.add_test(TestCase(
            name="Valid endpoints request",
            input_data={
                "machine": 123,
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "endpoints": [
                        {
                            "id": 1,
                            "name": "Test Endpoint 1",
                            "status": "active",
                            "machine_id": 123
                        },
                        {
                            "id": 2,
                            "name": "Test Endpoint 2", 
                            "status": "inactive",
                            "machine_id": 123
                        }
                    ]
                }
            },
            setup=self.setup_test_endpoints,
            cleanup=self.cleanup_test_endpoints
        ))

