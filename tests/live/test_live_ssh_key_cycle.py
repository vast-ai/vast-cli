"""Live SSH key CRUD lifecycle test — requires VAST_API_KEY.

Creates a test SSH key, reads it, and deletes it.
Deletion happens in a finally block for guaranteed cleanup.
"""

import pytest

pytestmark = pytest.mark.live


def _generate_test_ssh_key() -> str:
    """Generate a valid ephemeral ed25519 public key for testing."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    key = Ed25519PrivateKey.generate()
    pub = key.public_key().public_bytes(Encoding.OpenSSH, PublicFormat.OpenSSH).decode()
    return f"{pub} vasttest@test"


class TestSshKeyLifecycle:
    def test_create_read_delete(self, live_client):
        from vastai.api.keys import create_ssh_key, show_ssh_keys, delete_ssh_key

        test_key = _generate_test_ssh_key()
        created_key_id = None
        try:
            # Create
            result = create_ssh_key(live_client, ssh_key=test_key)
            assert isinstance(result, dict), f"Unexpected response: {result}"
            assert result.get("success") is True, f"Failed to create SSH key: {result}"
            created_key_id = result.get("key", {}).get("id")
            assert created_key_id is not None, f"No key ID in response: {result}"

            # Read and verify it's in the list
            keys = show_ssh_keys(live_client)
            assert keys is not None, "Failed to read SSH keys"

            if isinstance(keys, dict) and "ssh_keys" in keys:
                key_list = keys["ssh_keys"]
            elif isinstance(keys, list):
                key_list = keys
            else:
                key_list = []

            found = any(
                isinstance(k, dict) and k.get("id") == created_key_id
                for k in key_list
            )
            assert found, f"SSH key {created_key_id} not found in key list"

        finally:
            # Delete (guaranteed cleanup)
            if created_key_id is not None:
                try:
                    delete_ssh_key(live_client, id=created_key_id)
                except Exception:
                    pass

        # Verify deletion
        if created_key_id is not None:
            keys_after = show_ssh_keys(live_client)
            if isinstance(keys_after, dict) and "ssh_keys" in keys_after:
                key_list = keys_after["ssh_keys"]
            elif isinstance(keys_after, list):
                key_list = keys_after
            else:
                key_list = []
            found = any(
                isinstance(k, dict) and k.get("id") == created_key_id
                for k in key_list
            )
            assert not found, f"SSH key {created_key_id} still exists after deletion"
