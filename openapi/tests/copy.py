from .base import CommandTestSuite, TestCase
 

class CopyTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="copy",
            description="Copy directories between instances and/or local"
        )
        self.generate_test_cases()
    
    def generate_test_cases(self):
        # Test basic copy between instances
        self.add_test(TestCase(
            name="Basic copy between instances",
            input_data={
                "src_id": "13899983",
                "dst_id": "13899866",
                "src_path": "/root/sammy.txt",
                "dst_path": "/root"
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    # "msg": "Sending Command... Please Wait",
                    # "result_url": "s3_instance_logs_hash_here",
                }
            }
        ))

        # # Test copy with specific paths
        # self.add_test(TestCase(
        #     name="Copy with specific paths",
        #     input_data={
        #         "options": [
        #             "--src-path", "/custom/src/path",
        #             "--dst-path", "/custom/dst/path",
        #             "123", "456"
        #         ],
        #         "args": {
        #             "src_id": "123", 
        #             "dst_id": "456",
        #             "src_path": "/custom/src/path",
        #             "dst_path": "/custom/dst/path"
        #         }
        #     },
        #     expected_output={
        #         "status_code": 200,
        #         "response": {
        #             "success": True,
        #             "transfer_id": "def456",
        #             "status": "started",
        #             "src_id": "123",
        #             "dst_id": "456",
        #             "src_path": "/custom/src/path", 
        #             "dst_path": "/custom/dst/path"
        #         }
        #     }
        # ))

        # # Test local to remote copy
        # self.add_test(TestCase(
        #     name="Local to remote copy",
        #     input_data={
        #         "options": ["./local/path", "789:/remote/path"],
        #         "args": {
        #             "src_path": "./local/path",
        #             "dst_id": "789",
        #             "dst_path": "/remote/path"
        #         }
        #     },
        #     expected_output={
        #         "status_code": 200,
        #         "response": {
        #             "success": True,
        #             "transfer_id": "ghi789",
        #             "status": "started",
        #             "src_path": "./local/path",
        #             "dst_id": "789",
        #             "dst_path": "/remote/path"
        #         }
        #     }
        # ))
