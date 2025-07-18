from .base import CommandTestSuite, TestCase
 

class ScheduleMaintTestSuite(CommandTestSuite):
    def __init__(self):
        super().__init__(
            command="schedule maint",
            description="Schedule maintenance for a machine"
        )
        self.generate_test_cases()

    def setup_machine(self):
        # Implementation to create a test machine
        pass

    def cleanup_machine(self):
        # Implementation to remove the test machine
        pass

    def generate_test_cases(self):
        # Basic schedule maintenance test
        self.add_test(TestCase(
            name="Schedule maintenance successfully",
            input_data={
                "machine_id": 12345,  # Example machine ID
                "sdate": "-31536000",  # Example start date
                "duration": 2,  # Example duration
                "start_time": "2023-10-01T10:00:00Z",  # Example start time
                "end_time": "2023-10-01T12:00:00Z"  # Example end time
            },
            expected_output={
                "status_code": 200,
                "response": {
                    "success": True,
                    "msg": "Maintenance scheduled successfully"
                }
            },
            setup=self.setup_machine,
            cleanup=self.cleanup_machine
        ))

        # Test with invalid machine ID
        self.add_test(TestCase(
            name="Schedule maintenance with invalid machine ID",
            input_data={
                "machine_id": -1,  # Invalid machine ID
                "start_time": "2023-10-01T10:00:00Z",
                "end_time": "2023-10-01T12:00:00Z"
            },
            expected_output={
                "status_code": 400,
                "response": {
                    "success": False,
                    "error": "invalid_machine_id",
                    "msg": "Invalid machine ID provided"
                }
            }
        ))

        # Test with overlapping maintenance times
        self.add_test(TestCase(
            name="Schedule overlapping maintenance",
            input_data={
                "machine_id": 12345,
                "start_time": "2023-10-01T11:00:00Z",  # Overlapping start time
                "end_time": "2023-10-01T13:00:00Z"  # Overlapping end time
            },
            expected_output={
                "status_code": 409,
                "response": {
                    "success": False,
                    "error": "overlapping_maintenance",
                    "msg": "Maintenance times overlap with existing schedule"
                }
            }
        ))

        # Test without authorization
        self.add_test(TestCase(
            name="Schedule maintenance without authorization",
            input_data={
                "machine_id": 12345,
                "start_time": "2023-10-01T10:00:00Z",
                "end_time": "2023-10-01T12:00:00Z"
            },
            expected_output={
                "status_code": 401,
                "response": {
                    "success": False,
                    "error": "unauthorized",
                    "msg": "Authorization required"
                }
            }
        ))