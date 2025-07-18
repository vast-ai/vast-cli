# test_suite/remote_cloud_copy.py
from .base import CommandTestSuite, TestCase
from .config import TestConfig

class RemoteCloudCopyTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="cloud copy",
            description="Copy files/folders between instances and cloud storage"
        )
        self.generate_test_cases()
    
    def generate_test_cases(self):
        # Successful cloud copy to instance
        self.add_test(TestCase(
            name="Cloud to instance copy success",
            input_data={
                "instance_id": TestConfig.INSTANCE_ID,
                "src": "folder/source",
                "dst": "/workspace",
                "selected": "123",  # Cloud connection ID
                "transfer": "Cloud To Instance"
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "msg": "Sending Command... Please Wait",
                    "result_url": None  # Dynamic URL, don't check exact value
                }
            }
        ))

        # # Successful instance to cloud copy
        # self.add_test(TestCase(
        #     name="Instance to cloud copy success", 
        #     input_data={
        #         "instance_id": TestConfig.INSTANCE_ID,
        #         "src": "/workspace/data",
        #         "dst": "backup_folder",
        #         "selected": "123",
        #         "transfer": "Instance To Cloud"
        #     },
        #     expected_output={
        #         "status_code": 200,
        #         "response": {
        #             "success": True,
        #             "msg": "Sending Command... Please Wait",
        #             "result_url": None
        #         }
        #     }
        # ))

        # # Missing cloud connection ID
        # self.add_test(TestCase(
        #     name="No cloud connection selected",
        #     input_data={
        #         "instance_id": TestConfig.INSTANCE_ID,
        #         "src": "/workspace/data",
        #         "dst": "backup_folder", 
        #         "selected": None,
        #         "transfer": "Instance To Cloud"
        #     },
        #     expected_output={
        #         "status_code": 400,
        #         "response": {
        #             "success": False,
        #             "msg": "No Cloud Operation Selected. If you have one selected, but it is sending this error, refresh the page"
        #         }
        #     }
        # ))

        # # Invalid path characters
        # self.add_test(TestCase(
        #     name="Invalid path characters",
        #     input_data={
        #         "instance_id": TestConfig.INSTANCE_ID, 
        #         "src": "/workspace/bad path/with spaces",
        #         "dst": "backup_folder",
        #         "selected": "123",
        #         "transfer": "Instance To Cloud"
        #     },
        #     expected_output={
        #         "status_code": 400,
        #         "response": {
        #             "success": False,
        #             "msg": "Source and Destination Cannot Contain Whitespaces or Unauthorized characters"
        #         }
        #     }
        # ))

        # # Missing source path for instance to cloud
        # self.add_test(TestCase(
        #     name="Missing source path",
        #     input_data={
        #         "instance_id": TestConfig.INSTANCE_ID,
        #         "src": "",
        #         "dst": "backup_folder",
        #         "selected": "123",
        #         "transfer": "Instance To Cloud" 
        #     },
        #     expected_output={
        #         "status_code": 400,
        #         "response": {
        #             "success": False,
        #             "msg": "src can not be null"
        #         }
        #     }
        # ))

        # # Missing destination path for cloud to instance
        # self.add_test(TestCase(
        #     name="Missing destination path",
        #     input_data={
        #         "instance_id": TestConfig.INSTANCE_ID,
        #         "src": "cloud_folder",
        #         "dst": "",
        #         "selected": "123",
        #         "transfer": "Cloud To Instance"
        #     },
        #     expected_output={
        #         "status_code": 400,
        #         "response": {
        #             "success": False,
        #             "msg": "dst can not be null"
        #         }
        #     }
        # ))

        # # Invalid transfer direction
        # self.add_test(TestCase(
        #     name="Invalid transfer direction",
        #     input_data={
        #         "instance_id": TestConfig.INSTANCE_ID,
        #         "src": "/workspace/data",
        #         "dst": "backup_folder",
        #         "selected": "123",
        #         "transfer": "Invalid Direction"
        #     },
        #     expected_output={
        #         "status_code": 400,
        #         "response": {
        #             "success": False,
        #             "msg": "Could Not Determine Transfer Direction"
        #         }
        #     }
        # ))