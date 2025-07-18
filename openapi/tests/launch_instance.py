from .base import CommandTestSuite, TestCase
from .config import TestConfig

class LaunchInstanceTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="launch instance",
            description="Launch a new instance with specified parameters"
        )
        self.generate_test_cases()

    def setup_test_data(self):
        """Setup any required test data before running tests"""
        # Implementation to setup test data
        pass

    def cleanup_test_data(self):
        """Cleanup any test data after running tests"""
        # Implementation to cleanup test data
        pass

    def generate_test_cases(self):
        # Basic Successful Launch
        self.add_test(TestCase(
            name="Basic Instance Launch",
            input_data={
                "image": "ubuntu:latest",
                "gpu_name": "RTX_3090",
                "num_gpus": 1,
                "type": "t2.micro",
                "region": "us-west-1",
                "disk": 16
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "instance_id": TestConfig.INSTANCE_ID  # Will be validated for existence only
                }
            },
            setup=self.setup_test_data,
            cleanup=self.cleanup_test_data
        ))

        # # Invalid Image Format
        # self.add_test(TestCase(
        #     name="Invalid Image Format",
        #     input_data={
        #         "image": "invalid-image-format",
        #         "type": "t2.micro",
        #         "region": "us-west-1"
        #     },
        #     expected_output={
        #         "status_code": 400,
        #         "response": {
        #             "success": False,
        #             "error": "invalid_image_format",
        #             "msg": "The specified image format is invalid."
        #         }
        #     }
        # ))

        # # Missing Required Parameters
        # self.add_test(TestCase(
        #     name="Missing Required Parameters",
        #     input_data={
        #         # Missing 'image' and 'type' parameters
        #         "region": "us-west-1"
        #     },
        #     expected_output={
        #         "status_code": 400,
        #         "response": {
        #             "success": False,
        #             "error": "missing_parameters",
        #             "msg": "Required parameters are missing: image, type"
        #         }
        #     }
        # ))