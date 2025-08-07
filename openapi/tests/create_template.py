from .base import CommandTestSuite, TestCase

class CreateTemplateTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="create template",
            description="Create a new template"
        )
        self.generate_test_cases()

    def generate_test_cases(self):
        # Successful template creation
        self.add_test(TestCase(
            name="Create template success",
            input_data={
                "name": "basic-template",
                "image": "ubuntu:latest",  # Added missing image parameter
                "config": {
                    "cpu": 4,
                    "memory": "16GB",
                    "disk": "100GB"
                }
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "msg": "Template created successfully"
                }
            }
        ))
