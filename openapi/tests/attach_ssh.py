from .base import CommandTestSuite, TestCase

class AttachSSHTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="attach ssh",
            description="Attach SSH to a machine"
        )
        self.generate_test_cases()

    def setup_machine(self):
        # Implementation to create a test machine
        pass

    def cleanup_machine(self):
        # Implementation to remove the test machine
        pass

    def generate_test_cases(self):
        # Basic attach SSH test
        self.add_test(TestCase(
            name="Attach SSH to machine",
            input_data={
                "machine_id": 12345,  # Example machine ID
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "msg": "SSH attached successfully"
                }
            },
            setup=self.setup_machine,
            cleanup=self.cleanup_machine
        ))

        # Test case for invalid machine ID
        self.add_test(TestCase(
            name="Invalid machine ID",
            input_data={
                "machine_id": -1,  # Invalid machine ID
                "options": []
            },
            expected_output={
                "status_code": 400,
                "response": {
                    "success": False,
                    "error": "invalid_machine_id",
                    "msg": "Invalid machine ID provided"
                }
            }
        ))

        # Test case for unauthorized access
        self.add_test(TestCase(
            name="Unauthorized access",
            input_data={
                "machine_id": 12345,
                "options": []
            },
            expected_output={
                "status_code": 403,
                "response": {
                    "success": False,
                    "error": "not_authorized",
                    "msg": "User not authorized to attach SSH"
                }
            }
        ))