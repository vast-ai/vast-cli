# test_suite/cancel_maint.py
from typing import Dict, Any
from .base import CommandTestSuite, TestCase
from .config import TestConfig

class CancelMaintTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="cancel maint",
            description="Cancel a scheduled maintenance window for a machine"
        )
        self.generate_test_cases()
    
    def generate_test_cases(self):
        # Successful cancellation case
        self.add_test(TestCase(
            name="Cancel maintenance window success",
            input_data={
                "machine_id": TestConfig.VALID_MACHINE_ID
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "ctime": None,  # We don't check exact time value
                    "machine_id": 1234,
                    "msg": "deleted 1 scheduled maintenance window(s) on machine 1234"
                }
            }
        ))

        # # Machine not found case
        # self.add_test(TestCase(
        #     name="Machine not found",
        #     input_data={
        #         "machine_id": 99999
        #     },
        #     expected_output={
        #         "status_code": 404,
        #         "response": {
        #             "success": False,
        #             "msg": "No such machine id",
        #             "machine_id": 99999,
        #             "user_id": None  # We don't check exact user_id
        #         }
        #     }
        # ))

        # # Invalid machine ID format
        # self.add_test(TestCase(
        #     name="Invalid machine ID format",
        #     input_data={
        #         "machine_id": "invalid-id"  # Should be integer
        #     },
        #     expected_output={
        #         "status_code": 400,
        #         "response": {
        #             "success": False,
        #             "error": "invalid_args",
        #             "msg": "Machine ID must be an integer"
        #         }
        #     }
        # ))

        # # No maintenance window scheduled
        # self.add_test(TestCase(
        #     name="No maintenance window scheduled",
        #     input_data={
        #         "machine_id": 5678
        #     },
        #     expected_output={
        #         "status_code": 200,
        #         "response": {
        #             "success": True,
        #             "ctime": None,
        #             "machine_id": 5678,
        #             "msg": "deleted 0 scheduled maintenance window(s) on machine 5678"
        #         }
        #     }
        # ))

        # # Machine belongs to different user
        # self.add_test(TestCase(
        #     name="Machine belongs to different user",
        #     input_data={
        #         "machine_id": 4321
        #     },
        #     expected_output={
        #         "status_code": 404,
        #         "response": {
        #             "success": False,
        #             "msg": "Machine does not belong to user",
        #             "machine_id": 4321,
        #             "user_id": None
        #         }
        #     }
        # ))

        # # Missing machine ID parameter
        # self.add_test(TestCase(
        #     name="Missing machine ID",
        #     input_data={
        #         # Missing required machine_id parameter
        #     },
        #     expected_output={
        #         "status_code": 400,
        #         "response": {
        #             "success": False,
        #             "error": "invalid_args",
        #             "msg": "Missing required parameter: machine_id"
        #         }
        #     }
        # ))