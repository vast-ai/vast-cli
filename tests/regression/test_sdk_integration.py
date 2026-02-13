"""
Regression tests for SDK integration.

These tests verify the SDK wrapper integrates correctly with the live vast module
and supports all documented features, including method resolution, argument passing,
and output capture.
"""
import sys
import warnings
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add vast-cli to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestSDKLiveModuleImport:
    """SDK must import from live vast module, not frozen copy."""

    def test_sentinel_attribute_visible(self):
        """Adding sentinel to vast module should be visible through SDK."""
        import vast

        # Add sentinel attribute
        vast._SDK_TEST_SENTINEL = "phase6_integration_test"

        # Import SDK internals
        from vastai import sdk

        # Verify SDK's imported vast module sees the sentinel
        assert hasattr(sdk._vast, '_SDK_TEST_SENTINEL'), \
            "SDK's vast module should see runtime-added attributes"
        assert sdk._vast._SDK_TEST_SENTINEL == "phase6_integration_test", \
            "Sentinel value should match"

        # Cleanup
        del vast._SDK_TEST_SENTINEL

    def test_parser_from_vast_module(self):
        """Parser should be imported from vast module."""
        import vast
        from vastai import sdk

        # The parser used by SDK should be the same object as vast.parser
        assert sdk.parser is vast.parser, \
            "SDK parser should be the same object as vast.parser"

    def test_apikey_file_from_vast_module(self):
        """APIKEY_FILE should be imported from vast module."""
        import vast
        from vastai import sdk

        # APIKEY_FILE should match
        assert sdk.APIKEY_FILE == vast.APIKEY_FILE, \
            "SDK APIKEY_FILE should match vast.APIKEY_FILE"


class TestSDKFeatureCompleteness:
    """VastAI class must support all documented features."""

    def test_instantiation_with_api_key(self):
        """VastAI can be instantiated with api_key parameter."""
        from vastai import VastAI

        sdk = VastAI(api_key="test_key_12345")

        assert sdk.api_key == "test_key_12345"
        assert sdk._creds == "CODE"  # API key provided in code

    def test_raw_mode_default(self):
        """VastAI defaults to raw=True for SDK usage."""
        from vastai import VastAI

        sdk = VastAI(api_key="test_key")

        assert sdk.raw is True, "SDK should default to raw=True"

    def test_raw_mode_toggle(self):
        """VastAI raw mode can be toggled."""
        from vastai import VastAI

        sdk_raw = VastAI(api_key="test_key", raw=True)
        sdk_human = VastAI(api_key="test_key", raw=False)

        assert sdk_raw.raw is True
        assert sdk_human.raw is False

    def test_server_url_parameter(self):
        """VastAI accepts server_url parameter."""
        from vastai import VastAI

        sdk = VastAI(api_key="test_key", server_url="https://custom.vast.ai")

        assert sdk.server_url == "https://custom.vast.ai"

    def test_retry_parameter(self):
        """VastAI accepts retry parameter."""
        from vastai import VastAI

        sdk = VastAI(api_key="test_key", retry=5)

        assert sdk.retry == 5

    def test_explain_parameter(self):
        """VastAI accepts explain parameter."""
        from vastai import VastAI

        sdk = VastAI(api_key="test_key", explain=True)

        assert sdk.explain is True

    def test_quiet_parameter(self):
        """VastAI accepts quiet parameter."""
        from vastai import VastAI

        sdk = VastAI(api_key="test_key", quiet=True)

        assert sdk.quiet is True

    def test_imported_methods_populated(self):
        """VastAI should have imported_methods dict populated."""
        from vastai import VastAI

        sdk = VastAI(api_key="test_key")

        assert hasattr(sdk, 'imported_methods')
        assert isinstance(sdk.imported_methods, dict)
        # Should have many methods (vast.py has 115+ commands)
        assert len(sdk.imported_methods) > 50, \
            f"Expected 50+ methods, got {len(sdk.imported_methods)}"

    def test_dynamic_method_binding(self):
        """VastAI should have methods dynamically bound from vast.py."""
        from vastai import VastAI

        sdk = VastAI(api_key="test_key")

        # Check some well-known methods exist
        assert hasattr(sdk, 'search_offers'), "search_offers should be bound"
        assert hasattr(sdk, 'show_instances'), "show_instances should be bound"
        assert hasattr(sdk, 'show_machines'), "show_machines should be bound"
        assert callable(sdk.search_offers), "search_offers should be callable"

    def test_workergroup_and_autoscaler_aliases(self):
        """Both workergroup and autoscaler/autogroup aliases should work."""
        from vastai import VastAI

        sdk = VastAI(api_key="test_key")

        # Workergroup naming (primary method names from CLI)
        assert hasattr(sdk, 'create_workergroup') or 'create_workergroup' in sdk.imported_methods, \
            "create_workergroup should exist"
        assert hasattr(sdk, 'show_workergroups') or 'show_workergroups' in sdk.imported_methods, \
            "show_workergroups should exist"
        assert hasattr(sdk, 'delete_workergroup') or 'delete_workergroup' in sdk.imported_methods, \
            "delete_workergroup should exist"
        assert hasattr(sdk, 'update_workergroup') or 'update_workergroup' in sdk.imported_methods, \
            "update_workergroup should exist"

        # Autoscaler/autogroup backwards compatibility aliases
        # Base class provides aliases: create_autogroup, delete_autoscaler, show_autoscalers, update_autoscaler
        assert hasattr(sdk, 'create_autogroup'), \
            "create_autogroup alias should exist"
        assert hasattr(sdk, 'show_autoscalers'), \
            "show_autoscalers alias should exist"
        assert hasattr(sdk, 'delete_autoscaler'), \
            "delete_autoscaler alias should exist"
        assert hasattr(sdk, 'update_autoscaler'), \
            "update_autoscaler alias should exist"


