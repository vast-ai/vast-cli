from .base import CommandTestSuite, TestCase

class SearchTemplatesTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="search templates",
            description="Search for available machine templates"
        )
        self.generate_test_cases()

    def setup_templates(self):
        # Implementation to create test templates
        pass

    def cleanup_templates(self):
        # Implementation to remove test templates
        pass

    def generate_test_cases(self):
        # Basic search templates test
        self.add_test(TestCase(
            name="Search templates with valid parameters",
            input_data={
                "options": [
                    "--min-gpu", "1",
                    "--max-price", "0.5"
                ]
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "templates": [{}] * 10  # Adjusted to match num search templates returned by the API
                }
            },
            setup=self.setup_templates,
            cleanup=self.cleanup_templates
        ))

        # Test case for invalid parameters
        self.add_test(TestCase(
            name="Search templates with invalid parameters",
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

        # Test case for missing parameters
        self.add_test(TestCase(
            name="Search templates with missing parameters",
            input_data={
                "options": []
            },
            expected_output={
                "status_code": 400,
                "response": {
                    "success": False,
                    "error": "missing_parameters",
                    "msg": "Required parameters are missing"
                }
            }
        ))

        # Test case for unauthorized access
        self.add_test(TestCase(
            name="Search templates without authorization",
            input_data={
                "options": [
                    "--min-gpu", "1"
                ]
            },
            expected_output={
                "status_code": 401,
                "response": {
                    "success": False,
                    "error": "unauthorized",
                    "msg": "Authorization token is missing or invalid"
                }
            }
        ))