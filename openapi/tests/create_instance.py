from .base import CommandTestSuite, TestCase

class CreateInstanceTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="create instance",
            description="Create a new instance from a provider offer"
        )
        self.generate_test_cases()
    
    def setup_test_data(self):
        # Setup test SSH keys, templates, etc.
        pass
        
    def cleanup_test_data(self):
        # Cleanup test data
        pass
    
    def generate_test_cases(self):
        # Basic Successful Creation
        self.add_test(TestCase(
            name="Basic Instance Creation",
            input_data={
                "id": 1234567,  # As integer since it's a JSON request body
                "image": "tensorflow/tensorflow:latest-gpu",
                "disk": 32.0  # As float per the API spec
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "new_contract": None  # Will be validated for existence only
                }
            }
        ))