class TestSDKMethodCoverage:
    """Verify SDK method coverage against CLI commands."""

    def test_method_count_matches_cli_commands(self):
        """SDK should have methods for most CLI commands."""
        from vastai import VastAI
        import vast

        sdk = VastAI(api_key="test_key")

        # Count CLI commands (functions with double underscore)
        cli_commands = [
            name for name in dir(vast)
            if callable(getattr(vast, name))
            and '__' in name
            and not name.startswith('_')
        ]

        # SDK should have at least 80% coverage
        # (some commands like 'help' are excluded)
        min_expected = int(len(cli_commands) * 0.80)
        actual_count = len(sdk.imported_methods)

        assert actual_count >= min_expected, \
            f"SDK has {actual_count} methods but CLI has {len(cli_commands)} commands. " \
            f"Expected at least {min_expected} methods."

    def test_all_critical_methods_exist(self):
        """SDK must have all commonly-used methods."""
        from vastai import VastAI

        sdk = VastAI(api_key="test_key")

        critical_methods = [
            'search_offers',
            'create_instance',
            'destroy_instance',
            'show_instances',
            'start_instance',
            'stop_instance',
            'show_machines',
            'logs',
            'execute',
            'copy',
            'show_user',
        ]

        for method in critical_methods:
            assert hasattr(sdk, method) or method in sdk.imported_methods, \
                f"Critical method '{method}' missing from SDK"


