# test_suite/cancel_copy.py
from .base import CommandTestSuite, TestCase

class CancelCopyTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="cancel copy",
            description="Cancel a remote copy operation in progress"
        )
        self.generate_test_cases()
    
    def generate_test_cases(self):
        # Successful cancellation
        self.add_test(TestCase(
            name="Cancel copy success",
            input_data={
                "dst_id": "12345"  # Example destination ID
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True
                }
            }
        ))
        
        # # Invalid destination ID
        # self.add_test(TestCase(
        #     name="Invalid destination ID format",
        #     input_data={
        #         "dst_id": "invalid-id"  # Non-numeric ID
        #     },
        #     expected_output={
        #         "status_code": 400,
        #         "response": {
        #             "success": False,
        #             "error": "invalid_args",
        #             "msg": "Invalid dst_id."
        #         }
        #     }
        # ))
        
        # # Missing required parameter
        # self.add_test(TestCase(
        #     name="Missing destination ID",
        #     input_data={
        #         # Missing required dst_id parameter
        #     },
        #     expected_output={
        #         "status_code": 400,
        #         "response": {
        #             "success": False,
        #             "error": "invalid_args",
        #             "msg": "Missing required parameter: dst_id"
        #         }
        #     }
        # ))
        
        # # Destination ID not found
        # self.add_test(TestCase(
        #     name="Destination ID not found",
        #     input_data={
        #         "dst_id": "99999999"  # Non-existent ID
        #     },
        #     expected_output={
        #         "status_code": 404,
        #         "response": {
        #             "success": False,
        #             "error": "no_such_user",
        #             "msg": "No such user."
        #         }
        #     }
        # ))

        # # No active copy operation
        # self.add_test(TestCase(
        #     name="No active copy operation",
        #     input_data={
        #         "dst_id": "54321"  # Valid ID but no active copy
        #     },
        #     expected_output={
        #         "status_code": 400,
        #         "response": {
        #             "success": False,
        #             "error": "invalid_args",
        #             "msg": "No active copy operation found for this destination."
        #         }
        #     }
        # ))