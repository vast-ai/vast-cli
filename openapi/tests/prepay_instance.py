from .base import CommandTestSuite, TestCase
from .config import TestConfig

class PrepayInstanceTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="prepay instance", 
            description="Test instance prepayment functionality"
        )
        self.generate_test_cases()

    def generate_test_cases(self):
        # Successful prepayment test case
        self.add_test(TestCase(
            name="Successful instance prepayment",
            input_data={
                "id": TestConfig.INSTANCE_ID,
                "amount": 500.0
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "timescale": 3.5,  # Example number of months
                    "discount_rate": 0.3  # Example 30% discount
                }
            }
        ))

        # # Invalid instance ID test case
        # self.add_test(TestCase(
        #     name="Invalid instance ID",
        #     input_data={
        #         "id": -1,  # Invalid ID
        #         "amount": 100.0
        #     },
        #     expected_output={
        #         "status_code": 400,
        #         "response": {
        #             "success": False,
        #             "msg": "No such instance"
        #         }
        #     }
        # ))

        # # Insufficient credit balance test case  
        # self.add_test(TestCase(
        #     name="Insufficient credit balance",
        #     input_data={
        #         "id": TestConfig.INSTANCE_ID,
        #         "amount": 10000.0  # Large amount to trigger insufficient funds
        #     },
        #     expected_output={
        #         "status_code": 411,
        #         "response": {
        #             "success": False,
        #             "msg": "Insufficient credit"
        #         }
        #     }
        # ))

        # # Small amount test case (testing minimum prepayment)
        # self.add_test(TestCase(
        #     name="Small prepayment amount",
        #     input_data={
        #         "id": TestConfig.INSTANCE_ID,
        #         "amount": 0.01  # Very small amount
        #     },
        #     expected_output={
        #         "status_code": 200,
        #         "response": {
        #             "success": True,
        #             "timescale": 0.0,  # Near zero months
        #             "discount_rate": 0.0  # No discount for tiny prepayment
        #         }
        #     }
        # ))

        # # Large amount test case (testing maximum discount cap)
        # self.add_test(TestCase(
        #     name="Large prepayment amount",
        #     input_data={
        #         "id": TestConfig.INSTANCE_ID,
        #         "amount": 50000.0  # Very large amount
        #     },
        #     expected_output={
        #         "status_code": 200,
        #         "response": {
        #             "success": True,
        #             "timescale": 24.0,  # Many months
        #             "discount_rate": 0.4  # Maximum 40% discount cap
        #         }
        #     }
        # ))

        # # Rate limit test case
        # self.add_test(TestCase(
        #     name="Rate limit exceeded",
        #     input_data={
        #         "id": TestConfig.INSTANCE_ID,
        #         "amount": 100.0,
        #         "headers": {
        #             "X-Test-Rate-Limit": "exceed"  # Custom header to trigger rate limit in test environment
        #         }
        #     },
        #     expected_output={
        #         "status_code": 429,
        #         "response": {
        #             "detail": "API requests too frequent endpoint threshold=2.0"
        #         }
        #     }
        # ))