from .base import CommandTestSuite, TestCase
from .config import TestConfig

class RemoveTeamMemberTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="remove team member",
            description="Remove a member from a team"
        )
        self.generate_test_cases()

    def setup_team_member(self):
        # Implementation to create a test team member
        pass

    def cleanup_team_member(self):
        # Implementation to remove the test team member
        pass

    def generate_test_cases(self):
        # Positive test case for successful removal
        self.add_test(TestCase(
            name="Remove existing team member",
            input_data={
                "id": TestConfig.TEAM_MEMBER_ID
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "msg": "Team member removed successfully"
                }
            },
            setup=self.setup_team_member,
            cleanup=self.cleanup_team_member
        ))

        # Test case for attempting to remove a non-existent team member
        self.add_test(TestCase(
            name="Remove non-existent team member",
            input_data={
                "options": ["--member-id", "99999"]  # Non-existent member ID
            },
            expected_output={
                "status_code": 404,
                "response": {
                    "success": False,
                    "error": "not_found",
                    "msg": "Team member not found"
                }
            }
        ))

        # Test case for unauthorized removal attempt
        self.add_test(TestCase(
            name="Unauthorized removal attempt",
            input_data={
                "options": ["--member-id", "12345"]  # Example member ID
            },
            expected_output={
                "status_code": 403,
                "response": {
                    "success": False,
                    "error": "not_authorized",
                    "msg": "User is not authorized to remove team members"
                }
            }
        ))