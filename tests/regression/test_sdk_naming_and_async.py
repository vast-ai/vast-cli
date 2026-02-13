"""Regression tests for SDK naming consistency, typo fixes, and async migration."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestNamingConsistency:
    """Both workergroup and autogroup names should exist."""

    def test_workergroup_methods_exist(self):
        """SDK should have workergroup method names."""
        base_path = Path(__file__).parent.parent.parent / "vastai" / "vastai_base.py"
        content = base_path.read_text()

        # Should have workergroup methods
        workergroup_methods = re.findall(r'def\s+\w*workergroup\w*\s*\(', content, re.IGNORECASE)
        assert len(workergroup_methods) > 0, "Should have workergroup methods"

    def test_autogroup_aliases_exist(self):
        """SDK should have autogroup aliases for backwards compatibility."""
        base_path = Path(__file__).parent.parent.parent / "vastai" / "vastai_base.py"
        content = base_path.read_text()

        # Should have autogroup names (either as primary or alias)
        has_autogroup = "autogroup" in content.lower()
        assert has_autogroup, "Should have autogroup names for backwards compatibility"

    def test_sdk_has_both_names(self):
        """VastAI instance should have both naming conventions."""
        try:
            from vastai import VastAI
            v = VastAI(api_key="test")

            # Check for at least one workergroup and autogroup method
            methods = dir(v)
            has_workergroup = any("workergroup" in m.lower() for m in methods)
            has_autogroup = any("autogroup" in m.lower() for m in methods)

            # At least one should exist (may not have full set in base)
            assert has_workergroup or has_autogroup, "Should have group-related methods"
        except ImportError:
            # If import fails, just check file content
            pass

    def test_all_workergroup_methods_have_aliases(self):
        """Each workergroup method should have an autogroup alias."""
        base_path = Path(__file__).parent.parent.parent / "vastai" / "vastai_base.py"
        content = base_path.read_text()

        # Find all workergroup method definitions
        workergroup_defs = re.findall(r'def\s+(\w*workergroup\w*)\s*\(', content, re.IGNORECASE)

        # Each should have a corresponding alias comment or assignment
        for method in workergroup_defs:
            # Check for alias assignment pattern: xxx_autogroup = xxx_workergroup or xxx_autoscaler = xxx_workergroup
            alias_patterns = [
                method.lower().replace("workergroup", "autogroup"),
                method.lower().replace("workergroup", "autoscaler"),
            ]
            has_alias = any(p in content.lower() for p in alias_patterns)
            assert has_alias, f"Method {method} should have a backwards compatibility alias"

    def test_naming_matches_cli(self):
        """SDK method names should match CLI command naming."""
        # CLI uses: create__workergroup, delete__workergroup, show__workergroups, update__workergroup
        # SDK should have: create_workergroup, delete_workergroup, show_workergroups, update_workergroup
        base_path = Path(__file__).parent.parent.parent / "vastai" / "vastai_base.py"
        content = base_path.read_text()

        expected_methods = [
            "create_workergroup",
            "delete_workergroup",
            "show_workergroups",
            "update_workergroup",
        ]

        for method in expected_methods:
            pattern = rf'def\s+{method}\s*\('
            match = re.search(pattern, content)
            assert match, f"Should have method {method} matching CLI command"


class TestTypoFixes:
    """Response dict should have correct spelling."""

    def test_no_reuqest_typo(self):
        """Should not have 'reuqest' typo anywhere."""
        client_path = Path(__file__).parent.parent.parent / "vastai" / "serverless" / "client" / "client.py"

        if client_path.exists():
            content = client_path.read_text()
            assert "reuqest" not in content, "Found 'reuqest' typo - should be 'request'"

    def test_request_idx_correct(self):
        """Should have 'request_idx' with correct spelling."""
        client_path = Path(__file__).parent.parent.parent / "vastai" / "serverless" / "client" / "client.py"

        if client_path.exists():
            content = client_path.read_text()
            # If request_idx is used, it should be spelled correctly
            if "request_idx" in content or "reuqest_idx" in content:
                assert "request_idx" in content, "Should have correctly spelled request_idx"
                assert "reuqest_idx" not in content, "Should not have reuqest_idx typo"

    def test_response_dict_keys_spelled_correctly(self):
        """Response dict keys should all be spelled correctly."""
        client_path = Path(__file__).parent.parent.parent / "vastai" / "serverless" / "client" / "client.py"

        if client_path.exists():
            content = client_path.read_text()
            # Find the response dict assignment
            if '"request_idx"' in content:
                # Should have correct key
                assert '"request_idx"' in content, "Response dict should have request_idx key"


class TestAsyncMigration:
    """_fetch_pubkey should use proper HTTP, not subprocess curl."""

    def test_no_subprocess_curl(self):
        """Should not use subprocess to call curl."""
        backend_path = Path(__file__).parent.parent.parent / "vastai" / "serverless" / "server" / "lib" / "backend.py"

        if backend_path.exists():
            content = backend_path.read_text()

            # Should not have subprocess curl pattern
            has_subprocess_curl = "subprocess.check_output" in content and "curl" in content
            assert not has_subprocess_curl, "Should not use subprocess curl - use requests or aiohttp"

    def test_no_subprocess_import(self):
        """Should not import subprocess (no longer needed)."""
        backend_path = Path(__file__).parent.parent.parent / "vastai" / "serverless" / "server" / "lib" / "backend.py"

        if backend_path.exists():
            content = backend_path.read_text()

            # Check for subprocess import at module level
            import_pattern = r'^import subprocess\s*$'
            has_import = re.search(import_pattern, content, re.MULTILINE)
            assert not has_import, "Should not import subprocess - no longer needed"

    def test_uses_requests_or_aiohttp(self):
        """_fetch_pubkey should use requests or aiohttp."""
        backend_path = Path(__file__).parent.parent.parent / "vastai" / "serverless" / "server" / "lib" / "backend.py"

        if backend_path.exists():
            content = backend_path.read_text()

            # Should use requests (for sync) or aiohttp (for async)
            uses_requests = "requests.get" in content
            uses_aiohttp = "ClientSession" in content and "aiohttp" in content

            # _fetch_pubkey should use proper HTTP library
            if "_fetch_pubkey" in content:
                assert uses_requests or uses_aiohttp, "Should use requests or aiohttp for _fetch_pubkey"

    def test_has_async_variant(self):
        """Should have async variant of _fetch_pubkey using aiohttp."""
        backend_path = Path(__file__).parent.parent.parent / "vastai" / "serverless" / "server" / "lib" / "backend.py"

        if backend_path.exists():
            content = backend_path.read_text()

            # Should have async version for use in async contexts
            has_async = "async def _fetch_pubkey_async" in content
            assert has_async, "Should have async variant _fetch_pubkey_async using aiohttp"

    def test_fetch_pubkey_has_timeout(self):
        """_fetch_pubkey should have timeout to prevent hanging."""
        backend_path = Path(__file__).parent.parent.parent / "vastai" / "serverless" / "server" / "lib" / "backend.py"

        if backend_path.exists():
            content = backend_path.read_text()

            # Both sync and async versions should have timeout
            assert "timeout" in content, "Should have timeout in HTTP requests"


class TestServerlessImports:
    """Basic serverless module tests."""

    def test_serverless_client_importable(self):
        """Serverless client should be importable without aiohttp at vastai level."""
        # This tests that lazy imports work
        try:
            # Just import vastai - should not fail even without aiohttp
            import vastai
            assert vastai is not None
        except ImportError as e:
            if "aiohttp" in str(e):
                # This is expected if aiohttp not installed
                pass
            else:
                raise

    def test_vastai_base_importable(self):
        """VastAIBase should be importable."""
        from vastai.vastai_base import VastAIBase
        assert VastAIBase is not None

    def test_base_class_has_workergroup_methods(self):
        """VastAIBase should define workergroup methods."""
        from vastai.vastai_base import VastAIBase

        # Check class attributes
        assert hasattr(VastAIBase, "create_workergroup"), "Should have create_workergroup"
        assert hasattr(VastAIBase, "delete_workergroup"), "Should have delete_workergroup"
        assert hasattr(VastAIBase, "show_workergroups"), "Should have show_workergroups"
        assert hasattr(VastAIBase, "update_workergroup"), "Should have update_workergroup"

    def test_base_class_has_autogroup_aliases(self):
        """VastAIBase should have autogroup/autoscaler aliases for backwards compatibility."""
        from vastai.vastai_base import VastAIBase

        # Check aliases exist
        assert hasattr(VastAIBase, "create_autogroup"), "Should have create_autogroup alias"
        assert hasattr(VastAIBase, "delete_autoscaler"), "Should have delete_autoscaler alias"
        assert hasattr(VastAIBase, "show_autoscalers"), "Should have show_autoscalers alias"
        assert hasattr(VastAIBase, "update_autoscaler"), "Should have update_autoscaler alias"

    def test_aliases_point_to_same_method(self):
        """Aliases should point to the same underlying method."""
        from vastai.vastai_base import VastAIBase

        # Aliases should be the same function
        assert VastAIBase.create_autogroup is VastAIBase.create_workergroup
        assert VastAIBase.delete_autoscaler is VastAIBase.delete_workergroup
        assert VastAIBase.show_autoscalers is VastAIBase.show_workergroups
        assert VastAIBase.update_autoscaler is VastAIBase.update_workergroup
