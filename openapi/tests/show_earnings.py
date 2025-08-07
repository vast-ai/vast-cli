from .base import CommandTestSuite, TestCase
from .config import TestConfig

class ShowEarningsTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="show earnings",
            description="Get machine earning history reports"
        )
        self.generate_test_cases()
    
    def setup_test_data(self):
        """Create test earning entries"""
        pass
        
    def cleanup_test_data(self):
        """Remove test earning entries"""
        pass
    
    def generate_test_cases(self):
        # Test successful earnings retrieval with timeframe
        self.add_test(TestCase(
            name="Show earnings with timeframe",
            input_data={
                "user_id": TestConfig.USER_ID,
                "sdate": 1698796800,  # Nov 1 2023
                "edate": 1699228800   # Nov 7 2023
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "invoices": [
                        {
                            "amount": 10.50,
                            "timestamp": 1698796800, 
                            "description": "Machine earning charge",
                            "type": "charge"
                        }
                    ],
                    "current": {
                        "charges": 10.50,
                        "service_fee": 0.53,
                        "total": 11.03,
                        "credit": 0.0
                    }
                }
            },
            setup=self.setup_test_data,
            cleanup=self.cleanup_test_data
        ))
