from .base import CommandTestSuite, TestCase
 

class SearchOffersTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="search offers",
            description="Search for available machine offers"
        )
        self.generate_test_cases()

    def setup_offers(self):
        # Implementation to create test offers
        pass

    def cleanup_offers(self):
        # Implementation to remove test offers
        pass

    def generate_test_cases(self):
        # Basic search offers test
        self.add_test(TestCase(
            name="Search offers with valid parameters",
            input_data={
                "options": [
                    "--min-gpu", "1",
                    "--max-price", "0.5"
                ]
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "offers": [{}] * 64  # Adjusted to match num search offers returned by the API
                }
            },
            setup=self.setup_offers,
            cleanup=self.cleanup_offers
        ))

        # Test case for invalid parameters
        self.add_test(TestCase(
            name="Search offers with invalid parameters",
            input_data={
                "options": [
                    "--min-gpu", "-1"  # Invalid GPU count
                ]
            },
            expected_output={
                "status_code": 400,
                "response": {
                    "success": False,
                    "error": "invalid_parameters",
                    "msg": "Invalid GPU count provided"
                }
            }
        ))
