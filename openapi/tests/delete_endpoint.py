from .base import CommandTestSuite, TestCase

class DeleteEndpointTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="delete endpoint",
            description="Delete an endpoint group"
        )
        self.generate_test_cases()

    def generate_test_cases(self):
        # Successful endpoint deletion
        self.add_test(TestCase(
            name="Delete endpoint success",
            input_data={
                "client_id": "me",
                "endptjob_id": 4242,  # Example endpoint ID
                "id": 4242  # Adding the required 'id' parameter
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True
                }
            }
        ))
