from .base import CommandTestSuite, TestCase
from .config import TestConfig

class LabelInstanceTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="label instance",
            description="Add or update a label for an instance"
        )
        self.generate_test_cases()
    
    def generate_test_cases(self):
        # Successful label addition
        self.add_test(TestCase(
            name="Add label to instance success",
            input_data={
                "id": TestConfig.INSTANCE_ID,  # Example instance ID
                "label": "environment",
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "msg": "Label added successfully"
                }
            }
        ))

        # # Update existing label
        # self.add_test(TestCase(
        #     name="Update existing label success",
        #     input_data={
        #         "instance_id": 1234567,
        #         "label": "environment",
        #         "value": "staging"
        #     },
        #     expected_output={
        #         "status_code": 200,
        #         "response": {
        #             "success": True,
        #             "msg": "Label updated successfully"
        #         }
        #     }
        # ))

        # # Missing label parameter
        # self.add_test(TestCase(
        #     name="Missing label parameter",
        #     input_data={
        #         "instance_id": 1234567,
        #         "value": "production"
        #     },
        #     expected_output={
        #         "status_code": 400,
        #         "response": {
        #             "success": False,
        #             "error": "missing_label",
        #             "msg": "Label parameter is required"
        #         }
        #     }
        # ))

        # # Invalid instance ID
        # self.add_test(TestCase(
        #     name="Invalid instance ID",
        #     input_data={
        #         "instance_id": "invalid-id",  # Should be an integer
        #         "label": "environment",
        #         "value": "production"
        #     },
        #     expected_output={
        #         "status_code": 400,
        #         "response": {
        #             "success": False,
        #             "error": "invalid_instance_id",
        #             "msg": "Instance ID must be an integer"
        #         }
        #     }
        # ))