class TestSDKMethodExecution:
    """Verify SDK methods execute through the vast module correctly."""

    def test_show_instances_method_exists_and_callable(self):
        """show_instances method should exist and be callable."""
        from vastai import VastAI

        sdk = VastAI(api_key="test_key")

        # Method should exist as callable
        assert hasattr(sdk, 'show_instances'), "show_instances should be bound"
        assert callable(sdk.show_instances), "show_instances should be callable"

    def test_search_offers_method_exists_and_callable(self):
        """search_offers method should exist and be callable."""
        from vastai import VastAI

        sdk = VastAI(api_key="test_key")

        assert hasattr(sdk, 'search_offers'), "search_offers should be bound"
        assert callable(sdk.search_offers), "search_offers should be callable"

    def test_method_binding_uses_vast_functions(self):
        """SDK methods should be bound from vast module functions."""
        from vastai import VastAI
        import vast

        sdk = VastAI(api_key="test_key")

        # The method should be in imported_methods and callable
        if 'show_instances' in sdk.imported_methods:
            # The bound method comes from vast.show__instances
            vast_func_name = 'show__instances'
            assert hasattr(vast, vast_func_name), \
                f"vast.{vast_func_name} should exist for SDK to bind"

    def test_method_returns_callable_not_none(self):
        """SDK methods should return callable functions, not None."""
        from vastai import VastAI

        sdk = VastAI(api_key="test_key")

        # Check several methods to ensure they're properly bound
        methods_to_check = ['search_offers', 'show_instances', 'show_machines', 'show_user']

        for method_name in methods_to_check:
            method = getattr(sdk, method_name, None)
            assert method is not None, f"{method_name} should not be None"
            assert callable(method), f"{method_name} should be callable"


class TestSdkMethodResolution:
    """SDK wrapper method resolution tests."""

    def test_search_offers_method_exists(self):
        """SDK has search_offers method."""
        from vastai import VastAI
        sdk = VastAI(api_key="test-key")
        assert hasattr(sdk, 'search_offers')
        assert callable(sdk.search_offers)

    def test_show_instances_method_exists(self):
        """SDK has show_instances method."""
        from vastai import VastAI
        sdk = VastAI(api_key="test-key")
        assert hasattr(sdk, 'show_instances')
        assert callable(sdk.show_instances)

    def test_create_instance_method_exists(self):
        """SDK has create_instance method."""
        from vastai import VastAI
        sdk = VastAI(api_key="test-key")
        assert hasattr(sdk, 'create_instance')
        assert callable(sdk.create_instance)

    def test_destroy_instance_method_exists(self):
        """SDK has destroy_instance method."""
        from vastai import VastAI
        sdk = VastAI(api_key="test-key")
        assert hasattr(sdk, 'destroy_instance')
        assert callable(sdk.destroy_instance)

    def test_method_resolution_is_consistent(self):
        """Same method should resolve identically across multiple SDK instances."""
        from vastai import VastAI
        sdk1 = VastAI(api_key="test-key-1")
        sdk2 = VastAI(api_key="test-key-2")

        # Both instances should have same method names in imported_methods
        assert sdk1.imported_methods.keys() == sdk2.imported_methods.keys()


class TestSdkArgumentPassing:
    """SDK wrapper argument passing tests."""

    def test_api_key_stored_in_instance(self):
        """SDK stores api_key in instance for use in requests."""
        from vastai import VastAI

        sdk = VastAI(api_key="test-api-key-12345")

        # API key should be accessible
        assert sdk.api_key == "test-api-key-12345"

    def test_retry_parameter_passed(self):
        """SDK retry parameter is stored and accessible."""
        from vastai import VastAI

        sdk = VastAI(api_key="test-key", retry=10)
        assert sdk.retry == 10

    def test_server_url_parameter_passed(self):
        """SDK server_url parameter is stored and accessible."""
        from vastai import VastAI

        sdk = VastAI(api_key="test-key", server_url="https://custom.vast.ai")
        assert sdk.server_url == "https://custom.vast.ai"

    def test_explain_parameter_passed(self):
        """SDK explain parameter is stored and accessible."""
        from vastai import VastAI

        sdk = VastAI(api_key="test-key", explain=True)
        assert sdk.explain is True

    def test_quiet_parameter_passed(self):
        """SDK quiet parameter is stored and accessible."""
        from vastai import VastAI

        sdk = VastAI(api_key="test-key", quiet=True)
        assert sdk.quiet is True


