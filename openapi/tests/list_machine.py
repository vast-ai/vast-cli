from .base import CommandTestSuite, TestCase
from .config import TestConfig

class ListMachineTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="list machine",
            description="List all machines available to the user"
        )
        self.generate_test_cases()
    
    def generate_test_cases(self):
        # Successful listing of machines
        self.add_test(TestCase(
            name="List machines success",
            input_data={
                "machine": TestConfig.VALID_MACHINE_ID,
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "machines": []  # Check for structure, actual content may vary
                }
            }
        ))

        # # Unauthorized access
        # self.add_test(TestCase(
        #     name="Unauthorized access",
        #     input_data={
        #         "options": []
        #     },
        #     expected_output={
        #         "status_code": 401,
        #         "response": {
        #             "success": False,
        #             "error": "unauthorized",
        #             "msg": "Unauthorized access"
        #         }
        #     }
        # ))

        # # Invalid query parameters
        # self.add_test(TestCase(
        #     name="Invalid query parameters",
        #     input_data={
        #         "options": ["--invalid-param"]
        #     },
        #     expected_output={
        #         "status_code": 400,
        #         "response": {
        #             "success": False,
        #             "error": "invalid_args",
        #             "msg": "Invalid query parameters"
        #         }
        #     }
        # ))

        # # Too many requests
        # self.add_test(TestCase(
        #     name="Too many requests",
        #     input_data={
        #         "options": []
        #     },
        #     expected_output={
        #         "status_code": 429,
        #         "response": {
        #             "detail": "API requests too frequent endpoint threshold=4.0"
        #         }
        #     }
        # ))