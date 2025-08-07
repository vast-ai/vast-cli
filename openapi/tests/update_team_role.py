from .base import CommandTestSuite, TestCase

class UpdateTeamRoleTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="update team-role",
            description="Update an existing team role"
        )
        self.generate_test_cases()
    
    def setup_test_role(self):
        """Set up test team role"""
        pass
        
    def cleanup_test_role(self):
        """Clean up test team role"""
        pass
    
    def generate_test_cases(self):
        # Test case for successfully updating team role
        self.add_test(TestCase(
            name="Update team role success",
            input_data={
                "id": 123,
                "name": "Developer",
                "permissions": {
                    "can_view": True,
                    "can_edit": True,
                    "can_delete": False
                }
            },
            expected_output={
                "status_code": 200,
                "response": "Successfully Updated Team Role For Developer"
            },
            setup=self.setup_test_role,
            cleanup=self.cleanup_test_role
        ))
        
        # Test case for missing name
        self.add_test(TestCase(
            name="Missing name",
            input_data={
                "id": 123,
                "permissions": {
                    "can_view": True
                }
            },
            expected_output={
                "status_code": 400,
                "response": {
                    "error": "missing_parameter",
                    "msg": "Name is required"
                }
            }
        ))
        
        # Test case for missing permissions
        self.add_test(TestCase(
            name="Missing permissions",
            input_data={
                "id": 123,
                "name": "Developer"
            },
            expected_output={
                "status_code": 400,
                "response": {
                    "error": "missing_parameter",
                    "msg": "Permissions are required"
                }
            }
        ))
        
        # Test case for invalid role ID
        self.add_test(TestCase(
            name="Invalid role ID",
            input_data={
                "id": 99999,
                "name": "Developer",
                "permissions": {
                    "can_view": True
                }
            },
            expected_output={
                "status_code": 404,
                "response": {
                    "error": "not_found",
                    "msg": "Role not found"
                }
            }
        ))
        
        # Test case for forbidden access
        self.add_test(TestCase(
            name="Forbidden access",
            input_data={
                "id": 123,
                "name": "Developer",
                "permissions": {
                    "can_view": True
                }
            },
            expected_output={
                "status_code": 403,
                "response": {
                    "error": "forbidden",
                    "msg": "User does not have permission to update this role"
                }
            }
        ))