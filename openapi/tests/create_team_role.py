from .base import CommandTestSuite, TestCase

class CreateTeamRoleTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="create team role",
            description="Create a new role within a team"
        )
        self.generate_test_cases()

    def generate_test_cases(self):
        # Successful role creation
        self.add_test(TestCase(
            name="Create role success",
            input_data={
                "name": "developer",
                "permissions": {
                    "read": True,
                    "write": False
                }
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "msg": "Role created successfully"
                }
            }
        ))
