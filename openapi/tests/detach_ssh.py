from .base import CommandTestSuite, TestCase

class DetachSSHTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="detach ssh",
            description="Detach SSH key from instance"
        )
        self.generate_test_cases()

    def generate_test_cases(self):
        # Successful detachment case
        self.add_test(TestCase(
            name="Detach SSH key success",
            input_data={
                "id": 13813504,  # Path parameter
                "key": "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDZ"
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "msg": "SSH key detached successfully"
                }
            }
        ))

        # # Instance not found case
        # self.add_test(TestCase(
        #     name="Instance not found",
        #     input_data={
        #         "id": 99999  # Non-existent instance ID
        #     },
        #     expected_output={
        #         "status_code": 404,
        #         "response": {
        #             "success": False,
        #             "error": "no_such_instance",
        #             "msg": "No such instance."
        #         }
        #     }
        # ))

        # # Invalid instance ID format
        # self.add_test(TestCase(
        #     name="Invalid instance ID format",
        #     input_data={
        #         "id": "invalid-id"  # Should be integer
        #     },
        #     expected_output={
        #         "status_code": 400,
        #         "response": {
        #             "success": False,
        #             "error": "invalid_args",
        #             "msg": "Instance ID must be an integer"
        #         }
        #     }
        # ))

        # # Missing instance ID parameter
        # self.add_test(TestCase(
        #     name="Missing instance ID",
        #     input_data={
        #         # Missing required id parameter
        #     },
        #     expected_output={
        #         "status_code": 400,
        #         "response": {
        #             "success": False,
        #             "error": "invalid_args",
        #             "msg": "Missing required parameter: id"
        #         }
        #     }
        # ))