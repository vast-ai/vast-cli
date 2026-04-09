"""Live env-var CRUD lifecycle test — requires VAST_API_KEY.

Creates a unique env var, reads it, updates it, and deletes it.
Deletion happens in a finally block for guaranteed cleanup.

Note: The API masks env var values on read (returns '********'),
so we can only verify that the key exists, not the plaintext value.
"""

import uuid
import pytest

pytestmark = pytest.mark.live


class TestEnvVarLifecycle:
    def test_create_read_update_delete(self, live_client):
        from vastai.api.auth import create_env_var, show_env_vars, update_env_var, delete_env_var

        var_name = f"VASTTEST_{uuid.uuid4().hex[:12].upper()}"
        original_value = "test_value_1"
        updated_value = "test_value_2"

        try:
            # Create
            result = create_env_var(live_client, name=var_name, value=original_value)
            assert result.get("success") is True, f"Failed to create env var: {result}"

            # Read — API masks values, so just verify the key exists
            env_vars = show_env_vars(live_client)
            assert var_name in env_vars, f"Env var {var_name} not found after creation"

            # Update
            result = update_env_var(live_client, name=var_name, value=updated_value)
            assert result.get("success") is True, f"Failed to update env var: {result}"

            # Read — verify key still exists after update
            env_vars = show_env_vars(live_client)
            assert var_name in env_vars, f"Env var {var_name} not found after update"

        finally:
            # Delete (guaranteed cleanup)
            try:
                delete_env_var(live_client, name=var_name)
            except Exception:
                pass

        # Verify deletion
        env_vars = show_env_vars(live_client)
        assert var_name not in env_vars, f"Env var {var_name} still exists after deletion"
