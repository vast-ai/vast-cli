from .base import CommandTestSuite, TestCase

class ShowTeamMembersTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="show team-members",
            description="Display list of members in your team"
        )
        self.generate_test_cases()
    
    def setup_test_members(self):
        """Create test team members for testing"""
        # Implementation to create test team members
        pass
        
    def cleanup_test_members(self):
        """Remove test team members after testing"""
        # Implementation to remove test team members
        pass
    
    def generate_test_cases(self):
        # Test case for successfully listing team members
        self.add_test(TestCase(
            name="List all team members",
            input_data={
                "options": []
            },
            expected_output={
                "status_code": 200,
                "response": [
                    {
                        "id": 123,
                        "username": "johndoe",
                        "email": "johndoe@example.com",
                        "roles": ["admin", "member"]
                    },
                    {
                        "id": 124,
                        "username": "janesmith",
                        "email": "janesmith@example.com",
                        "roles": ["member"]
                    }
                ]
            },
            setup=self.setup_test_members,
            cleanup=self.cleanup_test_members
        ))
        
        # Test case for unauthorized access
        self.add_test(TestCase(
            name="Unauthorized access",
            input_data={
                "options": [],
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
        
        # Test case for forbidden access (not a team member)
        self.add_test(TestCase(
            name="Forbidden access",
            input_data={
                "options": []
            },
            expected_output={
                "status_code": 403,
                "response": {
                    "success": False,
                    "error": "forbidden",
                    "msg": "User is not a member of any team"
                }
            }
        ))
        
        # Test case for empty team
        self.add_test(TestCase(
            name="No team members found",
            input_data={
                "options": []
            },
            expected_output={
                "status_code": 200,
                "response": []
            },
            setup=lambda: None,  # Empty setup to ensure no team members exist
            cleanup=self.cleanup_test_members
        ))
        
        # Test case with role filtering
        self.add_test(TestCase(
            name="List team members with specific role",
            input_data={
                "options": ["--role", "admin"]
            },
            expected_output={
                "status_code": 200,
                "response": [
                    {
                        "id": 123,
                        "username": "johndoe",
                        "email": "johndoe@example.com",
                        "roles": ["admin", "member"]
                    }
                ]
            },
            setup=self.setup_test_members,
            cleanup=self.cleanup_test_members
        ))