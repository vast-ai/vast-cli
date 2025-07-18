from .base import CommandTestSuite, TestCase

class CreateTeamTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="create team",
            description="Create a new team with the authenticated user as owner"
        )
        self.generate_test_cases()

    def generate_test_cases(self):
        # Test case for successful team creation
        self.add_test(TestCase(
            name="test_create_team_success",
            input_data={
                "team_name": "my-awesome-team",
                "permissions": {
                    "roles": ["owner", "admin", "member"],
                    "budget": 1000.0,
                    "instances": 5,
                    "types": ["ssh", "jupyter"],
                    "images": ["pytorch/pytorch", "tensorflow/tensorflow"],
                    "machine_restrictions": {
                        "verified": True,
                        "rentable": True,
                        "external": True,
                        "max_instances": 10
                    },
                    "api_restrictions": {
                        "search_offers": True,
                        "create_instance": True,
                        "list_instances": True,
                        "manage_instances": True
                    }
                }
            },
            expected_output="Team Successfully Created!",
        ))
