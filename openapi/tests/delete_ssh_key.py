from .base import CommandTestSuite, TestCase

class DeleteSSHKeyTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="delete ssh-key",
            description="Delete an existing SSH key"
        )
        self.generate_test_cases()

    def generate_test_cases(self):
        # Successful SSH key deletion
        self.add_test(TestCase(
            name="Delete SSH key success",
            input_data={
                "id": 67890  # Example SSH key ID
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "msg": "SSH key deleted successfully"
                }
            }
        ))
