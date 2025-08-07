from .base import CommandTestSuite, TestCase
 
from .config import TestConfig

class ShowInstanceTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="show instance",
            description="Test showing instance details"
        )
        self.generate_test_cases()

    def generate_test_cases(self):
        # Test case for successfully showing an instance
        self.add_test(TestCase(
            name="Show instance successfully",
            input_data={
                "id": TestConfig.INSTANCE_ID  # Assuming we add this to TestConfig
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "instance_details": {},  # Allow any instance details structure
                    "name": None,            # Allow any name
                    "instance_id": None,     # Allow any ID
                    "created_at": None       # Allow any timestamp
                }
            }
        ))

        # Test case for instance not found
        self.add_test(TestCase(
            name="Instance not found",
            input_data={
                "id": 999999  # Assuming this ID does not exist
            },
            expected_output={
                "status_code": 404,
                "response": {
                    "error": "not_found",
                    "msg": "Instance not found"
                }
            }
        ))

        # Test case for unauthorized access
        self.add_test(TestCase(
            name="Unauthorized access",
            input_data={
                "id": TestConfig.INSTANCE_ID  # Assuming we add this to TestConfig
            },
            expected_output={
                "status_code": 403,
                "response": {
                    "error": "not_authorized",
                    "msg": "User is not authorized to view this instance"
                }
            }
        ))
from .config import TestConfig