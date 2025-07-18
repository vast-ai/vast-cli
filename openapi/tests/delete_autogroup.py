from .base import CommandTestSuite, TestCase

class DeleteAutogroupTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="delete autogroup",
            description="Delete an existing autoscaling group"
        )
        self.generate_test_cases()

    def generate_test_cases(self):
        # Successful deletion of an autogroup
        self.add_test(TestCase(
            name="Delete autogroup success",
            input_data={
                "id": 12345,  # Example autogroup ID
                "client_id": "me",  # Example client ID
                "autojob_id": 54321  # Example autojob ID
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "msg": "Autogroup deleted successfully"
                }
            }
        ))
