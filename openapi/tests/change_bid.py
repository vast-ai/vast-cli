from .base import CommandTestSuite, TestCase
from .config import TestConfig

class ChangeBidTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="change bid",
            description="Change bid price for an instance"
        )
        self.generate_test_cases()

    def setup_test_instance(self):
        # Implementation to create test instance would go here
        # In real tests this would create a test instance to modify
        pass

    def cleanup_test_instance(self):
        # Implementation to cleanup test instance
        pass

    def generate_test_cases(self):
        # Test basic bid change
        self.add_test(TestCase(
            name="Change instance bid price",
            input_data={
                "id": TestConfig.INSTANCE_ID,
                "price": 1.50
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "new_bid": 1.50,
                    "instance_id": TestConfig.INSTANCE_ID
                }
            },
            setup=self.setup_test_instance,
            cleanup=self.cleanup_test_instance
        ))

        # # Test bid change with minimum amount
        # self.add_test(TestCase(
        #     name="Change bid to minimum price",
        #     input_data={
        #         "instance_id": "1234567", 
        #         "bid_price": 0.1
        #     },
        #     expected_output={
        #         "status_code": 200,
        #         "response": {
        #             "success": True,
        #             "new_bid": 0.1,
        #             "instance_id": "1234567"
        #         }
        #     }
        # ))

        # # Test bid change with decimal precision
        # self.add_test(TestCase(
        #     name="Change bid with decimal precision",
        #     input_data={
        #         "instance_id": "1234567",
        #         "bid_price": 1.234
        #     },
        #     expected_output={
        #         "status_code": 200,
        #         "response": {
        #             "success": True,
        #             "new_bid": 1.234,
        #             "instance_id": "1234567"
        #         }
        #     }
        # ))