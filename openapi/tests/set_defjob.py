from .base import CommandTestSuite, TestCase

class SetDefJobTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="set defjob", 
            description="Test suite for the 'set defjob' CLI command"
        )
        self.generate_test_cases()

    def setup_function(self):
        # Setup logic if needed
        pass

    def cleanup_function(self):
        # Cleanup logic if needed
        pass

    def generate_test_cases(self):
        # Successful search test case
        self.add_test(TestCase(
            name="Successful machine listing",
            input_data={
                "machine": 123,
                "price_gpu": 0.5,
                "price_inetu": 0.1,
                "price_inetd": 0.1,
                "image": "example-image"
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "extended": 2
                }
            }
        ))
        
        # Example test case for a missing required parameter
        self.add_test(TestCase(
            name="Missing required parameter 'machine'",
            input_data={
                "options": [
                    "--price_gpu", "0.5"
                ]
            },
            expected_output={
                "status_code": 400,
                "response": {
                    "error": "missing_input",
                    "msg": "Missing required parameters: machine"
                }
            }
        ))

    

        # Example test case for unauthorized access
        self.add_test(TestCase(
            name="Unauthorized access attempt",
            input_data={
                "options": [
                    "--machine", "123",
                    "--price_gpu", "0.5"
                ]
            },
            expected_output={
                "status_code": 403,
                "response": {
                    "error": "not_authorized",
                    "msg": "Only machine owner can create ask contracts"
                }
            }
        ))
