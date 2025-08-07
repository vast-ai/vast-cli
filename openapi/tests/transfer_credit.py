from .base import CommandTestSuite, TestCase

class TransferCreditTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="transfer credit",
            description="Transfer credits to another user"
        )
        self.generate_test_cases()
    
    def setup_test_users(self):
        """Set up test user accounts with balances"""
        # Implementation to create test users
        pass
        
    def cleanup_test_users(self):
        """Clean up test user accounts"""
        # Implementation to clean up test users
        pass
    
    def generate_test_cases(self):
        # Test case for successful credit transfer by email
        self.add_test(TestCase(
            name="Transfer credits by email success",
            input_data={
                "recipient": "user@example.com",
                "amount": 100.00
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True
                }
            },
            setup=self.setup_test_users,
            cleanup=self.cleanup_test_users
        ))
        
        # Test case for successful credit transfer by user ID
        self.add_test(TestCase(
            name="Transfer credits by user ID success",
            input_data={
                "recipient": "12345",
                "amount": 50.50
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True
                }
            }
        ))
        
        # Test case for insufficient balance
        self.add_test(TestCase(
            name="Insufficient balance",
            input_data={
                "recipient": "user@example.com",
                "amount": 1000000.00
            },
            expected_output={
                "status_code": 400,
                "response": {
                    "success": False,
                    "error": "insufficient_balance",
                    "msg": "Insufficient balance for transfer"
                }
            }
        ))
        
        # Test case for invalid recipient email
        self.add_test(TestCase(
            name="Invalid recipient email",
            input_data={
                "recipient": "invalid@email",
                "amount": 100.00
            },
            expected_output={
                "status_code": 400,
                "response": {
                    "success": False,
                    "error": "invalid_recipient",
                    "msg": "Invalid recipient email address"
                }
            }
        ))
        
        # Test case for non-existent recipient
        self.add_test(TestCase(
            name="Non-existent recipient",
            input_data={
                "recipient": "nonexistent@example.com",
                "amount": 100.00
            },
            expected_output={
                "status_code": 400,
                "response": {
                    "success": False,
                    "error": "invalid_recipient",
                    "msg": "Recipient not found"
                }
            }
        ))
        
        # Test case for negative amount
        self.add_test(TestCase(
            name="Negative amount",
            input_data={
                "recipient": "user@example.com",
                "amount": -50.00
            },
            expected_output={
                "status_code": 400,
                "response": {
                    "success": False,
                    "error": "invalid_args",
                    "msg": "Amount must be positive"
                }
            }
        ))
        
        # Test case for amount below minimum
        self.add_test(TestCase(
            name="Amount below minimum",
            input_data={
                "recipient": "user@example.com",
                "amount": 0.001
            },
            expected_output={
                "status_code": 400,
                "response": {
                    "success": False,
                    "error": "invalid_args",
                    "msg": "Amount must be at least 0.01"
                }
            }
        ))
        
        # Test case for unauthorized access
        self.add_test(TestCase(
            name="Unauthorized access",
            input_data={
                "recipient": "user@example.com",
                "amount": 100.00,
                "headers": {
                    "Authorization": "Bearer invalid_token"
                }
            },
            expected_output={
                "status_code": 401,
                "response": {
                    "success": False,
                    "error": "unauthorized",
                    "msg": "Invalid or missing authentication token"
                }
            }
        ))
        
        # Test case for rate limit exceeded
        self.add_test(TestCase(
            name="Rate limit exceeded",
            input_data={
                "recipient": "user@example.com",
                "amount": 100.00
            },
            expected_output={
                "status_code": 429,
                "response": {
                    "detail": "API requests too frequent endpoint threshold=2.5"
                }
            }
        ))