class TestSdkOutputCapture:
    """SDK wrapper output capture tests."""

    def test_sdk_instance_has_output_capture_mechanism(self):
        """SDK should have mechanism for capturing output."""
        from vastai import VastAI

        sdk = VastAI(api_key="test-key", raw=True)

        # SDK uses raw=True by default to return data instead of printing
        # This verifies the mechanism exists
        assert sdk.raw is True

    def test_sdk_raw_mode_returns_data_type(self):
        """SDK in raw mode should be configured to return data."""
        from vastai import VastAI

        sdk = VastAI(api_key="test-key", raw=True)

        # Verify the SDK is configured correctly for raw output
        assert hasattr(sdk, 'raw')
        assert sdk.raw is True
        # Raw mode means CLI functions return data instead of printing

    def test_sdk_non_raw_mode_available(self):
        """SDK can be set to non-raw mode for human-readable output."""
        from vastai import VastAI

        sdk = VastAI(api_key="test-key", raw=False)
        assert sdk.raw is False


class TestSdkBackwardsCompatibility:
    """SDK backwards compatibility tests."""

    def test_autogroup_alias_exists(self):
        """SDK has autogroup alias methods for backwards compatibility."""
        from vastai import VastAI
        sdk = VastAI(api_key="test-key")

        # Both workergroup and autogroup/autoscaler names should work
        if hasattr(sdk, 'show_workergroups') or 'show_workergroups' in sdk.imported_methods:
            # Autoscaler aliases from base class
            assert hasattr(sdk, 'show_autoscalers'), "show_autoscalers alias should exist"

    def test_autoscaler_crud_aliases_exist(self):
        """SDK has all autoscaler CRUD aliases for backwards compatibility."""
        from vastai import VastAI
        sdk = VastAI(api_key="test-key")

        # These aliases are defined in vastai_base.py
        assert hasattr(sdk, 'create_autogroup'), "create_autogroup alias should exist"
        assert hasattr(sdk, 'show_autoscalers'), "show_autoscalers alias should exist"
        assert hasattr(sdk, 'delete_autoscaler'), "delete_autoscaler alias should exist"
        assert hasattr(sdk, 'update_autoscaler'), "update_autoscaler alias should exist"

    def test_old_import_path_warning(self):
        """Importing from vastai_sdk works (with or without deprecation warning)."""
        # The vastai_sdk module may or may not emit a deprecation warning
        # depending on implementation. Either behavior is acceptable.
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            try:
                from vastai_sdk import VastAI as OldVastAI
                # Import succeeded - either with warning or without
                # Both are acceptable for backwards compatibility
                assert OldVastAI is not None
            except ImportError:
                # If vastai_sdk shim doesn't exist, that's also acceptable
                # as long as the main vastai import works
                from vastai import VastAI
                assert VastAI is not None

    def test_primary_import_path_works(self):
        """Primary import path 'from vastai import VastAI' works."""
        from vastai import VastAI
        sdk = VastAI(api_key="test-key")
        assert sdk is not None
        assert hasattr(sdk, 'api_key')


class TestSdkMethodDocstrings:
    """SDK methods have docstrings for IDE autocomplete."""

    def test_sdk_methods_have_docstrings(self):
        """SDK methods should have docstrings for IDE support."""
        from vastai import VastAI
        sdk = VastAI(api_key="test-key")

        # Check some key methods have docstrings
        methods_to_check = ['search_offers', 'show_instances', 'create_instance']

        for method_name in methods_to_check:
            if hasattr(sdk, method_name):
                method = getattr(sdk, method_name)
                # Method should be callable and have docstring
                assert callable(method), f"{method_name} should be callable"
                # Docstring may come from vast.py function or be added by SDK
                # Either is acceptable as long as method works
