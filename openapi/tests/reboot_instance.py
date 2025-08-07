from .base import CommandTestSuite, TestCase

class RebootInstanceTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="reboot instance",
            description="Reboot a specific instance"
        )
        self.generate_test_cases()

    def setup_instance(self):
        # Implementation to create a test instance
        pass

    def cleanup_instance(self):
        # Implementation to remove the test instance
        pass

    def generate_test_cases(self):
        # Basic reboot test
        self.add_test(TestCase(
            name="Reboot instance successfully",
            input_data={
                "id": 12345,  # Required parameter 'id'
                "instance_id": 12345  # Example instance ID
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "msg": "Instance rebooted successfully"
                }
            },
            setup=self.setup_instance,
            cleanup=self.cleanup_instance
        ))

        # Test with invalid instance ID
        self.add_test(TestCase(
            name="Reboot instance with invalid ID",
            input_data={
                "instance_id": -1  # Invalid instance ID
            },
            expected_output={
                "status_code": 400,
                "response": {
                    "success": False,
                    "error": "invalid_instance_id",
                    "msg": "Invalid instance ID provided"
                }
            }
        ))

        # Test without authorization
        self.add_test(TestCase(
            name="Reboot instance without authorization",
            input_data={
                "instance_id": 12345  # Example instance ID
            },
            expected_output={
                "status_code": 401,
                "response": {
                    "success": False,
                    "error": "unauthorized",
                    "msg": "Authorization required"
                }
            }
        ))