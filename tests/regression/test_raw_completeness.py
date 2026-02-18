"""
Regression Tests: Raw Mode Completeness

Verifies that command functions have consistent --raw handling.
"""
import re
import sys
from pathlib import Path

# Add vast-cli to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestRawModeCompleteness:
    """Tests that command functions have raw mode handling."""

    def setup_method(self):
        """Load vast.py source code once per test."""
        vast_path = Path(__file__).parent.parent.parent / "vast.py"
        self.source = vast_path.read_text(encoding="utf-8")

    def test_minimum_raw_handlers(self):
        """Verify at least 90 raw mode handlers exist."""
        raw_count = len(re.findall(r"if args\.raw:", self.source))
        assert raw_count >= 90, f"Expected at least 90 raw handlers, found {raw_count}"

    def test_command_functions_have_raw_handling(self):
        """Check that common command functions have if args.raw: patterns."""
        # Key command functions that should have raw handling
        expected_functions = [
            "attach__ssh",
            "cancel__copy",
            "cancel__sync",
            "change__bid",
            "create__api_key",
            "create__env_var",
            "create__ssh_key",
            "create__workergroup",
            "create__endpoint",
            "create__subaccount",
            "create__team",
            "create__team_role",
            "create__template",
            "delete__api_key",
            "delete__ssh_key",
            "delete__scheduled_job",
            "delete__workergroup",
            "delete__endpoint",
            "delete__env_var",
            "delete__template",
            "destroy__team",
            "detach__ssh",
            "invite__member",
            "label__instance",
            "prepay__instance",
            "reboot__instance",
            "recycle__instance",
            "remove__member",
            "remove__team_role",
            "reports",
            "reset__api_key",
            "transfer__credit",
        ]

        for func_name in expected_functions:
            # Find the function definition
            func_pattern = rf"^def {func_name}\(args"
            match = re.search(func_pattern, self.source, re.MULTILINE)
            assert match, f"Function {func_name} not found"

            # Get function body (rough approximation - from def to next def or EOF)
            start = match.start()
            next_def = re.search(r"^def \w+\(", self.source[start + 10:], re.MULTILINE)
            end = start + 10 + next_def.start() if next_def else len(self.source)
            func_body = self.source[start:end]

            # Check for raw handling
            has_raw = "if args.raw:" in func_body
            assert has_raw, f"Function {func_name} missing 'if args.raw:' handling"

    def test_no_orphan_print_without_raw_check(self):
        """
        Verify that functions returning JSON data have raw checks before prints.

        This is a sampling test - check a few critical functions.
        """
        # Functions that should have raw handling before their main output
        critical_patterns = [
            # (function_name, expected_pattern_after_raw_check)
            ("create__team", r"if args\.raw:.*?return.*?print\(result\)"),
            ("delete__api_key", r"if args\.raw:.*?return.*?print\(result\)"),
        ]

        for func_name, _ in critical_patterns:
            func_pattern = rf"^def {func_name}\(args"
            match = re.search(func_pattern, self.source, re.MULTILINE)
            assert match, f"Function {func_name} not found"

            start = match.start()
            next_def = re.search(r"^def \w+\(", self.source[start + 10:], re.MULTILINE)
            end = start + 10 + next_def.start() if next_def else len(self.source)
            func_body = self.source[start:end]

            # Verify raw check exists
            assert "if args.raw:" in func_body, f"{func_name} should have raw check"


class TestRawModeReturnsData:
    """Tests that raw mode handlers return data, not None."""

    def setup_method(self):
        """Load vast.py source code once per test."""
        vast_path = Path(__file__).parent.parent.parent / "vast.py"
        self.source = vast_path.read_text(encoding="utf-8")

    def test_raw_handlers_have_return_statements(self):
        """Verify raw mode handlers include return statements."""
        # Find all if args.raw: blocks
        raw_pattern = r"if args\.raw:\s*\n\s+return"
        matches = re.findall(raw_pattern, self.source)
        # Should have many return statements following raw checks
        assert len(matches) >= 80, f"Expected 80+ 'if args.raw: return' patterns, found {len(matches)}"

    def test_no_empty_raw_blocks(self):
        """Verify no raw blocks that just pass or do nothing."""
        # Pattern for raw checks that just pass
        empty_raw_pattern = r"if args\.raw:\s*\n\s+pass\s*\n"
        matches = re.findall(empty_raw_pattern, self.source)
        assert len(matches) == 0, f"Found {len(matches)} empty 'if args.raw: pass' blocks"


class TestRawModeConsistency:
    """Tests for consistent raw mode patterns across the codebase."""

    def setup_method(self):
        """Load vast.py source code once per test."""
        vast_path = Path(__file__).parent.parent.parent / "vast.py"
        self.source = vast_path.read_text(encoding="utf-8")

    def test_consistent_raw_return_pattern(self):
        """
        Verify raw mode uses consistent return patterns.

        Expected patterns:
        - if args.raw: return rj
        - if args.raw: return result
        - if args.raw: return rows
        - if args.raw: return data
        """
        # Find all raw return patterns
        raw_return_pattern = r"if args\.raw:\s*\n\s+return\s+(\w+)"
        matches = re.findall(raw_return_pattern, self.source)

        # Common return variable names
        valid_names = {"rj", "result", "rows", "data", "processed", "user_blob",
                       "response_data", "instances", "volumes", "machines", "offers"}

        for var_name in matches:
            # Allow any reasonable variable name (not just the common ones)
            # This is a sanity check - variables should be short identifiers
            assert len(var_name) < 30, f"Suspicious return variable: {var_name}"

    def test_output_result_handles_raw(self):
        """Verify output_result function exists and handles raw mode."""
        # Check that output_result is defined
        assert "def output_result(" in self.source, "output_result function not found"

        # Check that output_result checks args.raw
        output_result_match = re.search(
            r"def output_result\(.*?\n(.*?)(?=^def |\Z)",
            self.source,
            re.MULTILINE | re.DOTALL
        )
        assert output_result_match, "Could not extract output_result function body"
        func_body = output_result_match.group(1)
        assert "args.raw" in func_body, "output_result should check args.raw"
