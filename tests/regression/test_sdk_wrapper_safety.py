"""Regression tests for SDK wrapper safety.

- stdout capture must use finally block for guaranteed restoration
- sys.exit() from CLI functions should return exit code, not crash SDK
- Exception handling should use specific types, not bare except
"""
import io
import re
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestStdoutCapture:
    """stdout capture must use finally block."""

    def test_finally_block_exists(self):
        """SDK wrapper should have finally block for stdout restoration."""
        sdk_path = Path(__file__).parent.parent.parent / "vastai" / "sdk.py"
        content = sdk_path.read_text()

        # Should have finally: followed by stdout restoration
        assert "finally:" in content, "SDK should have finally block"

        # The finally block should restore stdout
        finally_pattern = re.search(r'finally:.*?sys\.stdout\s*=', content, re.DOTALL)
        assert finally_pattern is not None, "finally block should restore sys.stdout"

    def test_stdout_restoration_guaranteed(self):
        """Verify stdout restoration code is in finally block, not outside."""
        sdk_path = Path(__file__).parent.parent.parent / "vastai" / "sdk.py"
        content = sdk_path.read_text()

        # Check that stdout restoration is inside finally
        finally_match = re.search(
            r'finally:\s*\n\s*#.*restore stdout.*\n\s*if out_o is not None.*:\s*\n\s*sys\.stdout = out_o',
            content,
            re.IGNORECASE
        )
        assert finally_match is not None, "stdout restoration should be inside finally block"

    def test_stdout_restored_after_sdk_init(self):
        """sys.stdout should be the original after SDK operations."""
        from vastai import VastAI

        original_stdout = sys.stdout

        # Create SDK instance
        v = VastAI(api_key="test_key_12345")

        # stdout should still be the original
        assert sys.stdout is original_stdout, "stdout was corrupted after SDK init"


class TestSysExitHandling:
    """sys.exit() should be caught and converted."""

    def test_systemexit_caught_separately(self):
        """SystemExit should have its own except block."""
        sdk_path = Path(__file__).parent.parent.parent / "vastai" / "sdk.py"
        content = sdk_path.read_text()

        # Should catch SystemExit separately
        assert "except SystemExit" in content, "Should catch SystemExit separately"

    def test_exit_code_extracted(self):
        """sys.exit() code should be extracted, not re-raised."""
        sdk_path = Path(__file__).parent.parent.parent / "vastai" / "sdk.py"
        content = sdk_path.read_text()

        # Should access e.code
        assert "e.code" in content, "Should extract exit code from SystemExit"

    def test_systemexit_before_general_exception(self):
        """SystemExit should be caught before general Exception."""
        sdk_path = Path(__file__).parent.parent.parent / "vastai" / "sdk.py"
        content = sdk_path.read_text()

        # Find positions of both except blocks
        systemexit_pos = content.find("except SystemExit")
        exception_pos = content.find("except Exception")

        assert systemexit_pos != -1, "SystemExit handler not found"
        assert exception_pos != -1, "Exception handler not found"
        assert systemexit_pos < exception_pos, "SystemExit should be caught before general Exception"


class TestExceptionSpecificity:
    """Exception handling should be specific, not broad."""

    def test_no_bare_except(self):
        """Should not have bare 'except:' without exception type."""
        sdk_path = Path(__file__).parent.parent.parent / "vastai" / "sdk.py"
        content = sdk_path.read_text()

        # Find bare except: (not except Something:)
        lines = content.split('\n')
        bare_excepts = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            # Match "except:" but not "except Something:" or "except (A, B):"
            if stripped == "except:" or stripped.startswith("except: "):
                bare_excepts.append(f"Line {i}: {line}")

        assert len(bare_excepts) == 0, f"Found bare except: {bare_excepts}"

    def test_exception_handlers_have_types(self):
        """except blocks should specify exception types."""
        sdk_path = Path(__file__).parent.parent.parent / "vastai" / "sdk.py"
        content = sdk_path.read_text()

        # Find all except statements
        except_lines = re.findall(r'^\s*except\s+.*:', content, re.MULTILINE)

        # All should have a type (not bare except:)
        for line in except_lines:
            stripped = line.strip()
            # Allow "except Type:" or "except (A, B):" or "except Type as e:"
            assert stripped != "except:", f"Found bare except: {line}"
            # Verify it has some type specification
            type_match = re.match(r'except\s+[\w\(\),\s]+', stripped)
            assert type_match, f"Exception handler should have type: {line}"

    def test_specific_exceptions_in_queryformatter(self):
        """queryFormatter should use specific exceptions (KeyError, TypeError)."""
        sdk_path = Path(__file__).parent.parent.parent / "vastai" / "sdk.py"
        content = sdk_path.read_text()

        # The queryFormatter function should have specific exceptions
        assert "except (KeyError, TypeError):" in content, \
            "queryFormatter should catch specific KeyError and TypeError"


class TestSDKImport:
    """Basic SDK import and instantiation tests."""

    def test_import_vastai(self):
        """from vastai import VastAI should work."""
        from vastai import VastAI
        assert VastAI is not None

    def test_instantiate_with_api_key(self):
        """VastAI(api_key='test') should not raise."""
        from vastai import VastAI
        v = VastAI(api_key="test_key_12345")
        assert v is not None
        assert hasattr(v, "api_key")

    def test_sdk_has_expected_attributes(self):
        """SDK instance should have standard attributes."""
        from vastai import VastAI
        v = VastAI(api_key="test_key_12345")

        # Core attributes
        assert hasattr(v, "api_key")
        assert hasattr(v, "server_url")
        assert hasattr(v, "retry")
        assert hasattr(v, "raw")
        assert hasattr(v, "last_output")

    def test_sdk_last_output_initialized(self):
        """SDK should initialize last_output to None."""
        from vastai import VastAI
        v = VastAI(api_key="test_key_12345")
        assert v.last_output is None


class TestStdoutCaptureIntegration:
    """Integration tests for stdout capture behavior."""

    def test_stdout_not_leaked_on_multiple_operations(self):
        """Multiple SDK operations should not leak stdout state."""
        from vastai import VastAI

        original_stdout = sys.stdout
        v = VastAI(api_key="test_key_12345")

        # Perform multiple operations (even if they fail due to no network)
        for _ in range(3):
            try:
                # These may fail due to no API key/network, but stdout should be safe
                v.show_user()
            except Exception:
                pass

            # Check stdout is still original
            assert sys.stdout is original_stdout, "stdout leaked after SDK operation"
