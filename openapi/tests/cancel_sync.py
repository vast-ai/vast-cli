from .base import CommandTestSuite, TestCase
from .config import TestConfig

class CancelSyncTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="cancel sync",
            description="Cancel a remote sync operation in progress"
        )
        self.generate_test_cases()
    
    def setup_sync_operation(self):
        # Implementation to create a sync operation that can be cancelled
        # In real tests this would start an actual sync
        pass
        
    def cleanup_sync_operation(self):
        # Cleanup any test sync operations
        pass
    
    def generate_test_cases(self):
        # Test successful cancellation
        self.add_test(TestCase(
            name="Cancel sync operation",
            input_data={
                "dst_id": TestConfig.INSTANCE_ID,
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True
                }
            },
            setup=self.setup_sync_operation,
            cleanup=self.cleanup_sync_operation
        ))